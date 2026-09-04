"""Rubric scoring infrastructure (Sprint 2B).

- mechanistic & design rubric schemas
- explicit 0-4 anchors for every dimension
- blind system identifiers for expert review
- randomized answer presentation (seed-controlled)
- two-reviewer scoring + disagreement-resolution fields
- inter-rater reliability computation
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCALE = 4  # 0..4

# shared 0-4 anchors (custom per dimension via dimension_anchors)
ANCHOR_0_4 = {
    0: "absent / fundamentally wrong / unsupported",
    1: "minimal / mostly wrong / major gaps",
    2: "partial / some valid points, missing key elements",
    3: "good / valid with minor gaps or minor unsupported claims",
    4: "complete / valid / fully supported with correct provenance",
}

MECHANISTIC_DIMENSIONS = [
    "evidence_grounding",       # uses permitted sources, no fabricated citations
    "mechanism_completeness",   # covers target-warhead-E3-linker-ternary-ubiquitination chain as required
    "uncertainty_handling",     # separates measured/retrieved/calculated/predicted/missing
    "conclusion_validity",      # conclusion follows from evidence
    "hallucination_avoidance",  # no fabricated numbers/citations
]
DESIGN_DIMENSIONS = [
    "constraint_compliance",    # chemistry validity + stated constraints
    "design_rationale",         # reasoning for scaffold/linker/vector choices
    "scientific_quality",       # novelty/feasibility sense
    "uncertainty_handling",
    "hallucination_avoidance",
]

RUBRIC_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "mechanistic_rubric": {
        "dimensions": MECHANISTIC_DIMENSIONS,
        "scale_max": SCALE,
        "anchors": ANCHOR_0_4,
        "dimension_anchors": {d: ANCHOR_0_4 for d in MECHANISTIC_DIMENSIONS},
    },
    "design_rubric": {
        "dimensions": DESIGN_DIMENSIONS,
        "scale_max": SCALE,
        "anchors": ANCHOR_0_4,
        "dimension_anchors": {d: ANCHOR_0_4 for d in DESIGN_DIMENSIONS},
    },
}

DEFAULT_WEIGHTS = {
    "mechanistic_rubric": {"evidence_grounding": .25, "mechanism_completeness": .30,
                            "uncertainty_handling": .20, "conclusion_validity": .15,
                            "hallucination_avoidance": .10},
    "design_rubric": {"constraint_compliance": .30, "design_rationale": .30,
                       "scientific_quality": .20, "uncertainty_handling": .10,
                       "hallucination_avoidance": .10},
}


def validate_rubric_schema(rubric_type: str) -> Dict[str, Any]:
    if rubric_type not in RUBRIC_SCHEMAS:
        raise ValueError(f"unknown rubric {rubric_type!r}")
    return RUBRIC_SCHEMAS[rubric_type]


def rubric_weighted(scores: Dict[str, float], rubric_type: str) -> Dict[str, Any]:
    schema = validate_rubric_schema(rubric_type)
    dims = schema["dimensions"]
    weights = DEFAULT_WEIGHTS[rubric_type]
    total = 0.0
    per = {}
    for d in dims:
        s = max(0, min(float(scores.get(d, 0)), SCALE)) / SCALE
        per[d] = round(s, 4)
        total += weights.get(d, 0) * s
    return {"rubric_type": rubric_type, "dimensions": per,
            "weighted": round(total, 4), "scale_max": SCALE}


@dataclass
class ExpertReview:
    """One reviewer's blind scoring of one anonymized answer."""

    answer_index: int               # randomized presentation index (no system id)
    rubric_type: str
    dimension_scores: Dict[str, float]
    notes: str = ""
    reviewer_id: str = ""

    def __post_init__(self):
        validate_rubric_schema(self.rubric_type)
        schema = RUBRIC_SCHEMAS[self.rubric_type]
        for d in schema["dimensions"]:
            if d not in self.dimension_scores:
                self.dimension_scores[d] = 0.0


def anonymize_and_shuffle(answers: List[Dict[str, Any]], seed: int) -> List[Dict[str, Any]]:
    """Copy answers, strip system id, randomize presentation order."""
    rng = random.Random(seed)
    items = [{"answer_index": i, "answer": a.get("answer"),
              "summary": a.get("summary", ""), "system": a.get("system")}
             for i, a in enumerate(answers)]
    rng.shuffle(items)
    for i, it in enumerate(items):
        it["answer_index"] = i
        it.pop("system", None)  # blind system identifiers
    return items


def irr_kappa(reviews_a: Dict[str, float], reviews_b: Dict[str, float]) -> Dict[str, Any]:
    """Cohen-style agreement across dimensions using a ±1 tolerance.

    Returns per-dimension observed agreement, expected (chance) agreement
    from the pooled marginal distribution of scores, and kappa.
    """
    dims = sorted(set(reviews_a) | set(reviews_b))
    out: Dict[str, Any] = {}
    n_dims = len(dims)
    if n_dims == 0:
        return {"kappa": 0.0, "observed": 0.0, "expected": 0.0}
    all_scores = [reviews_a.get(d, 0.0) for d in dims] + \
                 [reviews_b.get(d, 0.0) for d in dims]
    distribution: Dict[float, float] = {}
    for s in all_scores:
        distribution[s] = distribution.get(s, 0.0) + 1
    total = len(all_scores) or 1
    expected = sum((v / total) ** 2 for v in distribution.values())
    agree = 0
    for d in dims:
        if abs(reviews_a.get(d, 0) - reviews_b.get(d, 0)) <= 1.0:
            agree += 1
    observed = agree / n_dims
    denom = 1 - expected
    kappa = (observed - expected) / denom if denom > 0 else 1.0
    return {"kappa": round(kappa, 4), "observed": round(observed, 4),
            "expected": round(expected, 4), "dimensions": dims,
            "method": "cohen-style tolerance agreement"}


def export_expert_review(
    rubric_type: str,
    answers: List[Dict[str, Any]],
    reviews: List[ExpertReview],
    seed: int = 7,
    threshold_disagreement: float = 1.0,
) -> Dict[str, Any]:
    """Blind, two-reviewer expert review export with disagreement fields."""
    schema = validate_rubric_schema(rubric_type)
    shuffled = anonymize_and_shuffle(answers, seed)
    by_index = {r.answer_index: r for r in reviews}
    groups: Dict[int, List[ExpertReview]] = {}
    for r in reviews:
        groups.setdefault(r.answer_index, []).append(r)
    items = []
    for item in shuffled:
        idx = item["answer_index"]
        revs = groups.get(idx, [])
        scores = [r.dimension_scores for r in revs]
        resolved = {}
        if len(scores) == 2:
            a, b = scores[0], scores[1]
            for d in schema["dimensions"]:
                va, vb = a.get(d, 0), b.get(d, 0)
                if abs(va - vb) > threshold_disagreement:
                    resolved[d] = {"disagreement": True, "reviewer_a": va,
                                   "reviewer_b": vb,
                                   "adjudicated": None,  # filled by adjudicator
                                   "adjudicator": ""}
                else:
                    resolved[d] = {"disagreement": False, "reviewer_a": va,
                                   "reviewer_b": vb,
                                   "adjudicated": (va + vb) / 2, "adjudicator": "mean"}
        items.append({
            "answer_index": idx,
            "rubric_type": rubric_type,
            "dimension_scores": scores,
            "disagreement_resolution": resolved,
            "notes": [r.notes for r in revs],
        })
    irr = {}
    for revs in groups.values():
        if len(revs) == 2:
            irr = irr_kappa(revs[0].dimension_scores, revs[1].dimension_scores)
            break
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "system_ids_blinded": True,
        "items": items,
        "inter_rater_reliability": irr,
    }
