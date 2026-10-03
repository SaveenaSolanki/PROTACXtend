"""Typed schemas for the canonical PROTACXtend execution stack.

The canonical stack is the single control plane for every design run:

    User
     -> Scientific Request Parser
     -> Orchestrator
     -> Task Graph
     -> Specialized Scientific Modules
     -> Tool Executor
     -> Evidence Store
     -> Critic / Verifier
     -> Decision Engine
     -> TherapeuticStrategy

The types below are the contract between those stages. They are deliberately
stable, serialisable and independent from the two legacy execution engines
(``protacxtend.agents.graph`` and ``protacxtend.agents.agentic_core``), which
are now *tool-level* engines invoked by this control plane rather than
alternative entry points.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from protacxtend.backend.schemas import BaseModel, Field
from protacxtend.canonical.failures import CriticResult, Failure


class ScientificModuleId(str, Enum):
    """The nine logical scientific divisions, beneath one orchestrator."""

    REQUEST_PARSER = "scientific_request_parser"
    TARGET_DISEASE = "target_disease"
    TPD_TRACTABILITY = "tpd_tractability"
    E3_SELECTION = "e3_selection"
    CHEMISTRY_WARHEAD = "chemistry_warhead"
    STRUCTURE_TERNARY = "structure_ternary"
    DEGRADATION = "degradation"
    ADME_SAFETY = "adme_safety"
    RESISTANCE_BIOMARKER = "resistance_biomarker"
    EXPERIMENTAL_DESIGN = "experimental_design"


#: Ordered list used for reporting, benchmarking and attribution.
SCIENTIFIC_MODULE_ORDER: list[str] = [
    ScientificModuleId.TARGET_DISEASE.value,
    ScientificModuleId.TPD_TRACTABILITY.value,
    ScientificModuleId.E3_SELECTION.value,
    ScientificModuleId.CHEMISTRY_WARHEAD.value,
    ScientificModuleId.STRUCTURE_TERNARY.value,
    ScientificModuleId.DEGRADATION.value,
    ScientificModuleId.ADME_SAFETY.value,
    ScientificModuleId.RESISTANCE_BIOMARKER.value,
    ScientificModuleId.EXPERIMENTAL_DESIGN.value,
]

#: Version of the typed scientific output contract.
STRATEGY_SCHEMA_VERSION = "TherapeuticStrategy.v1"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"
    SKIPPED = "skipped"
    #: Explicit, typed non-answer: the module could not be recovered by the
    #: retry/fallback policy and the run declines to fabricate a result.
    ABSTAINED = "abstained"


class ScientificRequest(BaseModel):
    """Typed output of the Scientific Request Parser."""

    raw_request: str = ""
    normalized_request: str = ""
    target: str = ""
    target_uniprot_id: str | None = None
    e3_ligase: str = ""
    disease_context: str = ""
    cell_line: str = ""
    intent: str = "general_query"
    task_type: str = "general_query"
    requested_modality: str = "unspecified"
    objectives: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    candidate_count: int = 50
    missing_required: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class ModuleResult(BaseModel):
    """One specialized scientific module's contribution to a run.

    ``module_id`` is the stable attribution key for benchmarks: every claim,
    candidate and failure can be traced back to exactly one module here.
    """

    module_id: str = ""
    title: str = ""
    status: TaskStatus = TaskStatus.PENDING
    summary: str = ""
    outputs: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    runtime_s: float = 0.0


class TaskNodeSpec(BaseModel):
    node_id: str = ""
    module_id: str = ""
    title: str = ""
    depends_on: list[str] = Field(default_factory=list)
    optional: bool = False
    reason: str = ""


class TaskGraphSpec(BaseModel):
    graph_id: str = ""
    nodes: list[TaskNodeSpec] = Field(default_factory=list)

    def node_ids(self) -> list[str]:
        return [node.node_id for node in self.nodes]

    def topological_order(self) -> list[str]:
        """Kahn topological sort; raises on cycles or unknown dependencies."""
        ids = self.node_ids()
        known = set(ids)
        deps = {node.node_id: [d for d in node.depends_on if d in known] for node in self.nodes}
        order: list[str] = []
        ready = [n for n in ids if not deps[n]]
        while ready:
            current = ready.pop(0)
            order.append(current)
            for node_id in ids:
                if current in deps[node_id]:
                    deps[node_id].remove(current)
                    if not deps[node_id] and node_id not in order and node_id not in ready:
                        ready.append(node_id)
        if len(order) != len(ids):
            remaining = sorted(set(ids) - set(order))
            raise ValueError(f"Task graph has a cycle or unknown dependency among: {remaining}")
        return order


class CriticVerdict(BaseModel):
    """Output of the Critic / Verifier stage.

    ``failure_categories`` is retained as the flat, backward-compatible view.
    ``failures`` and ``critic_results`` carry the typed taxonomy and the
    per-critic evidence/mechanism/reproducibility breakdown.
    """

    status: str = "INSUFFICIENT EVIDENCE"
    failure_categories: list[str] = Field(default_factory=list)
    failures: list[Failure] = Field(default_factory=list)
    critic_results: dict[str, CriticResult] = Field(default_factory=dict)
    unsupported_claims: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    uncertainty: dict[str, str] = Field(default_factory=dict)
    recommended_action: str = ""
    checks_run: list[str] = Field(default_factory=list)
    policy_action: str = ""


# ══════════════════════════════════════════════════════════════════════
# Typed scientific output sub-models
# ══════════════════════════════════════════════════════════════════════

class TargetValidation(BaseModel):
    gene_symbol: str = ""
    uniprot_id: str | None = None
    protein_name: str = ""
    organism: str = "human"
    structures: list[str] = Field(default_factory=list)
    alphafold_id: str | None = None
    known_binder_count: int = 0
    validation_status: str = "unresolved"  # resolved | resolved_curated | unresolved
    evidence_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TPDTractabilityAssessment(BaseModel):
    known_binder_count: int = 0
    known_e3_ligand_count: int = 0
    has_experimental_structure: bool = False
    tractability_score: float | None = None
    tractable: bool = False
    rationale: str = ""
    limitations: list[str] = Field(default_factory=list)


class E3Recommendation(BaseModel):
    recommended_e3: str = ""
    alternative_e3s: list[str] = Field(default_factory=list)
    rejected_e3s: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""
    assumption: bool = False
    cell_context: list[dict[str, Any]] = Field(default_factory=list)


class BinaryStructureAssessment(BaseModel):
    available: bool = False
    structures: list[str] = Field(default_factory=list)
    method: str = "none"
    notes: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class TernaryComplexAssessment(BaseModel):
    available: bool = False
    method: str = "none"
    n_records: int = 0
    scores: list[float] = Field(default_factory=list)
    cooperativity: list[dict[str, Any]] = Field(default_factory=list)
    claim_allowed: bool = False
    limitations: list[str] = Field(default_factory=list)


class DegradationPredictionSummary(BaseModel):
    n_predictions: int = 0
    model_versions: list[str] = Field(default_factory=list)
    heuristic_fallback: bool = False
    top_dc50: list[Any] = Field(default_factory=list)
    hook_effect_records: int = 0
    ternary_revised: int = 0
    claim_allowed: bool = False
    limitations: list[str] = Field(default_factory=list)


class ADMERisk(BaseModel):
    candidate_id: str = ""
    overall_penalty: float | None = None
    flags: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class SafetyRisk(BaseModel):
    candidate_id: str = ""
    category: str = ""
    severity: str = "unknown"
    details: dict[str, Any] = Field(default_factory=dict)


class ResistanceMechanism(BaseModel):
    e3_ligase: str = ""
    mechanism: str = ""
    risk: str = ""
    evidence: str = ""


class Biomarker(BaseModel):
    name: str = ""
    role: str = ""
    evidence: str = ""
    status: str = "unavailable"


class CombinationStrategy(BaseModel):
    recommended: bool = False
    rationale: str = ""
    partners: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ExperimentalPlanStep(BaseModel):
    step: int = 0
    assay: str = ""
    purpose: str = ""
    controls: list[str] = Field(default_factory=list)


class ExperimentalPlan(BaseModel):
    objective: str = ""
    candidate_ids: list[str] = Field(default_factory=list)
    steps: list[ExperimentalPlanStep] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    failure_criteria: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class GoNoGoCriterion(BaseModel):
    criterion: str = ""
    threshold: str = ""
    current_status: str = ""
    met: bool | None = None
    rationale: str = ""


class EvidenceBundle(BaseModel):
    n_records: int = 0
    by_module: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    refs: list[str] = Field(default_factory=list)


class Contradiction(BaseModel):
    topic: str = ""
    left: str = ""
    right: str = ""
    resolution: str = ""
    severity: str = "warning"


class UncertaintyDecomposition(BaseModel):
    model: str = ""
    structural: str = ""
    evidence: str = ""
    assay_context: str = ""
    biology: str = ""
    data: str = ""


class RunManifest(BaseModel):
    run_id: str = ""
    strategy_id: str = ""
    schema_version: str = STRATEGY_SCHEMA_VERSION
    engine: str = ""
    execution_mode: str = ""
    request: str = ""
    started_at: str = ""
    finished_at: str = ""
    runtime_s: float = 0.0
    protacxtend_version: str = ""
    module_status: dict[str, str] = Field(default_factory=dict)
    module_runtimes: dict[str, float] = Field(default_factory=dict)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class TherapeuticStrategy(BaseModel):
    """Final typed output of the canonical stack.

    Every discovery run produces one of these. It is the *decision* artifact
    for benchmarking, UI rendering, scoring and downstream plots; markdown,
    CSV and JSON are renderings of it. Every field is evidence-linked and
    carries explicit limitations so measured/predicted separation survives.
    """

    # ── Identity ──
    strategy_id: str = ""
    run_id: str = ""
    schema_version: str = STRATEGY_SCHEMA_VERSION
    execution_mode: str = ""

    # ── Objective ──
    target: str = ""
    disease_context: str = ""
    indication: str = ""  # legacy alias of disease_context
    e3_ligase: str = ""    # legacy alias of recommended_e3
    objective: str = ""
    design_hypothesis: str = ""
    stopping_state: str = "INSUFFICIENT EVIDENCE"

    # ── Typed scientific output ──
    target_validation: TargetValidation = Field(default_factory=TargetValidation)
    tpd_tractability: TPDTractabilityAssessment = Field(default_factory=TPDTractabilityAssessment)
    recommended_e3: str = ""
    alternative_e3s: list[str] = Field(default_factory=list)
    rejected_e3s: list[dict[str, Any]] = Field(default_factory=list)
    warheads: list[dict[str, Any]] = Field(default_factory=list)
    attachment_vectors: list[dict[str, Any]] = Field(default_factory=list)
    linker_hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    candidate_protacs: list[dict[str, Any]] = Field(default_factory=list)
    binary_structure_assessment: BinaryStructureAssessment = Field(default_factory=BinaryStructureAssessment)
    ternary_complex_assessment: TernaryComplexAssessment = Field(default_factory=TernaryComplexAssessment)
    degradation_prediction: DegradationPredictionSummary = Field(default_factory=DegradationPredictionSummary)
    adme_risks: list[ADMERisk] = Field(default_factory=list)
    safety_risks: list[SafetyRisk] = Field(default_factory=list)
    resistance_mechanisms: list[ResistanceMechanism] = Field(default_factory=list)
    biomarkers: list[Biomarker] = Field(default_factory=list)
    combination_strategy: CombinationStrategy = Field(default_factory=CombinationStrategy)
    experimental_plan: ExperimentalPlan = Field(default_factory=ExperimentalPlan)
    go_no_go_criteria: list[GoNoGoCriterion] = Field(default_factory=list)
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)
    contradictions: list[Contradiction] = Field(default_factory=list)
    uncertainty: UncertaintyDecomposition = Field(default_factory=UncertaintyDecomposition)
    run_manifest: RunManifest = Field(default_factory=RunManifest)

    # ── Backward-compatible / derived views ──
    recommended_candidates: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    claims_allowed: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_experiments: list[dict[str, Any]] = Field(default_factory=list)
    module_status: dict[str, str] = Field(default_factory=dict)
    decision_rationale: str = ""
    next_action: str = ""
    critic: CriticVerdict = Field(default_factory=CriticVerdict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class CanonicalRunResult(BaseModel):
    """Envelope returned by :class:`CanonicalOrchestrator`."""

    run_id: str = ""
    status: str = "unknown"
    request: ScientificRequest = Field(default_factory=ScientificRequest)
    task_graph: TaskGraphSpec = Field(default_factory=TaskGraphSpec)
    module_results: list[ModuleResult] = Field(default_factory=list)
    critic: CriticVerdict = Field(default_factory=CriticVerdict)
    strategy: TherapeuticStrategy = Field(default_factory=TherapeuticStrategy)
    engine_state: Any = None
    policy_decisions: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    runtime_s: float = 0.0
