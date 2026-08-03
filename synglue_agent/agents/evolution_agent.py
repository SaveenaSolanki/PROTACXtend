"""Evolution / refinement agent."""

from __future__ import annotations

from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import WorkflowState


class EvolutionRefinementAgent(ReActAgent):
    name = "EvolutionRefinementAgent"
    thought = "Use review and ADME/Tox weaknesses to propose deterministic linker replacements and re-score evolved candidates."
    action = "evolution_refinement"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        evolved = self.toolbox.evolve_candidates(
            state.valid_candidates,
            state.ranking_results,
            state.admet_predictions,
            state.target_record,
            max_new=max(2, min(8, state.parsed_objective.candidate_count // 5)),
        )
        state.evolved_candidates = self.toolbox.validate_candidates(evolved)
        if state.evolved_candidates:
            state.valid_candidates = self.toolbox.remove_duplicate_candidates(list(state.valid_candidates) + state.evolved_candidates)
            state.degradation_predictions = self.toolbox.predict_degradation(state.valid_candidates, state.target_record)
            state.admet_predictions = self.toolbox.predict_admet(state.valid_candidates)
            state.novelty_results = self.toolbox.check_novelty(state.valid_candidates)
            state.applicability_domain_results = self.toolbox.compute_applicability_domain(state.valid_candidates)
            state.ranking_results = self.toolbox.rank_candidates(
                state.valid_candidates,
                state.degradation_predictions,
                state.admet_predictions,
                state.novelty_results,
                state.applicability_domain_results,
                state.ternary_feasibility_results,
                state.parsed_objective.ranking_weights,
            )
        return state

    def _observation(self, state: WorkflowState) -> str:
        return f"evolved={len(state.evolved_candidates)}, candidate_pool={len(state.valid_candidates)}"


def refine_candidate(*args, **kwargs):
    return EvolutionRefinementAgent().toolbox.evolve_candidates(*args, **kwargs)


def propose_linker_replacement(*args, **kwargs):
    return refine_candidate(*args, **kwargs)


def propose_e3_switch(candidate):
    return {"candidate_id": candidate.candidate_id, "action": "try alternate CRBN/VHL branch if compatible"}


def propose_exit_vector_change(candidate):
    return {"candidate_id": candidate.candidate_id, "action": "request curated alternate exit-vector map"}


def optimize_candidate_set(*args, **kwargs):
    return refine_candidate(*args, **kwargs)
