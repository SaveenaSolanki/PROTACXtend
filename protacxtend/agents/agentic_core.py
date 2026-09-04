"""
Agentic Core for ProtacPilot (v0.2)
=====================================

The deterministic agentic layer. No LLM. Conditional routing driven by evidence
state, not by a hardcoded ``zip()``.

This module implements Steps 1-6 of the ProtacPilot agentic build sequence:

  Step 1 — LangGraph as orchestration layer (StateGraph + conditional edges)
  Step 2 — TypedDict state with append-only decision_log (reducer=add)
  Step 3 — Uniform NodeResult / DecisionLog with controlled-vocab reason_codes
  Step 4 — Router functions (pure state → next_node_name)
  Step 5 — FailureClass dispatch table replacing static retry
  Step 6 — Three gate nodes: EvidenceSufficiencyGate, RepairController, HumanApprovalGate

The LLM layer (Step 7) is intentionally deferred to a separate module.

Key invariant:
  A node never mutates state in place. It returns a partial update dict.
  LangGraph merges it via the reducers declared in AgenticWorkflowState.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Literal, Optional, TypedDict, Annotated
from operator import add

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# STEP 2 — TypedDict state with append-only decision_log
# ═══════════════════════════════════════════════════════════════

class AgenticWorkflowState(TypedDict, total=False):
    """Append-only state for the agentic workflow.

    LangGraph merges partial updates using the declared reducers.
    ``decision_log`` uses ``operator.add`` so each node can only append,
    never overwrite another node's decisions.
    """

    # ── Input ──
    user_request: str                                  # natural-language request
    parsed_objective: Dict[str, Any]                   # structured spec

    # ── Plan ──
    design_plan: Dict[str, Any]                        # tools, gates, retry policy

    # ── Target ──
    target_record: Dict[str, Any]                      # UniProt/AlphaFold
    retrieved_binders: List[Dict[str, Any]]            # ChEMBL/PubChem/BindingDB

    # ── Components ──
    selected_warheads: List[Dict[str, Any]]
    selected_e3_ligands: List[Dict[str, Any]]
    exit_vectors: List[Dict[str, Any]]
    generated_linkers: List[Dict[str, Any]]

    # ── Candidates ──
    assembled_candidates: List[Dict[str, Any]]
    valid_candidates: List[Dict[str, Any]]

    # ── Evidence (per-candidate, keyed by candidate_id) ──
    evidence: Dict[str, Dict[str, Any]]                # candidate_id → evidence map

    # ── Predictions (parallel outputs, per candidate) ──
    degradation_predictions: List[Dict[str, Any]]
    admet_predictions: List[Dict[str, Any]]
    novelty_results: List[Dict[str, Any]]
    applicability_domain: List[Dict[str, Any]]
    ternary_feasibility: Dict[str, Dict[str, Any]]     # candidate_id → ternary result

    # ── Ranking ──
    ranking_results: List[Dict[str, Any]]
    reflection_reviews: List[Dict[str, Any]]
    diversity_clusters: List[Dict[str, Any]]
    final_ranked_candidates: List[Dict[str, Any]]

    # ── Output ──
    report: str
    pipeline_status: str                               # "running" | "paused_for_human" | "done" | "fatal"
    warnings: Annotated[List[str], add]                # append-only
    errors: Annotated[List[str], add]                   # append-only

    # ── Agent control ──
    decision_log: Annotated[List[Dict[str, Any]], add]  # append-only: the audit trail
    retry_counts: Dict[str, int]                        # per-node repair attempt count
    status: str                                         # "running" | "needs_evidence" | "needs_repair" | "needs_human" | "done"


# ═══════════════════════════════════════════════════════════════
# STEP 3 — Standardized node return: DecisionLog
# ═══════════════════════════════════════════════════════════════

# ── Controlled vocabulary for reason_codes ──

REASON_CODES = [
    # Internal infrastructure (node crash, wrapped by _wrap_legacy)
    "HARD_ERROR",
    # Evidence sufficiency
    "INSUFFICIENT_TARGET_EVIDENCE",
    "INSUFFICIENT_WARHEAD_EVIDENCE",
    "INSUFFICIENT_E3_CONTEXT",
    "INSUFFICIENT_STRUCTURE_DATA",
    "INSUFFICIENT_BINDER_DATA",
    # Chemistry validity
    "INVALID_SMILES",
    "INVALID_ATTACHMENT_ATOM",
    "STERIC_CLASH",
    "LINKER_STRAIN_HIGH",
    "STEREO_MISMATCH",
    "UNDEFINED_STEREO",
    # Ternary complex
    "TERNARY_POSE_POOR",
    "TERNARY_COOPERATIVITY_LOW",
    "NO_LYSINE_IN_RANGE",
    "P4WARD_TIMEOUT",
    "P4WARD_NO_POSES",
    # Degradation prediction
    "LOW_DEGRADATION_CONFIDENCE",
    "OUT_OF_DOMAIN",
    "HEURISTIC_MODEL_ONLY",
    # ADMET
    "ADMET_PENALTY_HIGH",
    "LOGP_TOO_HIGH",
    "TPSA_TOO_HIGH",
    "MW_TOO_HIGH",
    "ROT_BONDS_TOO_MANY",
    # Novelty
    "NEAR_DUPLICATE_KNOWN",
    "PATENT_HIT",
    # Synthesis
    "SYNTHESIS_INFEASIBLE",
    "NO_PURCHASABLE_BUILDING_BLOCKS",
    "UNSTABLE_FUNCTIONAL_GROUP",
    # Retry / repair
    "RETRY_RELAXED_PARAMS",
    "RETRY_ALTERNATE_SOURCE",
    "RETRY_ALTERNATE_LINKER",
    "RETRY_ALTERNATE_EXIT_VECTOR",
    "MAX_REPAIRS_EXHAUSTED",
    # Routing
    "PROCEED",
    "SKIP_STRUCTURE_AWARE",
    "SKIP_RETROSYNTHESIS",
    "ENABLED_BY_USER_REQUEST",
    "DISABLED_BY_EVIDENCE",
    # Human escalation
    "ESCALATE_OUT_OF_DOMAIN",
    "ESCALATE_LOW_CONFIDENCE",
    "ESCALATE_PRE_SYNTHESIS",
    "ESCALATE_CONFLICTING_EVIDENCE",
    # Accept
    "ACCEPT_CANDIDATE",
    "ACCEPT_WITH_CAVEATS",
    # Fatal
    "FATAL_NO_TARGET",
    "FATAL_NO_WARHEADS",
    "FATAL_NO_CANDIDATES",
]


def _validate_reason_code(code: str) -> str:
    """Enforce controlled vocabulary. Unknown codes raise — catches typos early."""
    if code not in REASON_CODES:
        raise ValueError(
            f"Unknown reason_code '{code}'. Must be one of "
            f"REASON_CODES (controlled vocabulary). "
            f"Add it there if genuinely new."
        )
    return code


@dataclass(frozen=True)
class DecisionLog:
    """Structured, immutable decision record. No free-text 'thought' strings."""

    node: str                                          # node name that made the decision
    decision_type: str                                  # "accept" | "retry" | "escalate" | "route" | "reject" | "repair"
    reason_codes: List[str]                            # controlled vocab (validated)
    evidence_refs: List[str]                           # URLs, file paths, run IDs
    tool_version: str                                  # e.g. "P4ward:1.2", "ChEMBL:2026_07"
    confidence: float                                  # 0-1
    next_proposed_node: str                            # where the router should go next
    elapsed_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        for code in self.reason_codes:
            _validate_reason_code(code)
        return {
            "node": self.node,
            "decision_type": self.decision_type,
            "reason_codes": self.reason_codes,
            "evidence_refs": self.evidence_refs,
            "tool_version": self.tool_version,
            "confidence": self.confidence,
            "next_proposed_node": self.next_proposed_node,
            "elapsed_s": self.elapsed_s,
        }


# ── Node return shape ──

@dataclass(frozen=True)
class NodeResult:
    """Uniform node return. Never mutates state in place — returns partial updates."""

    state_updates: Dict[str, Any]                      # partial state to merge
    decision: DecisionLog                             # audit trail
    status: Literal["ok", "skip", "needs_retry", "needs_repair", "needs_human", "fatal"] = "ok"


# ═══════════════════════════════════════════════════════════════
# STEP 5 — FailureClass dispatch table
# ═══════════════════════════════════════════════════════════════

class FailureClass(Enum):
    """Failure classes. Every tool wrapper returns one on failure instead of None."""
    NO_VALID_CONFORMER    = auto()    # conformer embedding failed → retry relaxed
    LOW_CONFIDENCE        = auto()    # prediction below threshold → escalate ensemble
    OUT_OF_DOMAIN         = auto()    # outside applicability domain → flag + continue
    TOOL_TIMEOUT          = auto()    # API/Docker timeout → retry once
    MISSING_INPUT         = auto()    # required input absent → human gate
    HARD_ERROR            = auto()    # unrecoverable → abort candidate
    INVALID_CHEMISTRY     = auto()    # invalid SMILES/attachment → recompute exit vectors
    LINKER_GEOMETRY_FAIL  = auto()    # ternary pose rejected → regenerate linker
    NO_BINDERS_FOUND      = auto()    # ChEMBL returns nothing → try BindingDB
    STEREO_UNDEFINED      = auto()    # undefined stereo → enumerate stereoisomers


# What each failure triggers — pure data, not logic
FAILURE_RESPONSES: Dict[FailureClass, Dict[str, Any]] = {
    FailureClass.NO_VALID_CONFORMER: {
        "action": "retry_relaxed_params",
        "max_retries": 3,
        "next_node": "repair_controller",
        "reason_code": "RETRY_RELAXED_PARAMS",
    },
    FailureClass.LOW_CONFIDENCE: {
        "action": "escalate_ensemble",
        "max_retries": 1,
        "next_node": "ternary_ensemble",
        "reason_code": "TERNARY_COOPERATIVITY_LOW",
    },
    FailureClass.OUT_OF_DOMAIN: {
        "action": "flag_and_continue",
        "max_retries": 0,
        "next_node": "human_gate",
        "reason_code": "ESCALATE_OUT_OF_DOMAIN",
    },
    FailureClass.TOOL_TIMEOUT: {
        "action": "retry_once",
        "max_retries": 1,
        "next_node": None,  # retry same node
        "reason_code": "P4WARD_TIMEOUT",
    },
    FailureClass.MISSING_INPUT: {
        "action": "human_gate",
        "max_retries": 0,
        "next_node": "human_gate",
        "reason_code": "ESCALATE_CONFLICTING_EVIDENCE",
    },
    FailureClass.HARD_ERROR: {
        "action": "abort_candidate",
        "max_retries": 0,
        "next_node": "report",
        "reason_code": "FATAL_NO_CANDIDATES",
    },
    FailureClass.INVALID_CHEMISTRY: {
        "action": "recompute_exit_vectors",
        "max_retries": 2,
        "next_node": "exit_vector_detection",
        "reason_code": "INVALID_ATTACHMENT_ATOM",
    },
    FailureClass.LINKER_GEOMETRY_FAIL: {
        "action": "regenerate_linker",
        "max_retries": 3,
        "next_node": "linker_generation",
        "reason_code": "RETRY_ALTERNATE_LINKER",
    },
    FailureClass.NO_BINDERS_FOUND: {
        "action": "try_alternate_source",
        "max_retries": 2,
        "next_node": "binder_retrieval",
        "reason_code": "RETRY_ALTERNATE_SOURCE",
    },
    FailureClass.STEREO_UNDEFINED: {
        "action": "enumerate_stereoisomers",
        "max_retries": 1,
        "next_node": "stereo_enumeration",
        "reason_code": "UNDEFINED_STEREO",
    },
}


def classify_failure(
    tool_output: Any,
    expected_type: type = type(None),
    confidence: float = 1.0,
    error_msg: str = "",
) -> FailureClass:
    """Map a tool's output/error into a FailureClass.

    This is the classification function the router reads.
    """
    if error_msg:
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return FailureClass.TOOL_TIMEOUT
        if "conformer" in error_msg.lower() or "embed" in error_msg.lower():
            return FailureClass.NO_VALID_CONFORMER
        if "invalid" in error_msg.lower() and "smiles" in error_msg.lower():
            return FailureClass.INVALID_CHEMISTRY
        return FailureClass.HARD_ERROR

    if tool_output is None:
        return FailureClass.MISSING_INPUT

    if isinstance(tool_output, list) and len(tool_output) == 0:
        return FailureClass.NO_BINDERS_FOUND

    if confidence < 0.45:
        return FailureClass.LOW_CONFIDENCE

    return FailureClass.HARD_ERROR  # default conservative


def get_failure_response(fc: FailureClass) -> Dict[str, Any]:
    """Look up the recovery action for a failure class."""
    return FAILURE_RESPONSES.get(fc, FAILURE_RESPONSES[FailureClass.HARD_ERROR])


# ═══════════════════════════════════════════════════════════════
# STEP 6a — Gate: EvidenceSufficiencyGate
# ═══════════════════════════════════════════════════════════════

def evidence_sufficiency_gate(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Check whether enough evidence exists to report a candidate score.

    Returns partial state update + decision log entry.
    """
    evidence = state.get("evidence", {})
    candidates = state.get("valid_candidates", [])
    reasons: List[str] = []
    next_node = "ranking"
    status = "ok"

    # Minimum evidence requirements for reporting a score.
    # Accept both the legacy stub key (ternary_confidence) and the real node
    # key (ternary_plausibility_score in state.ternary_feasibility).
    has_ternary = bool(state.get("ternary_feasibility")) or any(
        isinstance(ev, dict)
        and (ev.get("ternary_confidence") is not None or ev.get("ternary_plausibility_score") is not None)
        for ev in evidence.values()
    )
    has_degradation = bool(state.get("degradation_predictions"))
    has_admet = bool(state.get("admet_predictions"))
    has_novelty = bool(state.get("novelty_results"))

    if not candidates:
        reasons.append("FATAL_NO_CANDIDATES")
        next_node = "report"
        status = "fatal"
    elif not has_ternary:
        reasons.append("INSUFFICIENT_STRUCTURE_DATA")
        next_node = "ternary_feasibility"
        status = "needs_repair"
    elif not has_degradation:
        reasons.append("INSUFFICIENT_WARHEAD_EVIDENCE")
        next_node = "degradation_prediction"
        status = "needs_repair"
    elif not has_admet:
        reasons.append("INSUFFICIENT_E3_CONTEXT")
        next_node = "admet_prediction"
        status = "needs_repair"
    else:
        reasons.append("PROCEED")
        next_node = "ranking"
        status = "ok"

    decision = DecisionLog(
        node="EvidenceSufficiencyGate",
        decision_type="route" if status == "ok" else "repair",
        reason_codes=reasons,
        evidence_refs=[],
        tool_version="ProtacPilot:v0.2",
        confidence=0.9 if status == "ok" else 0.4,
        next_proposed_node=next_node,
        elapsed_s=0.001,
    )

    return {
        "decision_log": [decision.to_dict()],
        "status": status,
        "warnings": [] if status == "ok" else [f"EvidenceSufficiencyGate: {', '.join(reasons)}"],
    }


# ═══════════════════════════════════════════════════════════════
# STEP 6b — Gate: RepairController
# ═══════════════════════════════════════════════════════════════

# Thresholds (tunable, not hardcoded in conditionals)
TERNARY_CONFIDENCE_THRESHOLD = 0.45
DEGRADATION_CONFIDENCE_THRESHOLD = 0.40
ADMET_PENALTY_THRESHOLD = 0.65  # gate only egregious ADMET risk (composite:
                                  # 0.45*hERG + 0.30*DILI + 0.25*AMES from ADMET-AI)
MAX_REPAIR_ATTEMPTS = 3

def repair_controller(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Take a failed candidate, apply the recovery action, re-enter the relevant node.

    Inspects ACTUAL evidence state (not decision log reason codes) to determine
    what failed. This is because LangGraph routing functions are pure — they
    can only return a node name, they can't record what they decided.
    The RepairController reads what the router saw by inspecting evidence directly.

    This is the owned repair loop. Bounded by MAX_REPAIR_ATTEMPTS — no unbounded loops.
    """
    retry_counts = state.get("retry_counts", {})
    evidence = state.get("evidence", {})
    ternary_results = state.get("ternary_feasibility", {})
    deg_preds = state.get("degradation_predictions", [])
    admet_preds = state.get("admet_predictions", [])

    # ── Determine what failed by inspecting actual evidence ──
    # Priority: ternary → degradation → ADMET

    min_ternary = (
        min(tr.get("ternary_plausibility_score", 0.0) for tr in ternary_results.values())
        if ternary_results else 0.0
    )
    min_deg_conf = (
        min(p.get("model_confidence", 0.0) for p in deg_preds)
        if deg_preds else 0.0
    )
    max_admet_penalty = (
        max(p.get("overall_admet_penalty", 0.0) for p in admet_preds)
        if admet_preds else 0.0
    )

    repair_route: Optional[str] = None
    retry_key = ""

    if min_ternary < TERNARY_CONFIDENCE_THRESHOLD and ternary_results:
        # Ternary pose is poor — repair by regenerating linker
        repair_route = "linker_generation"
        retry_key = "ternary"
    elif min_deg_conf < DEGRADATION_CONFIDENCE_THRESHOLD and deg_preds:
        # Degradation prediction low confidence — not repairable, escalate
        decision = DecisionLog(
            node="RepairController",
            decision_type="escalate",
            reason_codes=["LOW_DEGRADATION_CONFIDENCE", "ESCALATE_LOW_CONFIDENCE"],
            evidence_refs=[],
            tool_version="ProtacPilot:v0.2",
            confidence=0.3,
            next_proposed_node="human_gate",
            elapsed_s=0.001,
        )
        return {
            "decision_log": [decision.to_dict()],
            "status": "needs_human",
            "warnings": ["RepairController: low degradation confidence — escalating"],
            "retry_counts": {**retry_counts, retry_key: retry_counts.get(retry_key, 0)},
        }
    elif max_admet_penalty > ADMET_PENALTY_THRESHOLD and admet_preds:
        # ADMET penalty high — repair by regenerating linker (shorter/polar)
        repair_route = "linker_generation"
        retry_key = "admet"
    else:
        # No recognizable failure — shouldn't be in repair. Default to report.
        decision = DecisionLog(
            node="RepairController",
            decision_type="accept",
            reason_codes=["PROCEED"],
            evidence_refs=[],
            tool_version="ProtacPilot:v0.2",
            confidence=0.5,
            next_proposed_node="evidence_sufficiency_gate",
            elapsed_s=0.001,
        )
        return {
            "decision_log": [decision.to_dict()],
            "status": "running",
            "warnings": ["RepairController: no failure detected — returning to main pipeline"],
            "retry_counts": retry_counts,
        }

    current_retries = retry_counts.get(retry_key, 0)

    if current_retries >= MAX_REPAIR_ATTEMPTS:
        # Exhausted retries → escalate
        decision = DecisionLog(
            node="RepairController",
            decision_type="escalate",
            reason_codes=["MAX_REPAIRS_EXHAUSTED", "ESCALATE_LOW_CONFIDENCE"],
            evidence_refs=[],
            tool_version="ProtacPilot:v0.2",
            confidence=0.3,
            next_proposed_node="human_gate",
            elapsed_s=0.001,
        )
        return {
            "decision_log": [decision.to_dict()],
            "status": "needs_human",
            "warnings": [f"RepairController: max repairs ({MAX_REPAIR_ATTEMPTS}) exhausted for {retry_key}"],
            "retry_counts": {**retry_counts, retry_key: current_retries},
        }

    # Continue repair route
    response_failure = (
        FailureClass.LINKER_GEOMETRY_FAIL if retry_key == "ternary"
        else FailureClass.LINKER_GEOMETRY_FAIL if retry_key == "admet"
        else FailureClass.HARD_ERROR
    )
    reason_code = get_failure_response(response_failure).get("reason_code", "RETRY_ALTERNATE_LINKER")

    decision = DecisionLog(
        node="RepairController",
        decision_type="repair",
        reason_codes=[reason_code],
        evidence_refs=[],
        tool_version="ProtacPilot:v0.2",
        confidence=0.6,
        next_proposed_node=repair_route,
        elapsed_s=0.001,
    )

    new_retry_counts = {**retry_counts, retry_key: current_retries + 1}

    return {
        "decision_log": [decision.to_dict()],
        "retry_counts": new_retry_counts,
        "status": "running",
        "warnings": [f"RepairController: repair {retry_key} → {repair_route} (attempt {current_retries + 1}/{MAX_REPAIR_ATTEMPTS})"],
    }


# ═══════════════════════════════════════════════════════════════
# STEP 6c — Gate: HumanApprovalGate
# ═══════════════════════════════════════════════════════════════

def human_approval_gate(state: AgenticWorkflowState) -> Dict[str, Any]:
    """Pause the graph and surface state for a human decision.

    In LangGraph, this uses ``interrupt()`` to pause execution.
    Returns an escalation packet.
    """
    candidates = state.get("valid_candidates", [])
    decision_log = state.get("decision_log", [])

    # Build escalation packet
    escalation_packet = {
        "candidates_for_review": [
            {
                "candidate_id": c.get("candidate_id", ""),
                "smiles": c.get("full_protac_smiles", ""),
                "warnings": c.get("warning_flags", []),
            }
            for c in candidates[:5]  # top 5
        ],
        "decision_history": decision_log[-10:],  # last 10 decisions
        "reason": "Out-of-domain or low-confidence candidate — requires human review",
    }

    decision = DecisionLog(
        node="HumanApprovalGate",
        decision_type="escalate",
        reason_codes=["ESCALATE_PRE_SYNTHESIS"],
        evidence_refs=[],
        tool_version="ProtacPilot:v0.2",
        confidence=0.0,  # unknown until human responds
        next_proposed_node="report",  # after human approval
        elapsed_s=0.001,
    )

    return {
        "decision_log": [decision.to_dict()],
        "status": "needs_human",
        "pipeline_status": "paused_for_human",
        "warnings": [f"HumanApprovalGate: paused for human review. {len(candidates)} candidate(s) escalated."],
        "escalation_packet": escalation_packet,
    }


# ═══════════════════════════════════════════════════════════════
# STEP 4 — Router functions (pure state → next_node_name)
# ═══════════════════════════════════════════════════════════════

def route_after_evidence_gate(state: AgenticWorkflowState) -> str:
    """Route based on evidence sufficiency gate verdict."""
    status = state.get("status", "running")
    if status == "fatal":
        return END if "END" in dir() else "report"
    if status == "needs_repair":
        return "repair_controller"
    if status == "needs_human":
        return "human_gate"
    return "ranking"


def route_after_ternary(state: AgenticWorkflowState) -> str:
    """Route based on ternary complex results.

    This is the demo router from the instruction set:
    - out_of_domain → human_gate
    - low confidence → ternary_repair (if retries available) or ternary_ensemble
    - acceptable → linker_design (or next stage)
    """
    evidence = state.get("evidence", {})
    domain_results = state.get("applicability_domain", [])
    retry_counts = state.get("retry_counts", {})

    # Check applicability domain
    for dr in domain_results:
        if dr.get("domain_status") == "outside":
            return "human_gate"

    # Check ternary confidence per candidate
    ternary_results = state.get("ternary_feasibility", {})
    if __debug__ and not isinstance(ternary_results, dict):
        print("DEBUG router ternary_feasibility type:", type(ternary_results), str(ternary_results)[:120], flush=True)
    elif __debug__ and any(not isinstance(v, dict) for v in ternary_results.values()):
        print("DEBUG router ternary_feasibility values:", {k: type(v).__name__ for k, v in ternary_results.items()}, flush=True)
    confidence_values = [
        tr.get("ternary_plausibility_score", 0.0)
        for tr in ternary_results.values()
    ]
    min_conf = min(confidence_values) if confidence_values else 0.0

    if min_conf < TERNARY_CONFIDENCE_THRESHOLD:
        ternary_retries = retry_counts.get("ternary", 0)
        if ternary_retries < MAX_REPAIR_ATTEMPTS:
            return "repair_controller"        # loop back with relaxed params
        return "human_gate"                    # budget exhausted → escalate to human

    return "degradation_prediction"


def route_after_degradation(state: AgenticWorkflowState) -> str:
    """Route based on degradation prediction quality."""
    deg_preds = state.get("degradation_predictions", [])
    if not deg_preds:
        return "repair_controller"

    min_conf = min(
        p.get("model_confidence", 0.0) for p in deg_preds
    ) if deg_preds else 0.0

    if min_conf < DEGRADATION_CONFIDENCE_THRESHOLD:
        deg_retries = state.get("retry_counts", {}).get("degradation", 0)
        if deg_retries < MAX_REPAIR_ATTEMPTS:
            return "repair_controller"
        return "human_gate"

    return "admet_prediction"


def route_after_admet(state: AgenticWorkflowState) -> str:
    """Route based on ADMET penalties. Repair high penalty candidates."""
    admet_preds = state.get("admet_predictions", [])

    for ap in admet_preds:
        if ap.get("overall_admet_penalty", 0.0) > ADMET_PENALTY_THRESHOLD:
            admet_retries = state.get("retry_counts", {}).get("admet", 0)
            if admet_retries < MAX_REPAIR_ATTEMPTS:
                return "repair_controller"    # try different linker
            return "human_gate"

    return "novelty_check"


def route_after_ranking(state: AgenticWorkflowState) -> str:
    """Final route: human gate for top candidates, else report."""
    rankings = state.get("ranking_results", [])

    # Check if any top candidate is out-of-domain or low-confidence
    for r in rankings[:5]:  # top 5
        if r.get("confidence", 0.0) < 0.45:
            return "human_gate"
        uncertainty_flags = r.get("uncertainty_flags", [])
        if "outside_applicability_domain" in uncertainty_flags:
            return "human_gate"

    return "report"


def route_after_repair(state: AgenticWorkflowState) -> str:
    """Route after repair controller: back to the target node or escalate."""
    # Look at the last decision from repair controller
    decision_log = state.get("decision_log", [])
    last_repair = None
    for d in reversed(decision_log):
        if d.get("node") == "RepairController":
            last_repair = d
            break

    if not last_repair:
        return "report"

    status = state.get("status", "running")
    if status == "needs_human":
        return "human_gate"

    next_node = last_repair.get("next_proposed_node", "report")
    return next_node


# ═══════════════════════════════════════════════════════════════
# STEP 1 — Build the LangGraph StateGraph with conditional edges
# ═══════════════════════════════════════════════════════════════

def build_agentic_graph(
    legacy_nodes: Optional[Dict[str, Callable]] = None,
    checkpointer=None,
) -> "StateGraph":
    """Build the adaptive LangGraph workflow.

    Args:
        legacy_nodes: Optional mapping of node_name → callable for reusing
                      existing deterministic agents. If None, uses stubs
                      that populate state from the toolbox.

    Returns:
        Compiled LangGraph StateGraph with conditional edges.

    The graph structure:

        START
          ↓
        supervisor ──→ planner ──→ safety ──→ target_resolver
                                                ↓
                                          binder_retrieval
                                                ↓
                                          warhead_selection
                                                ↓
                                          e3_selection
                                                ↓
                                          exit_vector_detection
                                                ↓
                                          linker_generation
                                                ↓
                                          construction
                                                ↓
                                          validation
                                                ↓
                                    ┌─── ternary_feasibility ───┐
                                    │        (conditional)        │
                                    │    repair / ensemble /      │
                                    │    degradation / human      │
                                    └────────────────────────────┘
                                                ↓
                                    degradation_prediction
                                                ↓ (conditional)
                                    admet_prediction
                                                ↓ (conditional)
                                    novelty_check
                                                ↓
                                    evidence_sufficiency_gate
                                                ↓ (conditional)
                                    ranking
                                                ↓ (conditional)
                                    human_gate  OR  report
                                                ↓
                                    END
    """
    from langgraph.graph import StateGraph, END

    builder = StateGraph(AgenticWorkflowState)

    # ── Use legacy nodes if provided (wrapping them to return partial updates) ──
    if legacy_nodes is None:
        legacy_nodes = {}

    # ── Add gate nodes (always use the new gate implementations) ──
    builder.add_node("evidence_sufficiency_gate", evidence_sufficiency_gate)
    builder.add_node("repair_controller", repair_controller)
    builder.add_node("human_gate", human_approval_gate)

    # ── Add legacy nodes (wrapped to return partial dicts) ──
    def _wrap_legacy(name: str, fn: Callable) -> Callable:
        """Wrap a legacy (state-mutating) agent to return a partial update dict.

        For v0.2, legacy agents still run with mutable state; the wrapper
        extracts the *new* fields after execution and returns them as a
        partial update. The decision_log entry is generated from the agent's
        trace.
        """
        def wrapped(state: AgenticWorkflowState) -> Dict[str, Any]:
            started = time.time()
            # Legacy agents may either mutate state in place AND/OR return a
            # partial update dict. We capture both paths.
            node_result = {}
            try:
                node_result = fn(state) or {}
            except Exception as e:
                return {
                    "decision_log": [DecisionLog(
                        node=name,
                        decision_type="reject",
                        reason_codes=["HARD_ERROR"],
                        evidence_refs=[],
                        tool_version="ProtacPilot:v0.2",
                        confidence=0.0,
                        next_proposed_node="repair_controller",
                        elapsed_s=time.time() - started,
                    ).to_dict()],
                    "errors": [f"{name}: {e}"],
                    "status": "needs_repair",
                }

            # Build decision log entry
            decision = DecisionLog(
                node=name,
                decision_type="accept",
                reason_codes=["PROCEED"],
                evidence_refs=[],
                tool_version="ProtacPilot:v0.2",
                confidence=0.8,
                next_proposed_node="",  # routing handles this
                elapsed_s=time.time() - started,
            )

            # Merge the legacy node's partial updates with the decision log.
            # The legacy node's keys take priority for data fields;
            # decision_log is always appended (reducer=add).
            merged = {**node_result}
            merged["decision_log"] = [decision.to_dict()]
            return merged
        return wrapped

    # Add all legacy nodes (if provided)
    for name, fn in legacy_nodes.items():
        builder.add_node(name, _wrap_legacy(name, fn))

    # ── Define edges ──
    # Entry chain (deterministic — these MUST run in order)
    chain = [
        "supervisor",
        "planner",
        "safety",
        "target_resolver",
        "binder_retrieval",
        "warhead_selection",
        "e3_selection",
        "exit_vector_detection",
        "linker_generation",
        "construction",
        "validation",
        "ternary_feasibility",
        "degradation_prediction",
        "admet_prediction",
        "novelty_check",
        "evidence_sufficiency_gate",
        "ranking",
        "report",
    ]

    # Only add edges for nodes that exist in the builder
    available = set(legacy_nodes.keys()) | {
        "evidence_sufficiency_gate", "repair_controller", "human_gate"
    }

    builder.set_entry_point(chain[0] if chain[0] in available else "evidence_sufficiency_gate")

    # ── Nodes that have conditional edges (cannot also have regular edges) ──
    # These nodes route based on evidence — the core of agentic behavior.
    conditional_nodes = {
        "ternary_feasibility",
        "degradation_prediction",
        "admet_prediction",
        "evidence_sufficiency_gate",
        "repair_controller",
        "ranking",
        "human_gate",
    }

    # Sequential edges for the entry chain — skip any node that has conditional edges
    for i in range(len(chain) - 1):
        src, dst = chain[i], chain[i + 1]
        if src not in available or dst not in available:
            continue
        if src in conditional_nodes:
            continue  # this node will use conditional edges instead
        builder.add_edge(src, dst)

    # ── Conditional edges: the heart of the agentic layer ──

    def _edge_map(mapping, available):
        """Filter a conditional-edge mapping to only nodes that exist."""
        return {k: v for k, v in mapping.items() if v in available}

    # After evidence sufficiency gate → repair, human gate, or ranking
    if "evidence_sufficiency_gate" in available:
        builder.add_conditional_edges(
            "evidence_sufficiency_gate",
            route_after_evidence_gate,
            _edge_map(
                {
                    "repair_controller": "repair_controller",
                    "human_gate": "human_gate",
                    "ranking": "ranking",
                    "report": "report",
                },
                available,
            ),
        )

    # After ternary → repair, ensemble, degradation, or human
    if "ternary_feasibility" in available:
        builder.add_conditional_edges(
            "ternary_feasibility",
            route_after_ternary,
            _edge_map(
                {
                    "repair_controller": "repair_controller",
                    "ternary_ensemble": "ternary_feasibility",  # self-loop for ensemble
                    "degradation_prediction": "degradation_prediction",
                    "human_gate": "human_gate",
                },
                available,
            ),
        )

    # After degradation → repair, human, or admet
    if "degradation_prediction" in available:
        builder.add_conditional_edges(
            "degradation_prediction",
            route_after_degradation,
            _edge_map(
                {
                    "repair_controller": "repair_controller",
                    "admet_prediction": "admet_prediction",
                    "human_gate": "human_gate",
                },
                available,
            ),
        )

    # After ADMET → repair, human, or novelty
    if "admet_prediction" in available:
        builder.add_conditional_edges(
            "admet_prediction",
            route_after_admet,
            _edge_map(
                {
                    "repair_controller": "repair_controller",
                    "novelty_check": "novelty_check",
                    "human_gate": "human_gate",
                },
                available,
            ),
        )

    # After repair → route to target or human gate
    builder.add_conditional_edges(
        "repair_controller",
        route_after_repair,
        _edge_map(
            {
                "evidence_sufficiency_gate": "evidence_sufficiency_gate",
                "ternary_feasibility": "ternary_feasibility",
                "degradation_prediction": "degradation_prediction",
                "admet_prediction": "admet_prediction",
                "linker_generation": "linker_generation",
                "exit_vector_detection": "exit_vector_detection",
                "binder_retrieval": "binder_retrieval",
                "human_gate": "human_gate",
                "report": "report",
            },
            available,
        ),
    )

    # After ranking → human gate or report
    if "ranking" in available:
        builder.add_conditional_edges(
            "ranking",
            route_after_ranking,
            _edge_map(
                {
                    "human_gate": "human_gate",
                    "report": "report",
                },
                available,
            ),
        )

    # After human gate → report (terminal)
    builder.add_edge("human_gate", END) if "human_gate" in available else None
    if "report" in available:
        builder.add_edge("report", END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def run_agentic_workflow(
    user_request: str,
    legacy_agents: Optional[Dict[str, Callable]] = None,
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the adaptive agentic workflow.

    Args:
        user_request: Natural language request
        legacy_agents: Optional dict of {name: callable} to reuse existing agents.
            If None, default stubs are used for the full node chain so that
            every router target exists and the graph compiles/runs.

    Returns:
        Final state dict with decision_log, candidates, report, etc.
    """
    if legacy_agents is None:
        legacy_agents = _default_stub_agents()
    # Persistent checkpointer (interrupt/resume capable) when a thread_id is given.
    checkpointer = None
    invoke_config = None
    if thread_id:
        from protacxtend.agents.checkpointer import get_checkpointer, run_id_thread
        checkpointer = get_checkpointer()
        invoke_config = {"configurable": {"thread_id": run_id_thread(thread_id)}}
    graph = build_agentic_graph(legacy_nodes=legacy_agents, checkpointer=checkpointer)
    initial_state: AgenticWorkflowState = {
        "user_request": user_request,
        "decision_log": [],
        "retry_counts": {},
        "warnings": [],
        "errors": [],
        "status": "running",
        "pipeline_status": "running",
        "evidence": {},
        "valid_candidates": [],
        "degradation_predictions": [],
        "admet_predictions": [],
        "novelty_results": [],
        "applicability_domain": [],
        "ternary_feasibility": {},
        "ranking_results": [],
    }
    result = graph.invoke(initial_state, config=invoke_config)
    return result


def _default_stub_agents() -> Dict[str, Callable]:
    """Minimal deterministic stubs so the graph can run without real agents.

    Each stub accepts/returns a state dict and records a lightweight trace.
    Used by run_agentic_workflow when legacy_agents is None; also guarantees
    every router target node exists in the compiled graph.
    """
    chain = [
        "supervisor", "planner", "safety", "target_resolver",
        "binder_retrieval", "warhead_selection", "e3_selection",
        "exit_vector_detection", "linker_generation", "construction",
        "validation", "ternary_feasibility", "degradation_prediction",
        "admet_prediction", "novelty_check", "ranking", "report",
    ]

    def make_stub(name: str) -> Callable:
        # Each stub populates the field its stage is responsible for, so the
        # routers and gates see a complete, coherent evidence picture and
        # the graph reaches report without an unresolvable repair loop.
        stage_fields = {
            "ternary_feasibility": {
                "ternary_feasibility": {
                    "stub_ternary": {"ternary_plausibility_score": 0.85}
                }
            },
            "degradation_prediction": {
                "degradation_predictions": [{"model_confidence": 0.8}]
            },
            "admet_prediction": {
                "admet_predictions": [{"overall_admet_penalty": 0.1}]
            },
            "novelty_check": {
                "novelty_results": [{"is_novel": True, "tanimoto_max": 0.3}]
            },
            "ranking": {
                "ranking_results": [{"confidence": 0.85, "candidate_id": "stub_top"}]
            },
        }

        def stub(state: AgenticWorkflowState) -> Dict[str, Any]:
            return {
                "status": "ok",
                "last_node": name,
                "evidence": {
                    "ternary": {
                        "ternary_confidence": 0.85,
                        "applicability_domain": "in_domain",
                        "status": "ok",
                    },
                    "degradation": {
                        "degradation_confidence": 0.8,
                        "status": "ok",
                    },
                    "admet": {
                        "admet_penalty": 0.1,
                        "status": "ok",
                    },
                },
                "valid_candidates": state.get("valid_candidates", []) or [
                    {"candidate_id": f"stub_{name}", "score": 0.5}
                ],
                **stage_fields.get(name, {}),
            }

        return stub

    return {name: make_stub(name) for name in chain}


def validate_agentic_behavior(state: Dict[str, Any]) -> Dict[str, Any]:
    """Test that the workflow is truly adaptive, not sequential.

    Per the instruction set:
    'If the same input always walks the same fixed path regardless of
    intermediate results, it's still a pipeline.
     If the path changes with the evidence, it's an agent.'

    This function checks:
    1. Did the decision_log contain entries with different next_proposed_node?
    2. Did any routing decision depend on evidence/confidence values?
    3. Were reason_codes from the controlled vocabulary?
    4. Did retry_counts change during the run?
    """
    decision_log = state.get("decision_log", [])
    next_nodes = [d.get("next_proposed_node") for d in decision_log if d.get("next_proposed_node")]
    unique_routes = set(next_nodes)
    retry_counts = state.get("retry_counts", {})
    retries_happened = any(v > 0 for v in retry_counts.values())

    # Check reason codes are from controlled vocab
    invalid_codes = []
    for d in decision_log:
        for code in d.get("reason_codes", []):
            if code not in REASON_CODES:
                invalid_codes.append(code)

    return {
        "is_truly_adaptive": len(unique_routes) > 1,
        "unique_routes": list(unique_routes),
        "decisions_made": len(decision_log),
        "retries_triggered": retries_happened,
        "retry_counts": dict(retry_counts),
        "all_reason_codes_valid": len(invalid_codes) == 0,
        "invalid_reason_codes": invalid_codes,
        "status": state.get("status"),
        "pipeline_status": state.get("pipeline_status"),
        "verdict": "AGENTIC" if len(unique_routes) > 1 or retries_happened else "PIPELINE",
    }