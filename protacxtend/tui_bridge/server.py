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


def handle_doctor() -> None:
    """Emit machine-readable /doctor diagnostics."""
    try:
        from protacxtend.diagnostics import build_doctor_report
        report = build_doctor_report()
        emit({"type": "doctor", "report": report, "ok": report.get("required_ok", False)})
    except Exception as exc:
        emit({"type": "doctor", "report": {"required_ok": False, "summary": {"ok": 0, "warn": 0, "fail": 1},
                                            "required_failures": ["diagnostics"], "checks": []},
              "ok": False, "error": str(exc)})


def handle_compare(path: str) -> None:
    """Prospective BRD4\u2013VHL six-PROTAC case study (/compare <file>)."""
    emit_tool_call("brd4_vhl_six_case_study", {"dataset": path or "bundled examples/brd4_vhl_6.csv"})
    try:
        from protacxtend.case_study.brd4_vhl_six import run_brd4_vhl_six_case_study
        out = run_brd4_vhl_six_case_study(path or None)
        payload = out["result"]
        emit({"type": "compare_result", "payload": payload})
        emit({"type": "scientific_result", "result": out["schema"]})
        emit_tool_result("brd4_vhl_six_case_study",
                         result=out["schema"],
                         status="ok")
    except Exception as exc:
        emit_tool_result("brd4_vhl_six_case_study",
                         result={"error": str(exc)},
                         status="error")
        emit({"type": "error", "message": f"case study failed: {exc}"})


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


def _schema_tool(tool: str, workflow: str, payload: dict, status: str = "ok", source: str = "",
                kind: str = "calculated", evidence: list[str] | None = None,
                provenance_tool: str = "") -> dict:
    """Wrap a tool payload in the shared ScientificResult envelope."""
    from protacxtend.results.schema import EvidenceItem, ScientificResult, Provenance
    evidence = evidence or [f"{tool} returned {status}"]
    from uuid import uuid4
    res = ScientificResult(
        workflow=workflow,
        summary=evidence[0],
        task_id=f"{tool}_{uuid4().hex[:8]}",
        status="ok" if status == "ok" else "failed",
        result=payload,
        evidence=[EvidenceItem(summary=ev, source=source, kind=kind) for ev in evidence],
        warnings=[payload.get("error", "")] if payload.get("error") else [],
        provenance=[Provenance(tool=provenance_tool or f"protacxtend.tools.{tool}", source=source)],
    )
    return res.to_dict()


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

        # Emit final results (rich + standardised schema)
        _emit_results()
        _emit_schema_result(request, run_id)
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


def _emit_schema_result(request: str, run_id: str) -> None:
    """Emit the shared ScientificResult envelope for a workflow run."""
    if not hasattr(_run_agent, "_state_cache") or _run_agent._state_cache is None:
        return
    state = _run_agent._state_cache

    from protacxtend.results.schema import ScientificResult, Provenance

    n_binders = len(getattr(state, "retrieved_binders", []) or [])
    n_warheads = len(getattr(state, "selected_warheads", []) or [])
    n_e3 = len(getattr(state, "selected_e3_ligands", []) or [])
    n_linkers = len(getattr(state, "generated_linkers", []) or [])
    n_candidates = len(getattr(state, "valid_candidates", []) or [])
    n_ranked = len(getattr(state, "final_ranked_candidates", []) or getattr(state, "ranking_results", []) or [])

    summary = (f"{n_candidates} candidates \u00b7 {n_ranked} ranked \u00b7 {n_binders} binders "
               f"\u00b7 {n_warheads} warheads \u00b7 {n_e3} E3 \u00b7 {n_linkers} linkers")
    res = ScientificResult(
        workflow="run",
        summary=summary,
        task_id=run_id,
        status="ok",
        result={
            "request": request,
            "candidates_generated": n_candidates,
            "candidates_ranked": n_ranked,
            "binders_found": n_binders,
            "warheads_selected": n_warheads,
            "e3_ligands_selected": n_e3,
            "linkers_generated": n_linkers,
            "run_id": run_id,
        },
        provenance=[Provenance(tool="run_syn_glue_workflow", source="protacxtend.agents.graph")],
    )
    if n_binders:
        res.add_evidence(f"{n_binders} binder record(s) retrieved for the target",
                         source="ChEMBL/PubChem/BindingDB", kind="retrieved")
    if n_candidates:
        res.add_evidence(f"{n_candidates} candidate(s) constructed and validated",
                         source="RDKit", kind="calculated")
    preds = getattr(state, "degradation_predictions", []) or []
    if preds:
        res.add_evidence(f"{len(preds)} degradation prediction(s) from trained model(s)",
                         source="chemprop/heuristic", kind="predicted")
    if not n_candidates and not n_binders:
        res.add_evidence("no measured potency data present for this objective",
                         source="run state", kind="missing")
        res.status = "partial"
    emit({"type": "scientific_result", "result": res.to_dict()})


def handle_validate(smiles: str) -> None:
    """Validate a SMILES string."""
    emit_tool_call("validate_smiles", {"smiles": smiles})
    try:
        from protacxtend.tools.molecule_standardizer import compute_basic_properties
        props = compute_basic_properties(smiles)
        summary = (f"MW {props.get('mw')} \u00b7 logP {props.get('logp')} \u00b7 TPSA {props.get('tpsa')} "
                   f"\u00b7 HBD {props.get('hbd')} \u00b7 HBA {props.get('hba')}")
        emit_tool_result("validate_smiles",
                         result=_schema_tool("validate_smiles", "admet", props, source="RDKit",
                                             kind="calculated", evidence=[summary],
                                             provenance_tool="protacxtend.tools.molecule_standardizer.compute_basic_properties"),
                         status="ok")
    except Exception as exc:
        emit_tool_result("validate_smiles",
                         result=_schema_tool("validate_smiles", "admet", {"error": str(exc)}, status="error",
                                             kind="missing", evidence=[f"validation failed: {exc}"]),
                         status="error")


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
        payload = {"linkers_generated": len(linkers),
                    "linker_types": ["PEG", "alkyl", "piperazine", "triazole", "semi-rigid"]}
        emit_tool_result("molecular_generator",
                         result=_schema_tool("molecular_generator", "generator", payload,
                                             kind="calculated", evidence=[f"{len(linkers)} linkers generated"],
                                             provenance_tool="protacxtend.tools.protac_toolbox"),
                         status="ok")
    except Exception as exc:
        emit_tool_result("molecular_generator",
                         result=_schema_tool("molecular_generator", "generator", {"error": str(exc)}, status="error",
                                             kind="missing", evidence=[f"generation failed: {exc}"]),
                         status="error")


def handle_retrosynthesis(smiles: str) -> None:
    """Run retrosynthesis planning."""
    emit_tool_call("retrosynthesis", {"smiles": smiles})
    try:
        from protacxtend.tools.retrosynthesis_engines import run_retrosynthesis
        result = run_retrosynthesis(smiles)
        routes = result.get("routes", []) if isinstance(result, dict) else []
        payload = {"smiles": smiles, "routes_found": len(routes), "routes": routes[:3]}
        emit_tool_result("retrosynthesis",
                         result=_schema_tool("retrosynthesis", "synthesis", payload,
                                             kind="calculated",
                                             evidence=[f"{len(routes)} retrosynthetic route(s) proposed for the target"],
                                             provenance_tool="protacxtend.tools.retrosynthesis_engines"),
                         status="ok")
    except Exception as exc:
        emit_tool_result("retrosynthesis",
                         result=_schema_tool("retrosynthesis", "synthesis", {"error": str(exc)}, status="error",
                                             kind="missing", evidence=[f"retrosynthesis failed: {exc}"]),
                         status="error")


def handle_docking(smiles: str, target: str = "") -> None:
    """Run molecular docking."""
    emit_tool_call("docking", {"smiles": smiles, "target": target})
    try:
        from protacxtend.tools.docking_pipeline import run_docking
        result = run_docking(smiles, target_pdb=target) if target else run_docking(smiles)
        payload = {"smiles": smiles, "target": target,
                    "binding_energy": getattr(result, "binding_energy", None),
                    "poses": getattr(result, "n_poses", 0)}
        emit_tool_result("docking",
                         result=_schema_tool("docking", "structure", payload, kind="predicted",
                                             evidence=["docking pose scored with AutoDock Vina"],
                                             provenance_tool="protacxtend.tools.docking_pipeline"),
                         status="ok")
    except Exception as exc:
        emit_tool_result("docking",
                         result=_schema_tool("docking", "structure", {"error": str(exc)}, status="error",
                                             kind="missing", evidence=[f"docking failed: {exc}"]),
                         status="error")


def handle_stereo(smiles: str) -> None:
    """Analyze stereochemistry."""
    emit_tool_call("stereochemistry", {"smiles": smiles})
    try:
        from protacxtend.tools.stereochemistry_engine import get_stereochemistry_profile
        profile = get_stereochemistry_profile(smiles)
        payload = {"smiles": smiles, "chiral_centers": getattr(profile, "n_chiral_centers", 0),
                    "ez_bonds": getattr(profile, "n_ez_bonds", 0),
                    "stereoisomers": getattr(profile, "n_stereoisomers", 1)}
        emit_tool_result("stereochemistry",
                         result=_schema_tool("stereochemistry", "structure", payload, kind="calculated",
                                             evidence=["stereochemistry profile enumerated"],
                                             provenance_tool="protacxtend.tools.stereochemistry_engine"),
                         status="ok")
    except Exception as exc:
        emit_tool_result("stereochemistry",
                         result=_schema_tool("stereochemistry", "structure", {"error": str(exc)}, status="error",
                                             kind="missing", evidence=[f"stereochemistry failed: {exc}"]),
                         status="error")


def handle_command(cmd: str, args: dict[str, Any]) -> None:
    """Dispatch a command from the TUI."""
    if cmd == "run":
        handle_run(args.get("request", ""))
    elif cmd == "doctor":
        handle_doctor()
    elif cmd == "compare":
        handle_compare(args.get("path", "") or args.get("file", ""))
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
