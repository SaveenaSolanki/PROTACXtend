"""Disposition of non-executable toolkit tools.

The toolkit registry contains far more tools than the 34 agent adapters. This
module makes an explicit, auditable *decision* for every registered tool rather
than leaving the gap implicit:

* ``adapted``               — backed by a live agent adapter;
* ``integration_candidate`` — open-source, offline-installable, in scope;
* ``credential_gated``      — executable once an API key/licence is supplied;
* ``commercial_excluded``   — commercial licence, not redistributable;
* ``web_service_documented`` — web-only endpoint, documented not integrated;
* ``repo_weights_required`` — a framework import only; the method repo/weights
  are still required;
* ``out_of_scope``          — outside the TPD benchmark scope.

The report is deterministic and offline and is written to
``outputs/tool_disposition.json`` (plus a markdown summary). It is asserted by
``tests/test_p1_governance.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from protacxtend.toolkit.registry import load_toolkit_registry

#: Backends/adapters that are genuinely executable in this build. Kept in sync
#: with the 34 agent tools and the matched-tool registry.
ADAPTED_TOKENS: frozenset[str] = frozenset(
    {
        "rdkit", "pymol", "chembl", "pubchem", "bindingdb", "uniprot", "rcsb",
        "pdb", "europepmc", "pubmed", "crossref", "openalex", "protacdb",
        "admet", "chemprop", "degradation", "linker", "exit_vector", "ternary",
        "cooperativity", "hook_effect", "cell_context", "pareto", "provenance",
        "molecule_standardizer", "novelty", "diversity", "uncertainty",
    }
)

#: Keywords that mark a licence/credential gate.
_CREDENTIAL_KEYWORDS = ("api key", "api_key", "api-key", "token", "credential", "login")
_COMMERCIAL_KEYWORDS = ("commercial", "schrödinger", "schrodinger", "proprietary", "licensed")
_WEB_KEYWORDS = ("web", "http", "rest", "endpoint", "server")


def _text(tool: dict[str, Any]) -> str:
    fields = tool.get("fields") or {}
    return " ".join(str(v) for v in fields.values()).lower()


def _adaptation_token(tool: dict[str, Any]) -> str:
    name = str((tool.get("fields") or {}).get("tool") or tool.get("name") or "").lower()
    return name.replace(" ", "_").replace("-", "_")


def decide_disposition(tool: dict[str, Any]) -> dict[str, Any]:
    """Return the disposition decision for one toolkit tool."""
    fields = tool.get("fields") or {}
    name = str(fields.get("tool") or tool.get("name") or "")
    token = _adaptation_token(tool)
    name_family = f"{name} {fields.get('tool_family', '')}".lower().replace(" ", "_").replace("-", "_")
    text = _text(tool)
    install = str(fields.get("install_access_command") or "").strip()
    licence = str(fields.get("license_access") or "").lower()

    if any(t in token or t in name_family for t in ADAPTED_TOKENS):
        disposition = "adapted"
        rationale = "backed by a live agent adapter / matched backend"
    elif any(k in text for k in _COMMERCIAL_KEYWORDS) or "commercial" in licence:
        disposition = "commercial_excluded"
        rationale = "commercial/proprietary licence; not redistributed"
    elif any(k in text for k in _CREDENTIAL_KEYWORDS):
        disposition = "credential_gated"
        rationale = "requires an API key or licence before execution"
    elif any(k in text for k in _WEB_KEYWORDS) and not install:
        disposition = "web_service_documented"
        rationale = "web-only service; documented, not locally executable"
    elif install:
        disposition = "integration_candidate"
        rationale = "open-source install command present; integrate on demand"
    else:
        disposition = "out_of_scope"
        rationale = "no adapter, credential or documented install; outside TPD scope"
    return {
        "tool": name,
        "id": tool.get("id", ""),
        "disposition": disposition,
        "rationale": rationale,
        "install_command": install,
        "source_link": fields.get("source_link", ""),
    }


def build_disposition_report(excel_path: str | Path | None = None) -> dict[str, Any]:
    registry = load_toolkit_registry(excel_path)
    rows = [decide_disposition(tool) for tool in registry.get("tools", [])]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["disposition"]] = counts.get(row["disposition"], 0) + 1
    non_executable = sum(count for disp, count in counts.items() if disp != "adapted")
    return {
        "schema_version": "1.0.0",
        "n_tools": len(rows),
        "n_adapted": counts.get("adapted", 0),
        "n_non_executable": non_executable,
        "counts": dict(sorted(counts.items())),
        "decision": (
            "Adapted tools are used directly. Credential-gated, commercial and "
            "web-only tools stay documented with an explicit blocker. "
            "Integration candidates are wired on demand via the matched-tool "
            "registry; out-of-scope tools are excluded from the benchmark "
            "denominator rather than silently substituted."
        ),
        "tools": rows,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Toolkit disposition",
        "",
        f"- registered tools: {report['n_tools']}",
        f"- adapted: {report['n_adapted']}",
        f"- non-executable (decided): {report['n_non_executable']}",
        "",
        "| disposition | count |",
        "|---|---|",
    ]
    for disposition, count in report["counts"].items():
        lines.append(f"| {disposition} | {count} |")
    lines += ["", report["decision"], ""]
    return "\n".join(lines)


def write_disposition_report(
    json_path: str | Path = "outputs/tool_disposition.json",
    md_path: str | Path | None = None,
    excel_path: str | Path | None = None,
) -> dict[str, Any]:
    report = build_disposition_report(excel_path)
    json_out = Path(json_path)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if md_path is not None:
        md_out = Path(md_path)
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(_markdown(report), encoding="utf-8")
    return report


def dispositions_for(tools: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [decide_disposition(tool) for tool in tools]


__all__ = [
    "ADAPTED_TOKENS",
    "build_disposition_report",
    "decide_disposition",
    "dispositions_for",
    "write_disposition_report",
]
