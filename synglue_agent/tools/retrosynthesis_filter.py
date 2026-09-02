"""Retrosynthesis-aware feasibility filter stubs."""

from __future__ import annotations

from synglue_agent.backend.schemas import CandidateRecord


def retrosynthesis_feasibility_filter(candidate: CandidateRecord, threshold: float = 0.45) -> bool:
    return candidate.synthetic_feasibility_score >= threshold


def explain_retrosynthesis_score(candidate: CandidateRecord) -> str:
    if candidate.synthetic_feasibility_score >= 0.65:
        return "High demo feasibility: common linker and component attachment pattern."
    if candidate.synthetic_feasibility_score >= 0.45:
        return "Medium demo feasibility: plausible but requires route review."
    return "Low demo feasibility: route should be reviewed before prioritization."
