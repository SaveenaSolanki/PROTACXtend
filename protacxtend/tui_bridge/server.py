"""PROTACXtend TUI Bridge Server.

Reads JSONL commands from stdin, dispatches to the Python backend,
and emits JSONL events to stdout. The TypeScript TUI spawns this
as a subprocess and communicates via this protocol.

Usage:
    python -m synglue_agent.tui_bridge.server
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
    emit_prediction,
    emit_candidate,
    emit_warning,
    emit_run_complete,
    AGENT_PIPELINE,
    RESEARCH_WORKFLOWS,
    SKILLS,
    DATABASES,
)


def handle_status() -> None:
    """Emit system status."""
    import importlib
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]

    version = "0.1.0"
    try:
        import protacxtend
        version = getattr(protacxtend, "__version__", version)
    except Exception:
        pass


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
        "version": version,
        "project_root": str(project_root),
        "dependencies": deps,
        "llm": llm,
        "agents": len(AGENT_PIPELINE),
        "workflows": len(RESEARCH_WORKFLOWS),
        "skills": len(SKILLS),
        "databases": len(DATABASES),
    })


def handle_run(request: str) -> None:
    """Run the PROTACXtend workflow and emit streaming events."""
    run_id = emit_run_start(request)

    try:
        for agent in AGENT_PIPELINE:
            emit_agent_start(agent["id"])

            try:
                _run_agent(agent["id"], request)
                emit_agent_complete(agent["id"], status="ok")
            except Exception as exc:
                emit_agent_complete(agent["id"], status="error", detail=str(exc)[:200])
                emit_warning(f"Agent {agent['name']} failed: {exc}", source=agent["id"])

        # Emit final results
        _emit_results()
        emit_run_complete("ok", run_id, {
            "agents_completed": len(AGENT_PIPELINE),
        })
    except Exception as exc:
        emit_run_complete("error", run_id, {"error": str(exc)})


def _run_agent(agent_id: str, request: str) -> None:
    """Run a single agent node. This delegates to the real Python backend."""
    from protacxtend.agents.graph import run_syn_glue_workflow

    # Cache the full workflow state
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
        if preds:
            for p in preds[:3]:
                emit_prediction(
                    getattr(p, "model", "heuristic"),
                    getattr(p, "target", "DC50"),
                    getattr(p, "predicted_dc50", 0.0),
                    confidence=getattr(p, "model_confidence", 0.5),
                )
        else:
            emit_prediction("heuristic", "DC50", "N/A", confidence=0.0)

    elif agent_id == "ranking":
        ranked = getattr(state, "final_ranked_candidates", []) or getattr(state, "ranking_results", []) or []
        for c in ranked[:5]:
            emit_candidate(
                getattr(c, "candidate_id", ""),
                getattr(c, "full_protac_smiles", "")[:60],
                getattr(c, "composite_score", 0.0),
                getattr(c, "tier", ""),
            )


def _emit_results() -> None:
    """Emit final workflow results summary."""
    if not hasattr(_run_agent, "_state_cache") or _run_agent._state_cache is None:  # type: ignore
        return

    state = _run_agent._state_cache  # type: ignore

    # Count results
    n_candidates = len(getattr(state, "valid_candidates", []) or [])
    n_ranked = len(getattr(state, "final_ranked_candidates", []) or getattr(state, "ranking_results", []) or [])
    n_binder = len(getattr(state, "retrieved_binders", []) or [])
    n_warhead = len(getattr(state, "selected_warheads", []) or [])
    n_e3 = len(getattr(state, "selected_e3_ligands", []) or [])
    n_linker = len(getattr(state, "generated_linkers", []) or [])

    # Report path
    report = getattr(state, "report", "")
    report_preview = report[:200] if report else "No report generated"

    emit({
        "type": "results",
        "candidates_generated": n_candidates,
        "candidates_ranked": n_ranked,
        "binders_found": n_binder,
        "warheads_selected": n_warhead,
        "e3_ligands_selected": n_e3,
        "linkers_generated": n_linker,
        "report_preview": report_preview,
    })


def handle_validate(smiles: str) -> None:
    """Validate a SMILES string."""
    emit_tool_call("validate_smiles", {"smiles": smiles})
    try:
        from protacxtend.tools.molecule_standardizer import compute_basic_properties
        props = compute_basic_properties(smiles)
        emit_tool_result("validate_smiles", result=props, status="ok")
    except Exception as exc:
        emit_tool_result("validate_smiles", result={"error": str(exc)}, status="error")


def handle_skills() -> None:
    """Emit the full skills list."""
    emit({"type": "skills_list", "skills": SKILLS})


def handle_databases() -> None:
    """Emit the full databases list."""
    emit({"type": "databases_list", "databases": DATABASES})


def handle_generator(request: str) -> None:
    """Run molecular generation."""
    emit_tool_call("molecular_generator", {"request": request})
    try:
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
        toolbox = ProtacDesignToolbox()
        linkers = toolbox.generate_rule_based_linkers() if hasattr(toolbox, 'generate_rule_based_linkers') else []
        emit_tool_result("molecular_generator", result={
            "linkers_generated": len(linkers),
            "linker_types": ["PEG", "alkyl", "piperazine", "triazole", "semi-rigid"],
        }, status="ok")
    except Exception as exc:
        emit_tool_result("molecular_generator", result={"error": str(exc)}, status="error")


def handle_retrosynthesis(smiles: str) -> None:
    """Run retrosynthesis planning."""
    emit_tool_call("retrosynthesis", {"smiles": smiles})
    try:
        from protacxtend.tools.retrosynthesis_engines import run_retrosynthesis
        result = run_retrosynthesis(smiles)
        routes = result.get("routes", []) if isinstance(result, dict) else []
        emit_tool_result("retrosynthesis", result={
            "smiles": smiles,
            "routes_found": len(routes),
            "routes": routes[:3],
        }, status="ok")
    except Exception as exc:
        emit_tool_result("retrosynthesis", result={"error": str(exc)}, status="error")


def handle_docking(smiles: str, target: str = "") -> None:
    """Run molecular docking."""
    emit_tool_call("docking", {"smiles": smiles, "target": target})
    try:
        from protacxtend.tools.docking_pipeline import run_docking
        result = run_docking(smiles, target_pdb=target) if target else run_docking(smiles)
        emit_tool_result("docking", result={
            "smiles": smiles,
            "target": target,
            "binding_energy": getattr(result, "binding_energy", None),
            "poses": getattr(result, "n_poses", 0),
        }, status="ok")
    except Exception as exc:
        emit_tool_result("docking", result={"error": str(exc)}, status="error")


def handle_stereo(smiles: str) -> None:
    """Analyze stereochemistry."""
    emit_tool_call("stereochemistry", {"smiles": smiles})
    try:
        from protacxtend.tools.stereochemistry_engine import get_stereochemistry_profile
        profile = get_stereochemistry_profile(smiles)
        emit_tool_result("stereochemistry", result={
            "smiles": smiles,
            "chiral_centers": getattr(profile, "n_chiral_centers", 0),
            "ez_bonds": getattr(profile, "n_ez_bonds", 0),
            "stereoisomers": getattr(profile, "n_stereoisomers", 1),
        }, status="ok")
    except Exception as exc:
        emit_tool_result("stereochemistry", result={"error": str(exc)}, status="error")


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
    elif cmd == "skills":
        handle_skills()
    elif cmd == "databases":
        handle_databases()
    elif cmd == "generator":
        handle_generator(args.get("request", ""))
    elif cmd == "retrosynthesis":
        handle_retrosynthesis(args.get("smiles", ""))
    elif cmd == "docking":
        handle_docking(args.get("smiles", ""), args.get("target", ""))
    elif cmd == "stereo":
        handle_stereo(args.get("smiles", ""))
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
