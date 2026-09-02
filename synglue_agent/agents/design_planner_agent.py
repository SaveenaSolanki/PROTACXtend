"""Top-level design planner for agentic PROTAC workflows."""

from __future__ import annotations

from typing import Any

from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import WorkflowState


class DesignPlannerAgent(ReActAgent):
    """Decide the workflow policy before specialist agents run.

    The planner is deterministic in the local scaffold, but it captures the
    same decisions a production LLM planner should make: required tools,
    missing user inputs, retry policy, external evidence search, stop rules,
    scientific invalidity rules, and deeper validation gates.
    """

    name = "DesignPlannerAgent"
    thought = "Plan tool routing, retries, evidence search, user-input gates, stopping rules, and validation depth."
    action = "create_design_plan"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        objective = state.parsed_objective
        request_upper = state.user_request.upper()
        curated_targets = self.toolbox.load_curated_targets()
        local_targets = {row.get("target_name", "").upper() for row in curated_targets}
        local_targets.update({row.get("gene_symbol", "").upper() for row in curated_targets})

        missing_input_questions = []
        if not objective.target_name:
            missing_input_questions.append("Which target protein or gene symbol should the PROTAC be designed for?")
        if not objective.e3_ligase:
            missing_input_questions.append("No E3 ligase was specified; default local branching will compare CRBN/VHL unless you choose one.")
        if not objective.warhead_smiles:
            missing_input_questions.append("No warhead SMILES was provided; the workflow will retrieve known binders before selecting warheads.")

        target_key = (objective.target_name or "").upper()
        should_search_external = bool(target_key and target_key not in local_targets)
        should_run_docking = bool(
            objective.use_structure_aware_ranking
            or any(term in request_upper for term in ["DOCK", "DOCKING", "TERNARY", "POSE", "STRUCTURE"])
        )
        should_run_retrosynthesis = bool(
            objective.use_retrosynthesis_filtering
            or any(term in request_upper for term in ["RETROSYNTHESIS", "SYNTHESIS", "SYNTHETICALLY FEASIBLE"])
        )
        should_run_strict_admet = bool(
            objective.admet_constraints
            or any(term in request_upper for term in ["ADME", "TOX", "HERG", "AMES", "DILI", "SOLUBILITY", "PERMEABILITY"])
        )

        objective.use_structure_aware_ranking = should_run_docking
        objective.use_retrosynthesis_filtering = should_run_retrosynthesis

        tools_to_call = [
            "SafetyGuardrailAgent",
            "TargetResolverAgent",
            "TargetBinderRetrievalAgent" if not objective.warhead_smiles else "UserProvidedWarheadPath",
            "WarheadSelectionAgent",
            "E3LigandSelectionAgent",
            "ExitVectorDetectionAgent",
            "LinkerGenerationAgent",
            "MolecularConstructionAgent",
            "CandidateValidationAgent",
            "DegradationPredictionAgent",
            "ADMETAgent",
            "NoveltySimilarityAgent",
            "ApplicabilityDomainAgent",
            "RankingTournamentAgent",
            "ReflectionReviewAgent",
            "EvolutionRefinementAgent",
            "FinalRankingTournamentAgent",
            "ReportAgent",
            "MemoryUpdateAgent",
        ]
        if should_run_docking:
            tools_to_call.insert(-3, "TernaryFeasibilityAgent")
        if should_run_retrosynthesis:
            tools_to_call.insert(8, "RetrosynthesisFilter")

        plan: dict[str, Any] = {
            "status": "needs_user_input" if not objective.target_name else "continue",
            "tools_to_call": tools_to_call,
            "repeat_policy": {
                "max_retries_per_step": 1,
                "retryable_steps": [
                    "resolve_target",
                    "retrieve_target_binders",
                    "predict_degradation",
                    "predict_admet",
                    "optional_ternary_feasibility",
                ],
                "retry_when": [
                    "required output is empty",
                    "transient external lookup failure is recorded",
                    "configured model/API backend returns no result",
                ],
            },
            "external_evidence_policy": {
                "search_external_target_evidence": should_search_external,
                "search_external_binders": bool(not objective.warhead_smiles),
                "allowed_sources": ["UniProt", "RCSB PDB", "ChEMBL", "PubChem", "local curated CSVs"],
                "fallback": "Use local curated/demo data only when external evidence is unavailable and label the fallback.",
            },
            "stop_conditions": [
                "missing target name",
                "no target could be resolved",
                "no warheads selected",
                "no E3 ligands selected",
                "no PROTAC candidates assembled",
                "no valid or unverified candidates after validation",
            ],
            "missing_input_questions": missing_input_questions,
            "scientific_invalidity_rules": [
                "Reject invalid RDKit molecules when RDKit validation is available.",
                "Flag candidates with hypothetical or ambiguous exit vectors for chemist review.",
                "Do not treat heuristic DC50/Dmax values as trained-model predictions.",
                "Penalize high hERG, AMES, DILI, solubility, or permeability risk rather than hiding the candidate.",
                "Require human review before synthesis, wet-lab testing, dosing, or biological claims.",
            ],
            "deeper_validation": {
                "run_admet_filtering": True,
                "strict_admet_constraints_requested": should_run_strict_admet,
                "run_retrosynthesis_filtering": should_run_retrosynthesis,
                "run_ternary_or_docking_triage": should_run_docking,
                "docking_gate": "Run only for top-ranked candidates after initial ranking.",
            },
            "candidate_budget": {
                "requested": objective.candidate_count,
                "max_local_default": 500,
            },
            "rationale": (
                "Plan uses local deterministic agents by default, adds external evidence search for unknown targets, "
                "runs ADME/novelty for all candidates, and gates expensive structure-aware validation to explicit requests."
            ),
        }
        state.design_plan = plan
        if not objective.target_name:
            state.errors.append("Planner requires a target protein/gene before the design workflow can continue.")
        return state

    def _observation(self, state: WorkflowState) -> str:
        plan = state.design_plan or {}
        deeper = plan.get("deeper_validation", {})
        return (
            f"status={plan.get('status')}, tools={len(plan.get('tools_to_call', []))}, "
            f"external_target_search={plan.get('external_evidence_policy', {}).get('search_external_target_evidence')}, "
            f"docking={deeper.get('run_ternary_or_docking_triage')}, "
            f"questions={len(plan.get('missing_input_questions', []))}"
        )
