"""Separate-metric scoring orchestration (Sections 21 & 25).

Primary output is a dict of *independent* dimension scores. A composite is
computed only secondarily and is explicitly labelled as such. Claim-boundary
language is attached to every aggregate so no downstream reader can mistake a
model score for experimental validation.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from tpdeval.taskmodel import ScoreRecord

# Default weights for the SECONDARY composite only. Never collapse before reporting.
SECONDARY_WEIGHTS: Dict[str, float] = {
    "scientific_correctness": 0.18,
    "evidence_grounding": 0.12,
    "mechanistic_correctness": 0.16,
    "tpd_decision_quality": 0.14,
    "experimental_design": 0.10,
    "tool_selection": 0.06,
    "tool_execution": 0.06,
    "quantitative_correctness": 0.06,
    "uncertainty_calibration": 0.04,
    "failure_recovery": 0.04,
    "temporal_compliance": 0.02,
    "reproducibility": 0.02,
}

FAILURE_CRITERIA = (
    "fabricated_experimental_result_presented_as_measured",
    "fake_or_uncited_primary_citation",
    "use_of_forbidden_information_or_ground_truth",
    "refusal_to_separate_measured_retrieved_calculated_predicted_missing",
    "missing_or_schema_invalid_deliverable",
    "overclaim_of_experimental_or_clinical_validation",
)


def composite_secondary(dimensions: Dict[str, Optional[float]],
                        weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    w = weights or SECONDARY_WEIGHTS
    num = den = 0.0
    used = {}
    for k, wk in w.items():
        v = dimensions.get(k)
        if v is None:
            continue
        num += wk * float(v)
        den += wk
        used[k] = wk
    score = round(num / den, 4) if den else None
    return {
        "composite_secondary": score,
        "weights_used": used,
        "coverage": round(den / sum(w.values()), 4) if w else 0.0,
        "label": "SECONDARY composite (report dimensions separately first)",
        "claim_boundary": claim_boundary(),
    }


def claim_boundary() -> str:
    return (
        "Scores reflect performance on a computational benchmark under stated "
        "evidence/tool constraints. Tool success is not scientific validation; "
        "docking scores are not experimental affinities; predicted degradation is "
        "not measured degradation; benchmark performance is not clinical utility. "
        "All outputs are computationally supported / model-supported hypotheses "
        "requiring experimental validation.")


def score_run(run_scores: Dict[str, Optional[float]],
              expert_scores: Optional[Dict[str, Any]] = None,
              triggered_failures: Optional[list] = None) -> ScoreRecord:
    """Build a ScoreRecord. A triggered failure criterion forces FAIL semantics."""
    rec = ScoreRecord(run_id=run_scores.get("run_id", ""),
                      task_id=run_scores.get("task_id", ""),
                      system=run_scores.get("system", ""))
    for dim in ScoreRecord.DIMENSIONS:
        if dim in run_scores:
            setattr(rec, dim, run_scores[dim])
    rec.expert_scores = expert_scores or {}
    failures = [f for f in (triggered_failures or []) if f in FAILURE_CRITERIA]
    rec.notes = ("; ".join(failures) if failures else "")
    rec.composite_secondary = composite_secondary(
        {d: getattr(rec, d) for d in ScoreRecord.DIMENSIONS})["composite_secondary"]
    return rec


def verdict(composite: Optional[float], triggered_failures: Optional[list] = None) -> str:
    if triggered_failures:
        return "FAIL"
    if composite is None:
        return "CONDITIONAL"
    if composite >= 0.75:
        return "PASS"
    if composite >= 0.50:
        return "CONDITIONAL"
    return "FAIL"
