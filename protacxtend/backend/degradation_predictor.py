"""Backend adapter for DC50/Dmax model infrastructure."""

from __future__ import annotations

from typing import Any, Sequence

from protacxtend.backend.schemas import CandidateRecord, DegradationPrediction, TargetRecord
from protacxtend.models.degradation_model import (
    discover_degradation_models,
    featurize_protac_for_degradation,
    load_dc50_model,
    load_dmax_model,
    predict_dc50_dmax,
    predict_with_uncertainty,
)


def predict_candidate_degradation(candidate: CandidateRecord, backend: str = "auto") -> dict[str, Any]:
    return predict_dc50_dmax(candidate, backend=backend)


def predict_candidate_with_uncertainty(candidate: CandidateRecord) -> dict[str, Any]:
    return predict_with_uncertainty(candidate)


def predict_batch_degradation(
    candidates: Sequence[CandidateRecord],
    target_record: TargetRecord | None = None,
    backend: str = "auto",
) -> list[DegradationPrediction]:
    rows: list[DegradationPrediction] = []
    for candidate in candidates:
        result = predict_dc50_dmax(candidate, backend=backend)
        status = result.get("status", "unknown")
        model_meta = result.get("model_metadata", {}) or {}
        dc50_meta = model_meta.get("dc50", {}) if isinstance(model_meta, dict) else {}
        version = dc50_meta.get("version") or "SynGlue-demo-heuristic-v0.1"
        warning = f"backend={result.get('backend_used')}; status={status}; limitations={result.get('limitations')}"
        rows.append(
            DegradationPrediction(
                candidate_id=candidate.candidate_id,
                predicted_dc50_nM=result.get("predicted_dc50_nM"),
                predicted_logdc50=None,
                predicted_dmax_percent=result.get("predicted_dmax_percent"),
                degradation_probability=0.0,
                model_confidence=0.0,
                applicability_domain_score=0.0,
                model_version=str(version),
                warning=warning,
            )
        )
    return rows


__all__ = [
    "discover_degradation_models",
    "load_dc50_model",
    "load_dmax_model",
    "featurize_protac_for_degradation",
    "predict_dc50_dmax",
    "predict_with_uncertainty",
    "predict_candidate_degradation",
    "predict_candidate_with_uncertainty",
    "predict_batch_degradation",
]

