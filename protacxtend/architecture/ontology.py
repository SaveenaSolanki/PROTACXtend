"""Canonical evidence / claim ontology for the agentic architecture (v1).

Separates ``evidence_kind`` (how the value was produced) from ``evidence_status``
(how well it is supported). They must never be collapsed: e.g.
``MODEL_PREDICTED`` + ``PARTIALLY_SUPPORTED`` is valid.

This extends — and does not replace — ``protacxtend.schemas.evidence_schema``.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from protacxtend.backend.schemas import BaseModel, Field


class EvidenceKind(str, Enum):
    OBSERVED = "OBSERVED"                 # measured in an assay/lab
    RETRIEVED = "RETRIEVED"               # from a database/literature source
    DERIVED = "DERIVED"                   # deterministic calculation over inputs
    MODEL_PREDICTED = "MODEL_PREDICTED"   # trained-model output
    HYPOTHESIZED = "HYPOTHESIZED"         # explicitly a hypothesis
    EXPLORATORY = "EXPLORATORY"           # generated / non-source-backed
    DEMO = "DEMO"                         # fixture/demo provenance
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EvidenceStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


#: Kinds admitted into SCIENTIFIC-mode claims. DEMO/EXPLORATORY are excluded by policy.
SCIENTIFIC_ADMISSIBLE_KINDS = {
    EvidenceKind.OBSERVED, EvidenceKind.RETRIEVED, EvidenceKind.DERIVED,
    EvidenceKind.MODEL_PREDICTED, EvidenceKind.HYPOTHESIZED,
}


class EvidenceRecordV1(BaseModel):
    evidence_id: str = ""
    claim_id: str = ""
    content: str = ""
    evidence_kind: EvidenceKind = EvidenceKind.INSUFFICIENT_EVIDENCE
    evidence_status: EvidenceStatus = EvidenceStatus.INSUFFICIENT_EVIDENCE
    source: str = ""
    source_version: str = ""
    citation: str = ""
    tool: str = ""
    tool_version: str = ""
    model: str = ""
    model_version: str = ""
    input_hash: str = ""
    output_hash: str = ""
    supports_claims: list[str] = Field(default_factory=list)
    contradicts_claims: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    timestamp: str = ""

    def scientific_claim_allowed(self) -> bool:
        """DEMO/EXPLORATORY evidence may not back a SCIENTIFIC claim."""
        return self.evidence_kind in SCIENTIFIC_ADMISSIBLE_KINDS


class Claim(BaseModel):
    claim_id: str
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_kind: EvidenceKind = EvidenceKind.INSUFFICIENT_EVIDENCE
    evidence_status: EvidenceStatus = EvidenceStatus.INSUFFICIENT_EVIDENCE
    inference_limit: str = ""


class Contradiction(BaseModel):
    contradiction_id: str
    claim_id: str = ""
    evidence_id_a: str
    evidence_id_b: str
    axis: str = ""
    description: str = ""
    resolution: str = ""          # e.g. "UNRESOLVED", "RESOLVED_BY_<evidence>"
    decision_relevant: bool = True


class Disagreement(BaseModel):
    disagreement_id: str
    axis: str                                  # scientific axis, not a global score
    positions: dict[str, str] = Field(default_factory=dict)   # family -> position
    decision_relevant: bool = True
    interpretation: str = ""
    resolving_action: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class UncertaintyAxis(BaseModel):
    axis: str
    level: str = "UNKNOWN"                     # LOW / MEDIUM / HIGH / UNKNOWN
    basis: str = ""                            # why this level; provenance
    evidence_gain_if_resolved: str = ""


class ScientificAxisProfile(BaseModel):
    """Per-candidate scientific axes — never averaged into one opaque score."""
    target_engagement: str = "UNKNOWN"
    ternary_geometry: str = "UNKNOWN"
    cooperativity: str = "UNKNOWN"
    residence_time: str = "UNKNOWN"
    ubiquitination_competence: str = "UNKNOWN"
    degradation_ml: str = "UNKNOWN"
    permeability: str = "UNKNOWN"
    efflux: str = "UNKNOWN"
    cell_context: str = "UNKNOWN"
    pk: str = "UNKNOWN"
    evidence_support: str = "UNKNOWN"

    def as_dict(self) -> dict[str, str]:
        return self.model_dump()


__all__ = [
    "EvidenceKind", "EvidenceStatus", "SCIENTIFIC_ADMISSIBLE_KINDS",
    "EvidenceRecordV1", "Claim", "Contradiction", "Disagreement",
    "UncertaintyAxis", "ScientificAxisProfile",
]
