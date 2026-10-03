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

The two engines are *leaves* of the canonical control plane
(``protacxtend.canonical``): whichever mode runs, the run is parsed, evidence-
recorded, critiqued and turned into a typed ``TherapeuticStrategy`` by the same
stack. ``run_protacpilot`` returns that strategy under ``therapeutic_strategy``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

# Bound OpenMP/BLAS pools early (see tools/thread_limits docstring): this makes
# sklearn/numpy/scipy inference fast on shared boxes (HGB predict measured
# ~11 s/model at machine load>40 with unbounded pools vs <1 ms bounded).
from protacxtend.tools.thread_limits import apply_thread_limits

apply_thread_limits()

logger = logging.getLogger("protacpilot.runtime")

VALID_MODES = {"deterministic", "agentic"}


def _as_state_dict(state: Any) -> Dict[str, Any]:
    """Normalize a runtime state (dict or pydantic WorkflowState) to the dict
    shape consumed by run_records.build_agent_run_record / write_run_record."""
    if state is None:
        return {}
    if isinstance(state, dict):
        return state
    if hasattr(state, "model_dump"):
        try:
            return state.model_dump()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("state.model_dump() failed: %s", exc)
    return {}


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
    if not config.get("capability"):
        config = {**config, "capability": _detect_capability(user_request)}
    run_id = config.get("run_id") or f"run_{uuid.uuid4().hex[:8]}"
    t0 = time.time()

    # One canonical run id everywhere: expose it to in-graph workflow-memory
    # writes (protac_toolbox.write_workflow_memory) for the duration of this run.
    from protacxtend.tools.protac_toolbox import reset_active_run_id, set_active_run_id
    _rid_token = None
    try:
        _rid_token = set_active_run_id(run_id)
    except Exception:  # pragma: no cover - defensive
        _rid_token = None

    # Central tracing: every run writes outputs/runs/<run_id>/trace.jsonl
    try:
        from protacxtend.observability.tracing import TraceSession
        trace = TraceSession(run_id=run_id, meta={"mode": mode, "request": user_request[:120]})
    except Exception:
        trace = None

    # TargetTherapeuticsAssessment design gate: a design must not bypass
    # identity / chemistry / therapeutic-window gates. Blocked or
    # assessment-mandatory cases fail closed with a typed reason.
    gate_out: dict[str, Any] = {}
    try:
        from protacxtend.therapeutics.api import design_gate, TherapeuticallyUnsuitable
        spec = config.get("target_spec") or _target_spec_from_request(user_request)
        if spec:
            gate_out = design_gate(spec,
                                   disease=config.get("disease", "") or "",
                                   cell_line=config.get("cell_line", "") or "",
                                   require_assessment=bool(config.get("require_assessment", False)),
                                   allow_requires_review=bool(config.get("allow_requires_review", True)))
    except TherapeuticallyUnsuitable as gate_err:
        if trace:
            trace.error("gate", str(gate_err))
            trace.end(status="blocked")
        return {"status": "blocked", "gate": "therapeutics", "error": str(gate_err),
                "request": user_request, "run_id": run_id, "runtime_s": round(time.time() - t0, 2)}

    try:
        if mode == "deterministic":
            result = _run_deterministic(user_request, config)
        else:
            result = _run_agentic(user_request, config)
    except Exception as exc:
        if trace:
            trace.error("runtime", str(exc))
            trace.end(status="failed")
        if _rid_token is not None:
            reset_active_run_id(_rid_token)
        raise

    runtime_s = round(time.time() - t0, 2)
    if gate_out:
        result["therapeutic_assessment"] = gate_out

    # Canonical control plane (single execution stack):
    #   Scientific Request Parser -> Evidence Store -> Critic -> Decision Engine
    # Both engines below are leaves reached through the canonical Tool Executor,
    # so provenance, routing and the final TherapeuticStrategy are identical
    # regardless of which engine produced the scientific state. Never fatal.
    try:
        from protacxtend.canonical import CanonicalOrchestrator

        config = {**config, "artifact_paths": result.get("artifacts") or {}}
        canonical = CanonicalOrchestrator().review_engine_state(
            user_request,
            result.get("state"),
            run_id=run_id,
            engine=mode,
            config=config,
        )
        result["canonical"] = {
            "run_id": canonical.run_id,
            "status": canonical.status,
            "critic": canonical.critic.model_dump(),
            "strategy": canonical.strategy.model_dump(),
            "task_graph": canonical.task_graph.model_dump(),
            "module_results": [item.model_dump() for item in canonical.module_results],
            "warnings": canonical.warnings,
            "errors": canonical.errors,
        }
        result["therapeutic_strategy"] = canonical.strategy.model_dump()
    except Exception as exc:  # pragma: no cover - canonical review is advisory
        logger.warning("canonical review skipped: %s", exc)

    # Coverage matrix (search instrumentation): record evaluated cells
    try:
        if mode == "agentic":
            from protacxtend.tools.coverage_matrix import coverage_snapshot
            st = result.get("state") or {}
            cands = [
                {"full_protac_smiles": getattr(c, "full_protac_smiles", ""),
                 "e3_ligase": getattr(c, "e3_ligase", ""),
                 "linker_name": getattr(c, "linker_name", "")}
                for c in st.get("valid_candidates", []) or []
            ]
            result["coverage"] = coverage_snapshot(cands, run_id)
    except Exception as exc:
        logger.warning("coverage snapshot failed: %s", exc)

    # Canonical AgentRunRecord (auditable run artifact set)
    try:
        if config.get("record_run", mode == "agentic"):
            from protacxtend.run_records import build_agent_run_record, write_run_record, OUTPUT_ROOT
            state_dict = _as_state_dict(result.get("state"))
            record = build_agent_run_record({**result, "state": state_dict},
                                            run_id, user_request, runtime_s)
            run_dir = OUTPUT_ROOT / run_id
            run_json = write_run_record(
                run_dir, record, state_dict,
                report_text=state_dict.get("report", ""),
            )
            # Typed scientific output is a first-class run artifact, so every
            # discovery run ships a machine-readable TherapeuticStrategy.
            strategy_path = None
            strategy_payload = result.get("therapeutic_strategy")
            if strategy_payload:
                strategy_path = run_dir / "therapeutic_strategy.json"
                strategy_path.write_text(
                    json.dumps(strategy_payload, indent=2, default=str), encoding="utf-8"
                )
            result["run_record"] = {
                "run_id": run_id,
                "dir": str(run_dir),
                "file": str(run_json),
                **({"strategy_file": str(strategy_path)} if strategy_path else {}),
            }
            # Optional cognitive-memory ingestion (opt-in via
            # PROTACPILOT_COGNITIVE_MEMORY=1; default OFF so frozen run
            # artifacts and benchmarks are unchanged).  Never fatal.
            try:
                from protacxtend.memory.cognitive_bridge import maybe_ingest
                result["cognitive_memory"] = maybe_ingest(record, state_dict)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("cognitive memory ingestion skipped: %s", exc)
    except Exception as exc:
        logger.warning("run record write failed: %s", exc)

    if trace:
        trace.tool_call("runtime.run_protacpilot",
                        {"mode": mode, "run_id": run_id},
                        result_summary={"status": result.get("status"),
                                        "n_decisions": result.get("summary", {}).get("n_decisions")},
                        elapsed_s=runtime_s)
        trace.end(status=result.get("status", "unknown"))
        result["trace"] = {"run_id": run_id,
                           "summary": trace.summary() if hasattr(trace, 'summary') else None}

    trace_info = None
    if trace is not None:
        trace_info = {
            "run_id": run_id,
            "trace_file": str(trace.dir / "trace.jsonl"),
            "summary_file": str(trace.dir / "summary.json"),
            "events": trace._events,
        }

    if _rid_token is not None:
        reset_active_run_id(_rid_token)

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
        "trace": trace_info,
        "run_record": result.get("run_record"),
        "canonical": result.get("canonical"),
        "therapeutic_strategy": result.get("therapeutic_strategy"),
    }


def _target_spec_from_request(request: str) -> str:
    """Best-effort target spec (symbol + optional variant) from the request."""
    try:
        from protacxtend.contracts.entities import parse_request
        import re as _re
        m = _re.search(r"([A-Z]{1,2}\d{2,4}[A-Z](?:del|ins|dup)?)", request or "")
        variant = m.group(1) if m else ""
        pr = parse_request(request or "")
        base = pr.target or ""
        return f"{base} {variant}".strip() if base else ""
    except Exception:  # noqa: BLE001
        return ""


_KNOW_MARKERS = ("which", "what is", "what are", "accession", "uniprot", "how many",
                  "pocket", "family", "documented", "list the", "identify the", "who")
_REASON_MARKERS = ("assess", "why", "explain", "retain", "liability", "mechanic",
                   "pharmacophore", "suitable", "compare", "would", "because", "motif")


def _detect_capability(question: str) -> str:
    """Smallest general KNOW/REASON router fallback (used when the caller does
    not supply an explicit capability). DESIGN/DISCOVER stay engine-default."""
    q = (question or "").lower()
    if any(m in q for m in _KNOW_MARKERS):
        return "KNOW"
    if any(m in q for m in _REASON_MARKERS):
        return "REASON"
    return ""


def _run_deterministic(user_request: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """v0.1 reproducible workflow; honors config['capability'] (KNOW/REASON/
    DESIGN/DISCOVER) so KNOW/REASON questions take the retrieval/evidence
    route instead of the full design graph."""
    from protacxtend.agents.graph import run_syn_glue_workflow
    from protacxtend.backend.main import summarize_state

    capability = (config.get("capability") or "").strip()
    state = run_syn_glue_workflow(user_request, capability=capability or None)
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

    Runs under a PERSISTENT checkpointer (interrupt/resume capable):
      - a run_id maps to a thread_id
      - human gates interrupt; the run resumes via Command(resume=...) on
        the same thread_id
    """
    from protacxtend.agents.agentic_core import run_agentic_workflow

    llm_enabled = config.get("llm_enabled", False)
    run_id = config.get("run_id") or f"run_{uuid.uuid4().hex[:8]}"
    # REAL graph nodes (scientific tools), not stubs — the agentic mode is a
    # working scientific pipeline: live ChEMBL binders, chemprop degradation,
    # ADMET-AI, fragment linkers, BRICS construction, NSGA-II ranking.
    try:
        from protacxtend.agents.real_nodes import real_nodes
        nodes = real_nodes()
    except Exception as exc:
        logger.warning("real_nodes unavailable (%s) — falling back to stubs", exc)
        nodes = None
    # e2e/offline runs use the in-memory checkpointer (no sqlite lock contention);
    # production API runs keep persistence (interrupt/resume).
    thread_id = run_id if config.get("persistent", True) else None
    state = run_agentic_workflow(user_request, legacy_agents=nodes, thread_id=thread_id)

    # A human gate may have interrupted the run (persistent checkpointer).
    interrupted = bool(state.get("__interrupt__"))

    # Learning persistence is part of the live graph output (Task 7 base)
    try:
        from protacxtend.agents.learning_integration import persist_run_learnings
        artifacts = persist_run_learnings(state)
    except Exception as exc:
        logger.warning("learning persistence skipped: %s", exc)
        artifacts = {"error": str(exc)}

    return {
        "status": "needs_human" if interrupted else state.get("status", "ok"),
        "summary": {
            "n_candidates": len(state.get("valid_candidates", [])),
            "n_decisions": len(state.get("decision_log", [])),
            "llm_enabled": llm_enabled,
            "interrupted": interrupted,
            "resume_thread": run_id,
        },
        "artifacts": artifacts,
        "state": state,
    }


def resume_agentic_run(run_id: str, resume_value: Any, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resume an interrupted agentic run on the persistent checkpointer.

    After a human gate interrupts (status needs_human), call this with the
    human's decision (e.g. "approve" / "abort") to continue the same thread.
    """
    from protacxtend.agents.checkpointer import (
        get_checkpointer, run_id_thread, resume_command,
    )
    from protacxtend.agents.agentic_core import build_agentic_graph

    graph = build_agentic_graph().compile(checkpointer=get_checkpointer())
    command = resume_command(resume_value)
    result = graph.invoke(command, config={"configurable": {"thread_id": run_id_thread(run_id)}})
    return {
        "run_id": run_id,
        "status": result.get("status", "ok"),
        "state": result,
        "resumed_with": resume_value,
    }


def summarize_run(result: Dict[str, Any]) -> str:
    """One-line human summary of a run (for UI/CLI)."""
    return (
        f"[{result['run_id']}] mode={result['mode']} status={result['status']} "
        f"({result['runtime_s']}s)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PROTACXtend through the unified runtime.")
    parser.add_argument(
        "request",
        nargs="?",
        default="Design CRBN PROTACs for BRD4 degradation.",
        help="Natural-language PROTAC design request.",
    )
    parser.add_argument("--mode", choices=sorted(VALID_MODES), default="agentic")
    parser.add_argument("--run-id", default="", help="Optional stable run id.")
    parser.add_argument("--persistent", action="store_true", help="Use persistent checkpointer for interrupt/resume.")
    parser.add_argument("--llm-enabled", action="store_true", help="Enable the configured LLM decision layer.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON result instead of a short summary.")
    args = parser.parse_args()

    config: dict[str, Any] = {
        "persistent": bool(args.persistent),
        "llm_enabled": bool(args.llm_enabled),
    }
    if args.run_id:
        config["run_id"] = args.run_id
    result = run_protacpilot(args.request, mode=args.mode, config=config)
    if args.json:
        from protacxtend.backend.schemas import model_to_dict

        print(json.dumps(model_to_dict(result), indent=2))
    else:
        print(summarize_run(result))
        artifacts = result.get("artifacts") or {}
        if artifacts:
            print(json.dumps(artifacts, indent=2))


if __name__ == "__main__":
    main()
