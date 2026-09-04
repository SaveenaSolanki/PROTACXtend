"""Degradation prediction and applicability-domain agents."""

from __future__ import annotations

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WorkflowState


class DegradationPredictionAgent(ReActAgent):
    name = "DegradationPredictionAgent"
    thought = "Predict DC50, Dmax, degradation probability, confidence, and model-version provenance."
    action = "predict_degradation"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.degradation_predictions = self.toolbox.predict_degradation(
            state.valid_candidates,
            state.target_record,
            state.parsed_objective.cell_line,
            state.parsed_objective.assay_context,
        )
        return state

    def _observation(self, state: WorkflowState) -> str:
        low_conf = sum(1 for item in state.degradation_predictions if item.model_confidence < 0.45)
        return f"predictions={len(state.degradation_predictions)}, low_confidence={low_conf}"


class ApplicabilityDomainAgent(ReActAgent):
    name = "ApplicabilityDomainAgent"
    thought = "Assess whether candidates are inside the demo model domain before ranking."
    action = "assess_applicability_domain"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.applicability_domain_results = self.toolbox.compute_applicability_domain(state.valid_candidates)
        return state

    def _observation(self, state: WorkflowState) -> str:
        outside = sum(1 for item in state.applicability_domain_results if item.domain_status == "outside")
        return f"domain_results={len(state.applicability_domain_results)}, outside={outside}"
