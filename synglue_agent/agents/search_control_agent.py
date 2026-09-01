"""Controlled-search agents for the NP-hard PROTAC funnel."""

from __future__ import annotations

from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import WorkflowState


class ControlledSearchAgent(ReActAgent):
    name = "ControlledSearchAgent"
    thought = "Set bounded linker, construction, stereoisomer, cheap-filter, and expensive-modeling budgets."
    action = "build_controlled_search_policy"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.search_policy = self.toolbox.build_search_policy(state.parsed_objective)
        state.design_plan["search_policy"] = state.search_policy.model_dump()
        return state

    def _observation(self, state: WorkflowState) -> str:
        p = state.search_policy
        return f"linkers={p.linker_budget}, construct={p.construction_budget}, cheap_keep={p.cheap_filter_budget}, expensive={p.expensive_modeling_budget}"


class StereochemistryEnumerationAgent(ReActAgent):
    name = "StereochemistryEnumerationAgent"
    thought = "Enumerate only a capped number of undefined stereoisomers and keep stereoisomers separately scored."
    action = "expand_stereoisomers_controlled"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        policy = state.search_policy
        expanded = self.toolbox.expand_stereoisomers_controlled(
            state.assembled_candidates,
            max_per_candidate=policy.stereoisomer_budget_per_candidate,
            max_total=policy.construction_budget,
        )
        if len(expanded) != len(state.assembled_candidates):
            state.warnings.append(
                f"Stereochemistry expansion changed candidate pool from {len(state.assembled_candidates)} to {len(expanded)} under capped policy."
            )
        state.assembled_candidates = expanded
        return state

    def _observation(self, state: WorkflowState) -> str:
        flagged = sum(1 for item in state.assembled_candidates if "stereoisomer_requires_separate_scoring" in item.warning_flags)
        return f"assembled_after_stereo={len(state.assembled_candidates)}, enumerated={flagged}"


class CheapFilterAgent(ReActAgent):
    name = "CheapFilterAgent"
    thought = "Apply validity, property, ADMET, novelty, domain, synthesis, and E3-context filters before expensive modeling."
    action = "cheap_filter_candidates"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        kept, summary = self.toolbox.cheap_filter_candidates(
            state.valid_candidates,
            state.admet_predictions,
            state.novelty_results,
            state.applicability_domain_results,
            state.e3_context_predictions,
            max_candidates=state.search_policy.cheap_filter_budget,
        )
        kept_ids = {item.candidate_id for item in kept}
        state.valid_candidates = kept
        state.admet_predictions = self.toolbox.filter_prediction_records(state.admet_predictions, kept_ids)
        state.novelty_results = self.toolbox.filter_prediction_records(state.novelty_results, kept_ids)
        state.applicability_domain_results = self.toolbox.filter_prediction_records(state.applicability_domain_results, kept_ids)
        state.e3_context_predictions = self.toolbox.filter_prediction_records(state.e3_context_predictions, kept_ids)
        state.cheap_filter_summary = summary
        if not kept:
            state.errors.append("CheapFilterAgent: no candidates survived cheap filtering.")
        return state

    def _observation(self, state: WorkflowState) -> str:
        summary = state.cheap_filter_summary or {}
        return f"cheap_filter_kept={summary.get('kept_candidates', 0)}/{summary.get('input_candidates', 0)}"


class ExpensiveModelingSelectionAgent(ReActAgent):
    name = "ExpensiveModelingSelectionAgent"
    thought = "Select a small ranked and diverse finalist set for ternary modeling."
    action = "select_expensive_modeling_finalists"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        finalists = self.toolbox.select_expensive_modeling_finalists(
            state.valid_candidates,
            state.ranking_results,
            max_finalists=state.search_policy.expensive_modeling_budget,
        )
        state.expensive_modeling_candidate_ids = [item.candidate_id for item in finalists]
        return state

    def _observation(self, state: WorkflowState) -> str:
        return f"expensive_modeling_finalists={len(state.expensive_modeling_candidate_ids)}"
