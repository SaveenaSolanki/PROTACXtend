"""
Unified ProtacPilot runtime — ONE production entry point (Task 1).
==================================================================

mode="deterministic" → the v0.1 reproducible workflow (agents/graph.py)
mode="agentic"       → the unified v0.3/v0.4 LangGraph
                          ├── deterministic scientific tools
                          ├── adaptive routers
                          ├── LLM decision layer (optional, gated)
                          └── human gates

Everything else (backend, CLI, UI) calls THIS. No other entry points.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger("protacpilot.runtime")

VALID_MODES = {"deterministic", "agentic"}


def run_protacpilot(
    user_request: str,
    mode: str = "deterministic",
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run a PROTAC design job through the unified runtime.

    Args:
        user_request: natural-language design request
        mode: "deterministic" (v0.1) | "agentic" (v0.3 unified graph)
        config: optional overrides (llm_enabled, human_gate, etc.)

    Returns:
        dict with: request, mode, run_id, status, summary, artifacts,
        state (mode-specific), runtime_s, pipeline_info
    """
    if mode not in VALID_MODES:
        raise ValueError(f"Unknown mode '{mode}'. Valid: {sorted(VALID_MODES)}")

    config = config or {}
    run_id = config.get("run_id") or f"run_{uuid.uuid4().hex[:8]}"
    t0 = time.time()

    if mode == "deterministic":
        result = _run_deterministic(user_request, config)
    else:
        result = _run_agentic(user_request, config)

    runtime_s = round(time.time() - t0, 2)
    return {
        "request": user_request,
        "mode": mode,
        "run_id": run_id,
        "status": result.get("status", "unknown"),
        "runtime_s": runtime_s,
        "pipeline_info": {"runtime": f"v0.1-deterministic" if mode == "deterministic" else "v0.3-agentic"},
        "summary": result.get("summary", {}),
        "artifacts": result.get("artifacts", {}),
        "state": result.get("state"),
    }


def _run_deterministic(user_request: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """v0.1 reproducible workflow (unchanged behavior)."""
    from synglue_agent.agents.graph import run_syn_glue_workflow
    from synglue_agent.backend.main import summarize_state

    state = run_syn_glue_workflow(user_request)
    return {
        "status": "ok",
        "summary": summarize_state(state),
        "artifacts": {"report": getattr(state, "report", None)},
        "state": state,
    }


def _run_agentic(user_request: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Unified v0.3 agentic path.

    Uses the adaptive graph (agents/agentic_core.py). When the LLM layer is
    enabled and reachable, evidence/repair decisions go through the gated
    gateway with deterministic validators + fallback; otherwise the
    deterministic adaptive graph runs unchanged (safe default).
    """
    from synglue_agent.agents.agentic_core import run_agentic_workflow

    llm_enabled = config.get("llm_enabled", False)
    state = run_agentic_workflow(user_request)

    # Learning persistence is part of the live graph output (Task 7 base)
    try:
        from synglue_agent.agents.learning_integration import persist_run_learnings
        artifacts = persist_run_learnings(state)
    except Exception as exc:
        logger.warning("learning persistence skipped: %s", exc)
        artifacts = {"error": str(exc)}

    return {
        "status": state.get("status", "ok"),
        "summary": {
            "n_candidates": len(state.get("valid_candidates", [])),
            "n_decisions": len(state.get("decision_log", [])),
            "llm_enabled": llm_enabled,
        },
        "artifacts": artifacts,
        "state": state,
    }


def summarize_run(result: Dict[str, Any]) -> str:
    """One-line human summary of a run (for UI/CLI)."""
    return (
        f"[{result['run_id']}] mode={result['mode']} status={result['status']} "
        f"({result['runtime_s']}s)"
    )
