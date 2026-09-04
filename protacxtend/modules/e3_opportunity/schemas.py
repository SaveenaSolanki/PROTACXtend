"""Module 6 schemas — E3 opportunity API."""

from __future__ import annotations

from pydantic import BaseModel, Field

MODEL_VERSION = "e3_opportunity-v1.0.0"


class E3OpportunityInput(BaseModel):
    poi: str = Field(..., min_length=1)
    cell_line: str | None = None
    tissue: str | None = None
    disease: str | None = None
    warhead: str | None = None
    poi_structure: str | None = None
    top_k: int = 10


class CandidateResult(BaseModel):
    rank: int
    e3_gene: str
    e3_family: str
    cell_context_score: float | None = None
    cell_context_confidence: float | None = None
    localization_score: float | None = None
    recruiter_available: bool | None = None
    recruiter_confidence: float | None = None
    structural_feasibility: float | None = None
    structural_confidence: float | None = None
    lysine_opportunity: float | None = None
    selectivity_opportunity: float | None = None
    known_precedent: float | None = None
    resistance_risk: float | None = None
    overall_rank_score: float = 0.0
    overall_confidence: float = 0.0
    verdict: str = "INSUFFICIENT EVIDENCE"
    supporting_evidence: dict = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    recommended_next_test: str = ""


class RankResponse(BaseModel):
    model: str = MODEL_VERSION
    poi: str
    poi_gene: str | None = None
    cell_line: str | None = None
    tissue: str | None = None
    disease: str | None = None
    candidates: list[CandidateResult]
    ood: dict = Field(default_factory=dict)
    claims: dict = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
