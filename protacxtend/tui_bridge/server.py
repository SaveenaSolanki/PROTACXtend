"""PROTACXtend TUI Bridge Server.

Reads JSONL commands from stdin, dispatches to the Python backend,
and emits JSONL events to stdout. The TypeScript TUI spawns this
as a subprocess and communicates via this protocol.

Usage:
    python -m protacxtend.tui_bridge.server
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from typing import Any

from protacxtend.tui_bridge.events import (
    emit,
    emit_ready,
    emit_run_start,
    emit_agent_start,
    emit_agent_complete,
    emit_tool_call,
    emit_tool_result,
    emit_evidence,
    emit_warning,
    emit_run_complete,
    AGENT_PIPELINE,
    RESEARCH_WORKFLOWS,
)


def handle_status() -> None:
    """Emit system status."""
    import importlib
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]

    deps = {}
    for name in ["rdkit", "pandas", "torch", "chemprop", "numpy", "sklearn"]:
        try:
            m = importlib.import_module(name)
            deps[name] = getattr(m, "__version__", "installed")
        except Exception:
            deps[name] = "missing"

    llm = {"provider": "unknown", "model": "unknown", "healthy": False}
    try:
        from protacxtend.llm.providers import get_config, provider_health
        cfg = get_config()
        health = provider_health(cfg)
        llm = {
            "provider": cfg.provider,
            "model": cfg.model,
            "base_url": cfg.base_url,
            "num_ctx": cfg.num_ctx,
            "healthy": health.get("ok", False),
        }
    except Exception:
        pass

    emit({
        "type": "status",
        "version": "0.1.0",
        "project_root": str(project_root),
        "dependencies": deps,
        "llm": llm,
        "agents": len(AGENT_PIPELINE),
        "workflows": len(RESEARCH_WORKFLOWS),
    })


def handle_run(request: str) -> None:
    """Run the PROTACXtend workflow and emit streaming events."""
    run_id = emit_run_start(request)

    try:
        for agent in AGENT_PIPELINE:
            emit_agent_start(agent["id"])

            # Run the actual agent through the runtime
            try:
                _run_agent(agent["id"], request)
                emit_agent_complete(agent["id"], status="ok")
            except Exception as exc:
                emit_agent_complete(agent["id"], status="error", detail=str(exc)[:200])
                emit_warning(f"Agent {agent['name']} failed: {exc}", source=agent["id"])

        emit_run_complete("ok", run_id, {
            "agents_completed": len(AGENT_PIPELINE),
        })
    except Exception as exc:
        emit_run_complete("error", run_id, {"error": str(exc)})


def _run_agent(agent_id: str, request: str) -> None:
    """Run a single agent node. This delegates to the real Python backend."""
    # Import lazily to avoid loading heavy deps at startup
    from protacxtend.agents.graph import run_syn_glue_workflow
    from protacxtend.backend.main import summarize_state

    # For now, we run the full workflow on the first agent call
    # and cache results. In production, this would run node-by-node.
    if not hasattr(_run_agent, "_state_cache"):
        _run_agent._state_cache = None  # type: ignore

    if _run_agent._state_cache is None:  # type: ignore
        emit_tool_call("run_syn_glue_workflow", {"request": request[:120]})
        state = run_syn_glue_workflow(request)
        _run_agent._state_cache = state  # type: ignore
        emit_tool_result("run_syn_glue_workflow", status="ok")

    state = _run_agent._state_cache  # type: ignore

    # Emit evidence based on agent
    if agent_id == "target_resolver":
        target = getattr(state, "target_record", None)
        if target:
            emit_evidence("uniprot", {
                "gene": getattr(target, "gene_name", ""),
                "uniprot_id": getattr(target, "uniprot_id", ""),
                "organism": getattr(target, "organism", ""),
            }, summary=f"Target: {getattr(target, 'gene_name', '?')} ({getattr(target, 'uniprot_id', '?')})")

    elif agent_id == "binder_retrieval":
        binders = getattr(state, "retrieved_binders", []) or []
        emit_evidence("chembl_pubchem", {
            "count": len(binders),
        }, summary=f"{len(binders)} binders retrieved")

    elif agent_id == "e3_selection":
        e3 = getattr(state, "selected_e3_ligands", []) or []
        emit_evidence("e3_library", {
            "count": len(e3),
            "ligands": [getattr(e, "name", "") for e in e3[:5]],
        }, summary=f"{len(e3)} E3 ligands selected")

    elif agent_id == "degradation_prediction":
        preds = getattr(state, "degradation_predictions", []) or []
        emit_prediction("heuristic", "DC50", len(preds), confidence=0.6)

    elif agent_id == "ranking":
        ranked = getattr(state, "final_ranked_candidates", []) or getattr(state, "ranking_results", []) or []
        for c in ranked[:5]:
            emit_candidate(
                getattr(c, "candidate_id", ""),
                getattr(c, "full_protac_smiles", "")[:60],
                getattr(c, "composite_score", 0.0),
                getattr(c, "tier", ""),
            )


def handle_validate(smiles: str) -> None:
    """Validate a SMILES string."""
    emit_tool_call("validate_smiles", {"smiles": smiles})
    try:
        from protacxtend.tools.rdkit_chemistry import compute_basic_properties
        props = compute_basic_properties(smiles)
        emit_tool_result("validate_smiles", result=props, status="ok")
    except Exception as exc:
        emit_tool_result("validate_smiles", result={"error": str(exc)}, status="error")


def handle_command(cmd: str, args: dict[str, Any]) -> None:
    """Dispatch a command from the TUI."""
    if cmd == "run":
        handle_run(args.get("request", ""))
    elif cmd == "status":
        handle_status()
    elif cmd == "validate":
        handle_validate(args.get("smiles", ""))
    elif cmd == "workflows":
        emit({"type": "workflows", "workflows": RESEARCH_WORKFLOWS})
    elif cmd == "agents":
        emit({"type": "agents", "agents": AGENT_PIPELINE})
    elif cmd == "ping":
        emit({"type": "pong"})
    else:
        emit({"type": "error", "message": f"Unknown command: {cmd}"})


def main() -> None:
    """Main loop: read JSONL from stdin, dispatch, emit to stdout."""
    emit_ready()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            cmd = msg.get("type", "")
            args = {k: v for k, v in msg.items() if k != "type"}
            handle_command(cmd, args)
        except json.JSONDecodeError:
            emit({"type": "error", "message": f"Invalid JSON: {line[:100]}"})
        except Exception as exc:
            emit({"type": "error", "message": str(exc)})
            traceback.print_exc(file=sys.stderr)


if __name__ == "__main__":
    main()
