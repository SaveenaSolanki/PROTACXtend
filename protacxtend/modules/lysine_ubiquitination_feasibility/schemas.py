"""Input/output schemas — Lysine Ubiquitination Feasibility Scorer."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MODEL_VERSION = "lysine_ubiquitination_feasibility-v1.0.0"


class E2CatalyticSite(BaseModel):
    chain: str = Field(..., description="chain id of the E2 carrying the catalytic cysteine")
    residue_number: int = Field(..., gt=0)
    residue_name: str = Field("CYS", description="catalytic residue (default CYS of the E2~Ub thioester active site)")


class LysineUbiquitinationInput(BaseModel):
    structure_paths: list[str] = Field(..., min_length=1,
                                       description="ternary-complex pose PDB file(s); >=2 poses enable ensemble consistency")
    poi_chain: str = Field(..., description="POI chain whose lysines are evaluated")
    e2_catalytic: E2CatalyticSite
    lysine_resnums: list[int] | None = Field(None, description="restrict evaluation to these POI lysines (default: all LYS)")
    distance_cutoff_angstrom: float = Field(15.0, gt=0, description="Nzeta..Sy productive distance cutoff (Angstrom)")
    orientation_cutoff_deg: float = Field(75.0, gt=0, le=180, description="max approach angle (deg) at the lysine")
    sasa_cutoff_angstrom2: float = Field(10.0, ge=0, description="minimum Nzeta solvent-accessible surface (A^2)")
    clash_cutoff_angstrom: float = Field(2.4, gt=0, description="non-bonded contact distance counted as a steric clash (A)")
    probe_radius_angstrom: float = Field(1.4, gt=0)
    n_sasa_dots: int = Field(92, ge=24, le=960, description="Shrake-Rupley dots per sphere (92 default)")
    vdw_radii: dict[str, float] = Field(default_factory=lambda: {"C": 1.7, "N": 1.55, "O": 1.52,
                                                                  "S": 1.8, "P": 1.8, "H": 1.1})

    @field_validator("structure_paths")
    @classmethod
    def _paths_exist(cls, v: list[str]) -> list[str]:
        from pathlib import Path
        for p in v:
            if not Path(p).exists():
                raise ValueError(f"structure file not found: {p}")
        return v


class LysineGeometry(BaseModel):
    """Per-pose geometry features for one lysine (distance/angle/SASA/clash)."""

    pose_index: int
    distance_nz_sy_angstrom: float
    nz_sasa_angstrom2: float
    sidechain_sasa_angstrom2: float
    approach_angle_deg: float
    clash_count: int
    productive: bool


class RankedLysine(BaseModel):
    residue_number: int
    ensemble_mean_score: float
    productive_pose_fraction: float
    mean_distance_angstrom: float = 0.0
    mean_sasa_angstrom2: float = 0.0
    mean_angle_deg: float = 0.0
    pose_geometries: list[LysineGeometry] = Field(default_factory=list)


class LysineUbiquitinationResult(BaseModel):
    model: str = MODEL_VERSION
    status: str = "SUPPORTED"          # SUPPORTED | INSUFFICIENT | REJECT
    ranked_lysines: list[RankedLysine] = Field(default_factory=list)
    productive_pose_fraction: float = 0.0   # poses with >=1 productive lysine
    ubiquitination_feasibility_score: float = 0.0  # 0..1 (best-pose mean over candidates)
    feasibility_label: str = "not_assessed"   # feasible | marginal | infeasible
    n_poses: int = 0
    n_lysines: int = 0
    warnings: list[str] = Field(default_factory=list)
    features: dict = Field(default_factory=dict)
