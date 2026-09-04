"""
Adaptive decision-graph extras (capabilities 2, 3, 4, 7).
==========================================================

Completes the v0.2 → v0.3 decision graph with four missing behaviors:

  1. Bounded repair loops for WARHEAD and EXIT-VECTOR failures (cap. 2)
  2. Dynamic tool selection from available evidence (cap. 3)
  3. Parallel candidate evaluation (cap. 4)
  4. Human approval gate before expensive modelling (cap. 7)

All deterministic; no LLM.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Sequence

from protacxtend.agents.state import NodeResult, DecisionLog, ReasonCode, FailureClass

logger = logging.getLogger("protacpilot.adaptive_extras")

MAX_SELECTION_RETRY = 2
EXIT_VECTOR_MIN_SCORE = 0.35
WARHEAD_MIN_POTENCY = 0.4      # normalized 0-1 binding-potency floor


# ═══════════════════════════════════════════════════════════════
# 1. Warhead repair loop
# ═══════════════════════════════════════════════════════════════

def warhead_evidence_check(state: Dict[str, Any]) -> Dict[str, Any]:
    """Check warhead quality: potency floor + attachment points exist."""
    evidence = state.get("evidence", {})
    warheads = evidence.get("warheads", [])
    if not warheads:
        return NodeResult(
            updates={"status": "needs_repair", "evidence": {"warhead_check": "no_warheads"}},
            decision=DecisionLog(
                node="warhead_evidence_check", decision_type="retry",
                reason_codes=(ReasonCode.EVIDENCE_INSUFFICIENT,),
                evidence_refs=("warheads",), tool_version="adaptive-v1",
                confidence=0.0, next_proposed_node="warhead_repair",
                failure_class=FailureClass.MISSING_INPUT,
            ),
            retry_bump="warhead",
        ).to_state()

    weak = [w for w in warheads if (w.get("potency") or 0.0) < WARHEAD_MIN_POTENCY]
    if weak and len(weak) == len(warheads):
        return NodeResult(
            updates={"status": "needs_repair", "evidence": {"warhead_check": "all_weak"}},
            decision=DecisionLog(
                node="warhead_evidence_check", decision_type="retry",
                reason_codes=(ReasonCode.TERNARY_CONF_LOW,),
                evidence_refs=("warheads",), tool_version="adaptive-v1",
                confidence=0.3, next_proposed_node="warhead_repair",
                failure_class=FailureClass.LOW_CONFIDENCE,
            ),
            retry_bump="warhead",
        ).to_state()

    return NodeResult(
        updates={"status": "ok", "evidence": {"warhead_check": "ok"}},
    ).to_state()


def warhead_repair(state: Dict[str, Any]) -> Dict[str, Any]:
    """Recovery: relax the potency threshold / request alternate chemotypes."""
    return NodeResult(
        updates={
            "evidence": {
                "warhead_relaxed": True,
                "warhead_repair_round": state.get("evidence", {}).get("warhead_repair_round", 0) + 1,
                "warhead_min_potency": max(0.1, WARHEAD_MIN_POTENCY - 0.1),
            }
        },
        retry_bump="warhead",
    ).to_state()


def route_after_warhead_check(state: Dict[str, Any]) -> str:
    check = state.get("evidence", {}).get("warhead_check", "")
    if check in ("no_warheads", "all_weak"):
        retries = state.get("retry_counts", {}).get("warhead", 0)
        return "warhead_repair" if retries < MAX_SELECTION_RETRY else "human_gate"
    return "exit_vector_detection"


# ═══════════════════════════════════════════════════════════════
# 2. Exit-vector repair loop
# ═══════════════════════════════════════════════════════════════

def exit_vector_check(state: Dict[str, Any]) -> Dict[str, Any]:
    """Score exit vectors: need at least one attachment point ≥ floor."""
    evidence = state.get("evidence", {})
    exit_vectors = evidence.get("exit_vectors", [])
    if not exit_vectors:
        return NodeResult(
            updates={"status": "needs_repair", "evidence": {"exit_vector_check": "none"}},
            decision=DecisionLog(
                node="exit_vector_check", decision_type="retry",
                reason_codes=(ReasonCode.NO_VALID_CONFORMER,),
                evidence_refs=("exit_vectors",), tool_version="adaptive-v1",
                confidence=0.0, next_proposed_node="exit_vector_repair",
                failure_class=FailureClass.NO_VALID_CONFORMER,
            ),
            retry_bump="exit_vector",
        ).to_state()

    good = [e for e in exit_vectors if (e.get("score") or 0.0) >= EXIT_VECTOR_MIN_SCORE]
    if not good:
        return NodeResult(
            updates={"status": "needs_repair", "evidence": {"exit_vector_check": "all_poor"}},
            decision=DecisionLog(
                node="exit_vector_check", decision_type="retry",
                reason_codes=(ReasonCode.TERNARY_CONF_LOW,),
                evidence_refs=("exit_vectors",), tool_version="adaptive-v1",
                confidence=0.3, next_proposed_node="exit_vector_repair",
                failure_class=FailureClass.LOW_CONFIDENCE,
            ),
            retry_bump="exit_vector",
        ).to_state()

    return NodeResult(
        updates={"status": "ok", "evidence": {"exit_vector_check": "ok"}},
    ).to_state()


def exit_vector_repair(state: Dict[str, Any]) -> Dict[str, Any]:
    """Recovery: expand attachment-point search (more atoms, relaxed SMARTS)."""
    return NodeResult(
        updates={
            "evidence": {
                "exit_vector_relaxed": True,
                "exit_vector_repair_round": state.get("evidence", {}).get("exit_vector_repair_round", 0) + 1,
                "attachment_search_mode": "expanded",
            }
        },
        retry_bump="exit_vector",
    ).to_state()


def route_after_exit_vector_check(state: Dict[str, Any]) -> str:
    check = state.get("evidence", {}).get("exit_vector_check", "")
    if check in ("none", "all_poor"):
        retries = state.get("retry_counts", {}).get("exit_vector", 0)
        return "exit_vector_repair" if retries < MAX_SELECTION_RETRY else "human_gate"
    return "linker_generation"


# ═══════════════════════════════════════════════════════════════
# 3. Dynamic tool selection (cap. 3)
# ═══════════════════════════════════════════════════════════════

def select_ternary_tool(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Choose the ternary-modelling tool from available evidence.

    Rules (deterministic priority):
      - P4ward (expensive, accurate): requires receptor+ligase PDBs AND ligand
        MOL2s AND Docker available
      - geometric proxy (cheap): requires warhead/E3 SMILES + attachment points
      - skip: only if no structural evidence at all → route to evidence repair
    """
    has_structures = bool(
        evidence.get("receptor_pdb") and evidence.get("ligase_pdb")
        and evidence.get("receptor_ligand_mol2") and evidence.get("ligase_ligand_mol2")
    )
    has_docker = bool(evidence.get("p4ward_docker_available"))
    has_smiles = bool(evidence.get("warhead_smiles") and evidence.get("e3_ligand_smiles"))
    has_attachment = bool(evidence.get("exit_vectors"))

    if has_structures and has_docker and has_attachment:
        return {"tool": "p4ward", "mode": "full", "cost": "hours", "reason": "all_structural_evidence"}
    if has_smiles and has_attachment:
        return {"tool": "geometric_proxy", "mode": "fast", "cost": "seconds", "reason": "smiles_only"}
    if has_smiles:
        return {"tool": "geometric_proxy", "mode": "minimal", "cost": "seconds", "reason": "smiles_no_attachment"}
    return {"tool": "none", "mode": "blocked", "cost": "n/a", "reason": "no_structural_evidence"}


def tool_selection_node(state: Dict[str, Any]) -> Dict[str, Any]:
    evidence = state.get("evidence", {})
    ternary_plan = select_ternary_tool(evidence)
    docking_plan = select_docking_tool(evidence)
    return NodeResult(
        updates={
            "evidence": {
                "tool_plan": {
                    "ternary": ternary_plan,
                    "docking": docking_plan,
                }
            }
        },
        decision=DecisionLog(
            node="tool_selection", decision_type="accept",
            reason_codes=(ReasonCode.TERNARY_CONF_OK,),
            evidence_refs=("tool_plan",), tool_version="adaptive-v1",
            confidence=0.9 if ternary_plan["tool"] != "none" else 0.3,
            next_proposed_node="route",
        ),
    ).to_state()


def select_docking_tool(evidence: Dict[str, Any]) -> Dict[str, Any]:
    has_protein = bool(evidence.get("receptor_pdb"))
    has_ligand = bool(evidence.get("warhead_smiles") or evidence.get("e3_ligand_smiles"))
    gnina_available = bool(evidence.get("gnina_available"))
    if has_protein and has_ligand:
        return {"tool": "gnina" if gnina_available else "vina", "reason": "structure_available"}
    if has_ligand:
        return {"tool": "skip", "reason": "no_protein_structure"}
    return {"tool": "none", "reason": "no_inputs"}


# ═══════════════════════════════════════════════════════════════
# 4. Parallel candidate evaluation (cap. 4)
# ═══════════════════════════════════════════════════════════════

def parallel_evaluate(
    candidates: Sequence[Dict[str, Any]],
    evaluator: Callable[[Dict[str, Any]], Dict[str, Any]],
    max_workers: int = 4,
) -> List[Dict[str, Any]]:
    """Evaluate candidates in parallel with a thread pool.

    evaluator(candidate) → result dict. Order preserved.
    Failures become {'evaluation_error': str} entries (never crash the batch).
    """
    results: List[Optional[Dict[str, Any]]] = [None] * len(candidates)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(evaluator, c): i for i, c in enumerate(candidates)}
        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                results[idx] = {"candidate_id": str(candidates[idx].get("candidate_id", idx)),
                                "evaluation_error": str(exc)}
    return [r for r in results if r is not None]


def parallel_degradation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Batch degradation evaluation across candidates (ThreadPool)."""
    from protacxtend.tools.uncertainty_aware_prediction import predict_with_uncertainty

    candidates = state.get("valid_candidates", [])
    smis = [(c.get("full_protac_smiles") or c.get("smiles") or "") for c in candidates]
    smis = [s for s in smis if s]
    if not smis:
        return NodeResult(
            updates={"status": "needs_repair"},
            decision=DecisionLog(
                node="parallel_degradation", decision_type="retry",
                reason_codes=(ReasonCode.EVIDENCE_INSUFFICIENT,),
                evidence_refs=(), tool_version="adaptive-v1",
                confidence=0.0, next_proposed_node="repair_controller",
                failure_class=FailureClass.MISSING_INPUT,
            ),
        ).to_state()

    # The prediction layer itself batches; split into chunks for parallelism.
    def _chunk_eval(chunk: List[str]) -> List[Dict[str, Any]]:
        return predict_with_uncertainty(chunk, use_conformal=True)

    chunk_size = max(1, len(smis) // 4)
    chunks = [smis[i:i + chunk_size] for i in range(0, len(smis), chunk_size)]
    chunk_results = parallel_evaluate(chunks, _chunk_eval, max_workers=4)

    flat: List[Dict[str, Any]] = []
    for cr in chunk_results:
        if "evaluation_error" in cr:
            flat.append(cr)
        else:
            flat.extend(cr)

    preds = []
    for i, r in enumerate(flat):
        if "evaluation_error" in r:
            preds.append({"candidate_id": candidates[i].get("candidate_id", i),
                          "verdict": "low_confidence", "error": r["evaluation_error"]})
        else:
            preds.append({"candidate_id": candidates[i].get("candidate_id", i),
                          **{k: v for k, v in r.items() if k != "smiles"}})

    return NodeResult(
        updates={"degradation_predictions": preds, "status": "ok"},
        decision=DecisionLog(
            node="parallel_degradation", decision_type="accept",
            reason_codes=(ReasonCode.TERNARY_CONF_OK,),
            evidence_refs=("degradation_predictions",), tool_version="adaptive-v1",
            confidence=0.8, next_proposed_node="route",
        ),
    ).to_state()


# ═══════════════════════════════════════════════════════════════
# 5. Human approval gate before expensive modelling (cap. 7)
# ═══════════════════════════════════════════════════════════════

def expensive_modeling_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause before any expensive step (P4ward hours, MD days).

    Emits an escalation packet; in a checkpointer-enabled graph this is where
    interrupt() would pause. Deterministic verdict: needs_human.
    """
    tool_plan = state.get("evidence", {}).get("tool_plan", {})
    ternary = tool_plan.get("ternary", {})
    if ternary.get("cost") == "hours":
        reason = f"P4ward will run for hours — approve before spending compute"
    elif ternary.get("tool") == "none":
        reason = "No structural evidence — approve evidence collection plan"
    else:
        reason = "Pre-ranking review of top candidates"

    return NodeResult(
        updates={"status": "needs_human", "pipeline_status": "paused_for_human"},
        decision=DecisionLog(
            node="expensive_modeling_gate", decision_type="gate",
            reason_codes=(ReasonCode.HUMAN_REQUIRED,),
            evidence_refs=("tool_plan",), tool_version="adaptive-v1",
            confidence=0.0, next_proposed_node="report",
        ),
    ).to_state()


def route_after_expensive_gate(state: Dict[str, Any]) -> str:
    """After human approval, proceed to the selected tool path."""
    plan = state.get("evidence", {}).get("tool_plan", {})
    ternary = plan.get("ternary", {})
    if ternary.get("tool") == "p4ward":
        return "p4ward_runner"
    if ternary.get("tool") == "geometric_proxy":
        return "ternary_feasibility"
    return "collect_evidence"
