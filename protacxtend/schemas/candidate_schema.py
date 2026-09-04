"""Candidate provenance schemas."""

from __future__ import annotations

from typing import Any, Optional

from protacxtend.backend.schemas import BaseModel, Field


class CandidateProvenance(BaseModel):
    candidate_id: str = ""
    source_warhead: str = ""
    source_e3_ligand: str = ""
    source_linker: str = ""
    exit_vector_source: str = ""
    construction_method: str = ""
    rdkit_validation_status: str = "unchecked"
    degradation_model_name: Optional[str] = None
    degradation_model_version: Optional[str] = None
    admet_backend_name: Optional[str] = None
    admet_backend_version: Optional[str] = None
    novelty_database_version: Optional[str] = None
    ternary_backend_name: Optional[str] = None
    ternary_backend_version: Optional[str] = None
    ranking_formula_version: str = "weighted-deterministic-v0.1"
    evidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

