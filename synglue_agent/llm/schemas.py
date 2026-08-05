"""
LLM decision schemas (A6) — every model decision conforms to a Pydantic schema.
==============================================================================

No free-text reasoning is stored. Only: decision, reason codes, selected
tools, evidence references, confidence, rejected alternatives.

Schemas (one per role):
  - EvidenceDecision   (evidence-assessment role)
  - DesignDecision     (design-strategy role)
  - RepairDecision     (repair role)
  - CritiqueDecision   (critic role)
  - SupervisorDecision (supervisor role)
  - ReportDecision     (report role)
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Route(str, Enum):
    SEARCH_MORE = "search_more"
    DESIGN = "design"
    HUMAN_REVIEW = "human_review"
    TERMINATE = "terminate"


# ── Evidence-assessment role ──────────────────────────────────────────

class EvidenceDecision(BaseModel):
    route: Route
    missing_evidence: List[str] = Field(default_factory=list)
    selected_tools: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rejected_alternatives: List[str] = Field(default_factory=list)


# ── Design-strategy role ──────────────────────────────────────────────

class DesignStrategy(str, Enum):
    STANDARD_PROTAC = "standard_protac"
    MINI_PROTAC = "mini_protac"
    MOLECULAR_GLUE = "molecular_glue"
    LINKER_SWAP = "linker_swap"
    WARHEAD_ANALOG = "warhead_analog"
    EXIT_VECTOR_SWAP = "exit_vector_swap"


class DesignDecision(BaseModel):
    strategy: DesignStrategy
    rationale_codes: List[str] = Field(default_factory=list)
    components_to_modify: List[str] = Field(default_factory=list)  # warhead/linker/e3/exit_vector
    selected_tools: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rejected_alternatives: List[str] = Field(default_factory=list)


# ── Repair role ───────────────────────────────────────────────────────

class RepairAction(str, Enum):
    RETRY_RELAXED_PARAMS = "retry_relaxed_params"
    ESCALATE_ENSEMBLE = "escalate_ensemble"
    ALTERNATE_LINKER = "alternate_linker"
    ALTERNATE_WARHEAD = "alternate_warhead"
    ALTERNATE_EXIT_VECTOR = "alternate_exit_vector"
    COLLECT_MORE_EVIDENCE = "collect_more_evidence"
    HUMAN_REVIEW = "human_review"
    ABORT = "abort"


class RepairDecision(BaseModel):
    action: RepairAction
    target_stage: str = ""
    reason_codes: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rejected_alternatives: List[str] = Field(default_factory=list)


# ── Critic role ───────────────────────────────────────────────────────

class CritiqueVerdict(str, Enum):
    ACCEPT = "accept"
    REVISE = "revise"
    REJECT = "reject"


class CritiqueDecision(BaseModel):
    verdict: CritiqueVerdict
    issues: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


# ── Supervisor role ───────────────────────────────────────────────────

class SupervisorDecision(BaseModel):
    intent: str
    target: str = ""
    modality: str = "protac"
    e3_ligase: str = ""
    constraints: List[str] = Field(default_factory=list)
    # bounded plan: ordered steps; must include validation; tools from registry
    plan_steps: List[str] = Field(default_factory=list)
    selected_tools: List[str] = Field(default_factory=list)
    includes_validation: bool = False
    confidence: float = Field(ge=0.0, le=1.0)


# ── Report role ───────────────────────────────────────────────────────

class ReportDecision(BaseModel):
    summary: str
    # Every supplied numerical value must be reproduced here exactly
    # (name + value string) — makes number fidelity machine-checkable.
    numbers: List[Dict[str, str]] = Field(default_factory=list)
    # predictions must be labelled as predictions (vs measured) in the summary
    evidence_refs: List[str] = Field(default_factory=list)
    top_candidates: List[str] = Field(default_factory=list)
    open_risks: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


# Validation helpers (deterministic gates on top of model output)

def validate_confidence(confidence: float) -> float:
    return max(0.0, min(1.0, float(confidence)))
