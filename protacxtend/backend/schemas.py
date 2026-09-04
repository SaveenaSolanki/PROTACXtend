"""Workflow schemas.

The project is designed to use Pydantic models in production. The execution
environment used for lightweight demos may not have Pydantic installed, so this
module provides a tiny compatible fallback that supports the subset used by the
workflow: typed attributes, default factories, and ``model_dump``.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional


try:  # pragma: no cover - exercised when pydantic is installed.
    from pydantic import BaseModel, Field

    PYDANTIC_AVAILABLE = True
except Exception:  # pragma: no cover - fallback is covered by local tests.
    PYDANTIC_AVAILABLE = False
    _MISSING = object()

    class _FieldInfo:
        def __init__(self, default: Any = _MISSING, default_factory: Any = None):
            self.default = default
            self.default_factory = default_factory

        def resolve(self) -> Any:
            if self.default_factory is not None:
                return self.default_factory()
            if self.default is _MISSING:
                return None
            return copy.deepcopy(self.default)

    def Field(default: Any = _MISSING, default_factory: Any = None, **_: Any) -> Any:
        return _FieldInfo(default=default, default_factory=default_factory)

    class BaseModel:
        """Small Pydantic-like fallback used only when Pydantic is absent."""

        def __init__(self, **data: Any):
            annotations: Dict[str, Any] = {}
            for cls in reversed(self.__class__.__mro__):
                annotations.update(getattr(cls, "__annotations__", {}))

            for name in annotations:
                default = getattr(self.__class__, name, _MISSING)
                if isinstance(default, _FieldInfo):
                    value = default.resolve()
                elif default is not _MISSING:
                    value = copy.deepcopy(default)
                else:
                    value = None
                setattr(self, name, data.pop(name, value))

            for name, value in data.items():
                setattr(self, name, value)

        def model_dump(self, **_: Any) -> Dict[str, Any]:
            def convert(value: Any) -> Any:
                if isinstance(value, BaseModel):
                    return value.model_dump()
                if isinstance(value, list):
                    return [convert(item) for item in value]
                if isinstance(value, dict):
                    return {key: convert(item) for key, item in value.items()}
                return copy.deepcopy(value)

            annotations: Dict[str, Any] = {}
            for cls in reversed(self.__class__.__mro__):
                annotations.update(getattr(cls, "__annotations__", {}))
            return {name: convert(getattr(self, name, None)) for name in annotations}

        def model_copy(self, update: Optional[Dict[str, Any]] = None, **_: Any) -> "BaseModel":
            payload = self.model_dump()
            if update:
                payload.update(update)
            return self.__class__(**payload)


class ParsedObjective(BaseModel):
    target_name: str = ""
    target_uniprot_id: Optional[str] = None
    disease_context: Optional[str] = None
    warhead_smiles: Optional[str] = None
    e3_ligase: Optional[str] = None
    e3_ligand_smiles: Optional[str] = None
    preferred_linker_types: List[str] = Field(default_factory=list)
    candidate_count: int = 50
    optimization_objective: str = "balanced degradation, ADME/Tox, novelty, and synthesis feasibility"
    admet_constraints: Dict[str, Any] = Field(default_factory=dict)
    novelty_requirement: str = "medium"
    use_structure_aware_ranking: bool = False
    use_retrosynthesis_filtering: bool = False
    desired_output_format: str = "markdown"
    ranking_weights: Dict[str, float] = Field(default_factory=dict)
    cell_line: Optional[str] = None
    assay_context: Optional[str] = None
    expression_overrides: Dict[str, float] = Field(default_factory=dict)


class AgentTrace(BaseModel):
    agent: str = ""
    thought: str = ""
    action: str = ""
    observation: str = ""
    processing_time_s: float = 0.0


class TargetRecord(BaseModel):
    target_name: str = ""
    gene_symbol: str = ""
    uniprot_id: Optional[str] = None
    organism: str = "human"
    synonyms: List[str] = Field(default_factory=list)
    structures: List[str] = Field(default_factory=list)
    alphafold_id: Optional[str] = None
    uniprot_confidence: float = 0.0
    known_binder_count: int = 0
    tractability_score: float = 0.0
    source: str = "local"
    external_ids: Dict[str, Any] = Field(default_factory=dict)
    biology_context: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class BinderRecord(BaseModel):
    name: str = ""
    target: str = ""
    smiles: str = ""
    activity_type: str = "IC50"
    activity_nM: Optional[float] = None
    p_activity: Optional[float] = None
    assay_confidence: float = 0.0
    source: str = "local"
    year: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WarheadRecord(BaseModel):
    name: str = ""
    target: str = ""
    smiles: str = ""
    source: str = "local"
    potency_nM: Optional[float] = None
    potency_score: float = 0.0
    derivatization_score: float = 0.0
    exit_vector_confidence: float = 0.0
    source_confidence: float = 0.0
    chemical_validity: str = "unchecked"
    provenance: Dict[str, Any] = Field(default_factory=dict)


class E3LigandRecord(BaseModel):
    name: str = ""
    e3_ligase: str = ""
    smiles: str = ""
    ligand_class: str = ""
    source: str = "local"
    exit_vector_confidence: float = 0.0
    stereochemistry_valid: bool = True
    source_confidence: float = 0.0
    diversity_score: float = 0.0
    provenance: Dict[str, Any] = Field(default_factory=dict)


class ExitVectorRecord(BaseModel):
    molecule_name: str = ""
    molecule_role: str = ""
    smiles: str = ""
    attachment_atom_index: Optional[int] = None
    attachment_smarts: str = ""
    confidence: float = 0.0
    rationale: str = ""
    warning: Optional[str] = None
    failure_reason: Optional[str] = None


class LinkerRecord(BaseModel):
    name: str = ""
    smiles: str = ""
    linker_class: str = ""
    source: str = "curated"
    graph_length: int = 0
    effective_length: float = 0.0
    rotatable_bonds: int = 0
    tpsa_contribution: float = 0.0
    hbd: int = 0
    hba: int = 0
    synthetic_feasibility_proxy: float = 0.0
    validity_status: str = "unchecked"
    provenance: Dict[str, Any] = Field(default_factory=dict)


class ConstructionAttempt(BaseModel):
    warhead_name: str = ""
    e3_ligand_name: str = ""
    linker_name: str = ""
    strategy: str = ""
    reaction_class: str = ""
    success: bool = False
    failure_category: Optional[str] = None
    message: str = ""
    candidate_id: Optional[str] = None


class CandidateRecord(BaseModel):
    candidate_id: str = ""
    evolution_generation: int = 0
    parent_ids: List[str] = Field(default_factory=list)
    operator_applied: str = ""
    # §3.7 structure-quality: AlphaFold pLDDT for the binding region (carried
    # from target resolution; None until a structure source provides it)
    plddt_min: Optional[float] = None
    plddt_mean: Optional[float] = None
    target: str = ""
    e3_ligase: str = ""
    warhead_name: str = ""
    warhead_smiles: str = ""
    warhead_source: str = ""
    e3_ligand_name: str = ""
    e3_ligand_smiles: str = ""
    linker_name: str = ""
    linker_smiles: str = ""
    linker_class: str = ""
    full_protac_smiles: str = ""
    assembly_strategy: str = ""
    reaction_class: str = ""
    validity_status: str = "unchecked"
    synthetic_feasibility_score: float = 0.0
    provenance: Dict[str, Any] = Field(default_factory=dict)
    warning_flags: List[str] = Field(default_factory=list)
    mw: Optional[float] = None
    tpsa: Optional[float] = None
    logp: Optional[float] = None
    hbd: Optional[int] = None
    hba: Optional[int] = None
    rotatable_bonds: Optional[int] = None


class DegradationPrediction(BaseModel):
    candidate_id: str = ""
    predicted_dc50_nM: Optional[float] = None
    predicted_logdc50: Optional[float] = None
    predicted_dmax_percent: Optional[float] = None
    degradation_probability: float = 0.0
    model_confidence: float = 0.0
    applicability_domain_score: float = 0.0
    model_version: str = "SynGlue-demo-heuristic-v0.1"
    warning: Optional[str] = None
    # Degradation backend (TACK-style primary when available, else Chemprop)
    tack_dc50_nM: Optional[float] = None
    tack_dmax_pct: Optional[float] = None
    tack_active: Optional[bool] = None
    tack_active_prob: Optional[float] = None
    # Chemprop cross-check (filled when the Chemprop endpoint also ran)
    chemprop_dc50_nM: Optional[float] = None
    chemprop_dmax_pct: Optional[float] = None


class CoverageCell(BaseModel):
    """One warhead x E3 x linker design cell (SEARCH_INSTRUMENTATION coverage
    matrix). Discipline: best_pass_rate stays NULL until a P4ward measurement
    exists — never backfilled from the uncalibrated proxy."""
    warhead_inchikey: str = ""
    e3: str = ""
    linker_inchikey: str = ""
    attach_pts: str = ""
    n_evaluated: int = 0
    best_proxy_score: Optional[float] = None
    best_pass_rate: Optional[float] = None   # NULL until measured
    n_passed: int = 0
    n_poses: int = 0
    last_run_id: str = ""
    measured: bool = False


class RetrievalCensus(BaseModel):
    """Node-5 evidence accounting: how much was looked at vs returned (AGENT_ARCHITECTURE_UPDATE §1.2)."""
    source: str = ""
    query: str = ""
    n_reported_total: Optional[int] = None
    n_fetched: int = 0
    n_after_dedup: int = 0
    n_after_quality: int = 0
    n_returned: int = 0
    truncated: bool = False
    selection_rule: str = ""
    cache_hit: bool = False


class GenerationRecord(BaseModel):
    """Node-19 per-generation record (AGENT_ARCHITECTURE_UPDATE §2.2)."""
    generation: int = 0
    n_produced: int = 0
    n_novel: int = 0
    novelty_ratio: float = 0.0
    best_score: float = 0.0
    mean_score: float = 0.0
    operator_counts: Dict[str, int] = Field(default_factory=dict)
    fitness_spec_id: str = ""


class CalibrationRecord(BaseModel):
    """Node-20 proxy-vs-P4ward calibration point (AGENT_ARCHITECTURE_UPDATE §3.5)."""
    candidate_inchikey: str = ""
    proxy_score: float = 0.0
    p4ward_pass_rate: Optional[float] = None
    n_passed: int = 0
    n_poses: int = 0
    plddt_min: Optional[float] = None
    plddt_mean: Optional[float] = None
    compute_hours: float = 0.0
    label_source: str = "p4ward"


class FitnessSpec(BaseModel):
    score_field: str = "final_priority_score"
    weights: Dict[str, float] = Field(default_factory=dict)
    config_hash: str = ""
    label_source: str = "heuristic"  # heuristic|published|p4ward|trained


class ADMETPrediction(BaseModel):
    candidate_id: str = ""
    mw: float = 0.0
    tpsa: float = 0.0
    logp: float = 0.0
    hbd: int = 0
    hba: int = 0
    rotatable_bonds: int = 0
    qed: Optional[float] = None
    sa_score_proxy: float = 0.0
    hERG_risk: str = "unknown"
    AMES_risk: str = "unknown"
    DILI_risk: str = "unknown"
    CYP_risk: str = "unknown"
    Pgp_risk: str = "unknown"
    solubility_risk: str = "unknown"
    overall_admet_penalty: float = 0.0
    warning: Optional[str] = None


class NoveltyResult(BaseModel):
    candidate_id: str = ""
    nearest_known_protac: Optional[str] = None
    max_tanimoto_similarity: float = 0.0
    duplicate_flag: bool = False
    novelty_score: float = 0.0
    scaffold_novelty: float = 0.0
    component_novelty: float = 0.0
    linker_novelty: float = 0.0
    # Live patent cross-reference evidence (PubChem PUG-View "Patents" section)
    patent_count: int = 0
    patent_ids: List[str] = Field(default_factory=list)
    patent_source: str = "unavailable"  # pubchem_patents | unavailable


class ApplicabilityDomainResult(BaseModel):
    candidate_id: str = ""
    similarity_to_training_set: float = 0.0
    embedding_distance: float = 0.0
    domain_status: str = "unknown"
    warning: Optional[str] = None


class TernaryFeasibilityResult(BaseModel):
    candidate_id: str = ""
    fast_geometry_feasibility_score: float = 0.0
    linker_reachability_score: float = 0.0
    ternary_plausibility_score: float = 0.0
    docking_status: str = "not_run"
    interface_warning: Optional[str] = None
    structure_availability: str = "unknown"
    proceed_to_expensive_modeling: bool = False
    structural_backend: str = ""
    pose_file: Optional[str] = None
    interface_quality_score: Optional[float] = None
    interface_contact_count: Optional[int] = None
    polar_contact_count: Optional[int] = None
    clash_count: Optional[int] = None
    buried_sasa_proxy: Optional[float] = None
    nearest_lysine: Optional[str] = None
    nearest_lysine_distance_A: Optional[float] = None
    accessible_lysine_count: Optional[int] = None
    productive_lysine_count: Optional[int] = None
    lysine_geometry_score: Optional[float] = None
    linker_strain_score: Optional[float] = None
    linker_energy_spread: Optional[float] = None
    real_structural_score: Optional[float] = None
    structural_confidence: Optional[float] = None
    structural_warnings: List[str] = Field(default_factory=list)


class E3ContextPrediction(BaseModel):
    candidate_id: str = ""
    e3_ligase: str = ""
    cell_line: str = "default"
    target_localization: str = "nuclear"
    expression_score: float = 0.0
    colocalization_score: float = 0.0
    ligand_availability_score: float = 0.0
    structural_support_score: float = 0.0
    resistance_risk: float = 0.0
    total_context_score: float = 0.0
    confidence: float = 0.0
    contraindications: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    explanation: str = ""


class CooperativityPrediction(BaseModel):
    candidate_id: str = ""
    predicted_alpha: float = 1.0
    log_alpha: float = 0.0
    cooperativity_score: float = 0.5
    interface_contact_score: float = 0.0
    linker_strain_score: float = 0.0
    lysine_geometry_score: float = 0.0
    ternary_geometry_score: float = 0.0
    confidence: float = 0.0
    model_version: str = "cooperativity-proxy-v0.1"
    warning: Optional[str] = None


class HookEffectPrediction(BaseModel):
    candidate_id: str = ""
    concentration_nM: List[float] = Field(default_factory=list)
    ternary_fraction: List[float] = Field(default_factory=list)
    hook_concentration_nM: Optional[float] = None
    max_ternary_fraction: float = 0.0
    high_concentration_fraction: float = 0.0
    hook_risk: str = "unknown"
    therapeutic_window_score: float = 0.0
    model_version: str = "hook-occupancy-v0.1"
    warning: Optional[str] = None


class AssayFeedbackRecord(BaseModel):
    candidate_id: str = ""
    target: str = ""
    e3_ligase: str = ""
    cell_line: str = "default"
    smiles: str = ""
    measured_dc50_nM: Optional[float] = None
    measured_dmax_percent: Optional[float] = None
    measured_hook_concentration_nM: Optional[float] = None
    degradation_observed: Optional[bool] = None
    source: str = "user_feedback"
    notes: str = ""


class ActiveLearningUpdate(BaseModel):
    status: str = "not_run"
    feedback_count: int = 0
    training_rows: int = 0
    dataset_path: str = ""
    registry_path: str = ""
    active_model_version: str = ""
    model_artifact_path: str = ""
    rollback_model_artifact_path: str = ""
    retraining_recommendation: str = ""
    warnings: List[str] = Field(default_factory=list)


class SearchPolicy(BaseModel):
    linker_budget: int = 32
    e3_ligand_budget: int = 6
    exit_vector_budget: int = 12
    stereoisomer_budget_per_candidate: int = 4
    construction_budget: int = 200
    cheap_filter_budget: int = 100
    expensive_modeling_budget: int = 12
    final_candidate_budget: int = 50
    policy_version: str = "controlled-funnel-v0.1"


class RankingResult(BaseModel):
    candidate_id: str = ""
    rank: int = 0
    tier: str = "Tier 3"
    final_priority_score: float = 0.0
    confidence: float = 0.0
    reason_for_rank: str = ""
    penalty_explanation: str = ""
    uncertainty_flags: List[str] = Field(default_factory=list)


class ReflectionReview(BaseModel):
    candidate_id: str = ""
    review_score: float = 0.0
    plausibility_score: float = 0.0
    evidence_score: float = 0.0
    risk_score: float = 0.0
    overclaiming_warning: Optional[str] = None
    factual_consistency_check: str = "unchecked"
    recommendations: List[str] = Field(default_factory=list)


class DiversityCluster(BaseModel):
    cluster_id: str = ""
    candidate_ids: List[str] = Field(default_factory=list)
    representative_id: Optional[str] = None
    redundancy_score: float = 0.0
    diversity_score: float = 0.0


class WorkflowState(BaseModel):
    user_request: str = ""
    parsed_objective: ParsedObjective = Field(default_factory=ParsedObjective)
    design_plan: Dict[str, Any] = Field(default_factory=dict)
    target_record: Optional[TargetRecord] = None
    retrieved_binders: List[BinderRecord] = Field(default_factory=list)
    selected_warheads: List[WarheadRecord] = Field(default_factory=list)
    selected_e3_ligands: List[E3LigandRecord] = Field(default_factory=list)
    exit_vectors: List[ExitVectorRecord] = Field(default_factory=list)
    generated_linkers: List[LinkerRecord] = Field(default_factory=list)
    construction_attempts: List[ConstructionAttempt] = Field(default_factory=list)
    assembled_candidates: List[CandidateRecord] = Field(default_factory=list)
    valid_candidates: List[CandidateRecord] = Field(default_factory=list)
    degradation_predictions: List[DegradationPrediction] = Field(default_factory=list)
    admet_predictions: List[ADMETPrediction] = Field(default_factory=list)
    novelty_results: List[NoveltyResult] = Field(default_factory=list)
    applicability_domain_results: List[ApplicabilityDomainResult] = Field(default_factory=list)
    ternary_feasibility_results: List[TernaryFeasibilityResult] = Field(default_factory=list)
    e3_context_predictions: List[E3ContextPrediction] = Field(default_factory=list)
    cooperativity_predictions: List[CooperativityPrediction] = Field(default_factory=list)
    hook_effect_predictions: List[HookEffectPrediction] = Field(default_factory=list)
    ranking_results: List[RankingResult] = Field(default_factory=list)
    reflection_reviews: List[ReflectionReview] = Field(default_factory=list)
    evolved_candidates: List[CandidateRecord] = Field(default_factory=list)
    diversity_clusters: List[DiversityCluster] = Field(default_factory=list)
    final_ranked_candidates: List[CandidateRecord] = Field(default_factory=list)
    pipeline_status: List[Dict[str, Any]] = Field(default_factory=list)
    report: str = ""
    workflow_log: List[AgentTrace] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    memory_updates: List[Dict[str, Any]] = Field(default_factory=list)
    assay_feedback: List[AssayFeedbackRecord] = Field(default_factory=list)
    active_learning_update: ActiveLearningUpdate = Field(default_factory=ActiveLearningUpdate)
    search_policy: SearchPolicy = Field(default_factory=SearchPolicy)
    cheap_filter_summary: Dict[str, Any] = Field(default_factory=dict)
    expensive_modeling_candidate_ids: List[str] = Field(default_factory=list)

    # AGENT_ARCHITECTURE_UPDATE additions (observability of what was NOT done)
    retrieval_census: List[RetrievalCensus] = Field(default_factory=list)
    retrieval_status: str = "ok"          # ok | sparse | empty
    seen_inchikeys: set[str] = Field(default_factory=set)
    generation_records: List[GenerationRecord] = Field(default_factory=list)
    fitness_spec: Optional[FitnessSpec] = None
    revised_degradation: List[DegradationPrediction] = Field(default_factory=list)


def model_to_dict(value: Any) -> Any:
    """Return a JSON-serializable dict/list/value for Pydantic or fallback models."""

    if hasattr(value, "model_dump"):
        return model_to_dict(value.model_dump())
    if isinstance(value, list):
        return [model_to_dict(item) for item in value]
    if isinstance(value, set):
        return sorted(model_to_dict(item) for item in value)
    if isinstance(value, dict):
        return {key: model_to_dict(item) for key, item in value.items()}
    return value
