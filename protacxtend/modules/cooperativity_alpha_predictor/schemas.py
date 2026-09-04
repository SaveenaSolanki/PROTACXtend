"""Schemas — Cooperativity (alpha) Predictor."""

from __future__ import annotations

from pydantic import BaseModel, Field

MODEL_VERSION = "cooperativity_alpha_predictor-v1.0.0"


class InterfaceFeatures(BaseModel):
    """Structural interface features computed from ternary pose(s)."""

    buried_surface_area_angstrom2: float = 0.0
    intermolecular_contacts: int = 0
    putative_hbonds: int = 0               # distance-based proxy (documented)
    salt_bridges: int = 0
    hydrophobic_contacts: int = 0
    steric_clashes: int = 0
    interface_residue_count: int = 0
    ensemble_bsa_relstd: float = 0.0       # across poses when available
    ensemble_interface_jaccard: float = 0.0
    n_poses: int = 0


class MolecularFeatures(BaseModel):
    """RDKit 2D descriptors (usable when SMILES are available)."""

    available: bool = False
    mol_wt: float | None = None
    clogp: float | None = None
    tpsa: float | None = None
    rotatable_bonds: int | None = None
    hbd: int | None = None
    hba: int | None = None
    aromatic_rings: int | None = None


class SurrogateEvidence(BaseModel):
    """Feature evidence behind the structural cooperativity-feasibility score."""

    interface: InterfaceFeatures = Field(default_factory=InterfaceFeatures)
    molecular: MolecularFeatures = Field(default_factory=MolecularFeatures)
    components: dict[str, float] = Field(default_factory=dict)  # normalized 0..1 parts
    formula_note: str = ""                  # exact score formula (documentation)
    cooperativity_feasibility_score: float = 0.0  # 0..1 heuristic — NOT experimental alpha


class CooperativityPrediction(BaseModel):
    model: str = MODEL_VERSION
    model_kind: str = "structural_surrogate"   # or "trained_model"
    protac: str = ""
    poi: str = ""
    e3: str = ""
    predicted_alpha: float | None = None
    predicted_log_alpha: float | None = None
    cooperativity_class: str = "not_assessed"  # positive|approximately_non_cooperative|negative|not_assessed
    confidence: float | None = None            # 0..1 (calibrated posterior for trained model)
    uncertainty: dict = Field(default_factory=dict)
    feature_evidence: SurrogateEvidence = Field(default_factory=SurrogateEvidence)
    structure_available: bool = False
    model_applicability: str = ""              # OOD / applicability warning
    limitations: list[str] = Field(default_factory=list)
    status: str = "SUPPORTED"                  # SUPPORTED | INSUFFICIENT | FAILED
