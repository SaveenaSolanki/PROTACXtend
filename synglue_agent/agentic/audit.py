"""Scientific critic and audit checks."""

from __future__ import annotations

from synglue_agent.backend.schemas import WorkflowState


class ScientificCriticAgent:
    """Check whether claims are supported by deterministic evidence."""

    name = "ScientificCriticAgent"

    def review(self, state: WorkflowState) -> dict[str, object]:
        warnings = list(state.warnings)
        actions: list[str] = []
        if not state.valid_candidates:
            actions.append("stop_no_valid_candidates")
        invalid = [candidate.candidate_id for candidate in state.valid_candidates if candidate.validity_status not in {"valid", "unverified_no_rdkit"}]
        if invalid:
            warnings.append(f"Some candidates are not RDKit-valid: {','.join(invalid[:5])}")
            actions.append("downgrade_confidence")
        if any((pred.warning or "").find("heuristic") >= 0 or "heuristic" in pred.model_version.lower() for pred in state.degradation_predictions):
            warnings.append("DC50/Dmax outputs are heuristic fallback outputs, not validated trained-model predictions.")
        if not state.applicability_domain_results:
            warnings.append("Applicability-domain assessment is missing or unavailable.")
            actions.append("downgrade_confidence")
        elif any(item.domain_status not in {"in_domain", "inside"} for item in state.applicability_domain_results):
            warnings.append("One or more candidates are outside or near the applicability domain.")
            actions.append("downgrade_confidence")
        if state.parsed_objective.use_structure_aware_ranking and not state.ternary_feasibility_results:
            warnings.append("Structure-aware ranking was requested, but ternary/docking evidence was unavailable.")
        unsupported = []
        if state.report and "experimentally validated" in state.report.lower():
            unsupported.append("report_mentions_experimentally_validated")
            actions.append("revise_report")
        return {
            "status": "fail" if "stop_no_valid_candidates" in actions else "pass_with_warnings" if warnings else "pass",
            "warnings": warnings,
            "actions": actions,
            "unsupported_claims": unsupported,
        }

