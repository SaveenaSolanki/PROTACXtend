"""PROTAC molecular construction and validation agents."""

from __future__ import annotations

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WorkflowState


class MolecularConstructionAgent(ReActAgent):
    name = "MolecularConstructionAgent"
    thought = "Construct PROTAC candidates with multi-strategy deterministic assembly and provenance tracking."
    action = "construct_protacs"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        if not state.selected_warheads or not state.selected_e3_ligands or not state.generated_linkers:
            state.errors.append("Construction skipped because required components are missing.")
            return state
        attempts, candidates = self.toolbox.construct_protac_candidates(
            state.selected_warheads,
            state.selected_e3_ligands,
            state.generated_linkers,
            state.target_record,
            candidate_count=max(1, state.search_policy.construction_budget),
            use_retrosynthesis_filtering=state.parsed_objective.use_retrosynthesis_filtering,
        )
        state.construction_attempts.extend(attempts)
        state.assembled_candidates = candidates
        if not candidates:
            state.errors.append("No PROTAC candidates assembled. Check attachment vectors and linker library.")
        return state

    def _observation(self, state: WorkflowState) -> str:
        success = sum(1 for attempt in state.construction_attempts if attempt.success)
        return f"attempts={len(state.construction_attempts)}, assembled={len(state.assembled_candidates)}, successes={success}"


class CandidateValidationAgent(ReActAgent):
    name = "CandidateValidationAgent"
    thought = "Sanitize, canonicalize, property-check, and deduplicate assembled PROTAC candidates."
    action = "validate_protacs"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.valid_candidates = self.toolbox.validate_candidates(state.assembled_candidates)
        if not state.valid_candidates:
            state.errors.append("No valid or unverified candidates remained after validation.")
        return state

    def _observation(self, state: WorkflowState) -> str:
        return f"valid_candidates={len(state.valid_candidates)}"
