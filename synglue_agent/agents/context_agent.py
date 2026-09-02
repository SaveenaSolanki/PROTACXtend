"""Cell-context and E3 expression scoring agent."""

from __future__ import annotations

from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import WorkflowState


class CellContextAgent(ReActAgent):
    name = "CellContextAgent"
    thought = "Score E3/target compatibility using explicit cell-line and expression context."
    action = "score_cell_type_e3_context"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.e3_context_predictions = self.toolbox.score_e3_context(
            state.valid_candidates,
            state.target_record,
            state.parsed_objective.cell_line,
            state.parsed_objective.expression_overrides,
        )
        return state

    def _observation(self, state: WorkflowState) -> str:
        weak = sum(1 for item in state.e3_context_predictions if item.total_context_score < 0.45)
        context = state.parsed_objective.cell_line or "default"
        return f"context={context}, e3_context_records={len(state.e3_context_predictions)}, weak={weak}"
