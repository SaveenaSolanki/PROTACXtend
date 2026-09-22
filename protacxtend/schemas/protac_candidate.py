"""Unified ProtacCandidate — single structured object for the full pipeline.

Every pipeline stage reads/writes the same object. Provenance is carried
forward automatically; unknown fields default to None (never fabricated).
"""

from __future__ import annotations

import hashlib
import json
import math
import warnings as _warnings
from typing import Any, Dict, List, Optional, Tuple

from protacxtend.backend.schemas import BaseModel, Field, Optional as O


class ProtacCandidate(BaseModel):
    # ── Identity ────────────────────────────────────────────────────────
    candidate_id: str = ""
    canonical_smiles: str = ""
    molecular_formula: str = ""
    molecular_weight: float = 0.0

    # ── Component provenance ───────────────────────────────────────────
    target_gene: str = ""
    warhead_smiles: str = ""
    warhead_source: str = ""
    e3_ligand_smiles: str = ""
    e3_ligase: str = ""
    linker_smiles: str = ""
    linker_source: str = ""
    linker_class: str = ""
    exit_vector_source: str = ""

    # ── Ternary complex ───────────────────────────────────────────────
    ternary_plausibility_score: float = 0.0
    ternary_methods_used: List[str] = Field(default_factory=list)
    ternary_confidence: float = 0.0

    # ── Cooperativity ─────────────────────────────────────────────────
    alpha: Optional[float] = None
    alpha_source: str = ""                 # "predicted" | "BSA_proxy" | "measured"
    alpha_confidence: float = 0.0
    alpha_warning: Optional[str] = None

    # ── Degradation ───────────────────────────────────────────────────
    predicted_dc50_nM: Optional[float] = None
    predicted_dmax_percent: Optional[float] = None
    degradation_confidence: float = 0.0
    degradation_model: str = "Chemprop"
    degradation_provenance: Dict[str, Any] = Field(default_factory=dict)

    # ── Hook effect ───────────────────────────────────────────────────
    hook_effect_EC50: Optional[float] = None
    hook_effect_ratio: Optional[float] = None
    dose_response_curve: List[Dict[str, float]] = Field(default_factory=list)

    # ── ADMET ─────────────────────────────────────────────────────────
    predicted_hERG: Optional[float] = None
    predicted_solubility: Optional[float] = None
    predicted_permeability: Optional[float] = None
    admet_confidence: float = 0.0
    admet_model: str = "ADMET-AI"
    lipinski_violations: int = 0
    veber_violations: int = 0
    rule_of_oral_protac: bool = False

    # ── Chameleonicity ────────────────────────────────────────────────
    psa_3d: Optional[float] = None
    sasa_3d: Optional[float] = None
    imhb_count: Optional[int] = None
    compactness: Optional[float] = None
    polar_exposure: Optional[float] = None
    chameleonicity_score: Optional[float] = None
    chameleonicity_warning: Optional[str] = None

    # ── Neosubstrate / off-target ─────────────────────────────────────
    neosubstrate_risk_score: float = 0.0
    neosubstrate_hit: bool = False
    neosubstrate_targets: List[str] = Field(default_factory=list)
    offtarget_count: int = 0

    # ── Resistance ────────────────────────────────────────────────────
    resistance_risk: float = 0.0
    e3_mutation_risk: str = "low"
    pathway_bypass_risk: str = "low"

    # ── Synthesis ─────────────────────────────────────────────────────
    synthesis_feasibility_score: float = 0.5
    route_step_count: Optional[int] = None

    # ── Ranking ───────────────────────────────────────────────────────
    pareto_rank: Optional[int] = None
    overall_score: float = 0.0

    # ── Validation ────────────────────────────────────────────────────
    rdkit_valid: bool = False
    validation_warnings: List[str] = Field(default_factory=list)

    # ── Evidence provenance ───────────────────────────────────────────
    evidence: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    run_id: str = ""

    def compute_hash(self) -> str:
        data = self.model_dump()
        data.pop("evidence", None)
        return hashlib.sha256(json.dumps(data, default=str).encode()).hexdigest()[:16]
