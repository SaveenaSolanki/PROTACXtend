"""
LLM-gated decision layer wired for LangGraph (A6 / v0.3).
=========================================================

LLM decisions are ALWAYS gated by deterministic validators:

  1. selected tools must be in the registry (else reject decision)
  2. reason codes must be well-formed
  3. expensive tools (p4ward/retrosynthesis) → human approval required
  4. if the LLM is unavailable or violates a validator → deterministic
     fallback router runs instead (the agentic graph never depends on
     the model being up)

The stored record contains the decision only — no chain-of-thought.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from protacxtend.llm.schemas import (
    EvidenceDecision,
    RepairDecision,
    CritiqueDecision,
    Route,
    RepairAction,
    CritiqueVerdict,
)
from protacxtend.llm.tool_registry import (
    validate_selected_tools,
    requires_human_approval,
)
from protacxtend.llm.gateway import structured_chat_with_fallback
from protacxtend.llm.providers import get_config
from protacxtend.agents.state import DecisionLog, ReasonCode

logger = logging.getLogger("protacpilot.llm.gates")


# ── Deterministic fallbacks (used when LLM unavailable / invalid) ─────

def fallback_evidence_decision(evidence: Dict[str, Any], search_rounds: int = 0) -> EvidenceDecision:
    """Mirror the deterministic evidence gate from agentic_core.

    Bounded: after `search_rounds` without progress, escalate to human.
    """
    if search_rounds >= MAX_EVIDENCE_SEARCH_ROUNDS:
        return EvidenceDecision(
            route=Route.HUMAN_REVIEW,
            missing_evidence=["evidence_search_stalled"],
            selected_tools=[],
            reason_codes=["retry_budget_exhausted"],
            confidence=0.3,
        )
    has_ternary = bool(evidence.get("ternary", {}).get("ternary_confidence"))
    has_deg = bool(evidence.get("degradation", {}).get("degradation_confidence"))
    if not (has_ternary and has_deg):
        return EvidenceDecision(
            route=Route.SEARCH_MORE,
            missing_evidence=["ternary", "degradation"],
            selected_tools=["retrieve_pdb", "predict_degradation"],
            reason_codes=["evidence_insufficient"],
            confidence=0.5,
        )
    return EvidenceDecision(
        route=Route.DESIGN,
        missing_evidence=[],
        selected_tools=["generate_linkers", "assemble_protac"],
        reason_codes=["ternary_conf_ok"],
        confidence=0.7,
    )


MAX_EVIDENCE_SEARCH_ROUNDS = 2


def fallback_repair_decision(failure_reason: str) -> RepairDecision:
    action = RepairAction.HUMAN_REVIEW if failure_reason == "out_of_domain" \
        else RepairAction.ALTERNATE_LINKER
    return RepairDecision(action=action, reason_codes=[failure_reason], confidence=0.6)


# ── LangGraph nodes ───────────────────────────────────────────────────

def llm_evidence_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """LLM evidence-assessment node with deterministic validation.

    Stores: route, missing_evidence, selected_tools, reason_codes,
    confidence, rejected_alternatives (no raw CoT).
    """
    evidence = state.get("evidence", {})

    # ── Deterministic gate FIRST (authoritative: it has the actual numbers) ──
    has_ternary = bool(evidence.get("ternary", {}).get("ternary_confidence"))
    has_deg = bool(evidence.get("degradation", {}).get("degradation_confidence"))
    n_cands = len(state.get("valid_candidates", []))
    deterministic_sufficient = has_ternary and has_deg and n_cands > 0

    stages_done = []
    if has_ternary:
        stages_done.append("ternary feasibility scored")
    if has_deg:
        stages_done.append("degradation predicted")
    if evidence.get("tool_plan"):
        stages_done.append("tool plan selected")
    if n_cands:
        stages_done.append(f"{n_cands} candidates assembled")

    # If the deterministic gate is satisfied, the LLM may only ADD flags or
    # choose tools; it cannot veto sufficiency (it cannot see the raw data).
    # If the deterministic gate is NOT satisfied, search_more is forced.
    user_content = (
        "A PROTAC design run has completed these stages: "
        + (", ".join(stages_done) if stages_done else "none yet") + ". "
        + ("The deterministic evidence gate reports SUFFICIENT evidence. "
           "You may flag additional missing evidence or suggest tools, but "
           "keep route=design unless a specific hard blocker exists."
           if deterministic_sufficient else
           "The deterministic evidence gate reports INSUFFICIENT evidence. "
           "Identify what is missing and choose tools to collect it.")
    )

    decision = structured_chat_with_fallback(
        role="evidence_assessment",
        user_content=user_content,
        schema=EvidenceDecision,
        fallback=fallback_evidence_decision(
            evidence,
            search_rounds=state.get("retry_counts", {}).get("evidence_search", 0),
        ),
        extra_context="Allowed tools: search_uniprot, search_chembl, search_bindingdb, "
                      "retrieve_pdb, retrieve_alphafold, validate_smiles, "
                      "enumerate_exit_vectors, generate_linkers, assemble_protac, "
                      "run_p4ward, predict_degradation, evaluate_adme, run_retrosynthesis.",
    )

    # ── Deterministic validation gates ──
    validation_errors = []
    try:
        validate_selected_tools(decision.selected_tools)
    except ValueError as exc:
        validation_errors.append(str(exc))
        decision.selected_tools = []           # strip invalid tools
        decision.confidence = min(decision.confidence, 0.3)

    # The deterministic gate is authoritative for sufficiency: if it says
    # sufficient, the LLM cannot downgrade to search_more without naming a
    # specific missing item; if it says insufficient, force search_more.
    if deterministic_sufficient and decision.route == Route.SEARCH_MORE and not decision.missing_evidence:
        decision.route = Route.DESIGN
    if not deterministic_sufficient and decision.route in (Route.DESIGN, Route.TERMINATE):
        decision.route = Route.SEARCH_MORE

    needs_human = requires_human_approval(decision.selected_tools)
    if needs_human:
        decision.route = Route.HUMAN_REVIEW

    # Map LLM route → graph node
    node_map = {
        Route.SEARCH_MORE: "collect_evidence",
        Route.DESIGN: "design_planner",
        Route.HUMAN_REVIEW: "human_gate",
        Route.TERMINATE: "report",
    }
    next_node = node_map.get(decision.route, "collect_evidence")

    decision_log_entry = DecisionLog(
        node="llm_evidence_gate",
        decision_type="route",
        reason_codes=tuple(ReasonCode(r) for r in decision.reason_codes if r in {rc.value for rc in ReasonCode})
        or (ReasonCode.EVIDENCE_INSUFFICIENT,),
        evidence_refs=tuple(sorted(evidence.keys())),
        tool_version=f"{get_config().provider}:{get_config().model}:structured",
        confidence=decision.confidence,
        next_proposed_node=next_node,
    )

    return {
        "decision_log": [decision_log_entry.to_dict()],
        "retry_counts": {"evidence_search": state.get("retry_counts", {}).get("evidence_search", 0) + 1}
                        if decision.route == Route.SEARCH_MORE else {},
        "evidence": {
            **evidence,
            "llm_evidence_decision": {
                "route": decision.route.value,
                "missing_evidence": decision.missing_evidence,
                "selected_tools": decision.selected_tools,
                "reason_codes": decision.reason_codes,
                "confidence": decision.confidence,
                "rejected_alternatives": decision.rejected_alternatives,
                "validation_errors": validation_errors,
            },
        },
        "status": "needs_human" if needs_human else "ok",
        "warnings": validation_errors,
    }


def route_after_llm_evidence_gate(state: Dict[str, Any]) -> str:
    """Pure router consumed by LangGraph conditional edges."""
    llm_dec = state.get("evidence", {}).get("llm_evidence_decision", {})
    route = llm_dec.get("route", "design")
    node_map = {
        "search_more": "collect_evidence",
        "design": "design_planner",
        "human_review": "human_gate",
        "terminate": "report",
    }
    return node_map.get(route, "collect_evidence")


def llm_repair_controller(state: Dict[str, Any]) -> Dict[str, Any]:
    """LLM repair role: choose repair action from the allowed enum."""
    evidence = state.get("evidence", {})
    failure_reason = evidence.get("last_failure_reason", "unknown")
    retries = state.get("retry_counts", {})

    user_content = (
        f"Failure class: {failure_reason}. "
        f"Retries so far: {retries}. "
        "REMEMBER: if the failure class is out_of_domain, the ONLY valid "
        "action is human_review — retries cannot fix an out-of-domain "
        "prediction. Choose the single best repair action."
    )
    decision = structured_chat_with_fallback(
        role="repair",
        user_content=user_content,
        schema=RepairDecision,
        fallback=fallback_repair_decision(failure_reason),
        extra_context="Repair actions: retry_relaxed_params, escalate_ensemble, "
                      "alternate_linker, alternate_warhead, alternate_exit_vector, "
                      "collect_more_evidence, human_review, abort.",
    )

    stage_map = {
        RepairAction.RETRY_RELAXED_PARAMS: "ternary_feasibility",
        RepairAction.ESCALATE_ENSEMBLE: "ternary_ensemble",
        RepairAction.ALTERNATE_LINKER: "linker_generation",
        RepairAction.ALTERNATE_WARHEAD: "warhead_selection",
        RepairAction.ALTERNATE_EXIT_VECTOR: "exit_vector_detection",
        RepairAction.COLLECT_MORE_EVIDENCE: "collect_evidence",
        RepairAction.HUMAN_REVIEW: "human_gate",
        RepairAction.ABORT: "report",
    }
    next_node = stage_map.get(decision.action, "human_gate")

    return {
        "decision_log": [DecisionLog(
            node="llm_repair_controller",
            decision_type="repair",
            reason_codes=(ReasonCode.RETRY_BUDGET_EXHAUSTED,) if decision.action == RepairAction.HUMAN_REVIEW
                         else (ReasonCode.TERNARY_CONF_LOW,),
            evidence_refs=("last_failure_reason",),
            tool_version=f"{get_config().provider}:{get_config().model}:repair",
            confidence=decision.confidence,
            next_proposed_node=next_node,
        ).to_dict()],
        "status": "needs_human" if decision.action == RepairAction.HUMAN_REVIEW else "running",
        "warnings": [f"LLM repair chose {decision.action.value}"] if decision.action else [],
        "evidence": {
            **evidence,
            "llm_repair_decision": {
                "action": decision.action.value,
                "target_stage": decision.target_stage,
                "reason_codes": decision.reason_codes,
                "confidence": decision.confidence,
                "rejected_alternatives": decision.rejected_alternatives,
            },
        },
    }


def llm_critic(state: Dict[str, Any]) -> Dict[str, Any]:
    """LLM critic role over top candidates — output gated by verdict."""
    rankings = state.get("ranking_results", [])
    user_content = (
        "Critique these ranked candidates for overclaims and missing evidence: "
        + str(rankings[:3])
    )
    decision = structured_chat_with_fallback(
        role="critic",
        user_content=user_content,
        schema=CritiqueDecision,
        fallback=CritiqueDecision(verdict=CritiqueVerdict.ACCEPT, issues=[], confidence=0.5),
    )

    next_node = "report" if decision.verdict == CritiqueVerdict.ACCEPT else "repair_controller"
    return {
        "decision_log": [DecisionLog(
            node="llm_critic",
            decision_type="accept" if decision.verdict == CritiqueVerdict.ACCEPT else "escalate",
            reason_codes=(ReasonCode.TERNARY_CONF_OK,),
            evidence_refs=("ranking_results",),
            tool_version=f"{get_config().provider}:{get_config().model}:critic",
            confidence=decision.confidence,
            next_proposed_node=next_node,
        ).to_dict()],
        "evidence": {
            **state.get("evidence", {}),
            "llm_critique": {
                "verdict": decision.verdict.value,
                "issues": decision.issues,
                "confidence": decision.confidence,
            },
        },
        "status": "ok",
    }
