"""Scientific contract layer for PROTACXtend.

This module implements the KNOW -> REASON -> DESIGN -> DISCOVER contract from
the development plan as structured, testable runtime objects. It intentionally
does not claim to finish prospective discovery; it gives the current system the
state, action, evidence, critique, dossier, and evaluation scaffolds required to
move toward that claim responsibly.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Literal

from protacxtend import __version__
from protacxtend.backend.schemas import (
    CandidateRecord,
    WorkflowState,
    model_to_dict,
    BaseModel,
    Field,
)


EvidenceLabel = Literal[
    "MEASURED",
    "CURATED",
    "REPORTED",
    "COMPUTED",
    "PREDICTED",
    "INFERRED",
    "HYPOTHETICAL",
    "CONTRADICTED",
]

StoppingState = Literal["SUPPORTED", "REVISE", "REJECT", "INSUFFICIENT EVIDENCE"]

ActionKind = Literal["retrieve", "compute", "design", "critique", "experiment", "report", "learn"]


class EvidenceClaim(BaseModel):
    claim_id: str = ""
    statement: str = ""
    label: EvidenceLabel = "HYPOTHETICAL"
    entity_type: str = ""
    entity_id: str = ""
    value: Any = None
    units: str = ""
    assay_context: str = ""
    biological_context: str = ""
    source: str = ""
    source_type: str = ""
    uncertainty: str = ""
    applicability_domain: str = ""
    supports: list[str] = Field(default_factory=list)
    conflicts_with: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ScientificHypothesis(BaseModel):
    hypothesis_id: str = ""
    statement: str = ""
    mechanism: str = ""
    enabling_assumptions: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    conflicting_evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    predicted_observations: list[str] = Field(default_factory=list)
    falsifying_observations: list[str] = Field(default_factory=list)
    uncertainty_decomposition: dict[str, str] = Field(default_factory=dict)
    next_discriminating_action: str = ""


class ActionContract(BaseModel):
    action_id: str = ""
    semantic_version: str = "0.1.0"
    kind: ActionKind = "compute"
    scientific_question: str = ""
    input_schema: dict[str, str] = Field(default_factory=dict)
    output_schema: dict[str, str] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    controlled_vocabularies: dict[str, list[str]] = Field(default_factory=dict)
    prerequisites: list[str] = Field(default_factory=list)
    incompatibilities: list[str] = Field(default_factory=list)
    supported_entity_types: list[str] = Field(default_factory=list)
    molecular_formats: list[str] = Field(default_factory=list)
    deterministic: bool = True
    random_seed_behavior: str = "not_applicable"
    applicability_domain: str = ""
    known_failure_modes: list[str] = Field(default_factory=list)
    expected_runtime: str = ""
    compute_requirements: str = ""
    external_cost: str = "none"
    timeout_s: int = 60
    retry_policy: str = "no_retry"
    resume_policy: str = "rerun_action"
    fallback_behavior: str = ""
    evidence_grade: EvidenceLabel = "COMPUTED"
    versions_and_citations: list[str] = Field(default_factory=list)
    tests: dict[str, list[str]] = Field(default_factory=dict)
    privacy_constraints: list[str] = Field(default_factory=list)
    license_constraints: list[str] = Field(default_factory=list)
    artifact_contract: dict[str, str] = Field(default_factory=dict)
    cannot_support: list[str] = Field(default_factory=list)

    def quality_gate(self) -> dict[str, Any]:
        missing: list[str] = []
        for field in [
            "action_id",
            "semantic_version",
            "scientific_question",
            "input_schema",
            "output_schema",
            "applicability_domain",
            "known_failure_modes",
            "fallback_behavior",
            "cannot_support",
        ]:
            value = getattr(self, field)
            if value in ("", [], {}, None):
                missing.append(field)
        test_groups = self.tests or {}
        for group in ["positive", "negative", "edge", "regression"]:
            if not test_groups.get(group):
                missing.append(f"tests.{group}")
        return {
            "action_id": self.action_id,
            "usable_in_paper_run": not missing,
            "missing": missing,
        }


class ActionDecisionRecord(BaseModel):
    action_id: str = ""
    expected_information_gain: float = 0.0
    probability_of_decision_change: float = 0.0
    scientific_validity: float = 0.0
    prerequisite_satisfaction: float = 0.0
    cost_penalty: float = 0.0
    failure_probability: float = 0.0
    redundancy_penalty: float = 0.0
    orthogonal_value: float = 0.0
    downstream_unlocks: float = 0.0
    score: float = 0.0
    selected: bool = False
    rationale: str = ""


class CandidateDossier(BaseModel):
    candidate_id: str = ""
    exact_structure: str = ""
    component_lineage: dict[str, Any] = Field(default_factory=dict)
    design_hypothesis: str = ""
    target_binder_evidence: list[EvidenceClaim] = Field(default_factory=list)
    e3_recruiter_rationale: str = ""
    linker_rationale: str = ""
    structural_evidence_vector: dict[str, Any] = Field(default_factory=dict)
    degradation_predictions: dict[str, Any] = Field(default_factory=dict)
    developability_assessment: dict[str, Any] = Field(default_factory=dict)
    synthesis_plan: dict[str, Any] = Field(default_factory=dict)
    novelty_assessment: dict[str, Any] = Field(default_factory=dict)
    supporting_evidence: list[str] = Field(default_factory=list)
    conflicting_evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    rejection_thresholds: list[str] = Field(default_factory=list)
    proposed_controls: list[str] = Field(default_factory=list)
    provenance_manifest: dict[str, Any] = Field(default_factory=dict)


class ExperimentDossier(BaseModel):
    experiment_id: str = ""
    candidate_ids: list[str] = Field(default_factory=list)
    objective: str = ""
    frozen_predictions: dict[str, Any] = Field(default_factory=dict)
    assay_ladder: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    failure_criteria: list[str] = Field(default_factory=list)
    outcome_ingestion_schema: dict[str, str] = Field(default_factory=dict)
    allowed_human_interventions: list[str] = Field(default_factory=list)
    evidence_cutoff_date: str = ""


class ScientificDecision(BaseModel):
    question: str = ""
    alternatives: list[str] = Field(default_factory=list)
    selected_option: str = ""
    rationale: str = ""
    stopping_state: StoppingState = "INSUFFICIENT EVIDENCE"
    uncertainty: dict[str, str] = Field(default_factory=dict)
    next_action: str = ""


class ScientificState(BaseModel):
    capability_model: list[str] = Field(default_factory=lambda: ["KNOW", "REASON", "DESIGN", "DISCOVER"])
    objective: dict[str, Any] = Field(default_factory=dict)
    known: dict[str, Any] = Field(default_factory=dict)
    unknown: dict[str, Any] = Field(default_factory=dict)
    hypotheses: list[ScientificHypothesis] = Field(default_factory=list)
    candidates: list[CandidateDossier] = Field(default_factory=list)
    rejected_candidates: list[dict[str, Any]] = Field(default_factory=list)
    actions: dict[str, Any] = Field(default_factory=dict)
    decision: ScientificDecision = Field(default_factory=ScientificDecision)
    provenance: dict[str, Any] = Field(default_factory=dict)
    memories: dict[str, Any] = Field(default_factory=dict)


class CritiqueRecord(BaseModel):
    status: StoppingState = "INSUFFICIENT EVIDENCE"
    failure_categories: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    uncertainty: dict[str, str] = Field(default_factory=dict)
    recommended_action: str = ""
    warnings: list[str] = Field(default_factory=list)


class BenchmarkTaskSpec(BaseModel):
    task_id: str = ""
    competency: str = ""
    difficulty_tier: str = ""
    scientific_objective: str = ""
    input_entities: dict[str, str] = Field(default_factory=dict)
    biological_context: str = ""
    evidence_cutoff_date: str = ""
    permitted_resources: list[str] = Field(default_factory=list)
    expected_artifacts: list[str] = Field(default_factory=list)
    process_rubric: list[str] = Field(default_factory=list)
    evidence_rubric: list[str] = Field(default_factory=list)
    outcome_rubric: list[str] = Field(default_factory=list)
    critical_errors: list[str] = Field(default_factory=list)
    split_tags: list[str] = Field(default_factory=list)
    leakage_record: dict[str, Any] = Field(default_factory=dict)


class ExternalMethodRecord(BaseModel):
    method_id: str = ""
    name: str = ""
    capability_placement: str = ""
    role: str = ""
    review_decision: str = ""
    gate: str = ""
    caution: str = ""
    integration_wave: int = 1
    status: str = "not_integrated"


def default_action_contracts() -> list[ActionContract]:
    common_tests = {
        "positive": ["valid BRD4/CRBN request returns typed output"],
        "negative": ["missing target returns explicit failure or abstention"],
        "edge": ["cell-line token such as MM1.S is not parsed as target"],
        "regression": ["schema output remains JSON-serializable"],
    }
    return [
        ActionContract(
            action_id="know.target_context",
            kind="retrieve",
            scientific_question="What is known about target tractability, biology, structures, binders, and degradation rationale?",
            input_schema={"target": "gene_symbol_or_uniprot", "cell_line": "optional str"},
            output_schema={"target_record": "TargetRecord", "evidence_claims": "list[EvidenceClaim]"},
            prerequisites=["objective.target"],
            supported_entity_types=["target", "cell_line"],
            molecular_formats=[],
            applicability_domain="human protein targets with resolvable identifiers or curated local fallback",
            known_failure_modes=["identifier_mismatch", "missing_structure", "sparse_binder_evidence"],
            expected_runtime="1-20 seconds",
            fallback_behavior="return partial target record and missing evidence list",
            versions_and_citations=["UniProt/PDB/ChEMBL/PubChem local or API versions recorded when used"],
            tests=common_tests,
            cannot_support=["clinical safety", "measured degradation without assay evidence"],
        ),
        ActionContract(
            action_id="reason.dynamic_action_selection",
            kind="critique",
            scientific_question="Which action is most likely to resolve the current decision-critical uncertainty?",
            input_schema={"scientific_state": "ScientificState", "contracts": "list[ActionContract]"},
            output_schema={"decisions": "list[ActionDecisionRecord]"},
            prerequisites=["scientific_state.objective"],
            supported_entity_types=["action", "hypothesis", "candidate"],
            applicability_domain="registered actions with declared prerequisites and failure modes",
            known_failure_modes=["bad_prerequisites", "overvalued_redundant_action", "missing_cost_model"],
            expected_runtime="<1 second",
            fallback_behavior="abstain with recommended missing prerequisite",
            tests=common_tests,
            cannot_support=["hidden scientific intervention", "unsafe action execution without approval"],
        ),
        ActionContract(
            action_id="design.candidate_dossier",
            kind="design",
            scientific_question="Which candidate should advance and why should similar alternatives not advance?",
            input_schema={"workflow_state": "WorkflowState", "candidate": "CandidateRecord"},
            output_schema={"candidate_dossier": "CandidateDossier"},
            prerequisites=["candidate.validity_status", "candidate.component_lineage"],
            supported_entity_types=["protac_candidate", "warhead", "linker", "e3_ligand"],
            molecular_formats=["SMILES"],
            applicability_domain="constructed candidates with explicit component lineage",
            known_failure_modes=["ambiguous_attachment", "invalid_stereochemistry", "missing_provenance"],
            expected_runtime="<1 second per candidate",
            fallback_behavior="reject or downgrade dossier confidence with decisive missing evidence",
            tests=common_tests,
            cannot_support=["synthesis recommendation without route evidence", "measured potency without assay evidence"],
        ),
        ActionContract(
            action_id="discover.experiment_dossier",
            kind="experiment",
            scientific_question="What experiment would most reduce uncertainty for the selected candidate set?",
            input_schema={"scientific_state": "ScientificState", "candidate_ids": "list[str]"},
            output_schema={"experiment_dossier": "ExperimentDossier"},
            prerequisites=["candidate_dossiers", "frozen_predictions"],
            supported_entity_types=["candidate", "assay", "cell_line"],
            applicability_domain="preclinical research planning with human review",
            known_failure_modes=["missing_controls", "unfrozen_predictions", "assay_context_missing"],
            expected_runtime="<1 second",
            fallback_behavior="return INSUFFICIENT EVIDENCE and required controls",
            tests=common_tests,
            cannot_support=["clinical protocol", "wet-lab execution without expert review"],
        ),
    ]


def reviewed_external_methods() -> list[ExternalMethodRecord]:
    return [
        ExternalMethodRecord(method_id="protac_degradation_predictor", name="PROTAC-Degradation-Predictor", capability_placement="KNOW context model + DESIGN activity prediction", role="primary immediate baseline", review_decision="adopt_after_tests", gate="run package tests, reproduce published experiments, recalibrate probabilities", caution="classifier output is not DC50/Dmax truth", integration_wave=1),
        ExternalMethodRecord(method_id="rp_protac", name="RP-PROTAC", capability_placement="REASON uncertainty + DESIGN prediction", role="uncertainty/OOD baseline and ranking comparator", review_decision="audit_before_use", gate="verify license, data provenance, weights, splits, and calibration", caution="publication/license state must be independently checked", integration_wave=1),
        ExternalMethodRecord(method_id="deep_qsp_hook", name="Deep-QSP Hook model", capability_placement="DISCOVER dose design", role="mechanistic ternary dose-response and hook-effect simulator", review_decision="integrate_or_adapt", gate="reproduce dose-response and hook-effect outputs with sensitivity analysis", caution="not trusted final predictor; Dmax calibration caution", integration_wave=1),
        ExternalMethodRecord(method_id="protacfold", name="PROTACFold", capability_placement="KNOW structural + DESIGN ternary generation", role="gated ternary structure-generation branch", review_decision="audit_and_wrap", gate="audit AF3/Boltz licenses, compute profile, and confidence calibration", caution="never sole structural method", integration_wave=1),
        ExternalMethodRecord(method_id="rover_schapira_benchmark", name="Rovers/Schapira ternary benchmark", capability_placement="KNOW structural validation", role="primary structural benchmark", review_decision="adopt_benchmark", gate="reproduce open PRosettaC branch and license boundaries", caution="MOE/ICM licensed branches cannot be assumed available", integration_wave=1),
        ExternalMethodRecord(method_id="synprotac", name="SynPROTAC", capability_placement="DESIGN synthesis-constrained generation", role="synthesis-aware generation baseline", review_decision="audit_before_wrap", gate="reproduce BRD4 examples and route validity", caution="license and building-block data must be audited", integration_wave=1),
        ExternalMethodRecord(method_id="deep_protacs", name="DeepPROTACs", capability_placement="DESIGN degradation benchmark", role="legacy structure-aware classification baseline and ablation comparator", review_decision="containerized_baseline", gate="reproduce examples under current splits", caution="older environment and binary labels", integration_wave=2),
        ExternalMethodRecord(method_id="bai_crl4a_crbn_geometry", name="CRL4A/CRBN ubiquitination geometry", capability_placement="PROTACXtend-native structural scoring", role="native feature source for Ubiquitination Geometry Scorer", review_decision="reimplement_and_validate", gate="reproduce CRBN geometric relationships before routine use", caution="CRBN assumptions do not transfer automatically", integration_wave=2),
        ExternalMethodRecord(method_id="hapod", name="HAPOD/PROTACModeling", capability_placement="DESIGN ternary scoring", role="finalist-only refinement", review_decision="containerize_and_gate", gate="reproduce quick-start and benchmark added value", caution="requires upstream poses and MD dependencies", integration_wave=2),
        ExternalMethodRecord(method_id="protac_invent", name="PROTAC-INVENT", capability_placement="DESIGN linker generation", role="3D linker generation baseline", review_decision="containerize_and_compare", gate="reproduce examples and compare validity/novelty/runtime", caution="custom REINVENT/DockStream environment", integration_wave=3),
        ExternalMethodRecord(method_id="rnf4_fem1b", name="RNF4/FEM1B recruiter discovery", capability_placement="future E3 intelligence + DISCOVER", role="experimental blueprint", review_decision="do_not_integrate_as_predictor", gate="define chemoproteomics and E3-dependence gates", caution="not a computational recruiter model", integration_wave=4),
    ]


def build_candidate_dossier(state: WorkflowState, candidate: CandidateRecord) -> CandidateDossier:
    cid = candidate.candidate_id
    ternary = next((item for item in state.ternary_feasibility_results if item.candidate_id == cid), None)
    degradation = next((item for item in state.degradation_predictions if item.candidate_id == cid), None)
    admet = next((item for item in state.admet_predictions if item.candidate_id == cid), None)
    novelty = next((item for item in state.novelty_results if item.candidate_id == cid), None)
    ranking = next((item for item in state.ranking_results if item.candidate_id == cid), None)
    risks = list(candidate.warning_flags)
    if degradation and (degradation.warning or "heuristic" in degradation.model_version.lower()):
        risks.append("degradation_prediction_not_measured")
    if ternary and ternary.structural_warnings:
        risks.extend(ternary.structural_warnings)
    if admet and admet.overall_admet_penalty > 0.6:
        risks.append("developability_penalty_high")
    if novelty and novelty.duplicate_flag:
        risks.append("known_or_near_duplicate")
    return CandidateDossier(
        candidate_id=cid,
        exact_structure=candidate.full_protac_smiles,
        component_lineage={
            "target": candidate.target,
            "warhead": candidate.warhead_name,
            "warhead_smiles": candidate.warhead_smiles,
            "e3_ligase": candidate.e3_ligase,
            "e3_ligand": candidate.e3_ligand_name,
            "linker": candidate.linker_name,
            "linker_class": candidate.linker_class,
            "assembly_strategy": candidate.assembly_strategy,
        },
        design_hypothesis=f"{cid} may degrade {candidate.target or state.parsed_objective.target_name} by recruiting {candidate.e3_ligase or state.parsed_objective.e3_ligase or 'an E3 ligase'} with {candidate.linker_class or 'a designed'} linker.",
        e3_recruiter_rationale=f"E3 selection remains context-dependent; {candidate.e3_ligase or 'selected E3'} requires cell-expression and engagement evidence.",
        linker_rationale=f"Linker class {candidate.linker_class or 'unknown'} must balance reachability, strain, permeability, and synthesis.",
        structural_evidence_vector=model_to_dict(ternary) if ternary else {"status": "missing", "required": "ternary feasibility and lysine/productive-geometry features"},
        degradation_predictions=model_to_dict(degradation) if degradation else {"status": "missing"},
        developability_assessment=model_to_dict(admet) if admet else {"status": "missing"},
        synthesis_plan={
            "status": "planned_not_validated",
            "required": ["reaction-aware route", "building-block availability", "purity/identity plan"],
        },
        novelty_assessment=model_to_dict(novelty) if novelty else {"status": "missing"},
        supporting_evidence=[ranking.reason_for_rank] if ranking and ranking.reason_for_rank else [],
        conflicting_evidence=[],
        risks=sorted(set(risks)),
        rejection_thresholds=[
            "invalid or ambiguous structure",
            "loss of target or E3 engagement",
            "nonproductive ternary/lysine geometry",
            "unacceptable permeability or safety liability",
            "unsupported measured-activity claim",
        ],
        proposed_controls=[
            "inactive stereoisomer or nonbinding analog",
            "proteasome-dependence control",
            "E3-dependence control",
            "target-engagement assay",
            "dose response sufficient to reveal hook effect",
        ],
        provenance_manifest={
            "candidate_provenance": candidate.provenance,
            "protacxtend_version": __version__,
            "schema": "CandidateDossier.v0.1",
        },
    )


def build_scientific_state(state: WorkflowState, *, evidence_cutoff_date: str = "") -> ScientificState:
    candidates = [build_candidate_dossier(state, candidate) for candidate in state.final_ranked_candidates[:6] or state.valid_candidates[:6]]
    missing: list[str] = []
    if not state.target_record:
        missing.append("target degradation rationale")
    if not state.e3_context_predictions:
        missing.append("E3-target cell-context compatibility matrix")
    if not state.ternary_feasibility_results:
        missing.append("ternary/productive-geometry vector")
    if not state.assay_feedback:
        missing.append("measured prospective outcome feedback")
    stopping: StoppingState = "SUPPORTED" if candidates and not missing[:3] else "REVISE" if candidates else "INSUFFICIENT EVIDENCE"
    objective = {
        "target": state.parsed_objective.target_name,
        "desired_phenotype": "targeted protein degradation",
        "biological_context": {
            "cell_line": state.parsed_objective.cell_line,
            "disease_context": state.parsed_objective.disease_context,
            "assay_context": state.parsed_objective.assay_context,
        },
        "constraints": state.parsed_objective.admet_constraints,
        "success_criteria": [
            "chemically valid candidates",
            "ranked candidate dossier",
            "measured/predicted distinction preserved",
            "next validation experiment specified",
        ],
    }
    decision = ScientificDecision(
        question="Which degrader hypothesis should advance next?",
        alternatives=[candidate.candidate_id for candidate in candidates],
        selected_option=candidates[0].candidate_id if candidates else "",
        rationale="Advance the best supported and most informative candidate only if evidence thresholds and caveats are visible.",
        stopping_state=stopping,
        uncertainty={
            "evidence": "public PROTAC evidence is incomplete",
            "model": "predictions require calibration and applicability-domain checks",
            "structural": "proxy or missing structural results cannot prove productive degradation",
            "assay_context": "cell-line transferability requires measured context",
        },
        next_action="prepare experiment dossier" if candidates else "retrieve missing target, E3, and chemistry evidence",
    )
    return ScientificState(
        objective=objective,
        known={
            "facts": [],
            "measured_values": [model_to_dict(item) for item in state.assay_feedback],
            "validated_structures": state.target_record.structures if state.target_record else [],
        },
        unknown={"decision_critical_questions": missing, "missing_data": missing},
        hypotheses=[
            ScientificHypothesis(
                hypothesis_id="h_design_001",
                statement=decision.rationale,
                mechanism="target engagement plus E3 recruitment plus productive ternary geometry plus cellular exposure",
                supporting_evidence=[candidate.candidate_id for candidate in candidates],
                confidence=max((ranking.confidence for ranking in state.ranking_results), default=0.0),
                falsifying_observations=[
                    "matched target engagement with absent degradation",
                    "E3-independent degradation",
                    "inactive ternary complex or inaccessible lysines",
                    "permeability/exposure failure despite biochemical engagement",
                ],
                uncertainty_decomposition=decision.uncertainty,
                next_discriminating_action=decision.next_action,
            )
        ],
        candidates=candidates,
        rejected_candidates=[
            {
                "identity": candidate.candidate_id,
                "reason": "; ".join(candidate.warning_flags) or "not selected for final dossier",
                "decisive_evidence": candidate.validity_status,
                "reconsideration_condition": "new measured evidence or corrected structure/context",
            }
            for candidate in state.assembled_candidates
            if candidate.candidate_id not in {item.candidate_id for item in candidates}
        ][:20],
        actions={
            "available": [contract.action_id for contract in default_action_contracts()],
            "completed": [trace.action for trace in state.workflow_log],
            "failed": state.errors,
            "proposed": [decision.next_action],
        },
        decision=decision,
        provenance={
            "sources": [],
            "datasets": ["PROTAC-DB local evidence when available"],
            "code_versions": {"protacxtend": __version__},
            "parameters": model_to_dict(state.search_policy),
            "artifacts": state.memory_updates,
            "human_interventions": [],
            "evidence_cutoff_date": evidence_cutoff_date,
        },
        memories={
            "project": {"request": state.user_request, "constraints": objective["constraints"]},
            "evidence": {"retrieval_census": model_to_dict(state.retrieval_census)},
            "execution": {"workflow_log": model_to_dict(state.workflow_log), "pipeline_status": state.pipeline_status},
            "outcome": {"assay_feedback": model_to_dict(state.assay_feedback)},
        },
    )


def select_next_actions(
    scientific_state: ScientificState,
    contracts: list[ActionContract] | None = None,
    *,
    budget_s: int = 600,
) -> list[ActionDecisionRecord]:
    contracts = contracts or default_action_contracts()
    missing_text = " ".join(scientific_state.unknown.get("decision_critical_questions", [])).lower()
    completed = set(scientific_state.actions.get("completed", []))
    decisions: list[ActionDecisionRecord] = []
    for contract in contracts:
        gate = contract.quality_gate()
        prereq = 1.0 if all(prereq.split(".")[0] in scientific_state.model_dump() for prereq in contract.prerequisites) else 0.65
        cost = 0.1 if contract.timeout_s <= budget_s else 0.8
        failure = 0.1 + 0.08 * len(contract.known_failure_modes)
        redundancy = 0.35 if contract.action_id in completed else 0.0
        relevance = 0.45
        if "target" in missing_text and "target" in contract.action_id:
            relevance = 0.95
        if "context" in missing_text and ("context" in contract.action_id or "experiment" in contract.action_id):
            relevance = 0.88
        if "ternary" in missing_text or "geometry" in missing_text:
            relevance = 0.9 if "dossier" in contract.action_id or "experiment" in contract.action_id else relevance
        if scientific_state.candidates and contract.kind in {"experiment", "critique"}:
            relevance = max(relevance, 0.82)
        validity = 0.95 if gate["usable_in_paper_run"] else 0.55
        score = (
            0.28 * relevance
            + 0.18 * relevance
            + 0.18 * validity
            + 0.12 * prereq
            + 0.12 * 0.7
            + 0.12 * 0.7
            - 0.12 * cost
            - 0.10 * failure
            - 0.08 * redundancy
        )
        decisions.append(
            ActionDecisionRecord(
                action_id=contract.action_id,
                expected_information_gain=round(relevance, 3),
                probability_of_decision_change=round(relevance, 3),
                scientific_validity=round(validity, 3),
                prerequisite_satisfaction=round(prereq, 3),
                cost_penalty=round(cost, 3),
                failure_probability=round(min(0.95, failure), 3),
                redundancy_penalty=round(redundancy, 3),
                orthogonal_value=0.7,
                downstream_unlocks=0.7,
                score=round(score, 3),
                rationale=f"{contract.action_id} addresses: {contract.scientific_question}",
            )
        )
    decisions.sort(key=lambda item: item.score, reverse=True)
    if decisions:
        decisions[0].selected = True
    return decisions


def critique_scientific_state(scientific_state: ScientificState) -> CritiqueRecord:
    failures: list[str] = []
    warnings: list[str] = []
    unsupported: list[str] = []
    labels = {"MEASURED", "CURATED", "REPORTED", "COMPUTED", "PREDICTED", "INFERRED", "HYPOTHETICAL", "CONTRADICTED"}
    for dossier in scientific_state.candidates:
        degradation = dossier.degradation_predictions
        if degradation and "measured" in str(degradation).lower() and "PREDICTED" not in str(degradation):
            unsupported.append(f"{dossier.candidate_id}: possible measured/predicted conflation")
        if not dossier.exact_structure:
            failures.append("chemistry_or_stereochemistry_error")
        if not dossier.provenance_manifest:
            failures.append("provenance_break")
        if "degradation_prediction_not_measured" in dossier.risks:
            warnings.append(f"{dossier.candidate_id}: predicted degradation is not experimental evidence")
    if scientific_state.decision.stopping_state == "SUPPORTED" and scientific_state.unknown.get("decision_critical_questions"):
        failures.append("overconfident_decision")
    if not set(scientific_state.capability_model) >= {"KNOW", "REASON", "DESIGN", "DISCOVER"}:
        failures.append("missing_capability_model")
    if not labels:
        failures.append("missing_evidence_labels")
    status: StoppingState
    if "chemistry_or_stereochemistry_error" in failures:
        status = "REJECT"
    elif failures or scientific_state.unknown.get("decision_critical_questions"):
        status = "REVISE" if scientific_state.candidates else "INSUFFICIENT EVIDENCE"
    else:
        status = scientific_state.decision.stopping_state
    return CritiqueRecord(
        status=status,
        failure_categories=sorted(set(failures)),
        unsupported_claims=unsupported,
        uncertainty=scientific_state.decision.uncertainty,
        recommended_action=scientific_state.decision.next_action,
        warnings=warnings,
    )


def build_experiment_dossier(scientific_state: ScientificState, max_candidates: int = 6) -> ExperimentDossier:
    candidate_ids = [candidate.candidate_id for candidate in scientific_state.candidates[:max_candidates]]
    digest = sha256("|".join(candidate_ids).encode("utf-8")).hexdigest()[:12]
    return ExperimentDossier(
        experiment_id=f"exp_{digest}",
        candidate_ids=candidate_ids,
        objective="Discriminate degradation, ternary geometry, permeability/context, and assay-artifact hypotheses.",
        frozen_predictions={candidate.candidate_id: candidate.degradation_predictions for candidate in scientific_state.candidates[:max_candidates]},
        assay_ladder=[
            "compound identity and purity",
            "binary target engagement",
            "E3 engagement where feasible",
            "ternary complex or proximity evidence",
            "cellular target degradation dose response",
            "Dmax/DC50 with replicates and confidence intervals",
            "time course and recovery",
            "hook-effect concentration range",
            "proteasome dependence",
            "E3 dependence",
            "inactive stereoisomer or nonbinding analog",
            "viability/cytotoxicity separation",
            "orthogonal degradation or target-engagement assay",
            "proteome-level selectivity for lead",
            "permeability or intracellular exposure assay",
        ],
        controls=[
            "vehicle control",
            "proteasome inhibitor rescue",
            "E3 loss or competition control",
            "inactive stereoisomer or nonbinding analog",
            "cell viability counter-assay",
        ],
        success_criteria=[
            "reproducible degradation with confidence intervals",
            "mechanistic dependence consistent with hypothesis",
            "prediction rank or uncertainty changes after outcome ingestion",
        ],
        failure_criteria=[
            "material identity failure",
            "target engagement absent",
            "E3/proteasome independence",
            "unacceptable cytotoxicity confounds degradation",
        ],
        outcome_ingestion_schema={
            "protocol_version": "str",
            "biological_system": "str",
            "treatment_conditions": "str",
            "raw_data_uri": "str",
            "replicates": "int",
            "measured_dc50_nM": "optional float",
            "measured_dmax_percent": "optional float",
            "uncertainty": "str",
            "qc_status": "str",
            "artifact_checksum": "str",
        },
        allowed_human_interventions=["approval", "chemist route correction", "assay feasibility override"],
        evidence_cutoff_date=str(scientific_state.provenance.get("evidence_cutoff_date", "")),
    )


def pilot_benchmark_specs() -> list[BenchmarkTaskSpec]:
    competencies = [
        ("knowledge_acquisition", "Atomic", "Recover target/E3 evidence and distinguish measured from predicted values."),
        ("molecular_design", "Compositional", "Select warhead, exit vector, recruiter, linker, and negative control."),
        ("structural_reasoning", "Decision", "Explain ternary feasibility using geometry features without overclaiming docking."),
        ("biological_reasoning", "Adversarial", "Resolve cell-context and E3-expression contradiction."),
        ("scientific_decision_making", "Autonomous", "Choose next action under incomplete evidence and cost limits."),
        ("research_autonomy", "Prospective", "Lock candidate predictions, ingest outcome, diagnose failure, and redesign."),
    ]
    return [
        BenchmarkTaskSpec(
            task_id=f"pilot_{index:03d}",
            competency=competency,
            difficulty_tier=tier,
            scientific_objective=objective,
            input_entities={"target": "BRD4", "e3": "CRBN/VHL", "cell_line": "MM1.S"},
            biological_context="targeted protein degradation, preclinical research",
            evidence_cutoff_date="2026-09-01",
            permitted_resources=["local curated data", "PROTAC-DB evidence", "registered deterministic actions"],
            expected_artifacts=["scientific_state.json", "decision_trace.json", "candidate_or_experiment_dossier.json"],
            process_rubric=["valid action choice", "failure recovery", "appropriate stopping"],
            evidence_rubric=["source relevance", "measured/predicted separation", "provenance completeness"],
            outcome_rubric=["scientific utility", "candidate validity", "expert-review readiness"],
            critical_errors=["unsupported measured claim", "wrong target identity", "hidden human intervention", "leakage"],
            split_tags=["pilot", tier.lower(), competency],
            leakage_record={"status": "development_task_not_protected"},
        )
        for index, (competency, tier, objective) in enumerate(competencies, start=1)
    ]


def scientific_contract_summary(state: WorkflowState | None = None) -> dict[str, Any]:
    contracts = default_action_contracts()
    payload: dict[str, Any] = {
        "capability_model": ["KNOW", "REASON", "DESIGN", "DISCOVER"],
        "evidence_labels": list(EvidenceLabel.__args__),  # type: ignore[attr-defined]
        "stopping_states": list(StoppingState.__args__),  # type: ignore[attr-defined]
        "action_contracts": [model_to_dict(contract) for contract in contracts],
        "action_quality_gates": [contract.quality_gate() for contract in contracts],
        "external_method_registry": [model_to_dict(method) for method in reviewed_external_methods()],
        "pilot_benchmark_specs": [model_to_dict(task) for task in pilot_benchmark_specs()],
    }
    if state is not None:
        scientific_state = build_scientific_state(state)
        payload["scientific_state"] = model_to_dict(scientific_state)
        payload["next_actions"] = [model_to_dict(item) for item in select_next_actions(scientific_state)]
        payload["critique"] = model_to_dict(critique_scientific_state(scientific_state))
        payload["experiment_dossier"] = model_to_dict(build_experiment_dossier(scientific_state))
    return payload
