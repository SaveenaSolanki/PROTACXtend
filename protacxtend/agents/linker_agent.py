"""Linker generation agent."""

from __future__ import annotations

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WorkflowState
from protacxtend.tools.protac_autopilot_toolbox import ProtacXtendToolbox


class LinkerGenerationAgent(ReActAgent):
    name = "LinkerGenerationAgent"
    thought = "Generate curated and rule-based linker candidates matching requested classes and PROTAC-aware constraints."
    action = "generate_linkers"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        xtend = ProtacXtendToolbox(self.toolbox)
        state.generated_linkers = xtend.linkers.generate_state_of_the_art_linker_panel(
            state.parsed_objective.preferred_linker_types,
            max_linkers=state.search_policy.linker_budget,
        )
        if not state.generated_linkers:
            state.generated_linkers = self.toolbox.generate_rule_based_linkers(["PEG", "alkyl", "piperazine", "triazole"])
            state.warnings.append("Requested linker generation failed; relaxed to default rule-based linker library.")
        return state

    def _observation(self, state: WorkflowState) -> str:
        classes = sorted({linker.linker_class for linker in state.generated_linkers})
        return f"linkers={len(state.generated_linkers)}, classes={classes}"
