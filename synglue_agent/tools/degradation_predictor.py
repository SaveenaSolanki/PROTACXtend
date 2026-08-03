"""SynGlue degradation model wrappers."""

from __future__ import annotations

from typing import Sequence

from synglue_agent.backend.schemas import CandidateRecord, TargetRecord
from synglue_agent.backend.degradation_predictor import (
    discover_degradation_models,
    featurize_protac_for_degradation,
    load_dc50_model as backend_load_dc50_model,
    load_dmax_model as backend_load_dmax_model,
    predict_batch_degradation,
    predict_candidate_with_uncertainty,
)
from synglue_agent.models.degradation_model import predict_dc50_dmax as predict_one_dc50_dmax


def load_dc50_model(model_path: str | None = None):
    if model_path:
        return backend_load_dc50_model(model_path)
    discovered = discover_degradation_models()
    if not discovered["dc50_candidates"]:
        return {"status": "model_missing", "success": False, "error": discovered["error"]}
    return backend_load_dc50_model(discovered["dc50_candidates"][0])


def load_dmax_model(model_path: str | None = None):
    if model_path:
        return backend_load_dmax_model(model_path)
    discovered = discover_degradation_models()
    if not discovered["dmax_candidates"]:
        return {"status": "model_missing", "success": False, "error": discovered["error"]}
    return backend_load_dmax_model(discovered["dmax_candidates"][0])


def featurize_component_sequence(candidate: CandidateRecord) -> dict:
    return featurize_protac_for_degradation(candidate)


def predict_dc50_dmax(candidates: Sequence[CandidateRecord], target_record: TargetRecord | None = None):
    return predict_batch_degradation(candidates, target_record, backend="auto")


def estimate_prediction_confidence(candidate: CandidateRecord) -> float:
    result = predict_candidate_with_uncertainty(candidate)
    uncertainty = result.get("uncertainty", {})
    if uncertainty.get("available") and uncertainty.get("dc50_std") is not None:
        std = float(uncertainty["dc50_std"])
        return max(0.0, min(1.0, 1.0 / (1.0 + std)))
    return 0.0


def compute_applicability_domain(candidate: CandidateRecord) -> float:
    result = predict_one_dc50_dmax(candidate, backend="auto")
    return 1.0 if result.get("status") == "model_loaded" else 0.0
