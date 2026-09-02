"""Candidate ranking functions."""

from __future__ import annotations

from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def compute_dc50_score(dc50_nM: float | None) -> float:
    return _TOOLBOX.compute_dc50_score(dc50_nM)


def compute_dmax_score(dmax_percent: float | None) -> float:
    return _TOOLBOX.compute_dmax_score(dmax_percent)


def compute_admet_score(admet_penalty: float) -> float:
    return max(0.0, min(1.0, 1.0 - admet_penalty))


def compute_novelty_score(novelty_score: float) -> float:
    return max(0.0, min(1.0, novelty_score))


def compute_synthetic_score(synthetic_feasibility_score: float) -> float:
    return max(0.0, min(1.0, synthetic_feasibility_score))


def compute_final_priority_score(*args, **kwargs):
    return _TOOLBOX.rank_candidates(*args, **kwargs)


def assign_candidate_tier(score: float, confidence: float) -> str:
    return _TOOLBOX.assign_candidate_tier(score, confidence)


def pairwise_tournament_ranking(*args, **kwargs):
    return _TOOLBOX.rank_candidates(*args, **kwargs)
