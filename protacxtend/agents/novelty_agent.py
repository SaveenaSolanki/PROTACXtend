"""Novelty and duplicate-checking agent."""

from __future__ import annotations

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WorkflowState


class NoveltyAgent(ReActAgent):
    name = "NoveltySimilarityAgent"
    thought = "Compare candidates against local known PROTAC-like records using fingerprints or deterministic string fallback."
    action = "check_novelty"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.novelty_results = self.toolbox.check_novelty(state.valid_candidates)
        return state

    def _observation(self, state: WorkflowState) -> str:
        duplicates = sum(1 for item in state.novelty_results if item.duplicate_flag)
        return f"novelty_results={len(state.novelty_results)}, duplicates={duplicates}"
