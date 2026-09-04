"""Assay-feedback active-learning update agent."""

from __future__ import annotations

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WorkflowState


class ActiveLearningAgent(ReActAgent):
    name = "ActiveLearningAgent"
    thought = "Convert assay feedback into supervised rows and report retraining readiness."
    action = "update_active_learning_from_feedback"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.active_learning_update = self.toolbox.update_active_learning_from_feedback(
            state.assay_feedback,
            state.valid_candidates,
        )
        if state.assay_feedback:
            try:
                from protacxtend.tools.learning_memory import LearningMemory, LearningSource, Outcome, ProblemType

                memory = LearningMemory()
                candidate_by_id = {candidate.candidate_id: candidate for candidate in state.valid_candidates}
                for feedback in state.assay_feedback:
                    candidate = candidate_by_id.get(feedback.candidate_id)
                    observed = feedback.degradation_observed
                    outcome = Outcome.SUCCESS.value if observed is True else Outcome.FAILURE.value if observed is False else Outcome.PARTIAL.value
                    details = (
                        f"candidate={feedback.candidate_id}; target={feedback.target or (candidate.target if candidate else '')}; "
                        f"e3={feedback.e3_ligase or (candidate.e3_ligase if candidate else '')}; cell={feedback.cell_line}; "
                        f"dc50={feedback.measured_dc50_nM}; dmax={feedback.measured_dmax_percent}; "
                        f"hook={feedback.measured_hook_concentration_nM}; notes={feedback.notes}"
                    )
                    memory.record(
                        problem_type=ProblemType.DEGRADATION_PREDICTION.value,
                        approach="assay_feedback_closed_loop",
                        outcome=outcome,
                        failure_reason="other" if observed is not False else "low_confidence",
                        details=details,
                        confidence=0.9,
                        source=LearningSource.HUMAN_FEEDBACK.value,
                        target=feedback.target or (candidate.target if candidate else ""),
                        e3_ligase=feedback.e3_ligase or (candidate.e3_ligase if candidate else ""),
                        auto_validate_human=True,
                    )
            except Exception as exc:  # noqa: BLE001
                state.warnings.append(f"ActiveLearningAgent: feedback memory update failed: {exc}")
        return state

    def _observation(self, state: WorkflowState) -> str:
        update = state.active_learning_update
        return f"feedback={update.feedback_count}, training_rows={update.training_rows}, recommendation={update.retraining_recommendation}"
