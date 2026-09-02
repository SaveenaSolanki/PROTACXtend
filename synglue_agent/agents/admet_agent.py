"""ADME/Tox agent."""

from __future__ import annotations

from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import WorkflowState


class ADMETAgent(ReActAgent):
    name = "ADMETAgent"
    thought = "Compute PROTAC-aware descriptor and toxicity-risk triage without strict Lipinski rejection."
    action = "predict_admet"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.admet_predictions = self.toolbox.predict_admet(state.valid_candidates)
        return state

    def _observation(self, state: WorkflowState) -> str:
        high = sum(1 for item in state.admet_predictions if "high" in {item.hERG_risk, item.DILI_risk, item.AMES_risk})
        return f"admet={len(state.admet_predictions)}, high_risk_records={high}"
