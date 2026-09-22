"""Resolve a failed capability to concrete external-tool candidates.

Candidates come from three places, in priority order:

1. the dynamic registry (tools already installed/registered by a previous
   escalation — cheapest to reuse),
2. the curated fallback list for the capability (``capabilities.py``),
3. any other toolkit-registry tool whose category matches the capability.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from protacxtend.escalation.capabilities import (
    CAPABILITY_DESCRIPTIONS,
    capability_for,
    fallbacks_for,
)
from protacxtend.escalation.contracts import ExternalToolCandidate
from protacxtend.escalation.installer import (
    detect_version,
    install_method_for,
    pip_package_for,
)


def _toolkit_row(tool_name: str) -> dict[str, Any] | None:
    from protacxtend.tools.toolkit_registry import get_tool_by_name

    return get_tool_by_name(tool_name)


def _status_for(tool_row: dict[str, Any]) -> dict[str, Any]:
    try:
        from protacxtend.tools.tool_status import detect_tool_status

        return detect_tool_status(tool_row)
    except Exception as exc:  # pragma: no cover - defensive
        return {"status": "unknown", "installed": False, "message": str(exc)}


# Generic ML frameworks are not evidence that a *method* is installed: tools
# whose only declared import is a framework still need their own repo + weights.
_PROXY_IMPORTS = {"torch", "tensorflow", "jax", "transformers", "sklearn"}


def _candidate_from_row(
    tool_row: dict[str, Any], capability: str, reason: str
) -> ExternalToolCandidate:
    status = _status_for(tool_row)
    candidate = ExternalToolCandidate(
        tool_name=tool_row["tool_name"],
        category=tool_row["category"],
        subcategory=tool_row.get("subcategory", ""),
        purpose=tool_row.get("purpose", ""),
        reason=reason,
        source="toolkit",
        status=status.get("status", "unknown"),
        installed=bool(status.get("installed")),
        install_hint=tool_row.get("install_hint", ""),
        executable_names=list(tool_row.get("executable_names", []) or []),
        python_imports=list(tool_row.get("python_imports", []) or []),
        web_service=bool(tool_row.get("web_service")),
        api_required=bool(tool_row.get("api_required")),
        commercial=bool(tool_row.get("commercial")),
        license_type=tool_row.get("license_type", ""),
        reliability_level=tool_row.get("reliability_level", ""),
        notes=tool_row.get("notes", ""),
    )
    method = install_method_for(tool_row)
    candidate.install_method = method
    candidate.pip_package = pip_package_for(candidate)
    candidate.installable = method in {"pip", "conda"} and not candidate.commercial
    imports = set(candidate.python_imports)
    # demote framework-only "installs" — the method repo/weights are still needed
    if candidate.installed and imports and imports.issubset(_PROXY_IMPORTS):
        candidate.installed = False
        candidate.status = "dependency_present_repo_required"
        candidate.notes = (
            (candidate.notes + " " if candidate.notes else "")
            + "Framework import present but method repo/weights required."
        )
    if candidate.installed:
        try:
            candidate.version = detect_version(candidate)
        except Exception:
            candidate.version = "installed"
    return candidate


def _dynamic_candidates(capability: str) -> list[ExternalToolCandidate]:
    try:
        from protacxtend.escalation.registry import DynamicToolRegistry

        reg = DynamicToolRegistry()
        out: list[ExternalToolCandidate] = []
        for row in reg.find_by_capability(capability):
            out.append(
                ExternalToolCandidate(
                    tool_name=row["tool_name"],
                    category=row.get("category", "dynamic") or "dynamic",
                    purpose=row.get("notes", "") or "dynamically registered tool",
                    reason=f"dynamic registry ({capability})",
                    source="dynamic",
                    status=row.get("status", "installed"),
                    installed=True,
                    version=row.get("version", ""),
                    install_method=row.get("install_method", ""),
                    pip_package=row.get("pip_package", ""),
                    installable=False,
                )
            )
        return out
    except Exception:
        return []


def resolve_candidates(
    capability: str,
    *,
    include_uninstalled: bool = True,
    only_installed: bool = False,
    max_candidates: int = 12,
) -> list[ExternalToolCandidate]:
    """Ordered candidates for a capability (installed/local first)."""
    capability = capability_for(capability)

    seen: set[str] = set()
    ordered: list[ExternalToolCandidate] = []

    # 1. dynamic registry first
    for cand in _dynamic_candidates(capability):
        if cand.tool_name not in seen:
            seen.add(cand.tool_name)
            ordered.append(cand)

    # 2. curated fallbacks
    preferred = fallbacks_for(capability)
    for idx, tool_name in enumerate(preferred):
        if tool_name in seen:
            continue
        row = _toolkit_row(tool_name)
        if not row:
            continue
        seen.add(tool_name)
        ordered.append(
            _candidate_from_row(row, capability, f"curated fallback #{idx + 1} for {capability}")
        )

    # 3. category match (same toolkit category)
    try:
        from protacxtend.tools.toolkit_registry import get_toolkit_registry

        for row in get_toolkit_registry():
            name = row["tool_name"]
            if name in seen:
                continue
            if capability in row.get("category", "") or row.get("category") == capability:
                seen.add(name)
                ordered.append(
                    _candidate_from_row(row, capability, f"same-category match for {capability}")
                )
    except Exception:
        pass

    # ranking: dynamic (already validated) first, then installed, then
    # non-commercial, then installable, preserving curated preference order.
    def rank(c: ExternalToolCandidate):
        return (
            0 if c.source == "dynamic" else 1,
            0 if c.installed else 1,
            0 if not c.commercial else 1,
            0 if c.installable else 1,
        )

    ordered = sorted(ordered, key=rank)
    if only_installed:
        ordered = [c for c in ordered if c.installed]
    if not include_uninstalled:
        ordered = [c for c in ordered if c.installed or c.installable]
    return ordered[:max_candidates]


def resolve_tool(tool_name: str, capability: str = "") -> ExternalToolCandidate | None:
    row = _toolkit_row(tool_name)
    if not row:
        return None
    cap = capability or capability_for(tool_name)
    return _candidate_from_row(row, cap, f"explicitly requested for {cap}")


def describe_capability(capability: str) -> dict[str, Any]:
    capability = capability_for(capability)
    return {
        "capability": capability,
        "description": CAPABILITY_DESCRIPTIONS.get(capability, ""),
        "curated_fallbacks": fallbacks_for(capability),
    }
