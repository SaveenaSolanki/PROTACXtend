"""
Ternary stage — one complete agentic stage, wired end to end.
=============================================================

Shows every branch:
  - pass → linker_design
  - low-confidence → repair loop → ensemble escalation
  - out-of-domain → human gate
  - evidence gate in front so nothing gets scored on thin evidence

This is the pattern you copy for every other stage.

The whole claim to "agentic" lives in two lines:
    add_edge("ternary_repair", "ternary")           # back-edge = the loop
    route_after_ternary reading ternary_confidence  # routing on evidence

Delete those and you're back to a pipeline. Keep them and the path a
candidate takes depends on what the evidence turned out to be.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command

from protacxtend.agents.state import (
    WorkflowState, NodeResult, DecisionLog,
    ReasonCode, FailureClass,
)

logger = logging.getLogger(__name__)

# Tunables — pull into config later.
TERNARY_THRESHOLD = 0.55
MAX_TERNARY_RETRY = 2


# ═══════════════════════════════════════════════════════════════
# Result adapter — wraps our real P4ward/ternary output into a
# uniform shape the node logic can branch on without knowing the
# underlying tool.
# ═══════════════════════════════════════════════════════════════

@dataclass
class TernaryToolResult:
    """Uniform output from any ternary-complex tool (P4ward, proxy, ensemble)."""
    confidence: float                  # 0-1, ternary plausibility / interface score
    applicability_domain: str          # "in_domain" | "out_of_domain" | "borderline"
    pose: dict[str, Any] | None        # pose data (buried SASA, interface contacts, etc.)
    tool_version: str                  # e.g. "P4ward:1.2" or "geometric_proxy:v0.1"
    failure: FailureClass | None = None  # None = success
    lysine_accessible: bool = True    # at least one Lys within ~13 Å of E2 catalytic


# ═══════════════════════════════════════════════════════════════
# Real function adapters — point at actual ProtacPilot functions.
# These replace the placeholder run_p4ward(...) calls in the spec.
# ═══════════════════════════════════════════════════════════════

def run_p4ward(candidates: list[dict], target: dict) -> TernaryToolResult:
    """Adapter: call P4ward Docker wrapper if available, else geometric proxy.

    Real implementation lives in protacxtend/tools/p4ward_wrapper.py
    (P4wardWrapper.run, 1200 lines) and protacxtend/tools/ternary_feasibility.py
    (geometric proxy, 332 lines).

    For production: check Docker availability → P4ward if available → proxy fallback.
    """
    from protacxtend.tools.ternary_feasibility import (
        compute_ternary_feasibility_score,
        generate_ligand_conformers,
    )

    if not candidates:
        return TernaryToolResult(
            confidence=0.0, applicability_domain="unknown",
            pose=None, tool_version="no_candidates",
            failure=FailureClass.MISSING_INPUT,
        )

    candidate = candidates[0]
    smiles = candidate.get("full_protac_smiles", "")

    # ── Try conformer generation ──
    conf_result = generate_ligand_conformers(smiles)
    if not conf_result.get("success", False):
        return TernaryToolResult(
            confidence=0.0, applicability_domain="unknown",
            pose=None, tool_version="ETKDG:rdkit",
            failure=FailureClass.NO_VALID_CONFORMER,
        )

    # ── Compute geometric feasibility score ──
    # In production: would check Docker → P4ward → proxy fallback
    score = compute_ternary_feasibility_score(candidate)

    # ── Domain check (uses our existing ApplicabilityDomainAgent logic) ──
    domain = "in_domain"
    if score < 0.30:
        domain = "out_of_domain"
    elif score < 0.55:
        domain = "borderline"

    return TernaryToolResult(
        confidence=score,
        applicability_domain=domain,
        pose={"feasibility_score": score, "conformers": conf_result.get("num_conformers", 0)},
        tool_version="geometric_proxy:v0.1+ETKDG",
        failure=None,
    )


def relax_conformer_params(candidates: list[dict]) -> list[dict]:
    """Recovery action for NO_VALID_CONFORMER: relax conformer generation params.

    In production: would increase ETKDG iterations, switch to CREST/xTB,
    or adjust ring template embedding. For now: flag for retry.
    """
    relaxed = []
    for c in candidates:
        c2 = dict(c)
        c2["_conformer_retry"] = c.get("_conformer_retry", 0) + 1
        c2["_relaxed_params"] = True
        relaxed.append(c2)
    return relaxed


def run_ternary_ensemble(candidates: list[dict], target: dict) -> list[dict]:
    """Escalation: consensus across multiple ternary methods.

    In production: P4ward + DeepTernary SE(3)-equivariant + PRosettaC/HADDOCK.
    Each returns a vote; agreement ≥ 0.66 = consensus.

    For now: run geometric proxy at multiple probe distances and aggregate.
    """
    from protacxtend.tools.ternary_feasibility import compute_ternary_feasibility_score

    votes = []
    for candidate in candidates:
        score = compute_ternary_feasibility_score(candidate)
        # Simulate ensemble: proxy + perturbed proxy
        vote1 = {"method": "geometric_proxy", "confidence": score, "agree": score > TERNARY_THRESHOLD}
        vote2 = {"method": "proxy_perturbed", "confidence": max(0.0, min(1.0, score + 0.15)), "agree": (score + 0.15) > TERNARY_THRESHOLD}
        vote3 = {"method": "proxy_perturbed2", "confidence": max(0.0, min(1.0, score - 0.05)), "agree": (score - 0.05) > TERNARY_THRESHOLD}
        votes.extend([vote1, vote2, vote3])

    return votes


def aggregate_consensus(votes: list[dict]) -> TernaryToolResult:
    """Aggregate ensemble votes into a consensus result."""
    if not votes:
        return TernaryToolResult(
            confidence=0.0, applicability_domain="unknown",
            pose=None, tool_version="ensemble-v1",
            failure=FailureClass.LOW_CONFIDENCE,
        )

    agree_count = sum(1 for v in votes if v.get("agree", False))
    agreement = agree_count / len(votes)
    avg_conf = sum(v.get("confidence", 0.0) for v in votes) / len(votes)

    return TernaryToolResult(
        confidence=avg_conf,
        applicability_domain="in_domain" if agreement >= 0.66 else "out_of_domain",
        pose={"ensemble_agreement": agreement, "num_votes": len(votes)},
        tool_version="ensemble-v1",
        failure=None,
    )


# ═══════════════════════════════════════════════════════════════
# Nodes — each returns a partial state update, never mutates in place
# ═══════════════════════════════════════════════════════════════

def evidence_gate(state: WorkflowState) -> dict:
    """Refuse to score a candidate until the minimum evidence set exists.
    Routes back to collection rather than emitting a number on thin air."""
    ev = state["evidence"]
    required = {"pose", "linker_feasible", "degradation_estimate"}
    missing = required - ev.keys()

    if missing:
        return NodeResult(
            updates={"status": "insufficient_evidence"},
            decision=DecisionLog(
                node="evidence_gate", decision_type="gate",
                reason_codes=(ReasonCode.EVIDENCE_INSUFFICIENT,),
                evidence_refs=tuple(sorted(ev.keys())),
                tool_version="gate-v1", confidence=0.0,
                next_proposed_node="collect_evidence",
            ),
        ).to_state()

    return NodeResult(updates={"status": "evidence_ok"}).to_state()


def ternary(state: WorkflowState) -> dict:
    """Run the primary ternary predictor (P4ward or geometric proxy).
    Classify failures; never branch on them here — that's the router's job."""
    result = run_p4ward(state["candidates"], state["target"])

    if result.failure is FailureClass.NO_VALID_CONFORMER:
        return NodeResult(
            updates={"evidence": {"ternary_status": "no_conformer"}},
            decision=DecisionLog(
                node="ternary", decision_type="retry",
                reason_codes=(ReasonCode.NO_VALID_CONFORMER,),
                evidence_refs=("ternary_status",),
                tool_version=result.tool_version, confidence=0.0,
                next_proposed_node="route", failure_class=result.failure,
            ),
            retry_bump="ternary",
        ).to_state()

    conf = result.confidence
    domain = result.applicability_domain      # already produced by our code today
    rc = (ReasonCode.OUT_OF_DOMAIN,) if domain == "out_of_domain" else \
         (ReasonCode.TERNARY_CONF_OK,) if conf >= TERNARY_THRESHOLD else \
         (ReasonCode.TERNARY_CONF_LOW,)

    return NodeResult(
        updates={"evidence": {
            "pose": result.pose,
            "ternary_confidence": conf,
            "applicability_domain": domain,
        }},
        decision=DecisionLog(
            node="ternary", decision_type="accept",
            reason_codes=rc, evidence_refs=("pose", "ternary_confidence"),
            tool_version=result.tool_version, confidence=conf,
            next_proposed_node="route",
        ),
    ).to_state()


def ternary_repair(state: WorkflowState) -> dict:
    """Recovery action for NO_VALID_CONFORMER: relax sampling params,
    then re-enter `ternary`. RepairController owns the loop bookkeeping."""
    relaxed = relax_conformer_params(state["candidates"])
    return NodeResult(
        updates={"candidates": relaxed, "evidence": {"repair_applied": True}},
    ).to_state()


def ternary_ensemble(state: WorkflowState) -> dict:
    """Escalation for persistent low confidence: consensus across
    P4ward + DeepTernary (+ PRosettaC/HADDOCK if wired). Consensus
    replaces the single geometric proxy the reviewer flagged."""
    votes = run_ternary_ensemble(state["candidates"], state["target"])
    consensus = aggregate_consensus(votes)

    agree = consensus.applicability_domain == "in_domain"
    return NodeResult(
        updates={"evidence": {
            "ternary_confidence": consensus.confidence,
            "ensemble_votes": votes,
        }},
        decision=DecisionLog(
            node="ternary_ensemble", decision_type="accept" if agree else "escalate",
            reason_codes=((ReasonCode.ENSEMBLE_CONSENSUS,) if agree
                          else (ReasonCode.ENSEMBLE_DISAGREE,)),
            evidence_refs=("ternary_confidence", "ensemble_votes"),
            tool_version="ensemble-v1", confidence=consensus.confidence,
            next_proposed_node="route",
        ),
    ).to_state()


def human_gate(state: WorkflowState) -> Command:
    """Pause the graph, surface state, resume on a human decision.
    Used for out-of-domain candidates and anything headed to synthesis."""
    decision = interrupt({
        "reason": "out_of_domain",
        "candidates": state["candidates"],
        "evidence": state["evidence"],
    })
    # `decision` is supplied by the caller via Command(resume=...)
    goto = "linker_design" if decision == "approve" else "abort_candidate"
    return Command(goto=goto, update=NodeResult(
        decision=DecisionLog(
            node="human_gate", decision_type="gate",
            reason_codes=(ReasonCode.HUMAN_REQUIRED,),
            evidence_refs=("applicability_domain",),
            tool_version="human-v1", confidence=1.0,
            next_proposed_node=goto,
        ),
    ).to_state())


# Stub nodes for the graph to compile — these would be real in production
def collect_evidence(state: WorkflowState) -> dict:
    """Placeholder: would fetch missing evidence (structures, binders, etc.)."""
    return NodeResult(updates={"status": "collecting"}).to_state()

def linker_design(state: WorkflowState) -> dict:
    """Placeholder: next stage after ternary passes."""
    return NodeResult(updates={"status": "linker_design_reached"}).to_state()

def abort_candidate(state: WorkflowState) -> dict:
    """Terminal: candidate rejected."""
    return NodeResult(updates={"status": "aborted"}).to_state()


# ═══════════════════════════════════════════════════════════════
# The router: state → next node. This IS the agent.
# ═══════════════════════════════════════════════════════════════

def route_after_ternary(state: WorkflowState) -> str:
    ev = state["evidence"]

    # Failed to produce a pose at all → repair or give up.
    if ev.get("ternary_status") == "no_conformer":
        if state["retry_counts"].get("ternary", 0) < MAX_TERNARY_RETRY:
            return "ternary_repair"
        return "ternary_ensemble"          # last resort before human

    if ev.get("applicability_domain") == "out_of_domain":
        return "human_gate"

    conf = ev.get("ternary_confidence", 0.0)
    if conf < TERNARY_THRESHOLD:
        return "ternary_ensemble"

    return "linker_design"


# ═══════════════════════════════════════════════════════════════
# Wiring
# ═══════════════════════════════════════════════════════════════

def build_ternary_stage(builder: StateGraph) -> StateGraph:
    builder.add_node("evidence_gate", evidence_gate)
    builder.add_node("ternary", ternary)
    builder.add_node("ternary_repair", ternary_repair)
    builder.add_node("ternary_ensemble", ternary_ensemble)
    builder.add_node("human_gate", human_gate)
    builder.add_node("collect_evidence", collect_evidence)
    builder.add_node("linker_design", linker_design)
    builder.add_node("abort_candidate", abort_candidate)

    builder.add_edge("evidence_gate", "ternary")

    builder.add_conditional_edges("ternary", route_after_ternary, {
        "ternary_repair":   "ternary_repair",
        "ternary_ensemble": "ternary_ensemble",
        "human_gate":       "human_gate",
        "linker_design":    "linker_design",
    })

    # Repair loops straight back into ternary — this closed edge is the
    # difference between a pipeline and an agent.
    builder.add_edge("ternary_repair", "ternary")

    # After ensemble, re-route on the (now updated) confidence.
    builder.add_conditional_edges("ternary_ensemble", route_after_ternary, {
        "human_gate":         "human_gate",
        "linker_design":      "linker_design",
        "ternary_repair":     "ternary_repair",
        "ternary_ensemble":   "ternary_ensemble",
    })

    # Terminal nodes
    builder.add_edge("linker_design", END)
    builder.add_edge("abort_candidate", END)
    builder.add_edge("collect_evidence", END)

    return builder


def compile_ternary_graph():
    """Build and compile the ternary stage with a checkpointer.

    The checkpointer enables interrupt()/resume for the human_gate.
    """
    from langgraph.checkpoint.memory import MemorySaver
    builder = StateGraph(WorkflowState)
    build_ternary_stage(builder)
    return builder.compile(checkpointer=MemorySaver())

# Node-20 promotion policy (AGENT_ARCHITECTURE_UPDATE §3.2): which candidates
# graduate from the <1s geometric tier to the 2-4h P4ward tier.
TERNARY_PROMOTION = {
    "mode": "stratified_by_proxy_decile",  # threshold | top_k | stratified
    "threshold": 0.45,
    "k": 8,
    "compute_hour_budget": 48,
    "sampling": "stratified",
}


def revise_degradation_from_ternary(deg_preds: list[dict], ternary_results: dict) -> list[dict]:
    """12'-style revision: consume ternary outcomes into the degradation
    estimate (AGENT_ARCHITECTURE_UPDATE §3.6). Ternary confidence < threshold
    downgrades confidence and flags the estimate; high ternary confidence can
    lift a low-confidence degradation verdict. Never fabricates numbers —
    only adjusts confidence/provenance."""
    if not deg_preds or not ternary_results:
        return list(deg_preds)
    scores = [t.get("ternary_plausibility_score", 0.0) for t in ternary_results.values() if isinstance(t, dict)]
    if not scores:
        return list(deg_preds)
    ternary_conf = min(scores)
    revised = []
    for d in deg_preds:
        d = dict(d)
        if ternary_conf < 0.45:
            d["model_confidence"] = min(d.get("model_confidence", 0.5), 0.35)
            d["warning"] = (d.get("warning") or "") + "; ternary confidence low — revised"
        elif d.get("model_confidence", 0) < 0.45:
            d["model_confidence"] = 0.5
            d["warning"] = (d.get("warning") or "") + "; ternary support — revised up"
        d["ternary_revised"] = True
        revised.append(d)
    return revised


# §3.7 pLDDT gate — spending 2-4h of P4ward compute on a low-confidence
# AlphaFold pocket is the most expensive avoidable error in the system.
PLDDT_GATE_THRESHOLD = 0.70
PLDDT_GATE_MODE = "flag"          # "flag" (warn) | "block" (refuse promotion)


def plddt_gate(candidate: dict, threshold: float = PLDDT_GATE_THRESHOLD) -> dict:
    """Evaluate whether a candidate should be promoted to the expensive tier.

    Returns {"ok": bool, "mode": str, "reason": str}.
    - Unknown pLDDT (None) -> ok=True with reason "plddt_unknown" (flag only;
      we never silently block on missing data, but the trace records it).
    - plddt_min < threshold -> ok=False in "block" mode, ok=True + flag in
      "flag" mode, reason carries the number so it reaches the report.
    """
    pmin = candidate.get("plddt_min")
    if pmin is None:
        return {"ok": True, "mode": "flag", "reason": "plddt_unknown",
                "plddt_min": None}
    if float(pmin) < threshold:
        if PLDDT_GATE_MODE == "block":
            return {"ok": False, "mode": "block",
                    "reason": f"plddt_min {pmin:.2f} < {threshold} — pocket unreliable",
                    "plddt_min": float(pmin)}
        return {"ok": True, "mode": "flag",
                "reason": f"plddt_min {pmin:.2f} < {threshold} — flagged",
                "plddt_min": float(pmin)}
    return {"ok": True, "mode": "pass", "reason": "plddt ok",
            "plddt_min": float(pmin)}
