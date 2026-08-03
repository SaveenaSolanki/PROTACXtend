"""Reflection / review agent."""

from __future__ import annotations

from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import WorkflowState


class ReflectionReviewAgent(ReActAgent):
    name = "ReflectionReviewAgent"
    thought = "Critique top candidates for evidence strength, overclaims, ADME/Tox risk, novelty, and synthesis plausibility."
    action = "reflection_review"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        top_ids = {ranking.candidate_id for ranking in state.ranking_results[: min(20, len(state.ranking_results))]}
        top_candidates = [candidate for candidate in state.valid_candidates if candidate.candidate_id in top_ids]
        state.reflection_reviews = self.toolbox.critique_candidates(
            top_candidates,
            state.ranking_results,
            state.degradation_predictions,
            state.admet_predictions,
            state.novelty_results,
        )
        return state

    def _observation(self, state: WorkflowState) -> str:
        risks = sum(1 for item in state.reflection_reviews if item.risk_score > 0.3)
        return f"reviews={len(state.reflection_reviews)}, high_review_risk={risks}"


def critique_candidate(*args, **kwargs):
    return ReflectionReviewAgent().toolbox.critique_candidates(*args, **kwargs)


def check_evidence_consistency(review) -> str:
    return getattr(review, "factual_consistency_check", "unchecked")


def identify_overclaims(review) -> str | None:
    return getattr(review, "overclaiming_warning", None)


def score_plausibility(review) -> float:
    return getattr(review, "plausibility_score", 0.0)


def recommend_refinement(review) -> list[str]:
    return getattr(review, "recommendations", [])
