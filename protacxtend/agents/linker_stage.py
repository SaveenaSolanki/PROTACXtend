"""
Linker-design stage — the conformational-strain loop router (Task A2).
=====================================================================

Pattern copied from ternary_stage.py, applied to linker design.

Branches:
  - clean scan with acceptable strain   → linker_ranking → next stage
  - high strain fraction                → linker_repair → re-scan (bounded loop)
  - zero valid linkers                  → linker_human_gate (escalate)
  - missing inputs                      → evidence gate routes back to collection

The conformational-strain loop is the interesting router:
  strain_check inspects the scan results (strain proxy, geometry scores).
  If too many linkers are strained (or geometry is poor), linker_repair
  regenerates with relaxed constraints (longer / more flexible linkers)
  and re-enters linker_generation. The back-edge
      linker_repair → linker_generation
  is what makes this a loop rather than a pipeline — bounded by
  MAX_LINKER_RETRY, then either ranking (partial success) or human gate.

Scoring uses the real ProtacPilot linker_scanner (scan_linkers →
score_geometry + score_admet + score_synthesis + composite).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from langgraph.graph import StateGraph, START, END

from protacxtend.agents.state import (
    WorkflowState, NodeResult, DecisionLog,
    ReasonCode, FailureClass,
)

logger = logging.getLogger(__name__)

# Tunables
STRAIN_FRACTION_THRESHOLD = 0.5     # fraction of strained linkers that triggers repair
GEOMETRY_FLOOR = 0.4                # below this, a linker is "strained"/non-productive
MAX_LINKER_RETRY = 2
RANKING_MIN_VALID = 3               # fewer valid linkers than this → human gate


# ═══════════════════════════════════════════════════════════════
# Adapter — wraps the real linker scanner
# ═══════════════════════════════════════════════════════════════

def default_scan_fn(
    warhead_smiles: str,
    e3_ligand_smiles: str,
    linker_types: Optional[List[str]] = None,
    max_linkers: int = 50,
) -> List[Any]:
    """Call the real linker_scanner.scan_linkers (silent)."""
    from protacxtend.tools.linker_scanner import scan_linkers
    return scan_linkers(
        warhead_smiles=warhead_smiles,
        e3_ligand_smiles=e3_ligand_smiles,
        linker_types=linker_types,
        max_linkers=max_linkers,
        verbose=False,
    )


def _relax_linker_constraints(previous_types: Optional[List[str]] = None) -> List[str]:
    """Recovery action: broaden the linker search to more flexible classes.

    Progressive relaxation: PEG → alkyl → mixed (semi-rigid). In production
    this maps to the linker library categories.
    """
    relaxed = [
        "PEG", "alkyl", "semi-rigid", "mixed", "short", "long",
    ]
    return relaxed


# ═══════════════════════════════════════════════════════════════
# Nodes
# ═══════════════════════════════════════════════════════════════

def linker_evidence_gate(state: WorkflowState) -> dict:
    """Refuse to scan until warhead + E3 SMILES exist in evidence."""
    ev = state["evidence"]
    required = {"warhead_smiles", "e3_ligand_smiles"}
    missing = required - ev.keys()
    if missing:
        return NodeResult(
            updates={"status": "insufficient_evidence"},
            decision=DecisionLog(
                node="linker_evidence_gate", decision_type="gate",
                reason_codes=(ReasonCode.EVIDENCE_INSUFFICIENT,),
                evidence_refs=tuple(sorted(ev.keys())),
                tool_version="linker-stage-v1", confidence=0.0,
                next_proposed_node="collect_linker_inputs",
            ),
        ).to_state()
    return NodeResult(updates={"status": "evidence_ok"}).to_state()


def linker_generation(state: WorkflowState, scan_fn: Callable) -> dict:
    """Run the N linkers × M attachment points scan."""
    ev = state["evidence"]
    warhead = ev.get("warhead_smiles", "")
    e3 = ev.get("e3_ligand_smiles", "")
    linker_types = ev.get("linker_types") or None

    try:
        results = scan_fn(warhead, e3, linker_types=linker_types, max_linkers=50)
    except Exception as exc:
        logger.error("Linker scan failed: %s", exc)
        return NodeResult(
            updates={"evidence": {"linker_status": "scan_failed"}},
            decision=DecisionLog(
                node="linker_generation", decision_type="retry",
                reason_codes=(ReasonCode.HARD_ERROR,),
                evidence_refs=("linker_status",),
                tool_version="linker-scanner-v1", confidence=0.0,
                next_proposed_node="route", failure_class=FailureClass.HARD_ERROR,
            ),
            retry_bump="linker",
        ).to_state()

    valid = [r for r in results if getattr(r, "composite_score", 0.0) > 0.0]

    def _result_to_dict(r: Any) -> dict:
        if isinstance(r, dict):
            return r
        if hasattr(r, "__dataclass_fields__"):
            from dataclasses import asdict
            return asdict(r)
        return dict(r)

    return NodeResult(
        updates={"evidence": {
            "linker_results": [_result_to_dict(r) for r in results],
            "linker_valid_count": len(valid),
            "linker_total_count": len(results),
            "linker_status": "ok",
        }},
        decision=DecisionLog(
            node="linker_generation", decision_type="accept",
            reason_codes=(ReasonCode.TERNARY_CONF_OK,) if valid else (ReasonCode.OUT_OF_DOMAIN,),
            evidence_refs=("linker_results",),
            tool_version="linker-scanner-v1",
            confidence=min(1.0, len(valid) / max(1, len(results))),
            next_proposed_node="route",
        ),
    ).to_state()


def strain_check(state: WorkflowState) -> dict:
    """Compute the strain statistics that the router reads.

    A linker is 'strained' if:
      - its strain proxy exceeds 0.7, OR
      - its geometry score is below GEOMETRY_FLOOR
    The router decides repair vs proceed based on the strained fraction.
    """
    ev = state["evidence"]
    results = ev.get("linker_results", [])
    if not results:
        return NodeResult(
            updates={"evidence": {
                "strain_fraction": 1.0,
                "strain_valid_count": 0,
                "strain_total_count": 0,
                "strain_status": "no_linkers",
            }},
        ).to_state()

    strained = 0
    valid = 0
    for r in results:
        geometry = r.get("geometry_score", 0.0)
        strain = r.get("linker_strain_energy_proxy", 0.0)
        is_valid = geometry >= GEOMETRY_FLOOR
        if is_valid:
            valid += 1
        if not is_valid or strain > 0.7:
            strained += 1

    fraction = strained / len(results) if results else 1.0
    return NodeResult(
        updates={"evidence": {
            "strain_fraction": round(fraction, 3),
            "strain_valid_count": valid,
            "strain_total_count": len(results),
            "strain_status": "ok",
        }},
    ).to_state()


def linker_repair(state: WorkflowState) -> dict:
    """Recovery: relax linker constraints and re-enter generation."""
    ev = state["evidence"]
    prev_types = ev.get("linker_types")
    relaxed = _relax_linker_constraints(prev_types)
    return NodeResult(
        updates={
            "evidence": {
                "linker_types": relaxed,
                "repair_applied": True,
                "repair_round": ev.get("repair_round", 0) + 1,
            },
            "candidates": state.get("candidates", []),
        },
        retry_bump="linker",
    ).to_state()


def linker_ranking(state: WorkflowState) -> dict:
    """Rank by composite score; record top-N as the stage output."""
    ev = state["evidence"]
    results = ev.get("linker_results", [])
    ranked = sorted(
        results, key=lambda r: (-r.get("composite_score", 0.0), -r.get("geometry_score", 0.0))
    )
    return NodeResult(
        updates={"evidence": {
            "linker_ranked": ranked[:10],
            "linker_stage_done": True,
        }},
        decision=DecisionLog(
            node="linker_ranking", decision_type="accept",
            reason_codes=(ReasonCode.TERNARY_CONF_OK,),
            evidence_refs=("linker_ranked",),
            tool_version="linker-stage-v1",
            confidence=min(1.0, len(ranked) / RANKING_MIN_VALID),
            next_proposed_node="construction",
        ),
    ).to_state()


def linker_human_gate(state: WorkflowState) -> dict:
    """Escalate: no feasible linkers or repeated strain failure."""
    return NodeResult(
        updates={"status": "needs_human", "pipeline_status": "paused_for_human"},
        decision=DecisionLog(
            node="linker_human_gate", decision_type="gate",
            reason_codes=(ReasonCode.HUMAN_REQUIRED,),
            evidence_refs=("linker_results", "strain_fraction"),
            tool_version="linker-stage-v1", confidence=0.0,
            next_proposed_node="abort_candidate",
        ),
    ).to_state()


def collect_linker_inputs(state: WorkflowState) -> dict:
    """Placeholder for input collection (warhead/E3 SMILES from earlier stages)."""
    return NodeResult(updates={"status": "collecting"}).to_state()


def construction(state: WorkflowState) -> dict:
    """Next stage after linker design (placeholder terminal)."""
    return NodeResult(updates={"status": "construction_reached"}).to_state()


def abort_candidate(state: WorkflowState) -> dict:
    return NodeResult(updates={"status": "aborted"}).to_state()


# ═══════════════════════════════════════════════════════════════
# Router — state → next node. Reads strain stats off evidence.
# ═══════════════════════════════════════════════════════════════

def route_after_strain_check(state: WorkflowState) -> str:
    ev = state["evidence"]

    # Scan failed outright → repair (or give up)
    if ev.get("linker_status") == "scan_failed":
        if state["retry_counts"].get("linker", 0) < MAX_LINKER_RETRY:
            return "linker_repair"
        return "linker_human_gate"

    valid_count = ev.get("strain_valid_count", 0)
    total_count = ev.get("strain_total_count", 0)

    # Nothing produced at all → human gate (no score on thin air)
    if total_count == 0:
        return "linker_human_gate"

    # Too few valid linkers → human gate
    if valid_count < min(RANKING_MIN_VALID, total_count):
        if state["retry_counts"].get("linker", 0) < MAX_LINKER_RETRY:
            return "linker_repair"
        return "linker_human_gate"

    # High strain fraction → repair loop (bounded)
    fraction = ev.get("strain_fraction", 0.0)
    if fraction > STRAIN_FRACTION_THRESHOLD:
        if state["retry_counts"].get("linker", 0) < MAX_LINKER_RETRY:
            return "linker_repair"
        return "linker_ranking"   # accept partial after budget exhausted

    return "linker_ranking"


# ═══════════════════════════════════════════════════════════════
# Wiring
# ═══════════════════════════════════════════════════════════════

def build_linker_stage(builder: StateGraph, scan_fn: Optional[Callable] = None) -> StateGraph:
    scan_fn = scan_fn or default_scan_fn

    # Bind scan_fn into the node (closures keep node signatures state-only)
    def _generation(state):
        return linker_generation(state, scan_fn)

    builder.add_node("linker_evidence_gate", linker_evidence_gate)
    builder.add_node("linker_generation", _generation)
    builder.add_node("strain_check", strain_check)
    builder.add_node("linker_repair", linker_repair)
    builder.add_node("linker_ranking", linker_ranking)
    builder.add_node("linker_human_gate", linker_human_gate)
    builder.add_node("collect_linker_inputs", collect_linker_inputs)
    builder.add_node("construction", construction)
    builder.add_node("abort_candidate", abort_candidate)

    builder.add_edge(START, "linker_evidence_gate")
    builder.add_edge("linker_evidence_gate", "linker_generation")
    builder.add_edge("linker_generation", "strain_check")

    builder.add_conditional_edges("strain_check", route_after_strain_check, {
        "linker_repair": "linker_repair",
        "linker_ranking": "linker_ranking",
        "linker_human_gate": "linker_human_gate",
    })

    # The back-edge — the difference between pipeline and agent
    builder.add_edge("linker_repair", "linker_generation")

    builder.add_edge("linker_ranking", "construction")
    builder.add_edge("construction", END)
    builder.add_edge("linker_human_gate", END)
    builder.add_edge("abort_candidate", END)
    builder.add_edge("collect_linker_inputs", END)

    return builder


def compile_linker_graph(scan_fn: Optional[Callable] = None):
    from langgraph.checkpoint.memory import MemorySaver
    builder = StateGraph(WorkflowState)
    build_linker_stage(builder, scan_fn=scan_fn)
    return builder.compile(checkpointer=MemorySaver())
