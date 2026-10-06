"""Canonical scientific state + termination policy for agentic architecture v1.

One authoritative representation (``TherapeuticHypothesisState``) that every
worker/tool action updates through validated interfaces. Sections mirror the
architecture specification §5. Fields without supporting evidence are explicitly
``UNKNOWN`` / ``INSUFFICIENT_EVIDENCE`` — never invented numbers.
"""
from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Optional

from protacxtend.backend.schemas import BaseModel, Field
from protacxtend.architecture.ontology import (
    Claim, Contradiction, Disagreement, EvidenceRecordV1, ScientificAxisProfile,
    UncertaintyAxis,
)

ARCHITECTURE_VERSION = "PROTACXTEND_AGENTIC_ARCHITECTURE_V1"
STATE_SCHEMA_VERSION = "therapeutic_hypothesis_state.v1"
EVIDENCE_SCHEMA_VERSION = "evidence_record.v1"
TRACE_SCHEMA_VERSION = "protacxtend.agent_trace.v2"


class TerminalStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    JUSTIFIED_ABSTENTION = "JUSTIFIED_ABSTENTION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    HUMAN_INPUT_REQUIRED = "HUMAN_INPUT_REQUIRED"
    SAFETY_BLOCK = "SAFETY_BLOCK"
    ERROR = "ERROR"


from protacxtend.architecture.ontology import EvidenceKind  # noqa: E402,F401


class PlanStep(BaseModel):
    step_id: str
    worker: str = ""
    action: str = ""
    capability: str = ""
    status: str = "pending"          # pending / active / done / blocked / skipped
    observation: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    blocked_reason: str = ""


class Plan(BaseModel):
    version: int = 1
    goal: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    revision_reason: str = ""
    triggering_evidence_ids: list[str] = Field(default_factory=list)
    created_by: str = "coordinator"


class Budget(BaseModel):
    max_steps: int = 25
    steps_used: int = 0
    max_tool_calls: int = 30
    tool_calls_used: int = 0
    max_wall_s: float = 900.0
    retries_used: int = 0
    max_retries: int = 3

    def exhausted(self) -> bool:
        return (self.steps_used >= self.max_steps
                or self.tool_calls_used >= self.max_tool_calls)


class RunIdentity(BaseModel):
    run_id: str = ""
    thread_id: str = ""
    architecture_version: str = ARCHITECTURE_VERSION
    state_schema_version: str = STATE_SCHEMA_VERSION
    timestamp: str = ""
    execution_mode: str = "scientific"


class RequestContract(BaseModel):
    original_query: str = ""
    scientific_intent: str = ""
    objective: str = ""
    constraints: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class BiologicalContext(BaseModel):
    disease: str = ""
    indication: str = ""
    tissue: str = ""
    cell_context: str = ""
    patient_context: str = ""
    biomarker_context: str = ""


class TargetBiology(BaseModel):
    target: str = ""
    causal_evidence: list[str] = Field(default_factory=list)
    target_validation: str = "UNKNOWN"
    desired_perturbation: str = "degradation"
    pathway_context: str = ""
    ppi_context: str = ""
    degradation_rationale: str = ""


class ProtacDesign(BaseModel):
    e3_candidates: list[str] = Field(default_factory=list)
    target_warheads: list[str] = Field(default_factory=list)
    e3_recruiters: list[str] = Field(default_factory=list)
    attachment_points: list[str] = Field(default_factory=list)
    linker_candidates: list[str] = Field(default_factory=list)
    candidate_structures: list[str] = Field(default_factory=list)


class InteractionState(BaseModel):
    binary_binding: str = "UNKNOWN"
    ternary_complexes: str = "UNKNOWN"
    ternary_geometry: str = "UNKNOWN"
    cooperativity: str = "UNKNOWN"
    residence_time: str = "UNKNOWN"
    conformational_state: str = "UNKNOWN"
    interface_contacts: str = "UNKNOWN"
    accessible_lysines: str = "UNKNOWN"
    ubiquitination_competence: str = "UNKNOWN"
    hook_effect_risk: str = "UNKNOWN"


class ResidenceTime(BaseModel):
    binary_target_residence: Optional[float] = None
    binary_e3_residence: Optional[float] = None
    ternary_residence: Optional[float] = None
    formation_rate: Optional[float] = None
    dissociation_rate: Optional[float] = None
    cooperativity_relationship: str = ""
    evidence_source: str = ""
    prediction_source: str = ""
    confidence: Optional[float] = None
    status: str = "INSUFFICIENT_EVIDENCE"


class CellularPharmacology(BaseModel):
    target_abundance: str = "UNKNOWN"
    e3_abundance: str = "UNKNOWN"
    localization: str = "UNKNOWN"
    permeability: str = "UNKNOWN"
    efflux: str = "UNKNOWN"
    degradation_prediction: str = "UNKNOWN"
    degradation_kinetics: str = "UNKNOWN"
    dc50: Optional[float] = None
    dmax: Optional[float] = None
    recovery_kinetics: str = "UNKNOWN"


class Translational(BaseModel):
    selectivity: str = "UNKNOWN"
    off_target_degradation: str = "UNKNOWN"
    toxicity: str = "UNKNOWN"
    resistance: str = "UNKNOWN"
    resistance_mechanisms: list[str] = Field(default_factory=list)
    metabolism: str = "UNKNOWN"
    admet: str = "UNKNOWN"
    pk: str = "UNKNOWN"
    pd: str = "UNKNOWN"
    pk_pd_relationship: str = "UNKNOWN"
    synthesis_feasibility: str = "UNKNOWN"


class Experiment(BaseModel):
    experiment: str
    competing_hypotheses: list[str] = Field(default_factory=list)
    predicted_outcome_under: dict[str, str] = Field(default_factory=dict)
    information_gain: str = ""
    required_controls: list[str] = Field(default_factory=list)
    decision_after_each_outcome: dict[str, str] = Field(default_factory=dict)


class ScientificEvidence(BaseModel):
    claims: list[Claim] = Field(default_factory=list)
    evidence_records: list[EvidenceRecordV1] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    disagreements: list[Disagreement] = Field(default_factory=list)


class Epistemics(BaseModel):
    known: list[str] = Field(default_factory=list)
    derived: list[str] = Field(default_factory=list)
    predicted: list[str] = Field(default_factory=list)
    hypothesized: list[str] = Field(default_factory=list)
    exploratory: list[str] = Field(default_factory=list)
    uncertainties: list[UncertaintyAxis] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


class ControlState(BaseModel):
    selected_worker: str = ""
    selected_tool: str = ""
    next_action: str = ""
    retries: int = 0
    fallbacks: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


class Finalization(BaseModel):
    verdict: str = ""
    overall_verdict: str = ""
    limitations: list[str] = Field(default_factory=list)
    terminal_status: TerminalStatus = TerminalStatus.ERROR
    termination_reason: str = ""
    recommended_next_action: str = ""


class TherapeuticHypothesisState(BaseModel):
    run_identity: RunIdentity = Field(default_factory=RunIdentity)
    request: RequestContract = Field(default_factory=RequestContract)
    biological_context: BiologicalContext = Field(default_factory=BiologicalContext)
    target_biology: TargetBiology = Field(default_factory=TargetBiology)
    protac_design: ProtacDesign = Field(default_factory=ProtacDesign)
    interaction_state: InteractionState = Field(default_factory=InteractionState)
    residence: ResidenceTime = Field(default_factory=ResidenceTime)
    cellular_pharmacology: CellularPharmacology = Field(default_factory=CellularPharmacology)
    translational: Translational = Field(default_factory=Translational)
    evidence: ScientificEvidence = Field(default_factory=ScientificEvidence)
    axes: ScientificAxisProfile = Field(default_factory=ScientificAxisProfile)
    epistemics: Epistemics = Field(default_factory=Epistemics)
    plan: Plan = Field(default_factory=Plan)
    plan_history: list[Plan] = Field(default_factory=list)
    control: ControlState = Field(default_factory=ControlState)
    experiments: list[Experiment] = Field(default_factory=list)
    finalization: Finalization = Field(default_factory=Finalization)

    # ── helpers ───────────────────────────────────────────────────────
    def add_evidence(self, rec: EvidenceRecordV1) -> None:
        self.evidence.evidence_records.append(rec)
        if rec.citation:
            self.evidence.citations.append(rec.citation)
        if rec.source:
            self.evidence.provenance.append(rec.source)

    def add_claim(self, claim: Claim) -> None:
        self.evidence.claims.append(claim)

    def revision(self, reason: str, new_steps: list[PlanStep],
                 triggering: list[str]) -> Plan:
        """Create a genuine plan revision, preserving history."""
        self.plan_history.append(self.plan)
        new_plan = Plan(
            version=self.plan.version + 1,
            goal=self.plan.goal,
            steps=new_steps,
            revision_reason=reason,
            triggering_evidence_ids=list(triggering),
            created_by="coordinator",
        )
        self.plan = new_plan
        return new_plan

    def fingerprint(self) -> str:
        blob = json.dumps(self.model_dump(mode="json"), sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


__all__ = [
    "ARCHITECTURE_VERSION", "STATE_SCHEMA_VERSION", "EVIDENCE_SCHEMA_VERSION",
    "TRACE_SCHEMA_VERSION", "TerminalStatus", "Plan", "PlanStep", "Budget",
    "RunIdentity", "RequestContract", "BiologicalContext", "TargetBiology",
    "ProtacDesign", "InteractionState", "ResidenceTime", "CellularPharmacology",
    "Translational", "Experiment", "ScientificEvidence", "Epistemics",
    "ControlState", "Finalization", "TherapeuticHypothesisState",
]
