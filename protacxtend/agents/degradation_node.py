"""
Real degradation_prediction node — wires the validated, uncertainty-aware
Chemprop layer (B1 + capability 5) into the agentic graph.

Replaces the heuristic/stub degradation step. Reads candidate SMILES from
state, runs predict_with_uncertainty, stores structured predictions with
verdict + confidence that the existing degradation router consumes:
  - high/medium confidence → proceed to ADMET
  - low confidence        → repair (bounded) → escalate to human gate
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from protacxtend.agents.state import NodeResult, DecisionLog, ReasonCode
from protacxtend.tools.uncertainty_aware_prediction import (
    predict_with_uncertainty,
    ENSEMBLE_PATHS,
)

logger = logging.getLogger("protacpilot.degradation_node")

VERDICT_CONFIDENCE = {
    "high_confidence": 0.85,
    "medium_confidence": 0.55,
    "low_confidence": 0.20,
}


def degradation_prediction_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the validated uncertainty-aware degradation layer on candidates.

    Reads candidates from state['valid_candidates'] (each may carry
    'full_protac_smiles' or 'smiles'). Falls back to a 'not_run' result
    when no model is available (so the graph can route to repair).
    """
    candidates = state.get("valid_candidates", [])
    if not candidates:
        return {
            "decision_log": [DecisionLog(
                node="degradation_prediction", decision_type="reject",
                reason_codes=(ReasonCode.EVIDENCE_INSUFFICIENT,),
                evidence_refs=(), tool_version="degradation-node-v1",
                confidence=0.0, next_proposed_node="repair_controller",
            ).to_dict()],
            "warnings": ["degradation_prediction: no candidates to score"],
            "status": "needs_repair",
        }

    smiles_list = []
    idx_of = {}
    for i, c in enumerate(candidates):
        smi = c.get("full_protac_smiles") or c.get("smiles") or ""
        if smi:
            idx_of[len(smiles_list)] = i
            smiles_list.append(smi)

    if not smiles_list:
        return {
            "decision_log": [DecisionLog(
                node="degradation_prediction", decision_type="reject",
                reason_codes=(ReasonCode.EVIDENCE_INSUFFICIENT,),
                evidence_refs=(), tool_version="degradation-node-v1",
                confidence=0.0, next_proposed_node="repair_controller",
            ).to_dict()],
            "warnings": ["degradation_prediction: candidates carry no SMILES"],
            "status": "needs_repair",
        }

    # ── Run the validated layer (ensemble + conformal + AD) ──
    try:
        results = predict_with_uncertainty(smiles_list, use_conformal=True)
    except Exception as exc:
        logger.error("degradation node failed: %s", exc)
        return {
            "decision_log": [DecisionLog(
                node="degradation_prediction", decision_type="reject",
                reason_codes=(ReasonCode.HARD_ERROR,),
                evidence_refs=(), tool_version="degradation-node-v1",
                confidence=0.0, next_proposed_node="repair_controller",
            ).to_dict()],
            "errors": [f"degradation_prediction: {exc}"],
            "status": "needs_repair",
        }

    predictions = []
    for j, r in enumerate(results):
        cand_idx = idx_of.get(j)
        pred = {
            "candidate_id": candidates[cand_idx].get("candidate_id", f"c{j}") if cand_idx is not None else f"c{j}",
            "dc50_nM": r.get("dc50_nM"),
            "log_dc50": r.get("log_dc50"),
            "uncertainty_log10": r.get("unc_log10"),
            "applicability_status": r.get("ad_status"),
            "nn_tanimoto": r.get("nn_tanimoto"),
            "verdict": r.get("verdict"),
            "model_confidence": VERDICT_CONFIDENCE.get(r.get("verdict"), 0.2),
            "model_version": "chemprop-ensemble-conformal-v1",
            "evidence_type": "trained_model",
        }
        predictions.append(pred)

    min_conf = min((p["model_confidence"] for p in predictions), default=0.2)
    low_conf = sum(1 for p in predictions if p["verdict"] == "low_confidence")

    return {
        "degradation_predictions": predictions,
        "evidence": {
            "degradation": {
                "degradation_confidence": min_conf,
                "n_candidates": len(predictions),
                "n_low_confidence": low_conf,
                "status": "ok",
            }
        },
        "decision_log": [DecisionLog(
            node="degradation_prediction", decision_type="accept",
            reason_codes=(ReasonCode.TERNARY_CONF_OK,) if min_conf >= 0.4
                          else (ReasonCode.TERNARY_CONF_LOW,),
            evidence_refs=("degradation_predictions",),
            tool_version="degradation-node-v1",
            confidence=min_conf,
            next_proposed_node="route",
        ).to_dict()],
        "status": "ok" if min_conf >= 0.4 else "needs_repair",
        "warnings": [] if min_conf >= 0.4 else [
            f"degradation_prediction: {low_conf}/{len(predictions)} candidates low-confidence"
        ],
    }


def degradation_router(state: Dict[str, Any]) -> str:
    """Route on the validated verdicts (replaces heuristic threshold only).

    - no predictions / all low → repair_controller (bounded) then human gate
    - mixed or medium → admet_prediction (proceed, flagged)
    - high → admet_prediction
    """
    preds = state.get("degradation_predictions", [])
    if not preds:
        return "repair_controller"
    min_conf = min((p.get("model_confidence", 0.0) for p in preds), default=0.0)
    if min_conf < 0.35:
        retries = state.get("retry_counts", {}).get("degradation", 0)
        return "repair_controller" if retries < 3 else "human_gate"
    return "admet_prediction"
