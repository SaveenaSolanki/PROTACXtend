"""Single-mode router for Ask/Design/Validate/Ternary/Report workflows."""

from __future__ import annotations

from typing import Any

from synglue_agent.agents.graph import run_syn_glue_workflow
from synglue_agent.backend.schemas import model_to_dict
from synglue_agent.memory.literature_rag import search_literature, summarize_retrieved_context
from synglue_agent.models.degradation_model import predict_dc50_dmax
from synglue_agent.toolkit.registry import search_databases, search_registry, search_skills, search_tools
from synglue_agent.toolkit.status import get_tool_status
from synglue_agent.tools.admet_predictors import predict_admet
from synglue_agent.tools.rdkit_chemistry import calculate_basic_protac_properties, validate_smiles
from synglue_agent.tools.report_generator import generate_candidate_table
from synglue_agent.tools.ternary_feasibility import assess_ternary_feasibility


VALID_MODES = {"ask", "design", "validate", "ternary", "report", "agentic"}


def _run_workflow_from_request(user_request: str):
    """Deterministic v0.1 path — unchanged behavior (agentic_mode=False)."""
    return run_syn_glue_workflow(user_request)


def _run_agentic_from_request(user_request: str, config=None):
    """Unified v0.3 agentic path via the single runtime entry point."""
    from synglue_agent.agents.runtime import run_protacpilot
    result = run_protacpilot(user_request, mode="agentic", config=config or {})
    return result


def _summarize_state(state: Any) -> dict[str, Any]:
    top = state.ranking_results[0] if state.ranking_results else None
    return {
        "target": state.parsed_objective.target_name,
        "e3_ligase": state.parsed_objective.e3_ligase or "CRBN/VHL branch",
        "binders_retrieved": len(state.retrieved_binders),
        "warheads_selected": len(state.selected_warheads),
        "e3_ligands_selected": len(state.selected_e3_ligands),
        "linkers_generated": len(state.generated_linkers),
        "valid_candidates": len(state.valid_candidates),
        "final_candidates": len(state.final_ranked_candidates),
        "top_candidate_id": getattr(top, "candidate_id", None),
        "top_score": getattr(top, "final_priority_score", None),
        "pipeline_status": state.pipeline_status,
        "warnings": state.warnings,
        "errors": state.errors,
    }


def _tool_label(tool_name: str, real_output_generated: bool) -> dict[str, Any]:
    status = get_tool_status(tool_name)
    return {
        "selected_tool_or_method": tool_name,
        "tool_status": {
            "registered": bool(status.get("registered")),
            "available": bool(status.get("available")),
            "executable": bool(status.get("executable")),
            "execution_mode": status.get("execution_mode"),
            "evidence": status.get("evidence"),
            "failure_reason": status.get("failure_reason"),
        },
        "real_output_generated": bool(real_output_generated),
    }


def _run_ask_mode(payload: dict[str, Any]) -> dict[str, Any]:
    query = (payload.get("query") or payload.get("request") or "").strip()
    if not query:
        raise ValueError("Ask mode requires 'query' or 'request'.")
    top_k = int(payload.get("top_k", 10))
    tools = search_tools(query, top_k=top_k)
    databases = search_databases(query, top_k=top_k)
    skills = search_skills(query, top_k=top_k)
    all_hits = search_registry(query, top_k=top_k)
    lit_pack = search_literature(query, top_k=min(5, top_k))
    lit_hits = lit_pack.get("results", []) if isinstance(lit_pack, dict) else []
    return {
        "mode": "ask",
        "input": {"query": query, "top_k": top_k},
        "results": {
            "tools": tools,
            "databases": databases,
            "skills": skills,
            "registry_hits": all_hits,
            "literature_hits": lit_pack,
            "literature_summary": summarize_retrieved_context(lit_hits),
        },
        "status_labels": [
            _tool_label("Toolkit registry", real_output_generated=bool(all_hits)),
            _tool_label("Literature RAG", real_output_generated=bool(lit_hits)),
        ],
    }


def _run_design_mode(payload: dict[str, Any]) -> dict[str, Any]:
    request = (payload.get("request") or payload.get("query") or "").strip()
    if not request:
        raise ValueError("Design mode requires 'request'.")
    state = _run_workflow_from_request(request)
    return {
        "mode": "design",
        "input": {"request": request},
        "summary": _summarize_state(state),
        "candidate_table": generate_candidate_table(state),
        "pipeline_status": state.pipeline_status,
        "report": state.report,
        "state": model_to_dict(state),
    }


def _run_validate_mode(payload: dict[str, Any]) -> dict[str, Any]:
    smiles = (payload.get("smiles") or payload.get("protac_smiles") or "").strip()
    if not smiles:
        raise ValueError("Validate mode requires 'smiles' or 'protac_smiles'.")
    validation = validate_smiles(smiles)
    descriptor_pack = calculate_basic_protac_properties(smiles) if validation.get("success") else {}
    admet = predict_admet(smiles, backend=str(payload.get("admet_backend", "auto")))
    deg_input = {"candidate_id": payload.get("candidate_id", "validate_input"), "full_protac_smiles": smiles}
    degradation = predict_dc50_dmax(deg_input, backend=str(payload.get("degradation_backend", "auto")))
    return {
        "mode": "validate",
        "input": {"smiles": smiles},
        "validation": validation,
        "chemistry": descriptor_pack,
        "admet": admet,
        "degradation": degradation,
        "status_labels": [
            _tool_label("RDKit", real_output_generated=bool(validation.get("success"))),
            _tool_label("ADME/Tox skill", real_output_generated=bool(admet.get("real_output_generated"))),
            _tool_label("DC50/Dmax prediction", real_output_generated=bool(degradation.get("real_output_generated"))),
        ],
    }


def _run_ternary_mode(payload: dict[str, Any]) -> dict[str, Any]:
    smiles = (payload.get("smiles") or payload.get("protac_smiles") or "").strip()
    if not smiles:
        raise ValueError("Ternary mode requires 'smiles' or 'protac_smiles'.")
    candidate = {
        "candidate_id": payload.get("candidate_id", "ternary_input"),
        "full_protac_smiles": smiles,
        "warhead_smiles": payload.get("warhead_smiles", ""),
        "e3_ligand_smiles": payload.get("e3_ligand_smiles", ""),
        "target_uniprot_id": payload.get("target_uniprot_id"),
        "e3_uniprot_id": payload.get("e3_uniprot_id"),
    }
    ternary_result = assess_ternary_feasibility(candidate, backend=str(payload.get("backend", "auto")))
    return {
        "mode": "ternary",
        "input": {"candidate_id": candidate["candidate_id"], "backend": payload.get("backend", "auto")},
        "ternary": ternary_result,
        "status_labels": [
            _tool_label(
                "Ternary complex modeling",
                real_output_generated=bool(isinstance(ternary_result, dict) and ternary_result.get("success")),
            ),
            _tool_label(
                "AutoDock Vina",
                real_output_generated=bool(isinstance(ternary_result, dict) and ternary_result.get("docking_score") is not None),
            ),
        ],
    }


def _run_report_mode(payload: dict[str, Any]) -> dict[str, Any]:
    request = (payload.get("request") or payload.get("query") or "").strip()
    if not request:
        raise ValueError("Report mode requires 'request'.")
    state = _run_workflow_from_request(request)
    return {
        "mode": "report",
        "input": {"request": request},
        "report": state.report,
        "candidate_table": generate_candidate_table(state),
        "pipeline_status": state.pipeline_status,
        "status_labels": [_tool_label("Report generation", real_output_generated=bool(state.report))],
    }


def run_mode(payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode", "")).strip().lower()
    if mode not in VALID_MODES:
        raise ValueError(f"Unknown mode '{mode}'. Valid modes: {sorted(VALID_MODES)}")
    if mode == "ask":
        return _run_ask_mode(payload)
    if mode == "agentic":
        return _run_agentic_from_request(
            payload.get("request") or payload.get("user_request") or "",
            config=payload.get("config"),
        )
    if mode == "design":
        return _run_design_mode(payload)
    if mode == "validate":
        return _run_validate_mode(payload)
    if mode == "ternary":
        return _run_ternary_mode(payload)
    return _run_report_mode(payload)
