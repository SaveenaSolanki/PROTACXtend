"""Schemas — PROTAC Degradation ML Model (Module 4)."""

from __future__ import annotations

from pydantic import BaseModel, Field

MODEL_VERSION = "protac_degradation_ml-v1.0.0"


class DegradationInput(BaseModel):
    smiles: str = Field(..., min_length=1)
    target: str | None = None          # POI name when available
    e3: str | None = None              # E3 ligase when available
    model_path: str | None = None      # trained artifact (default artifact used when None)


class PredictionResult(BaseModel):
    model: str = MODEL_VERSION
    model_path: str = ""
    pdc50: float | None = None                 # -log10(DC50/M)
    dc50_nM: float | None = None               # 10^-pdc50 * 1e9
    dmax_pct: float | None = None              # trained when Dmax labels exist
    degradation_probability: float | None = None  # None unless a binary-label classifier exists
    pdc50_lower_nM: float | None = None
    pdc50_upper_nM: float | None = None        # empirical (conformal-style) interval on DC50
    ood_score: float | None = None             # kNN descriptor distance to training set
    ood_flag: bool = False
    tasks: dict = Field(default_factory=dict)  # per-task availability + enabled flags
    limitations: list[str] = Field(default_factory=list)
    status: str = "SUPPORTED"
