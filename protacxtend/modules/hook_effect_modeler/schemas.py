"""Input/output schemas for the Hook Effect Modeler."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MODEL_VERSION = "hook_effect_modeler-v1.0.0"


class HookEffectInput(BaseModel):
    """Mechanistic three-body equilibrium inputs (concentrations in nM)."""

    poI_conc_nM: float = Field(100.0, gt=0, description="total POI (target protein) concentration")
    e3_conc_nM: float = Field(100.0, gt=0, description="total E3 ligase concentration")
    kd_poi_protac_nM: float = Field(50.0, gt=0, description="POI-PROTAC binary dissociation constant")
    kd_e3_protac_nM: float = Field(50.0, gt=0, description="E3-PROTAC binary dissociation constant")
    alpha: float = Field(1.0, ge=0, description="ternary cooperativity factor (>=1 favours ternary)")
    min_dose_nM: float = Field(0.01, gt=0)
    max_dose_nM: float = Field(10_000.0, gt=0)
    points: int = Field(120, ge=20, le=1000)
    uncertainty_pct: dict[str, float] = Field(
        default_factory=lambda: {"kd": 0.0, "alpha": 0.0},
        description="relative (%) 1-sigma uncertainty on Kds (both) and alpha; >0 enables Monte-Carlo")
    seed: int | None = Field(42, description="RNG seed for reproducible Monte-Carlo")

    @field_validator("max_dose_nM")
    @classmethod
    def _max_gt_min(cls, v: float, info) -> float:
        mn = info.data.get("min_dose_nM")
        if mn is not None and v <= mn:
            raise ValueError("max_dose_nM must exceed min_dose_nM")
        return v


class CurvePoint(BaseModel):
    """Species resolved at one dose. Ternary = POI:PROTAC:E3; binaries TL/EL are
    exposed so the hook regime (binary dominance at high dose) is inspectable."""

    dose_nM: float
    ternary_nM: float                      # TLE
    poi_protac_binary_nM: float = 0.0      # TL
    e3_protac_binary_nM: float = 0.0       # EL
    free_poi_nM: float = 0.0               # T
    free_e3_nM: float = 0.0                # E
    free_protac_nM: float = 0.0            # L
    occupancy_fraction: float = 0.0        # TLE / POI_total
    ternary_bound_poi_fraction: float = 0.0


class HookMetrics(BaseModel):
    """Deterministic metrics. Cmax and ternary_max are DIFFERENT quantities:
      * cmax_nM       = PROTAC dose (nM) maximising ternary (x-axis argmax)
      * ternary_max_nM = ternary-complex concentration (nM) AT cmax (y-axis max)
    Hook thresholds are defined on the descending/post-maximum limb only:
      * hook_90_nM = first dose > cmax with ternary <= 0.90 x ternary_max
      * hook_50_nM = first dose > cmax with ternary <= 0.50 x ternary_max
    hook_severity is the operational relative loss of ternary over the tested
    post-Cmax window: (ternary_max - min ternary over (cmax, max_dose]) / ternary_max
    (monotonic post-peak decay => equals the drop at the window edge)."""

    cmax_nM: float | None = None
    ternary_max_nM: float = 0.0
    max_occupancy_fraction: float = 0.0
    hook_90_nM: float | None = None
    hook_50_nM: float | None = None
    hook_cmax_ratio: float | None = None   # cmax / hook_50 (closer to 1 => hook nearer Cmax)
    hook_severity: float = 0.0             # 0..1, see class docstring
    hook_label: str = "no_hook"            # no_hook | moderate | severe
    occupancy_window_fold: float = 0.0     # dose ratio where occupancy >= 50% of peak
    severity_reference_max_dose_nM: float | None = None

    # deprecated aliases (kept for back-compat; prefer the explicit fields)
    @property
    def optimal_concentration_nM(self) -> float | None:
        return self.cmax_nM

    @property
    def max_ternary_nM(self) -> float:
        return self.ternary_max_nM

    @property
    def hook_onset_nM(self) -> float | None:
        return self.hook_50_nM


class UncertaintySummary(BaseModel):
    enabled: bool = False
    n_samples: int = 0
    peak_ternary_nM: dict[str, float] = Field(default_factory=dict)   # p5/median/p95
    optimal_concentration_nM: dict[str, float] = Field(default_factory=dict)
    hook_severity_p95: float = 0.0
    reference_optimum_nM: float | None = None          # deterministic optimal dose used for containment
    fraction_within_25pct: float = 0.0                 # MC optimum doses within +/-25% of reference


class HookEffectResult(BaseModel):
    model: str = MODEL_VERSION
    status: str = "SUPPORTED"             # SUPPORTED | REVISED
    inputs: HookEffectInput
    curve: list[CurvePoint] = Field(default_factory=list)
    metrics: HookMetrics = Field(default_factory=HookMetrics)
    uncertainty: UncertaintySummary = Field(default_factory=UncertaintySummary)
    warnings: list[str] = Field(default_factory=list)
    solver: dict = Field(default_factory=dict)
