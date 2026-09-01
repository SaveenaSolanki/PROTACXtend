"""Ranking and tournament agent."""

from __future__ import annotations

from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import WorkflowState


class RankingAgent(ReActAgent):
    name = "RankingTournamentAgent"
    thought = "Rank candidates with weighted multi-objective scoring and pairwise-comparator-compatible outputs."
    action = "rank_candidates"

    def __init__(self, final: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.final = final
        if final:
            self.name = "FinalRankingTournamentAgent"
            self.action = "final_ranking"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.ranking_results = self.toolbox.rank_candidates(
            state.valid_candidates,
            state.degradation_predictions,
            state.admet_predictions,
            state.novelty_results,
            state.applicability_domain_results,
            state.ternary_feasibility_results,
            state.cooperativity_predictions,
            state.hook_effect_predictions,
            state.e3_context_predictions,
            state.parsed_objective.ranking_weights,
        )
        if self.final:
            state.final_ranked_candidates = self.toolbox.choose_diverse_representatives(
                state.valid_candidates,
                state.ranking_results,
                max_count=max(1, min(state.parsed_objective.candidate_count, len(state.valid_candidates))),
            )
        return state

    def _observation(self, state: WorkflowState) -> str:
        top = state.ranking_results[0].final_priority_score if state.ranking_results else None
        return f"ranked={len(state.ranking_results)}, top_score={top}"
