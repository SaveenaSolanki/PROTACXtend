"""TargetTherapeuticsAssessment — typed, evidence-backed pre-design stage.

Every conclusion carries: source IDs, assay context, evidence type
(genetic_association | experimental_causality | dependency | expression |
predicted | curated_template | unavailable), conflicting evidence, missing
data, and the experiment that would change the decision.

Association vs causality and expression vs functional ligase activity are
never conflated: labels are set by the evidence tier, not by prose.

Gates that design must not bypass (enforced in gates.py / runtime):
  identity  -> canonical target+variant resolved
  chemistry -> source-backed binder with attachment vector before design
  window    -> modality decision != unsuitable for the requested context
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "TargetTherapeuticsAssessment.v1"

EvidenceTier = Literal[
    "genetic_association", "experimental_causality", "dependency", "expression",
    "predicted", "curated_template", "unavailable",
]

Verdict = Literal["degradation_justified", "degradation_uncertain", "degradation_unsuitable"]


class Conclusion(BaseModel):
    dimension: str
    conclusion: str = ""
    verdict: Literal["supports_degradation", "neutral", "against_degradation", "unknown"] = "unknown"
    source_ids: list[str] = Field(default_factory=list)
    assay_context: str = ""
    evidence_tier: EvidenceTier = "unavailable"
    conflicting: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    experiment_to_change: str = ""


class EvidenceBlock(BaseModel):
    name: str
    status: Literal["available", "partial", "unavailable", "conflicting"] = "unavailable"
    sources: list[str] = Field(default_factory=list)
    summary: str = ""
    assay_context: str = ""
    evidence_tier: EvidenceTier = "unavailable"
    conflicts: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    experiment_to_change: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    verdict: Verdict                                   # MECHANISTIC rationale for exploring degradation
    mechanism_rationale: str = ""
    therapeutic_suitability: Literal["supported", "requires_review", "not_supported"] = "requires_review"
    suitability_reason: str = ""
    rationale: str = ""                                # alias of mechanism_rationale (back-compat)
    criteria_met: list[str] = Field(default_factory=list)
    criteria_missed: list[str] = Field(default_factory=list)
    gates: dict[str, str] = Field(default_factory=dict)   # gate -> pass|requires_review|fail|not_run|blocked


class TargetTherapeuticsAssessment(BaseModel):
    schema_version: str = SCHEMA_VERSION
    target: dict[str, Any] = Field(default_factory=dict)      # resolved identity (symbol/uniprot/variant/organism)
    disease_context: str = ""
    cell_context: str = ""
    context_fingerprint: str = ""     # exact (target, variant, disease, cell, source_versions, schema)
    source_versions: dict[str, str] = Field(default_factory=dict)   # per-evidence-source version/hash
    modality: str = "targeted protein degradation"
    blocks: dict[str, EvidenceBlock] = Field(default_factory=dict)
    conclusions: list[Conclusion] = Field(default_factory=list)
    decision: Decision = Field(default_factory=Decision)
    generated_by: str = "protacxtend/therapeutics"
    artifact_path: str = ""