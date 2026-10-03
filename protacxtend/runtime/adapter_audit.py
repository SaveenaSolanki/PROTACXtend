"""Per-adapter fixture-default audit for the 34 agent tools.

P0 made the agent-tool path fail closed in SCIENTIFIC mode. This audit closes
the remaining gap: it inspects every one of the 34 registered adapters and
flags *internal* default substitutions — a hard-coded ``CRBN``, ``default`` or
probe SMILES that the adapter would use when the caller omits a required
scientific input.

A tool is reported as:

* ``clean``            — no internal default for a required input;
* ``guarded_default``  — a default exists but SCIENTIFIC mode validates (and
  rejects) the missing input upstream, so it is unreachable in a scientific run;
* ``residual_default`` — a default for a required input that is not covered by
  the scientific-input guard (must be fixed).

The audit is deterministic and offline. It is asserted by
``tests/test_p1_governance.py`` so a regression cannot be merged silently.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any

from protacxtend.agentic import registry as agent_registry
from protacxtend.runtime.modes import SCIENTIFIC_REQUIRED_INPUTS

#: Literal values that are never legitimate scientific inputs.
_FIXTURE_LITERALS = frozenset(
    {
        "CRBN", "VHL", "cIAP1", "MDM2", "default", "demo", "test",
        "CCO", "CC", "c1ccccc1", "JQ1", "BRD4", "example", "placeholder",
    }
)


def _target_functions(entry: Any) -> list[Any]:
    names = [n for n in getattr(entry, "__code__", None).co_names if n.startswith("exec_")] if getattr(entry, "__code__", None) else []
    return [getattr(agent_registry, name) for name in names if hasattr(agent_registry, name)]


def _signature_defaults(fn: Any, required: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return out
    for pname, param in signature.parameters.items():
        default = param.default
        if pname in required and isinstance(default, str) and default:
            out.append(
                {
                    "kind": "signature_default",
                    "function": fn.__name__,
                    "parameter": pname,
                    "value": default,
                    "fixture_like": default in _FIXTURE_LITERALS,
                }
            )
    return out


def _or_substitutions(fn: Any, required: set[str]) -> list[dict[str, Any]]:
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        return []
    out: list[dict[str, Any]] = []
    for match in re.finditer(r"(\w+)\s+or\s+[\"']([^\"']+)[\"']", source):
        name, literal = match.group(1), match.group(2)
        if name in required:
            out.append(
                {
                    "kind": "or_substitution",
                    "function": fn.__name__,
                    "parameter": name,
                    "value": literal,
                    "fixture_like": literal in _FIXTURE_LITERALS,
                }
            )
    return out


def _lambda_defaults(entry: Any, required: set[str]) -> list[dict[str, Any]]:
    try:
        source = inspect.getsource(entry)
    except (OSError, TypeError):
        return []
    out: list[dict[str, Any]] = []
    for match in re.finditer(r"params\.get\(\s*[\"'](\w+)[\"']\s*,\s*[\"']([^\"']+)[\"']\s*\)", source):
        name, literal = match.group(1), match.group(2)
        if name in required:
            out.append(
                {
                    "kind": "lambda_default",
                    "function": "<lambda>",
                    "parameter": name,
                    "value": literal,
                    "fixture_like": literal in _FIXTURE_LITERALS,
                }
            )
    return out


def audit_agent_tool(name: str) -> dict[str, Any]:
    """Audit one registered agent tool for residual internal defaults."""
    entry = agent_registry._EXECUTORS.get(name)
    required = set(SCIENTIFIC_REQUIRED_INPUTS.get(name, ()))
    findings: list[dict[str, Any]] = []
    if entry is None:
        return {
            "tool": name,
            "status": "no_executor",
            "required_inputs": sorted(required),
            "findings": [],
            "scientific_guard": False,
        }
    for fn in _target_functions(entry):
        findings.extend(_signature_defaults(fn, required))
        findings.extend(_or_substitutions(fn, required))
    findings.extend(_lambda_defaults(entry, required))

    guard = bool(required)
    risky = [f for f in findings if f.get("fixture_like")]
    if not risky:
        status = "clean"
    elif guard:
        status = "guarded_default"
    else:
        status = "residual_default"
    return {
        "tool": name,
        "status": status,
        "required_inputs": sorted(required),
        "scientific_guard": guard,
        "findings": findings,
    }


def audit_all_agent_tools() -> dict[str, Any]:
    """Audit all 34 ready agent tools; return rows + summary + residuals."""
    names = sorted(agent_registry._EXECUTORS)
    rows = [audit_agent_tool(name) for name in names]
    residual = [row for row in rows if row["status"] == "residual_default"]
    return {
        "schema_version": "1.0.0",
        "n_tools": len(rows),
        "n_clean": sum(1 for row in rows if row["status"] == "clean"),
        "n_guarded_default": sum(1 for row in rows if row["status"] == "guarded_default"),
        "n_residual_default": len(residual),
        "residuals": [row["tool"] for row in residual],
        "tools": rows,
    }


def write_adapter_audit(path: str | Path) -> dict[str, Any]:
    report = audit_all_agent_tools()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


__all__ = [
    "audit_agent_tool",
    "audit_all_agent_tools",
    "write_adapter_audit",
]
