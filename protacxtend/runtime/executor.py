"""Single capability executor shared by CLI, FastAPI and the TUI bridge.

This is the one code path every public surface calls so that a capability is
traced identically regardless of entry point:

    surface -> executor -> acquisition resolver -> tool/backend
      -> output validation -> provenance record

The executor never installs anything (acquisition is human-only) and never
claims scientific validation from execution alone.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from protacxtend.runtime import modes

ROOT = Path(__file__).resolve().parents[2]


def _norm(status: Any) -> str:
    return str(status).replace("ToolStatus.", "").strip().lower()


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def _params_hash(params: dict) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:16]


# ── lightweight, deterministic scientific runners ───────────────────────
def _runners() -> dict[str, Callable[[dict], Any]]:
    from protacxtend.scientific_backends import (
        analyze_linker, chemistry, generate_conformers, predict_admet,
        rank_candidates, retrieve_structure,
    )
    # No silent default substitution: a missing/empty input must reach the backend
    # and be rejected there, never replaced by a hard-coded "CCO" fixture
    # (which produced a fabricated result for an empty SMILES).
    return {
        "chemistry": lambda p: chemistry(p.get("smiles", ""),
                                         operation=p.get("operation", "descriptors")),
        "conformer_generation": lambda p: generate_conformers(p.get("smiles", ""),
                                                              n_conformers=int(p.get("n_conformers", 3))),
        "admet": lambda p: predict_admet(p.get("smiles", "")),
        "linker_analysis": lambda p: analyze_linker(p.get("linker_smiles", "")),
        "candidate_ranking": lambda p: rank_candidates(p.get("candidates") or []),
        "protein_structure": lambda p: retrieve_structure(p.get("identifier", "")),
    }


#: Retained for backward compatibility, but intentionally empty: hard-coded
#: ``smiles="CCO"`` probe defaults were removed.  Scientific inputs must now be
#: supplied by the caller (and are validated in SCIENTIFIC mode).
AGENT_TOOL_RUNNERS: dict[str, dict[str, Any]] = {}

#: Required scientific inputs for the lightweight capability runners.  Only
#: enforced in SCIENTIFIC mode; DEMO/TEST keep their exploratory behaviour.
_CAPABILITY_REQUIRED_INPUTS: dict[str, tuple[str, ...]] = {
    "chemistry": ("smiles",),
    "conformer_generation": ("smiles",),
    "admet": ("smiles",),
    "linker_analysis": ("linker_smiles",),
    "candidate_ranking": ("candidates",),
    "protein_structure": ("identifier",),
}


def _is_agent_tool(name: str) -> bool:
    """True when *name* is a registered, executor-backed agent tool."""
    if not name:
        return False
    tool = name.split("agent_tool:", 1)[1] if name.startswith("agent_tool:") else name
    try:
        from protacxtend.agentic.registry import _EXECUTORS, spec_for
        return spec_for(tool)["readiness"] == "ready" and tool in _EXECUTORS
    except Exception:
        return False


def _is_scientific_backend(name: str) -> bool:
    """True when *name* is one of the 19 capability-first scientific backends."""
    try:
        from protacxtend.scientific_backends.registry import Capability
        return name in {c.value for c in Capability}
    except Exception:
        return False


def _agent_tool_branch(tool: str, params: dict) -> tuple[dict[str, Any], bool, str]:
    """Run one registered agent tool and return (result, executed, reason)."""
    try:
        from protacxtend.runtime.agent_tools import run_agent_tool

        run = run_agent_tool(tool, params)
        envelope = run.get("scientific_result") or {}
        result = {
            "status": run.get("status", "error"),
            "method_label": tool,
            "backend": "agentic.registry",
            "evidence_tier": run.get("evidence_kind", ""),
            "data": (envelope.get("result") or {}).get("data", {}),
            "scientific_result": envelope,
            "agent_tool": {k: run[k] for k in
                           ("RESOLVED", "EXECUTED", "VALID_OUTPUT",
                            "FALLBACK_TESTED", "AGENT_EXPOSED")},
        }
        return result, bool(run.get("EXECUTED")), (run.get("error") or "")
    except modes.ScientificInputError:
        # Fixture / synthetic / missing-input policy violations must surface as
        # explicit errors, not be swallowed into a generic error result.
        raise
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}", "data": {}}, False, "agent tool raised"


def run_capability(name: str, params: dict | None = None) -> dict[str, Any]:
    """Execute (or plan) one capability through the shared resolution path."""
    from protacxtend.runtime import acquisition as acq

    params = dict(params or {})
    t0 = time.time()
    resolution = acq.resolve(name)
    cap = resolution.capability or name
    result: dict[str, Any] = {"status": "error", "data": {}, "method_label": ""}
    executed = False
    reason = ""

    runners = _runners()
    non_finite = False

    # Agent-tool names take precedence over a resolved scientific capability:
    # e.g. `inspect_smiles` resolves to capability `chemistry`, but the caller
    # asked for the agent tool and must get its real adapter + typed envelope.
    agent_tool_name = ""
    if _is_agent_tool(name):
        agent_tool_name = name.split("agent_tool:", 1)[1] if name.startswith("agent_tool:") else name
    elif cap.startswith("agent_tool:"):
        agent_tool_name = cap.split("agent_tool:", 1)[1]

    if agent_tool_name:
        result, executed, reason = _agent_tool_branch(agent_tool_name, params)
    elif cap in runners:
        if modes.is_scientific():
            modes.validate_scientific_params(
                f"capability '{cap}'", params,
                _CAPABILITY_REQUIRED_INPUTS.get(cap, ()),
            )
        try:
            sr = runners[cap](params)
            executed = True
            result = {"status": _norm(getattr(sr, "status", "unknown")),
                      "method_label": getattr(sr, "method_label", ""),
                      "backend": getattr(sr, "backend", ""),
                      "evidence_tier": getattr(sr, "evidence_tier", ""),
                      "data": getattr(sr, "data", {})}
        except Exception as exc:  # noqa: BLE001
            result = {"status": "error", "error": f"{type(exc).__name__}: {exc}", "data": {}}
            reason = "runner raised"
    elif _is_agent_tool(cap):
        tool = cap.split("agent_tool:", 1)[1] if cap.startswith("agent_tool:") else cap
        result, executed, reason = _agent_tool_branch(tool, params)
    elif _is_scientific_backend(cap):
        # Every one of the 19 capability-first backends is reachable through the
        # shared executor; licence-gated backends degrade to their result, never
        # to a fabricated one.
        try:
            from protacxtend.scientific_backends.runner import run_capability as run_sci
            sr = run_sci(cap, **params)
            executed = True
            result = {"status": _norm(getattr(sr, "status", "unknown")),
                      "method_label": getattr(sr, "method_label", ""),
                      "backend": getattr(sr, "backend", ""),
                      "evidence_tier": getattr(sr, "evidence_tier", ""),
                      "data": getattr(sr, "data", {})}
        except Exception as exc:  # noqa: BLE001
            result = {"status": "error", "error": f"{type(exc).__name__}: {exc}", "data": {}}
            reason = "scientific backend raised"
    else:
        reason = ("heavy/heavyweight capability: resolution traced, execution skipped in the "
                  "interactive executor; frozen evidence cited instead")

    # JSON-safe transport: non-finite floats become null and are flagged
    def _scan(o: Any) -> bool:
        if isinstance(o, float):
            return math.isnan(o) or math.isinf(o)
        if isinstance(o, dict):
            return any(_scan(v) for v in o.values())
        if isinstance(o, (list, tuple)):
            return any(_scan(v) for v in o)
        return False
    non_finite = _scan(result.get("data"))
    result["data"] = _sanitize(result.get("data"))
    result["non_finite_sanitized"] = non_finite

    valid = _validate(result)
    input_origins = modes.classify_input_origin(params)
    provenance = {
        "tool": name,
        "resolved_capability": cap,
        "backend": result.get("backend") or resolution.backend,
        "resolution_state": resolution.state,
        "input_origin": modes.dominant_input_origin(input_origins),
        "input_origins": input_origins,
        "failure_code": result.get("failure_code", ""),
        "params": params,
        "params_sha256": _params_hash(params),
        "timestamp_utc": _utc(),
        "git_commit": _git_commit(),
        "host": platform.node(),
        "python": platform.python_version(),
        "seeds": params.get("seed"),
        "executed": executed,
    }
    return {
        "capability": name,
        "resolved_capability": cap,
        "execution_mode": modes.get_execution_mode().value,
        "resolution": resolution.to_dict(),
        "executed": executed,
        "result": result,
        "output_valid": valid,
        "reason": reason,
        "provenance": provenance,
        "latency_s": round(time.time() - t0, 3),
    }


def _validate(result: dict) -> bool:
    if not isinstance(result, dict):
        return False
    if "status" not in result:
        return False
    if result.get("status") in ("error", "unknown", "not_available",
                                "capability_unavailable", "license_required", "blocked"):
        return False
    data = result.get("data")
    if not isinstance(data, dict) or not data:
        return False
    try:
        json.dumps(result.get("data", {}), default=str)
    except Exception:  # noqa: BLE001
        return False
    return True
