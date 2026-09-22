"""End-to-end decision trajectory (Section 12).

Each discovery step is scored independently: decision validity, evidence
adequacy, mechanistic coherence, constraint satisfaction, consistency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Canonical discovery trajectory steps (Section 2)
TRAJECTORY_STEPS: List[str] = [
    "target_validated",
    "tpd_appropriate",
    "e3_selected",
    "warhead_selected",
    "exit_vector_selected",
    "linker_selected",
    "structure_modeled",
    "candidate_selected",
    "experiment_selected",
]


@dataclass
class StepDecision:
    step: str
    decision: Optional[str] = None
    valid: Optional[bool] = None            # matches truth / accepted alternative
    evidence_adequate: Optional[bool] = None
    mechanistically_coherent: Optional[bool] = None
    constraints_satisfied: Optional[bool] = None
    rationale: str = ""


def score_trajectory(steps: List[StepDecision],
                     expected_order: Optional[List[str]] = None) -> Dict[str, Any]:
    by = {s.step: s for s in steps}
    present = [s.step for s in steps]

    def rate(attr: str) -> Optional[float]:
        vals = [getattr(s, attr) for s in steps if getattr(s, attr) is not None]
        return round(sum(1 for v in vals if v) / len(vals), 4) if vals else None

    order_ok = True
    if expected_order:
        idx = {s: i for i, s in enumerate(present)}
        seq = [idx[e] for e in expected_order if e in idx]
        order_ok = seq == sorted(seq)

    missing = [s for s in (expected_order or TRAJECTORY_STEPS) if s not in by]
    return {
        "n_steps": len(steps),
        "missing_steps": missing,
        "decision_validity": rate("valid"),
        "evidence_adequacy": rate("evidence_adequate"),
        "mechanistic_coherence": rate("mechanistically_coherent"),
        "constraint_satisfaction": rate("constraints_satisfied"),
        "order_consistent": order_ok,
        "per_step": [
            {"step": s.step, "decision": s.decision, "valid": s.valid,
             "evidence_adequate": s.evidence_adequate,
             "mechanistically_coherent": s.mechanistically_coherent,
             "constraints_satisfied": s.constraints_satisfied}
            for s in steps
        ],
    }


def decision_consistency(rep_trajectories: List[List[StepDecision]]) -> Dict[str, Any]:
    """Across repeats of the same task: fraction of steps with identical decision."""
    if len(rep_trajectories) < 2:
        return {"n_repeats": len(rep_trajectories), "consistency": None}
    maps = [{s.step: s.decision for s in t} for t in rep_trajectories]
    all_steps = set().union(*[set(m) for m in maps])
    agree = 0
    for step in all_steps:
        vals = [m.get(step) for m in maps]
        if len(set(map(str, vals))) == 1:
            agree += 1
    return {"n_repeats": len(maps),
            "consistency": round(agree / len(all_steps), 4) if all_steps else 1.0}
