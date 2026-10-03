"""PROTACXtend TUI Bridge Server.

Reads JSONL commands from stdin, dispatches to the Python backend,
and emits JSONL events to stdout. The TypeScript TUI spawns this
as a subprocess and communicates via this protocol.

Usage:
    python -m protacxtend.tui_bridge.server
"""

from __future__ import annotations

import concurrent.futures
import json
import os
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


def _resource_reason_summary_uncapped(text: str, *, offline: bool = True) -> dict[str, Any]:
    if not (text or "").strip():
        return {}
    from protacxtend.workflows.resource_audit import shortlist_resources
    return shortlist_resources(text, offline=offline, top_k=16).get("resource_reason_summary", {})


def _resource_reason_summary_for(text: str, *, offline: bool = True) -> dict[str, Any]:
    if not (text or "").strip():
        return {}
    timeout_s = float(os.environ.get("PROTACXTEND_RESOURCE_REASON_TIMEOUT_S", "2.0"))
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="protac-resource-reasons")
    fut = executor.submit(_resource_reason_summary_uncapped, text, offline=offline)
    try:
        out = fut.result(timeout=timeout_s)
        executor.shutdown(wait=False, cancel_futures=True)
        return out
    except concurrent.futures.TimeoutError:
        cancelled = fut.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        return {
            "schema_version": "resource-reason-summary.v1",
            "status": "partial_timeout",
            "timeout_s": timeout_s,
            "backend_continues_after_timeout": not cancelled,
            "late_results_can_overwrite": False,
            "selected": [],
            "rejected": [],
            "limitation": "resource-reason selection exceeded the bridge timeout; core answer preserved",
        }
    except Exception as exc:  # noqa: BLE001
        executor.shutdown(wait=False, cancel_futures=True)
        return {"schema_version": "resource-reason-summary.v1", "status": "failed", "error": str(exc),
                "late_results_can_overwrite": False}


from protacxtend.tui_bridge import semantics as _sem
from protacxtend.tui_bridge import evidence_synthesis as _synth

_CONTEXT = _sem.ContextStore()


def _merge_context(cmd: str, text: str, understanding, conversation_id: str) -> dict:
    """Project conversation context (target/E3) onto under-specified commands."""
    from protacxtend.request.controller import RequestController
    roles = _sem.resolve_roles(text, understanding)
    ctx = _CONTEXT.get(conversation_id)
    injected = {}
    had_target = bool(getattr(understanding, "primary_target", None) and
                      getattr(understanding.primary_target, "symbol", None))
    had_e3 = str(getattr(getattr(understanding, "e3", None), "mode", "")) == "explicit"
    if not had_target and ctx.target_symbol:
        injected["target_injected"] = ctx.target_symbol
    if not had_e3 and ctx.e3:
        injected["e3_injected"] = ctx.e3
    _CONTEXT.update_from_understanding(conversation_id, understanding, roles)
    return injected


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

    llm = {"provider": "(none)", "model": "", "healthy": False}
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


def _is_design_like_request(request: str) -> bool:
    text = (request or "").lower()
    return "protac" in text or "degrader" in text or "design" in text


def _handle_design_run_via_workflows_api(request: str) -> None:
    """Run design-like /run through workflows.api, then emit TUI events."""
    from protacxtend.workflows.api import _design_run_id

    expected_run_id = _design_run_id(f"/run {request}")
    run_id = emit_run_start(request, run_id=expected_run_id)
    try:
        from protacxtend.workflows.api import run_command

        payload = run_command("run", f"/run {request}", resume_from="", offline=True)
        payload.setdefault("run_id", run_id)
        payload.setdefault("resource_reason_summary", _resource_reason_summary_for(request, offline=True))
        emit_tool_result("workflows.api.run_command",
                         result={"run_id": payload.get("run_id"), "status": payload.get("status")},
                         status="ok")
        for idx, stage in enumerate(payload.get("stage_timeline", []) or []):
            emit({"type": "progress", "run_id": payload.get("run_id", run_id),
                  "stage": stage.get("stage"), "status": stage.get("status"),
                  "detail": stage.get("detail", ""), "index": idx,
                  "total": len(payload.get("stage_timeline", []) or [])})
        for row in (payload.get("candidate_evidence_table") or [])[:10]:
            rank = row.get("ranking") or {}
            emit_candidate(row.get("candidate_id", ""), row.get("canonical_smiles", "")[:80],
                           rank.get("final_priority_score"), rank.get("tier", ""),
                           score_label="final_priority_score")
        emit({"type": "results",
              "run_id": payload.get("run_id", run_id),
              "saved_dir": (payload.get("artifacts", {}).get("engine_run_record", {}) or {}).get("dir", ""),
              "persisted": bool((payload.get("artifacts", {}).get("engine_run_record", {}) or {}).get("dir")),
              "status": payload.get("status"),
              "candidates_generated": payload.get("assembly_counts", {}).get("valid", 0),
              "candidates_ranked": len(payload.get("candidate_evidence_table") or []),
              "stage_timeline": payload.get("stage_timeline", []),
              "intermediate_files": payload.get("intermediate_files", {}),
              "scientific_findings": payload.get("scientific_findings", []),
              "candidate_evidence_table": payload.get("candidate_evidence_table", []),
              "resume_state": payload.get("resume_state", {}),
              "evidence_gates": payload.get("evidence_gates", {}),
              "resource_reason_summary": payload.get("resource_reason_summary", {})})
        emit({"type": "research_answer", "command": "run", **payload})
        emit_run_complete("ok", payload.get("run_id", run_id), {
            "run_id": payload.get("run_id", run_id),
            "status": payload.get("status"),
            "executed_stages": payload.get("executed_stages", []),
            "unevaluated_stages": payload.get("unevaluated_stages", []),
            "intermediate_files": payload.get("intermediate_files", {}),
            "resume_state": payload.get("resume_state", {}),
        })
    except Exception as exc:  # noqa: BLE001
        emit_run_complete("error", run_id, {"error": str(exc), "run_id": run_id})


def handle_run(request: str) -> None:
    """Run a workflow through the PRODUCTION runtime and emit streaming events.

    Execution goes through protacxtend.agents.runtime.run_protacpilot
    (deterministic mode = the same scientific graph as before), which owns the
    canonical run id, TraceSession and the outputs/runs/<run_id>/ artifact
    bundle (run.json / summary.json / trace.jsonl / decisions.jsonl /
    evidence.jsonl / candidates.parquet / report.md).

    The bridge-generated run id is passed in as config run_id so TUI, runtime,
    trace, output directory, run.json and workflow memory all share ONE id.
    No module-level state cache survives between independent user runs.
    """
    if _is_design_like_request(request):
        _handle_design_run_via_workflows_api(request)
        return

    run_id = emit_run_start(request)
    saved_dir = ""
    try:
        # Single canonical execution through the existing runtime wrapper.
        from protacxtend.agents.runtime import run_protacpilot
        from protacxtend.agents.graph import set_progress_callback
        emit_tool_call("run_protacpilot",
                       {"mode": "deterministic", "request": request[:120], "run_id": run_id})

        # Stream live per-node progress so a multi-minute run is not silent.
        def _progress(stage: str, status_: str, elapsed_s: float, index: int, total: int) -> None:
            emit({"type": "progress", "run_id": run_id, "stage": stage,
                  "status": status_, "elapsed_s": elapsed_s, "index": index, "total": total})

        set_progress_callback(_progress)
        try:
            result = run_protacpilot(request, mode="deterministic",
                                     config={"run_id": run_id, "record_run": True})
        finally:
            set_progress_callback(None)
        state = result.get("state")
        emit_tool_result("run_protacpilot",
                         result={"run_id": run_id, "status": result.get("status")},
                         status="ok")

        record = result.get("run_record") or {}
        saved_dir = str(record.get("dir") or "")

        # Progress + evidence stream (kept: Supervisor, Target Resolver, ...).
        for agent in AGENT_PIPELINE:
            emit_agent_start(agent["id"])
            try:
                _emit_agent_evidence(agent["id"], state)
                emit_agent_complete(agent["id"], status="ok")
            except Exception as exc:
                emit_agent_complete(agent["id"], status="error", detail=str(exc)[:200])
                emit_warning(f"Agent {agent['name']} failed: {exc}", source=agent["id"])

        # Final results (rich + standardised schema) — only on success, with
        # the exact persisted directory (empty when persistence failed).
        status = result.get("status") or "ok"
        warnings = list(getattr(state, "warnings", []) or [])
        _emit_results(state, run_id=run_id, saved_dir=saved_dir,
                      status=status, warnings=warnings)
        _emit_schema_result(request, run_id, state)
        # One canonical verdict: the final result line for the TUI and artifacts.
        from protacxtend.run_verdict import compute_verdict, verdict_line
        verdict = compute_verdict(state)
        emit({"type": "verdict", "run_id": run_id, "line": verdict_line(verdict), **verdict})
        emit_run_complete("ok", run_id, {
            "agents_completed": len(AGENT_PIPELINE),
            "run_id": run_id,
            "saved_dir": saved_dir,
            "persisted": bool(saved_dir),
            "status": status,
            "verdict": verdict["verdict"],
            "scientific_result": verdict["scientific_result"],
            "verdict_line": verdict_line(verdict),
            "warnings": warnings[:10],
        })
    except Exception as exc:
        emit_run_complete("error", run_id, {"error": str(exc), "run_id": run_id})


def _emit_agent_evidence(agent_id: str, state: Any) -> None:
    """Emit per-agent evidence from a completed workflow state (no graph run)."""
    if state is None:
        return

    if agent_id == "target_resolver":
        target = getattr(state, "target_record", None)
        if target:
            # TargetRecord carries gene_symbol/target_name (not gene_name);
            # reading the wrong field rendered "Target: ?".
            gene = (getattr(target, "gene_symbol", "")
                    or getattr(target, "target_name", "")
                    or getattr(target, "gene_name", ""))
            emit_evidence("uniprot", {
                "gene": gene,
                "uniprot_id": getattr(target, "uniprot_id", ""),
                "organism": getattr(target, "organism", ""),
            }, summary=f"Target: {gene or '?'} ({getattr(target, 'uniprot_id', '?')})")

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
            # Ranking results carry `final_priority_score`; the legacy
            # `composite_score` is absent on that schema. Falling back to 0.0
            # previously made every ranked candidate render as 0.00 while the
            # persisted pareto_front.csv showed ~0.78 — two different fields.
            score = getattr(c, "final_priority_score", None)
            if score is None:
                score = getattr(c, "composite_score", None)
            if score is None:
                score = getattr(c, "score", None)
            emit_candidate(
                getattr(c, "candidate_id", ""),
                getattr(c, "full_protac_smiles", "")[:60],
                float(score) if score is not None else None,
                getattr(c, "tier", ""),
                score_label="final_priority_score",
            )


def _emit_results(state: Any, run_id: str = "", saved_dir: str = "",
                  status: str = "ok", warnings: list | None = None) -> None:
    """Emit final workflow results summary (with exact persisted path)."""
    if state is None:
        return

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
        "run_id": run_id,
        "saved_dir": saved_dir,
        "persisted": bool(saved_dir),
        "status": status,
        "warnings": list(warnings or [])[:10],
    })


def _emit_schema_result(request: str, run_id: str, state: Any) -> None:
    """Emit the shared ScientificResult envelope for a workflow run."""
    if state is None:
        return

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
        provenance=[Provenance(tool="run_protacpilot", source="protacxtend.agents.runtime")],
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
        linker_types = ["PEG", "alkyl", "piperazine", "triazole", "semi-rigid"]
        linkers = (toolbox.generate_rule_based_linkers(linker_types)
                   if hasattr(toolbox, "generate_rule_based_linkers") else [])
        payload = {"linkers_generated": len(linkers), "linker_types": linker_types}
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
        from protacxtend.tools.retrosynthesis import assess_retrosynthesis
        result = assess_retrosynthesis(smiles, use_aizynth=True, max_steps=3)
        routes = list(getattr(result, "route_files", []) or [])
        payload = {
            "smiles": smiles,
            "routes_found": getattr(result, "route_count", len(routes)),
            "routes": routes[:3],
            "status": getattr(result, "status", "unknown"),
            "rascore": getattr(result, "rascore", None),
            "engines_ran": getattr(result, "engines_ran", []),
            "note": getattr(result, "note", ""),
        }
        emit_tool_result("retrosynthesis",
                         result=_schema_tool("retrosynthesis", "synthesis", payload,
                                             kind="calculated",
                                             evidence=[f"{payload['routes_found']} retrosynthetic route(s) proposed for the target"],
                                             provenance_tool="protacxtend.tools.retrosynthesis"),
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


# ── LLM-backed conversation (Pi/Feynman-style answers) ─────────────────
#
# A single ConversationalAgent instance is reused for the lifetime of the
# bridge process so follow-up questions share context (target, E3, last run).
# `chat_reset` clears it; a provider switch is picked up on the next reset.

_CHAT_AGENT: Any = None


def _chat_agent() -> Any:
    global _CHAT_AGENT
    if _CHAT_AGENT is None:
        from protacxtend.agentic.chat_agent import ConversationalAgent
        from protacxtend.llm.providers import get_config
        _CHAT_AGENT = ConversationalAgent(get_config(), allow_handoff=False)
    return _CHAT_AGENT


def handle_therapeutics(target: str = "", disease: str = "", cell_line: str = "",
                         conversation_id: str = "default") -> None:
    """Run TargetTherapeuticsAssessment (typed, evidence-backed pre-design
    stage). Emits the full record: verdict, gates, per-dimension conclusions
    with source IDs / assay context / conflicts / missing data / and the
    experiment that would change the decision."""
    import os as _os
    from protacxtend.therapeutics.api import run_assessment
    spec = (target or "").strip()
    if not spec:
        emit({"type": "therapeutics_answer", "kind": "error",
              "answer": "therapeutics: no target given (e.g. '/therapeutics KRAS G12C')"})
        return
    offline = _os.environ.get("PROTACXTEND_PLANNER_OFFLINE", "") in ("1", "true", "yes")
    try:
        rec = run_assessment(spec, disease=disease, cell_line=cell_line, offline=offline)
    except Exception as exc:  # noqa: BLE001
        emit({"type": "therapeutics_answer", "kind": "error",
              "answer": f"assessment failed: {exc}", "target": spec})
        return
    emit({
        "type": "therapeutics_answer", "kind": "assessment", "target": spec,
        "verdict": rec.decision.verdict, "gates": rec.decision.gates,
        "rationale": rec.decision.rationale,
        "criteria_met": rec.decision.criteria_met,
        "criteria_missed": rec.decision.criteria_missed,
        "assessment": rec.model_dump(), "artifact": rec.artifact_path,
        "final": True,
    })


def handle_plan(request: str = "", conversation_id: str = "default", *, use_llm_planner: bool = False) -> None:
    """Goal-driven /plan through the durable planning contract.

    The bridge emits a run/request id immediately, streams typed stage status,
    persists the plan when ready, and still returns the established
    ``plan_answer`` payload for the TUI renderer. /plan never executes
    compound design and never presents a design result as the plan.
    """
    import os as _os
    from protacxtend.planning.contract import execute_plan_contract

    offline = _os.environ.get("PROTACXTEND_PLANNER_OFFLINE", "") in ("1", "true", "yes")
    payload = execute_plan_contract(
        request or "",
        conversation_id=conversation_id,
        offline=offline,
        emit_event=emit,
        use_llm_planner=use_llm_planner,
    )
    from protacxtend.tui_bridge.contract import annex as _annex, classify as _classify

    payload["contract"] = _classify(payload)
    payload["annex"] = _annex(payload)
    # scientific plan contract + persistence (semantics: /plan produces a plan)
    try:
        payload["plan_sections"] = _sem.plan_contract(payload)
        pl = _sem.persist_plan(payload)
        payload["plan_object_path"] = str(pl)
    except Exception:
        payload["plan_sections"] = None
    # record resolved entities into conversation context (spec §13)
    try:
        from protacxtend.request.controller import RequestController as _RC
        _u = _RC(offline=offline).understand(request or "", default_action="plan")
        _roles = _sem.resolve_roles(request or "", _u)
        _CONTEXT.update_from_understanding(conversation_id, _u, _roles)
    except Exception:
        pass
    emit(payload)
    emit({"type": "plan_complete", "status": "ok" if payload.get("status") != "failed" else "failed",
          "plan_id": payload.get("plan_id"), "run_id": payload.get("run_id"),
          "request_id": payload.get("request_id"), "conversation_id": conversation_id})


def _diagnosis_hypotheses_for_tui(diag: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dm = getattr(diag, "discriminating_measurement", None)
    default_test = getattr(dm, "experiment", "") if dm else ""
    for h in diag.hypotheses:
        raw = h.to_dict() if hasattr(h, "to_dict") else dict(h)
        hid = str(raw.get("hypothesis_id") or raw.get("id") or "").strip()
        label = str(raw.get("label") or raw.get("title") or raw.get("statement") or "").strip()
        statement = str(raw.get("statement") or label).strip()
        axis = str(raw.get("axis") or label or hid).strip()
        evidence_for = [str(x) for x in (raw.get("evidence_for") or []) if str(x).strip()]
        evidence_against = [str(x) for x in (raw.get("evidence_against") or []) if str(x).strip()]
        rationale = str(raw.get("rationale") or "; ".join(evidence_for[:2]) or label).strip()
        tests = [str(x) for x in (raw.get("discriminating_tests") or []) if str(x).strip()]
        if not tests and default_test:
            tests = [str(default_test)]
        if not (hid and label and axis and statement and rationale and tests):
            continue
        raw.update({
            "hypothesis_id": hid,
            "label": label,
            "statement": statement,
            "axis": axis,
            "rationale": rationale,
            "discriminating_tests": tests,
            "evidence_for": evidence_for,
            "evidence_against": evidence_against,
        })
        rows.append(raw)
    return rows


def handle_diagnose(command: str, request: str = "", conversation_id: str = "default") -> None:
    """Mechanistic diagnosis for /reason, /experiment, /optimize on a case
    with recorded observations (e.g. strong binding, absent cellular
    degradation). Empty hypotheses or missing scientific fields are explicit
    unsupported answers, never successful diagnoses."""
    from protacxtend.planning.causal import egfr_strong_binding_no_degradation_case
    from protacxtend.planning.diagnose import diagnose

    case = egfr_strong_binding_no_degradation_case()
    diag = diagnose(case)
    hypotheses = _diagnosis_hypotheses_for_tui(diag)
    supported = bool(diag.case and diag.observations and hypotheses and diag.recommended_action)
    base = {
        "type": "diagnosis_answer", "command": command, "conversation_id": conversation_id,
        "case": diag.case, "observations": diag.observations,
        "hypotheses": hypotheses, "recommended_action": diag.recommended_action,
        "gated": diag.gated, "final": True,
        "request_completed": True,
        "plan_generated": False,
        "scientific_answer_supported": supported,
        "status": "ok" if supported else "unsupported",
        "summary": {
            "note": ("Mechanistic hypotheses are inferred from the supplied observation pattern; "
                     "no hypothesis is reported as measured without a source record."),
            "n_hypotheses": len(hypotheses),
        },
    }
    if not supported:
        base["error"] = "diagnosis missing hypotheses, observations, or recommended action"

    dm = diag.discriminating_measurement
    tests = []
    if dm and dm.experiment:
        tests.append({"test": dm.experiment, "tool": dm.tool, "expected_artifact": dm.expected_artifact,
                      "controls": dm.controls, "outcomes": dm.outcomes})
    base["tests"] = tests

    # Row-level packaged evidence for the case target: answer the LITERAL
    # question ("which PROTACs work for X") with packaged rows when they
    # exist, otherwise state the evidence gap explicitly. Never present the
    # scenario diagnosis as if it answered the row-level question.
    from hashlib import sha1
    from pathlib import Path
    from protacxtend.tui_bridge.contract import annex as _annex, classify as _classify
    from protacxtend.tui_bridge._evidence_rows import row_audit_for_request

    direct, gap, source = row_audit_for_request(request)
    answer_supported = bool(supported and (direct or gap))
    run_id = "reason_" + sha1(f"{conversation_id}|{command}|{request}".encode()).hexdigest()[:12]
    out_dir = Path("outputs") / "workflows" / "reason"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"{run_id}_diagnosis.json"
    base.update({
        "run_id": run_id,
        "scientific_direct_answer": direct,
        "evidence_gap_conclusion": gap,
        "case_source": source,
        "scientific_answer_supported": answer_supported,
        "status": "ok" if answer_supported else "unsupported",
        "stage_timeline": [
            {"stage": "row_level_evidence", "status": "completed" if (direct or gap) else "missing",
             "detail": source or "no row audit source"},
            {"stage": "hypothesis_generation", "status": "completed" if hypotheses else "failed",
             "detail": f"{len(hypotheses)} hypotheses"},
            {"stage": "response_serialization", "status": "completed", "detail": "diagnosis payload serialized"},
        ],
        "artifact_paths": {"diagnosis_json": str(artifact.resolve())},
    })
    base["contract"] = _classify(base)
    base["annex"] = _annex(base)
    artifact.write_text(json.dumps(base, indent=2, sort_keys=True, default=str))

    if command == "experiment":
        base.update({"experiment": dm.experiment, "tool": dm.tool, "inputs": dm.inputs,
                     "expected_artifact": dm.expected_artifact, "controls": dm.controls,
                     "outcomes": dm.outcomes})
    emit(base)
    emit({"type": "diagnosis_complete", "status": "ok" if base.get("scientific_answer_supported") else "unsupported",
          "run_id": base.get("run_id"), "conversation_id": conversation_id})


def handle_investigate(task_id: str = "", request: str = "", conversation_id: str = "default") -> None:
    """Execute ONE evidence task of an existing plan (T0..T5).

    /investigate gathers and evaluates evidence only: it never generates
    candidates and never runs the design graph. If a required tool or data
    source is unavailable, it emits an open question + a revised-plan fragment
    instead of fabricating a result."""
    import os as _os
    from protacxtend.planning.goal_planner import build_plan
    from protacxtend.planning.goal_planner import _probe_tools

    offline = _os.environ.get("PROTACXTEND_PLANNER_OFFLINE", "") in ("1", "true", "yes")
    req = request or _os.environ.get("PROTACXTEND_PLAN_LAST_REQUEST", "")
    if not req:
        emit({"type": "investigate_answer", "kind": "error",
              "answer": "investigate: no plan request bound (run /plan first or pass --request)."})
        return
    plan = build_plan(req, conversation_id=conversation_id, offline=offline)
    if plan.run_status == "clarification_needed":
        emit({"type": "investigate_answer", "kind": "clarification_needed",
              "question": plan.clarification_question})
        return
    if task_id == "T1b_therapeutic_assessment":
        from protacxtend.therapeutics.api import run_assessment
        spec = (plan.target.get("symbol") if isinstance(plan.target, dict) else getattr(plan.target, "symbol", "")) or ""
        variant = ""
        if isinstance(plan.target, dict):
            variant = plan.target.get("variant") or ""
        elif hasattr(plan.target, "variant"):
            variant = plan.target.variant or ""
        rec = run_assessment((f"{spec} {variant}" if variant else spec).strip(), offline=offline)
        emit({"type": "investigate_answer", "kind": "assessment",
              "task_id": task_id, "plan_id": plan.plan_id,
              "answer": (f"TargetTherapeuticsAssessment for {spec}: verdict={rec.decision.verdict}; "
                         f"gates={rec.decision.gates}"),
              "verdict": rec.decision.verdict, "gates": rec.decision.gates,
              "assessment": rec.model_dump(), "artifact": rec.artifact_path,
              "executed_design": False, "final": True})
        return
    task = next((t for t in plan.tasks if t.id == task_id), None)
    if task is None:
        emit({"type": "investigate_answer", "kind": "error",
              "answer": f"unknown task '{task_id}'; plan tasks: "
                        f"{[t.id for t in plan.tasks]}"})
        return

    tools_ok = _probe_tools()
    missing = [tool for tool in task.tools if not tools_ok.get(tool)]
    if missing:
        emit({"type": "investigate_answer", "kind": "open_question",
              "task_id": task_id,
              "answer": (f"Task {task_id} cannot run: tool(s) unavailable -> {', '.join(missing)}. "
                         "This is a revised plan node: seek the data source or defer; no fabricated result."),
              "revised_plan": True, "final": True})
        return

    import json as _json, time
    from protacxtend.agentic.registry import execute_tool
    target_sym = (plan.target.get("symbol")
                  if isinstance(plan.target, dict) and plan.target
                  else (plan.target.symbol if plan.target and not isinstance(plan.target, dict) else ""))
    params_base = {"target": target_sym, "target_name": target_sym,
                   "gene_symbol": target_sym, "conversation_id": conversation_id}
    records = []
    for tool in task.tools:
        try:
            result = execute_tool(tool, params_base)
            records.append({"tool": tool, "status": result.status.value,
                            "summary": result.summary[:300],
                            "evidence_type": result.evidence_type.value,
                            "n_sources": len(result.sources)})
        except Exception as exc:  # noqa: BLE001
            records.append({"tool": tool, "status": "error", "summary": str(exc)[:200]})
            emit({"type": "investigate_answer", "kind": "open_question",
                  "task_id": task_id, "tool": tool,
                  "answer": f"{tool} failed; revised plan node (no fabricated result): {str(exc)[:160]}",
                  "revised_plan": True, "final": True})
            return
    out_dir = _os.path.join("outputs", "plans", plan.plan_id, "artifacts")
    _os.makedirs(out_dir, exist_ok=True)
    artifact = _os.path.join(out_dir, f"{task_id}.jsonl")
    with open(artifact, "w") as f:
        for rec in records:
            f.write(_json.dumps(rec, default=str) + "\n")
    emit({"type": "investigate_answer", "kind": "evidence",
          "task_id": task_id, "plan_id": plan.plan_id,
          "answer": f"Executed evidence task {task_id} ({task.title}); "
                    f"{len(records)} tool result(s) recorded.",
          "artifact": artifact, "records": records,
          "executed_design": False, "final": True})


def handle_research(command: str, request: str = "", conversation_id: str = "default") -> None:
    """Per-command mechanistic dispatch: every research command runs its own
    contract through :mod:`protacxtend.workflows.api` (shared evidence graph,
    goal-typed plans for /plan, DAG execution with replanning for /run)."""
    import os as _os
    from protacxtend.workflows.api import run_command

    text = (request or "").strip()
    offline = _os.environ.get("PROTACXTEND_PLANNER_OFFLINE", "") in ("1", "true", "yes")
    from protacxtend.tui_bridge.contract import annex as _annex, classify as _classify

    payload = run_command(command, text, offline=offline)
    payload.setdefault("resource_reason_summary", _resource_reason_summary_for(text, offline=offline))
    payload.update({"type": "research_answer", "command": command,
                    "conversation_id": conversation_id})
    # Normalize findings into renderable lines (the Node renderer must never
    # guess keys): scientific_findings + explicit evidence-gap conclusion.
    sf: list[str] = []
    if not payload.get("scientific_findings"):
        f = payload.get("findings")
        if isinstance(f, dict):
            if f.get("interpretation"):
                sf.append(str(f["interpretation"]))
            rb = f.get("known_binder_count")
            mpr = f.get("measured_precedent_rows")
            if rb is not None:
                sf.append(f"Known binder count: {rb} (census, not row-level activity).")
            if mpr is not None:
                sf.append(f"Measured precedent rows in packaged context set: {mpr}.")
        payload["scientific_findings"] = sf
    if not sf and not str(payload.get("evidence_gap_conclusion") or "").strip():
        payload["evidence_gap_conclusion"] = (
            f"Evidence-gap: {command} returned no substantive findings for {text!r} in the "
            "packaged set; live retrieval (Europe PMC/PubMed/ChEMBL) is the required next "
            "evidence step and was not available offline."
        )
    payload["contract"] = _classify(payload)
    payload["annex"] = _annex(payload)
    # semantic synthesis for /investigate: sections + structured result, not counts only
    if command == "investigate":
        try:
            depth, _clean = _sem.parse_depth(text)
            from protacxtend.request.controller import RequestController as _RC
            _u = _RC(offline=offline).understand(_clean, default_action="investigate")
            _merge_context("investigate", _clean, _u, conversation_id)
            _st = payload.get("state") or {}
            _sym = str((_st.get("target") or {}).get("symbol") or "")
            _sts = str((_st.get("target") or {}).get("status") or "")
            _resolved = _sym and _sts in ("verified", "resolved", "tentative")
            _ct = _CONTEXT.get(conversation_id)
            if (not _resolved) and _ct.target_symbol:
                payload.setdefault("state", {})["target"] = {
                    "symbol": _ct.target_symbol, "uniprot_id": _ct.target_uniprot,
                    "status": "context_inferred", "resolver_source": "conversation_context"}
            secs = _synth.investigate_sections(_clean, _u, payload, depth)
            payload["sections"] = secs
            payload["structured"] = _sem.make_structured(
                "investigate", "TARGET_ASSESSMENT",
                {"target": (payload.get("state") or {}).get("target", {}),
                        "e3": (_CONTEXT.get(conversation_id).e3 if _CONTEXT.get(conversation_id) else "")},
                findings=[{"text": st["text"], "tier": st["tier"], "source": st.get("source", "")}
                          for sec in secs for st in sec.get("statements", [])],
                evidence=[ev for sec in secs for ev in sec.get("evidence", [])],
                uncertainties=[], gaps=[_sem.render_sections(secs)[0]] if False else [],
                conclusion={}, artifacts=[str(payload.get("evidence_graph", ""))] if payload.get("evidence_graph") else [])
        except Exception:
            # semantics layer is advisory on top of the contract; never break the answer
            pass
    emit(payload)



def handle_reason(request: str = "", conversation_id: str = "default") -> None:
    """Intent-driven /reason (semantics): WHY_WORKS / WHY_FAILS / COMPARE / ..."""
    import os as _os
    from protacxtend.request.controller import RequestController

    text = (request or "").strip()
    offline = _os.environ.get("PROTACXTEND_PLANNER_OFFLINE", "") in ("1", "true", "yes")
    u = RequestController(offline=offline).understand(text, default_action="reason")
    roles = _sem.resolve_roles(text, u)
    _merge_context("reason", text, u, conversation_id)
    ctx = _CONTEXT.get(conversation_id)
    symbol = roles.get("target_symbol") or ctx.target_symbol
    e3 = roles.get("e3") or ctx.e3
    intent = _sem.classify_reasoning_intent(text) or "EVIDENCE_SYNTHESIS"
    sections = _synth.reason_sections(text, intent, symbol, e3)
    n_ev = sum(1 for sec in sections for ev in sec.get("evidence", []))
    if intent == "WHY_WORKS":
        conclusion = {
            "verdict": "plausible_causal_chain" if n_ev else "evidence_insufficient",
            "rationale": ("Causal chain supported by packaged measured evidence rows (see sections)."
                          if n_ev else "No packaged measured evidence for this pair; explanation is "
                                       "a hypothesis requiring retrieval/measurement."),
            "confidence": "moderate" if n_ev >= 5 else ("low" if n_ev else "none"),
        }
    elif intent == "WHY_FAILS":
        conclusion = {"verdict": "hypothesis_families_unranked",
                      "rationale": "Failure hypotheses listed as testable possibilities; no ranking without evidence.",
                      "confidence": "none"}
    else:
        conclusion = {"verdict": "evidence_synthesis",
                      "rationale": "Synthesis of packaged evidence + explicit gaps.",
                      "confidence": "low"}
    base = {
        "type": "diagnosis_answer", "command": "reason", "conversation_id": conversation_id,
        "kind": intent, "case": f"{symbol or '?'}" + (f" ({e3})" if e3 else ""),
        "intent": intent, "sections": sections,
        "structured": _sem.make_structured(
            "reason", intent, {"target": symbol, "e3": e3},
            findings=[{"text": st["text"], "tier": st["tier"], "source": st.get("source", "")}
                      for sec in sections for st in sec.get("statements", [])],
            evidence=[ev for sec in sections for ev in sec.get("evidence", [])],
            uncertainties=[], gaps=[], conclusion=conclusion, artifacts=[]),
        "conclusion": conclusion,
        "request": text, "final": True, "request_completed": True,
        "plan_generated": False,
        "scientific_answer_supported": bool(sections),
        "status": "ok" if sections else "unsupported",
    }
    emit(base)
    emit({"type": "diagnosis_complete", "status": "ok" if sections else "unsupported",
          "conversation_id": conversation_id})


def handle_run_plan(plan_id: str, conversation_id: str = "default") -> None:
    """/run <plan_id> — execute the evidence stages of a persisted plan."""
    plan = _sem.load_plan(plan_id)
    if not plan:
        emit({"type": "run_answer", "command": "run", "status": "blocked",
              "error": f"plan not found: {plan_id}", "final": True, "conversation_id": conversation_id})
        return
    stages = plan.get("stages") or []
    if not stages:
        try:
            stages = [x["stage"] for x in _sem.plan_contract(plan).get("workflow_stages", [])]
        except Exception:
            stages = []
    pid = plan.get("plan_id") or plan_id
    executed: list[dict] = []
    for st in stages:
        num = str(st).split(".")[0]
        if num in ("6", "7", "8", "9"):
            executed.append({"stage": st, "status": "deferred",
                             "note": "expensive/design stage — requires /design or explicit run"})
            continue
        executed.append({"stage": st, "status": "planned_evidence_stage",
                         "note": "evidence stage scheduled in /run (T0..T3-style)"})
    emit({"type": "run_answer", "command": "run", "plan_id": pid,
          "executed_stages": executed,
          "conclusion": "Plan persisted; evidence stages scheduled; expensive stages deferred "
                        "to /design (plan/run separation).",
          "final": True, "request_completed": True, "conversation_id": conversation_id})


def handle_context(conversation_id: str, action: str = "get", e3: str = "",
                   target: str = "") -> None:
    ctx = _CONTEXT.get(conversation_id)
    if action == "set_e3" and e3:
        upd = ctx.update_e3_only(e3)
        emit({"type": "context_answer", "action": "set_e3", "old_e3": upd["old_e3"],
              "new_e3": upd["new_e3"], "context": ctx.to_dict(), "conversation_id": conversation_id})
        return
    if action == "set_target" and target:
        ctx.note_target(target)
    emit({"type": "context_answer", "action": action, "context": ctx.to_dict(),
          "conversation_id": conversation_id})


def handle_chat(request: str, conversation_id: str = "default") -> None:
    """Answer a free-form scientific question with the configured LLM.

    Control-flow contract (fix 2026-09-24):
      1. a bare recognized target (e.g. ``BRD4``) is answered deterministically
         with a target card — the LLM is never asked to identify it;
      2. a resolved target/runnable workflow from the planning session is
         injected as session context and the LLM may explain/synthesize, but
         its free-form "clarification" must NOT override the resolved state —
         the bridge answers from the target card instead.

    Emits chat_start -> chat_event* -> chat_answer -> chat_complete.
    """
    text = (request or "").strip()
    if not text:
        emit({"type": "error", "message": "chat: empty request"})
        return

    try:
        from protacxtend.llm.providers import get_config
        cfg = get_config()
    except Exception as exc:  # pragma: no cover - defensive
        emit({"type": "chat_answer", "kind": "error", "provider": "", "model": "",
              "answer": f"Could not load LLM configuration: {exc}", "evidence": []})
        emit({"type": "chat_complete", "status": "error"})
        return

    if not cfg.provider:
        emit({"type": "chat_answer", "kind": "error", "provider": "", "model": "",
              "answer": ("No LLM provider is configured. Run `protacxtend setup` "
                         "(or `protacxtend llm --setup`) to point PROTACXtend at a local "
                         "Ollama model or a hosted API, then ask again."),
              "evidence": []})
        emit({"type": "chat_complete", "status": "error"})
        return

    emit({"type": "chat_start", "request": text,
          "provider": cfg.provider, "model": cfg.model})
    try:
        from protacxtend.agentic.chat_agent import ClarificationNeeded
        agent = _chat_agent()

        # ── control-flow fix: inject resolved session state and guard the loop ──
        import os as _os
        from protacxtend.planning.planner import get_session as _get_plan_session
        offline = _os.environ.get("PROTACXTEND_PLANNER_OFFLINE", "") in ("1", "true", "yes")
        session = _get_plan_session(conversation_id)
        resolved_session = bool(session and session.resolved_target)
        if resolved_session:
            agent.session_context = {
                **(agent.session_context or {}),
                "resolved_target": session.resolved_target,
                "workflow_runnable": True,
                "plan_pending_clarification": session.pending_clarification,
            }

        # 1) bare recognized target -> deterministic target card (never the LLM)
        if len(text.split()) == 1 and not text.startswith("/"):
            import re as _re
            if _re.fullmatch(r"[A-Za-z][A-Za-z0-9]{1,19}", text):
                from protacxtend.request.model import TargetMention
                from protacxtend.request.resolver import resolve_target
                r = resolve_target(TargetMention(raw=text, organism="Homo sapiens"), offline=offline)
                if r.status in ("verified", "tentative"):
                    from protacxtend.planning.target_card import target_card, target_card_markdown
                    card_md = target_card_markdown(target_card(r.symbol))
                    emit({"type": "chat_answer", "kind": "target_card",
                          "provider": cfg.provider, "model": cfg.model,
                          "answer": card_md,
                          "evidence": [f"resolver={r.resolver_source}", f"match={r.match_type}"],
                          "clarification_overridden": False})
                    emit({"type": "chat_complete", "status": "ok"})
                    return

        # 2) LLM answers freely, but its clarification must not override a
        #    resolved target + runnable workflow -> deterministic target card.
        def _clarification_fallback(question: str) -> None:
            rinfo = session.resolved_target if session else None
            if resolved_session and rinfo and rinfo.get("status") in ("resolved", "tentative"):
                from protacxtend.planning.target_card import target_card, target_card_markdown
                sym = rinfo.get("symbol") or ""
                card_md = target_card_markdown(target_card(sym)) if sym else (
                    "Target is resolved in this session; answering from resolved state "
                    "instead of the model's clarification request.")
                emit({"type": "chat_answer", "kind": "answer",
                      "provider": cfg.provider, "model": cfg.model,
                      "answer": card_md,
                      "evidence": ["session-resolved-target", "clarification-overridden"],
                      "clarification_overridden": True,
                      "model_question": question})
                emit({"type": "chat_complete", "status": "ok"})
                return
            emit({"type": "chat_answer", "kind": "clarification", "provider": cfg.provider,
                  "model": cfg.model, "answer": question, "evidence": []})
            emit({"type": "chat_complete", "status": "ok"})

        generic = {"", "please clarify.", "please clarify", "clarify.", "clarify",
                   "could you please clarify?", "could you clarify?"}
        try:
            run = agent.turn(text, ask=None)
        except ClarificationNeeded as need:
            question = (need.question or "").strip()
            if question.lower() in generic and not resolved_session:
                # A weak model sometimes emits a content-free clarification. Nudge
                # once for a real answer instead of dead-ending the user.
                try:
                    run = agent.turn(
                        "Answer my previous question directly using your best current knowledge. "
                        "Do not ask for clarification.", ask=None)
                except ClarificationNeeded as need2:
                    _clarification_fallback(need2.question or (need.question or ""))
                    return
            else:
                # Specific clarification: allowed ONLY when the session has no
                # resolved target/runnable workflow. Otherwise we answer from
                # the resolved state (the LLM never overrides it).
                _clarification_fallback(question)
                return

        for ev in run.events:
            emit({"type": "chat_event", "kind": ev.kind, "action": ev.action,
                  "tool": ev.tool, "status": ev.status, "summary": ev.summary})

        summary = run.summary or {}
        kind = str(summary.get("kind") or "answer")
        answer = (summary.get("answer") or summary.get("question")
                  or summary.get("error") or "")
        emit({"type": "chat_answer", "kind": kind, "provider": cfg.provider,
              "model": cfg.model, "answer": str(answer),
              "evidence": summary.get("evidence", []), "run_id": run.run_id,
              "objective": summary.get("objective"), "run_summary": summary.get("summary")})
        emit({"type": "chat_complete", "status": "ok"})
    except Exception as exc:
        emit({"type": "chat_answer", "kind": "error", "provider": cfg.provider,
              "model": cfg.model, "answer": f"LLM request failed: {exc}", "evidence": []})
        emit({"type": "chat_complete", "status": "error"})


def handle_chat_reset() -> None:
    """Forget the conversation context (after a provider switch or /clear)."""
    global _CHAT_AGENT
    _CHAT_AGENT = None
    emit({"type": "chat_reset", "status": "ok"})


def handle_report(run_id: str = "") -> None:
    """Load a *persisted* run and emit its report + artifact manifest.

    `/report run_xxxx` must read ``outputs/runs/<run_id>/`` rather than start a
    new workflow (the previous behaviour re-ran the whole graph).
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    runs_dir = root / "outputs" / "runs"
    rid = (run_id or "").strip()
    from protacxtend.run_quarantine import iter_valid_run_dirs, quarantine_reason

    if not rid:
        try:
            dirs = sorted(iter_valid_run_dirs(runs_dir),
                          key=lambda p: p.stat().st_mtime, reverse=True)
            rid = dirs[0].name if dirs else ""
        except Exception:
            rid = ""
    run_dir = runs_dir / rid if rid else None
    if run_dir is None or not run_dir.is_dir():
        emit({"type": "report", "status": "error", "run_id": rid,
              "error": f"run {rid!r} not found under {runs_dir}"})
        return
    # Classify the run: INVALID runs must never be served; COMPARISON_ONLY
    # replays are served but visibly labelled, and the response is checked
    # against the run record (run.json), not merely report.md text.
    from protacxtend.run_quarantine import serve_payload, citation_claim

    payload = serve_payload(run_dir)
    if payload["status"] == "invalid":
        emit({"type": "report", **payload, "report": payload["error"],
              "summary": {}, "artifacts": []})
        return
    comp_only = payload["status"] == "comparison_only"

    run_json_path = run_dir / "run.json"
    manifest_path = run_dir / "manifest.json"
    record_summary: dict = {}
    has_run_record = False
    source = run_json_path if run_json_path.exists() else (manifest_path if manifest_path.exists() else None)
    if source is not None:
        try:
            rec = json.loads(source.read_text(encoding="utf-8"))
            has_run_record = True
            record_summary = {
                "run_id": rec.get("run_id") or rec.get("compares_to"),
                "candidates_generated": rec.get("candidates_generated"),
                "candidates_valid": rec.get("candidates_valid"),
                "scientific_evidence": rec.get("scientific_evidence"),
                "role": rec.get("role"),
                "verdict": rec.get("verdict"),
            }
            if not record_summary.get("scientific_evidence"):
                record_summary["scientific_evidence"] = rec.get("scientific_evidence")
        except Exception:  # noqa: BLE001
            record_summary = {}
    report_path = run_dir / "report.md"
    summary_path = run_dir / "summary.json"
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    if comp_only:
        report = (
            "\n>>> COMPARISON-ONLY REPLAY <<<\n"
            "This run is citeable as a reference reconstruction only; it is NOT "
            "scientific evidence (run manifest: scientific_evidence=false).\n\n"
            + report
        )
    try:
        from protacxtend.reporting.landscape_scoring import build_scored_record, render_markdown
        landscape_entry = render_markdown(build_scored_record(run_dir))
        report = (report.rstrip() + "\n\n" + landscape_entry).lstrip()
    except Exception as exc:  # noqa: BLE001
        report = (report.rstrip() + "\n\n## M1-M12 Evidence-to-Score Rubric\n\n"
                  f"Landscape scoring unavailable: {exc}\n").lstrip()
    try:
        summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    except Exception:
        summary = {}
    if record_summary:
        summary["run_record"] = record_summary
        summary["citation_claim"] = citation_claim(run_dir)
    artifacts = [
        {"name": str(p.relative_to(run_dir)), "bytes": p.stat().st_size}
        for p in sorted(run_dir.rglob("*")) if p.is_file()
    ]
    emit({"type": "report", "status": "comparison_only" if comp_only else "ok",
          "run_id": rid, "dir": str(run_dir), "has_run_record": has_run_record,
          "report": report, "summary": summary, "artifacts": artifacts, "final": True})


def handle_explain(run_id: str = "") -> None:
    """Emit the typed researcher explanation for a persisted run.

    The answer is generated from the persisted run record by
    ``protacxtend.explain.builder`` — the display layer never invents facts.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    run_dir = root / "outputs" / "runs" / (run_id or "").strip()
    if not run_dir.is_dir():
        emit({"type": "explain", "status": "error", "run_id": run_id,
              "error": f"run {run_id!r} not found under {root / 'outputs' / 'runs'}"})
        return
    from protacxtend.explain.builder import build_explanation
    from protacxtend.explain.renderer import render

    ans = build_explanation(run_dir)
    rendered = render(ans)
    emit({
        "type": "explain",
        "status": ans.status,
        "render_status": ans.render_status,
        "scientific_outcome": ans.scientific_outcome,
        "run_id": ans.run_id,
        "mode": ans.mode,
        "answer": ans.model_dump(),
        "concise": rendered["concise"],
        "plain": rendered["plain"],
        "technical": rendered["technical"],
        "sections": ["Why", "Evidence", "What could be wrong", "Next experiment"],
        "final": True,
    })


def handle_command(cmd: str, args: dict[str, Any]) -> None:
    """Dispatch a command from the TUI."""
    if cmd == "run":
        _req = str(args.get("request", "") or "")
        if _req.startswith("plan_") and " " not in _req.strip():
            handle_run_plan(_req.strip(), args.get("conversation_id", "default") or "default")
        else:
            handle_run(_req)
    elif cmd == "plan":
        handle_plan(args.get("request", "") or "",
                    args.get("conversation_id", "default") or "default",
                    use_llm_planner=bool(args.get("use_llm_planner", False)))
    elif cmd == "therapeutics":
        handle_therapeutics(args.get("target", "") or args.get("spec", "") or "",
                            args.get("disease", "") or "", args.get("cell_line", "") or "",
                            args.get("conversation_id", "default") or "default")
    elif cmd == "investigate":
        # Intent routing: a plain /investigate <query> runs the deterministic
        # investigate RESEARCH contract (run_command("investigate") -> binder
        # census + measured-precedent evidence graph). The plan-task executor
        # (task_id given, e.g. T0) stays available for /investigate T<n>.
        tid = args.get("task", "") or args.get("task_id", "") or ""
        if tid:
            handle_investigate(tid,
                               args.get("request", "") or "",
                               args.get("conversation_id", "default") or "default")
        else:
            handle_research("investigate", args.get("request", "") or "",
                            args.get("conversation_id", "default") or "default")
    elif cmd == "reason":
        handle_reason(args.get("request", "") or args.get("query", "") or "",
                      args.get("conversation_id", "default") or "default")
    elif cmd in ("experiment", "optimize"):
        handle_diagnose(cmd, args.get("request", "") or "",
                        args.get("conversation_id", "default") or "default")
    elif cmd in ("investigate", "compare", "design", "structure",
                 "selectivity", "degradation", "admet", "synthesis",
                 "evidence", "run"):
        handle_research(cmd, args.get("request", "") or "",
                        args.get("conversation_id", "default") or "default")
    elif cmd == "explain":
        handle_explain(args.get("run", "") or args.get("run_id", "") or "")
    elif cmd in ("chat", "ask", "explain"):
        handle_chat(args.get("request", "") or args.get("query", ""),
                    args.get("conversation_id", "default") or "default")
    elif cmd == "context":
        handle_context(args.get("conversation_id", "default") or "default",
                       args.get("action", "get") or "get",
                       args.get("e3", "") or "", args.get("target", "") or "")
    elif cmd == "chat_reset":
        handle_chat_reset()
    elif cmd == "report":
        handle_report(args.get("run_id", ""))
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
    elif cmd == "capability":
        from protacxtend.runtime.executor import run_capability
        emit({"type": "capability_result",
              "result": run_capability(args.get("name", ""), args.get("params") or {})})
    elif cmd == "capabilities":
        from protacxtend.runtime.registry import build_registry, summary
        recs = build_registry()
        emit({"type": "capabilities", "summary": summary(recs),
              "capabilities": [r.to_row() for r in recs]})
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
