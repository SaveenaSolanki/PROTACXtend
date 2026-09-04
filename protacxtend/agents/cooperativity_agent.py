"""Cooperativity and hook-effect prediction agents."""

from __future__ import annotations

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WorkflowState


class CooperativityPredictionAgent(ReActAgent):
    name = "CooperativityPredictionAgent"
    thought = "Estimate ternary cooperativity from interface, linker strain, lysine geometry, and ternary feasibility evidence."
    action = "predict_cooperativity"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.cooperativity_predictions = self.toolbox.predict_cooperativity(
            state.valid_candidates,
            state.ternary_feasibility_results,
        )
        return state

    def _observation(self, state: WorkflowState) -> str:
        anti = sum(1 for item in state.cooperativity_predictions if item.predicted_alpha < 1.0)
        return f"cooperativity_records={len(state.cooperativity_predictions)}, anti_cooperative={anti}"


class HookEffectPredictionAgent(ReActAgent):
    name = "HookEffectPredictionAgent"
    thought = "Model concentration-dependent ternary occupancy to detect high-dose hook-effect risk."
    action = "predict_hook_effect"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.hook_effect_predictions = self.toolbox.predict_hook_effect(
            state.valid_candidates,
            state.degradation_predictions,
            state.cooperativity_predictions,
            state.e3_context_predictions,
        )
        return state

    def _observation(self, state: WorkflowState) -> str:
        high = sum(1 for item in state.hook_effect_predictions if item.hook_risk == "high")
        return f"hook_records={len(state.hook_effect_predictions)}, high_hook_risk={high}"
