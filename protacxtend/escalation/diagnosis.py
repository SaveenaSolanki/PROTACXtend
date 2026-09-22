"""Failure diagnosis: turn a raw exception into an actionable root cause.

The classifier is deliberately conservative — it never claims a cause it cannot
support from the exception type/message, and it always produces a
``recovery_hint`` plus a boolean ``recommend_external`` flag that tells the
orchestrator whether escalation to an external tool is worth attempting.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

# Failure classes mirror protacxtend.agents.state.FailureClass where possible.
FAILURE_CLASSES = {
    "NO_VALID_CONFORMER",
    "LOW_CONFIDENCE",
    "OUT_OF_DOMAIN",
    "TOOL_TIMEOUT",
    "MISSING_INPUT",
    "MISSING_DEPENDENCY",
    "MISSING_ASSET",
    "INVALID_INPUT",
    "DATA_SCHEMA",
    "RESOURCE_EXHAUSTED",
    "NETWORK_UNAVAILABLE",
    "NOT_IMPLEMENTED",
    "COMMERCIAL_LICENSE",
    "HARD_ERROR",
}


@dataclass
class Diagnosis:
    failure_class: str
    root_cause: str
    recovery_hint: str
    recommend_external: bool
    error_type: str
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_TIMEOUT_NAMES = {"TimeoutError", "ReadTimeout", "ConnectTimeout", "Timeout"}
_NETWORK_NAMES = {
    "ConnectionError", "ConnectionResetError", "ConnectionRefusedError",
    "RemoteDisconnected", "SSLError", "HTTPError", "URLError",
}
_DEP_NAMES = {"ModuleNotFoundError", "ImportError"}
_INPUT_NAMES = {"FileNotFoundError"}
_INVALID_NAMES = {"ValueError", "TypeError", "AssertionError"}
_SCHEMA_NAMES = {"KeyError", "IndexError", "AttributeError"}


def _match_name(exc: BaseException) -> str:
    return type(exc).__name__


def diagnose(
    exc: BaseException,
    *,
    internal_tool: str = "",
    capability: str = "",
    context: dict[str, Any] | None = None,
) -> Diagnosis:
    """Classify an exception into a failure class + root cause + recovery hint."""
    context = context or {}
    name = _match_name(exc)
    message = str(exc) or repr(exc)
    lowered = message.lower()

    # ── dependency / import ─────────────────────────────────────────
    if name in _DEP_NAMES:
        missing = getattr(exc, "name", None) or message
        return Diagnosis(
            failure_class="MISSING_DEPENDENCY",
            root_cause=f"Python dependency not importable: {missing}",
            recovery_hint=(
                f"Install the missing package for '{internal_tool or capability}', then re-run. "
                "The escalation installer maps this to a pip/conda package."
            ),
            recommend_external=True,
            error_type=name,
            evidence=message[:400],
        )

    # ── explicit commercial/license failures ────────────────────────
    if "license" in lowered and ("commercial" in lowered or "not available" in lowered):
        return Diagnosis(
            failure_class="COMMERCIAL_LICENSE",
            root_cause="A commercial/licensed backend is required but not configured.",
            recovery_hint="Configure the license/API credentials or use an open-source fallback.",
            recommend_external=True,
            error_type=name,
            evidence=message[:400],
        )

    # ── timeouts ────────────────────────────────────────────────────
    if name in _TIMEOUT_NAMES or "timed out" in lowered or "timeout" in lowered:
        return Diagnosis(
            failure_class="TOOL_TIMEOUT",
            root_cause="Internal tool exceeded its time budget.",
            recovery_hint="Retry once with relaxed parameters; otherwise escalate to a faster external engine.",
            recommend_external=True,
            error_type=name,
            evidence=message[:400],
        )

    # ── network ─────────────────────────────────────────────────────
    if name in _NETWORK_NAMES or "connection" in lowered or "unreachable" in lowered:
        return Diagnosis(
            failure_class="NETWORK_UNAVAILABLE",
            root_cause="A remote service or network resource was unreachable.",
            recovery_hint="Check connectivity/credentials; fall back to a local external tool if one is installed.",
            recommend_external=True,
            error_type=name,
            evidence=message[:400],
        )

    # ── missing asset / input file ──────────────────────────────────
    if name in _INPUT_NAMES:
        return Diagnosis(
            failure_class="MISSING_ASSET",
            root_cause="A required local file/asset (model, table or structure) was not found.",
            recovery_hint="Restore/download the asset, or register an external tool that ships its own data.",
            recommend_external=True,
            error_type=name,
            evidence=message[:400],
        )

    # ── resources ───────────────────────────────────────────────────
    if name == "MemoryError" or "out of memory" in lowered:
        return Diagnosis(
            failure_class="RESOURCE_EXHAUSTED",
            root_cause="Process ran out of memory.",
            recovery_hint="Reduce batch size or escalate to a lighter external implementation.",
            recommend_external=True,
            error_type=name,
            evidence=message[:400],
        )

    # ── domain-specific heuristics ──────────────────────────────────
    if "conformer" in lowered and ("fail" in lowered or "no valid" in lowered or "embed" in lowered):
        return Diagnosis(
            failure_class="NO_VALID_CONFORMER",
            root_cause="3D conformer generation produced no valid embed.",
            recovery_hint="Retry with relaxed ETKDG parameters; escalate to CREST/OpenEye OMEGA if installed.",
            recommend_external=True,
            error_type=name,
            evidence=message[:400],
        )

    if "not implemented" in lowered or name == "NotImplementedError":
        return Diagnosis(
            failure_class="NOT_IMPLEMENTED",
            root_cause="The internal code path is a stub/placeholder.",
            recovery_hint="Wire an external implementation for this capability and register it.",
            recommend_external=True,
            error_type=name,
            evidence=message[:400],
        )

    # ── input/schema errors ─────────────────────────────────────────
    if name in _INVALID_NAMES:
        return Diagnosis(
            failure_class="INVALID_INPUT",
            root_cause="Internal tool rejected the supplied inputs.",
            recovery_hint="Inspect/repair inputs; if the internal validator is too strict escalate to an external validator.",
            recommend_external=True,
            error_type=name,
            evidence=message[:400],
        )

    if name in _SCHEMA_NAMES:
        return Diagnosis(
            failure_class="DATA_SCHEMA",
            root_cause="Unexpected data shape/keys reached the internal tool.",
            recovery_hint="Normalise the upstream payload; escalate only if the tool is the bottleneck.",
            recommend_external=True,
            error_type=name,
            evidence=message[:400],
        )

    # ── default ─────────────────────────────────────────────────────
    return Diagnosis(
        failure_class="HARD_ERROR",
        root_cause=f"Unhandled {name}: {message[:200]}",
        recovery_hint="Capture traceback for audit; attempt external escalation for the capability.",
        recommend_external=True,
        error_type=name,
        evidence=message[:400],
    )


def classify_name(failure_class: str) -> Any:
    """Best-effort map to the agent FailureClass enum (kept for graph reuse)."""
    try:
        from protacxtend.agents.state import FailureClass

        mapping = {
            "NO_VALID_CONFORMER": FailureClass.NO_VALID_CONFORMER,
            "LOW_CONFIDENCE": FailureClass.LOW_CONFIDENCE,
            "OUT_OF_DOMAIN": FailureClass.OUT_OF_DOMAIN,
            "TOOL_TIMEOUT": FailureClass.TOOL_TIMEOUT,
            "MISSING_INPUT": FailureClass.MISSING_INPUT,
            "MISSING_ASSET": FailureClass.MISSING_INPUT,
            "MISSING_DEPENDENCY": FailureClass.HARD_ERROR,
            "HARD_ERROR": FailureClass.HARD_ERROR,
        }
        return mapping.get(failure_class, FailureClass.HARD_ERROR)
    except Exception:
        return re.sub(r"[^A-Z_]", "", failure_class)
