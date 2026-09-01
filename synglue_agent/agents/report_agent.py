"""Report generation agent."""

from __future__ import annotations

from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import WorkflowState


class ReportAgent(ReActAgent):
    name = "ReportAgent"
    thought = "Generate transparent candidate table, workflow summary, provenance, warnings, and scientific limitations."
    action = "generate_report"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.report = self.toolbox.generate_markdown_report(state)
        state.pipeline_status = self.toolbox.generate_pipeline_status_table(state)
        return state

    def _observation(self, state: WorkflowState) -> str:
        return f"report_chars={len(state.report)}"
