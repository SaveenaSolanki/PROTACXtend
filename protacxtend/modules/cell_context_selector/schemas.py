"""Module 5 schemas — cell-context degradation prediction API."""

from __future__ import annotations

from pydantic import BaseModel, Field

MODEL_VERSION = "cell_context_degradation-v1.0.0"


class CellContextInput(BaseModel):
    protac: str = Field(..., min_length=1,
                        description="PROTAC SMILES (or name if resolvable)")
    poi: str | None = None
    e3: str | None = None
    cell_line: str = Field(..., min_length=1)
    model_path: str | None = None


class PredictionResult(BaseModel):
    model: str = MODEL_VERSION
    model_path: str = ""
    predicted_pdc50: float | None = None
    predicted_DC50_nM: float | None = None
    predicted_Dmax_pct: float | None = None
    degradation_probability: float | None = None
    degradation_probability_note: str = (
        "binary activity is threshold-DERIVED (pDC50>=6.0 AND Dmax>=60 per "
        "arXiv 2406.02637), not an experimentally measured probability")
    uncertainty: dict = Field(default_factory=dict)
    cell_context_features_used: list[str] = Field(default_factory=list)
    mechanistic_features_used: list[str] = Field(default_factory=list)
    ood_flags: dict = Field(default_factory=dict)
    applicability: dict = Field(default_factory=dict)
    claims: dict = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    status: str = "SUPPORTED"
