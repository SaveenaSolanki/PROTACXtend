"""Evidence-gated design bridge for workflows.api and the TUI.

This module is deliberately an adapter, not a second design implementation. It
runs the existing deterministic engine through :func:`run_protacpilot` and then
serializes the resulting WorkflowState into user-visible timeline, artifacts,
candidate evidence rows, and evidence gates.
"""
from __future__ import annotations

import csv
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from protacxtend.backend.schemas import model_to_dict
from protacxtend.evidence.graph import EvidenceGraph, make_claim
from protacxtend.identity_gate import candidate_passes_identity_gate

OUT_ROOT = Path("outputs/workflows/design")


def _run_dir(run_id: str) -> Path:
    preferred = OUT_ROOT / run_id
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write_probe"
        probe.write_text("ok")
        probe.unlink(missing_ok=True)
        return preferred
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "protacxtend_workflows" / "design" / run_id
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _load_resume(resume_from: str) -> dict[str, Any]:
    if not resume_from:
        return {}
    try:
        return json.loads(Path(resume_from).read_text())
    except Exception as exc:  # noqa: BLE001
        return {"resume_error": str(exc), "resumed_from": resume_from}


def _dump_model(value: Any) -> dict[str, Any]:
    out = model_to_dict(value)
    return out if isinstance(out, dict) else {}


def _by_candidate(rows: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        d = _dump_model(row)
        cid = d.get("candidate_id")
        if cid:
            out[cid] = d
    return out


def _attachment_map(state: Any) -> dict[str, dict[str, int | None]]:
    mapping: dict[str, dict[str, int | None]] = {"warhead": {}, "e3_ligand": {}, "linker": {}}
    for ev in getattr(state, "exit_vectors", []) or []:
        d = _dump_model(ev)
        role = str(d.get("molecule_role") or "").lower()
        name = d.get("molecule_name") or ""
        if role in mapping and name:
            mapping[role][name] = d.get("attachment_atom_index")
    return mapping


def _stage_timeline(state: Any, result: dict[str, Any]) -> list[dict[str, Any]]:
    ledger = list(getattr(state, "stage_ledger", []) or [])
    if ledger:
        timeline = []
        for item in ledger:
            d = dict(item)
            d.setdefault("executed", d.get("status") not in {"unevaluated", "skipped"})
            d.setdefault("stage", d.get("node_id") or d.get("stage") or "stage")
            timeline.append(d)
    else:
        timeline = []
        counts = [
            ("target_resolution", getattr(state, "target_record", None) is not None, "target resolved"),
            ("binder_retrieval", bool(getattr(state, "retrieved_binders", []) or []), f"{len(getattr(state, 'retrieved_binders', []) or [])} binders"),
            ("warhead_selection", bool(getattr(state, "selected_warheads", []) or []), f"{len(getattr(state, 'selected_warheads', []) or [])} warheads"),
            ("e3_selection", bool(getattr(state, "selected_e3_ligands", []) or []), f"{len(getattr(state, 'selected_e3_ligands', []) or [])} E3 ligands"),
            ("linker_generation", bool(getattr(state, "generated_linkers", []) or []), f"{len(getattr(state, 'generated_linkers', []) or [])} linkers"),
            ("construction", bool(getattr(state, "assembled_candidates", []) or []), f"{len(getattr(state, 'assembled_candidates', []) or [])} assembled"),
            ("validation", bool(getattr(state, "valid_candidates", []) or []), f"{len(getattr(state, 'valid_candidates', []) or [])} valid"),
            ("degradation_prediction", bool(getattr(state, "degradation_predictions", []) or []), f"{len(getattr(state, 'degradation_predictions', []) or [])} predictions"),
            ("admet_prediction", bool(getattr(state, "admet_predictions", []) or []), f"{len(getattr(state, 'admet_predictions', []) or [])} records"),
            ("ranking", bool(getattr(state, "ranking_results", []) or getattr(state, "final_ranked_candidates", []) or []), "ranked candidates"),
        ]
        for stage, ok, detail in counts:
            timeline.append({"stage": stage, "status": "executed" if ok else "not_available", "executed": bool(ok), "detail": detail})
    timeline.append({
        "stage": "ternary_coordinates",
        "status": "unevaluated",
        "executed": False,
        "detail": "No validated ternary-coordinate backend/DockQ benchmark is available for this run.",
    })
    timeline.append({
        "stage": "synthesis_route",
        "status": "unevaluated",
        "executed": False,
        "detail": "Retrosynthetic routes were not executed; synthetic feasibility remains a proxy/gate.",
    })
    return timeline


def _candidate_rows(state: Any) -> list[dict[str, Any]]:
    deg = _by_candidate(getattr(state, "degradation_predictions", []) or [])
    admet = _by_candidate(getattr(state, "admet_predictions", []) or [])
    ranks = _by_candidate(getattr(state, "ranking_results", []) or [])
    attach = _attachment_map(state)
    rows: list[dict[str, Any]] = []
    for cand in getattr(state, "valid_candidates", []) or []:
        c = _dump_model(cand)
        cid = c.get("candidate_id") or f"candidate_{len(rows)+1:04d}"
        wname = c.get("warhead_name") or ""
        ename = c.get("e3_ligand_name") or ""
        lname = c.get("linker_name") or ""
        identity_gate = (c.get("provenance") or {}).get("identity_assembly_gate") or {}
        identity_ok = bool(identity_gate.get("all_required_passed"))
        d = deg.get(cid, {}) if identity_ok else {}
        a = admet.get(cid, {}) if identity_ok else {}
        r = ranks.get(cid, {}) if identity_ok else {}
        row = {
            "candidate_id": cid,
            "canonical_smiles": c.get("full_protac_smiles") or c.get("canonical_smiles") or "",
            "components": {
                "target": c.get("target") or getattr(getattr(state, "target_record", None), "gene_symbol", ""),
                "e3_ligase": c.get("e3_ligase") or "",
                "warhead": wname,
                "e3_ligand": ename,
                "linker": lname,
            },
            "component_smiles": {
                "warhead": c.get("warhead_smiles") or "",
                "e3_ligand": c.get("e3_ligand_smiles") or "",
                "linker": c.get("linker_smiles") or "",
            },
            "attachment_atoms": {
                "warhead": attach.get("warhead", {}).get(wname),
                "e3_ligand": attach.get("e3_ligand", {}).get(ename),
            },
            "provenance": c.get("provenance") or {},
            "warning_flags": c.get("warning_flags") or [],
            "identity_assembly_gate": identity_gate or {
                "all_required_passed": False,
                "reasons": ["identity gate missing from candidate provenance"],
                "gates": {},
            },
            "degradation": {
                "evidence_kind": "predicted" if d else "not_assessable",
                "predicted_dc50_nM": d.get("predicted_dc50_nM") or d.get("predicted_dc50"),
                "predicted_dmax_percent": d.get("predicted_dmax_percent"),
                "model_confidence": d.get("model_confidence"),
                "model_version": d.get("model_version"),
            },
            "admet": {
                "evidence_kind": "calculated" if a else "not_assessable",
                "mw": a.get("mw"),
                "tpsa": a.get("tpsa"),
                "logp": a.get("logp"),
                "overall_admet_penalty": a.get("overall_admet_penalty"),
            },
            "ranking": {
                "rank": r.get("rank"),
                "tier": r.get("tier"),
                "final_priority_score": r.get("final_priority_score"),
                "confidence": r.get("confidence"),
            },
        }
        rows.append(row)
    return rows


def _write_artifacts(run_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    paths: dict[str, str] = {}
    timeline_path = run_dir / "stage_timeline.json"
    candidates_json = run_dir / "candidate_evidence.json"
    candidates_csv = run_dir / "candidate_evidence.csv"
    resume_path = run_dir / "resume_state.json"
    timeline_path.write_text(json.dumps(payload["stage_timeline"], indent=2, default=str))
    candidates_json.write_text(json.dumps(payload["candidate_evidence_table"], indent=2, default=str))
    resume_path.write_text(json.dumps(payload["resume_state"], indent=2, default=str))
    rows = payload["candidate_evidence_table"]
    with candidates_csv.open("w", newline="") as f:
        fieldnames = ["candidate_id", "canonical_smiles", "target", "e3_ligase", "warhead", "e3_ligand", "linker", "predicted_dc50_nM", "predicted_dmax_percent", "admet_penalty", "rank", "final_priority_score"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "candidate_id": row["candidate_id"],
                "canonical_smiles": row["canonical_smiles"],
                "target": row["components"].get("target"),
                "e3_ligase": row["components"].get("e3_ligase"),
                "warhead": row["components"].get("warhead"),
                "e3_ligand": row["components"].get("e3_ligand"),
                "linker": row["components"].get("linker"),
                "predicted_dc50_nM": row["degradation"].get("predicted_dc50_nM"),
                "predicted_dmax_percent": row["degradation"].get("predicted_dmax_percent"),
                "admet_penalty": row["admet"].get("overall_admet_penalty"),
                "rank": row["ranking"].get("rank"),
                "final_priority_score": row["ranking"].get("final_priority_score"),
            })
    paths.update({
        "stage_timeline": str(timeline_path),
        "candidate_evidence_json": str(candidates_json),
        "candidate_evidence_csv": str(candidates_csv),
        "resume_state": str(resume_path),
    })
    graph = EvidenceGraph()
    for row in rows:
        if row["degradation"].get("evidence_kind") == "predicted":
            graph.add(make_claim(
                command="design",
                dimension="degradation",
                kind="computed",
                statement=f"ML-predicted degradation for {row['candidate_id']}",
                value=row["degradation"].get("predicted_dc50_nM"),
                unit="nM",
                tool="deterministic_design_engine.degradation_prediction",
                version=str(row["degradation"].get("model_version") or ""),
                params={"candidate_id": row["candidate_id"]},
                artifact=str(candidates_json),
            ))
    evidence_path = run_dir / "evidence_graph.json"
    graph.to_json(str(evidence_path))
    paths["evidence_graph"] = str(evidence_path)
    return paths


def summarize_design_result(result: dict[str, Any], *, request: str, resume_from: str = "") -> dict[str, Any]:
    state = result.get("state")
    run_id = result.get("run_id") or f"design_{int(time.time())}"
    run_dir = _run_dir(run_id)
    rows = _candidate_rows(state)
    assembled_ids = {(_dump_model(c).get("candidate_id") or "") for c in (getattr(state, "assembled_candidates", []) or [])}
    valid_ids = {row["candidate_id"] for row in rows}
    identity_pass_ids = {row["candidate_id"] for row in rows if (row.get("identity_assembly_gate") or {}).get("all_required_passed")}
    deg_ids = {(_dump_model(d).get("candidate_id") or "") for d in (getattr(state, "degradation_predictions", []) or [])} & identity_pass_ids
    admet_ids = {(_dump_model(a).get("candidate_id") or "") for a in (getattr(state, "admet_predictions", []) or [])} & identity_pass_ids
    target = _dump_model(getattr(state, "target_record", None)) if state is not None else {}
    timeline = _stage_timeline(state, result) if state is not None else []
    resume_payload = _load_resume(resume_from)
    resume_state = {
        "run_id": run_id,
        "resumed_from": resume_from or "",
        "failed_stage": resume_payload.get("failed_stage", ""),
        "resume_command": f"/resume {run_dir / 'resume_state.json'}",
        "request": request,
    }
    payload = {
        "status": result.get("status") or "ok",
        "run_id": run_id,
        "engine": "run_protacpilot",
        "mode": result.get("mode") or "deterministic",
        "executed_design": True,
        "target": target,
        "stage_timeline": timeline,
        "executed_stages": [s["stage"] for s in timeline if s.get("executed")],
        "unevaluated_stages": [s["stage"] for s in timeline if s.get("status") == "unevaluated"],
        "assembly_counts": {
            "assembled": len(assembled_ids),
            "valid": len(valid_ids),
            "rejected_before_scoring": max(0, len(assembled_ids) - len(valid_ids)),
        },
        "downstream_scoring_candidate_ids": sorted((deg_ids | admet_ids) & valid_ids),
        "candidate_evidence_table": rows,
        "scientific_findings": [
            f"{len(valid_ids)} valid PROTAC candidate(s) reached degradation/ADMET scoring.",
            f"{max(0, len(assembled_ids) - len(valid_ids))} assembled candidate(s) were rejected before downstream scoring.",
            "Degradation and ADMET values are computational predictions/calculations, not observed measurements.",
            "Ternary coordinates and synthesis routes remain unevaluated evidence gates.",
        ],
        "evidence_gates": {
            "identity_assembly": {
                "status": "passed" if identity_pass_ids else "failed",
                "criterion": "Only candidates passing source-component identity and atom-mapped assembly gates may enter prediction, ranking, or nomination.",
                "passed_candidates": len(identity_pass_ids),
                "candidate_denominator": len(valid_ids),
            },
            "non_protac_rejection": {
                "status": "passed" if deg_ids <= identity_pass_ids and admet_ids <= identity_pass_ids else "failed",
                "criterion": "Only identity-gated valid PROTAC candidates may enter degradation or ADMET scoring.",
            },
            "degradation": {
                "status": "predicted" if deg_ids else "not_assessable",
                "limitation": "ML prediction only; cannot be observed without published/wet-lab assay source.",
            },
            "ternary_coordinates": {
                "status": "unevaluated",
                "limitation": "No validated coordinate backend/DockQ benchmark available in this run.",
            },
            "synthesis_route": {
                "status": "unevaluated",
                "limitation": "No retrosynthetic route execution; no route claim is nominated.",
            },
            "nomination": {
                "status": "gated",
                "blocked": not bool(identity_pass_ids),
                "limitation": "Candidates may be prioritized for review only after identity/assembly gates pass; no validated degrader nomination is allowed from predictions alone.",
            },
        },
        "resume_state": resume_state,
        "intermediate_files": {},
        "artifacts": {
            "engine_run_record": result.get("run_record") or {},
            "engine_trace": result.get("trace") or {},
            **(result.get("artifacts") or {}),
        },
    }
    paths = _write_artifacts(run_dir, payload)
    payload["intermediate_files"] = paths
    payload["evidence_graph"] = paths["evidence_graph"]
    from protacxtend.runtime import modes
    if modes.is_scientific():
        modes.assert_scientific_payload_clean("workflows.designer.run_design", payload)
    return payload


def run_design(text: str, *, offline: bool = True, run_id: str = "", resume_from: str = "") -> dict[str, Any]:
    """Run existing deterministic design engine and return TUI/API summary."""
    from protacxtend.agents.runtime import run_protacpilot

    resume_payload = _load_resume(resume_from)
    request = (resume_payload.get("request") if resume_payload else "") or text
    request = request.replace("/run", "", 1).strip() or text.strip()
    rid = run_id or resume_payload.get("run_id") or f"design_{int(time.time())}"
    result = run_protacpilot(
        request,
        mode="deterministic",
        config={"run_id": rid, "record_run": True, "capability": "DESIGN", "resume_from": resume_from},
    )
    return summarize_design_result(result, request=request, resume_from=resume_from)
