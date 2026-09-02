"""Mechanistic ternary dose-response and hook-effect simulator."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DoseResponseResult:
    status: str
    dc50_pred_nM: float | None
    dmax_pred_percent: float
    hook_concentration_nM: float | None
    ternary_peak_concentration_nM: float
    dose_window_width: float
    curve: list[dict[str, float]] = field(default_factory=list)
    parameter_sensitivity: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    backend: str = "protacxtend_deep_qsp_hook_adapter_v0.1"

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def simulate_ternary_dose_response(
    target_conc_nM: float = 100.0,
    e3_conc_nM: float = 100.0,
    kd_target_nM: float = 50.0,
    kd_e3_nM: float = 50.0,
    alpha: float = 1.0,
    degradation_rate: float = 1.0,
    resynthesis_rate: float = 0.15,
    min_dose_nM: float = 0.01,
    max_dose_nM: float = 10000.0,
    points: int = 80,
) -> DoseResponseResult:
    """Simulate bell-shaped ternary complex abundance across a dose grid."""

    import math

    warnings: list[str] = []
    if min(target_conc_nM, e3_conc_nM, kd_target_nM, kd_e3_nM, alpha) <= 0:
        return DoseResponseResult(
            status="REJECT",
            dc50_pred_nM=None,
            dmax_pred_percent=0.0,
            hook_concentration_nM=None,
            ternary_peak_concentration_nM=0.0,
            dose_window_width=0.0,
            warnings=["Concentrations, Kd values, and alpha must be positive."],
        )
    points = max(8, int(points))
    log_min = math.log10(min_dose_nM)
    log_max = math.log10(max_dose_nM)
    doses = [10 ** (log_min + i * (log_max - log_min) / (points - 1)) for i in range(points)]
    curve: list[dict[str, float]] = []
    best_ternary = 0.0
    peak_dose = doses[0]
    for dose in doses:
        target_bound_fraction = dose / (kd_target_nM + dose)
        e3_bound_fraction = dose / (kd_e3_nM + dose)
        binary_competition = 1.0 + dose / (kd_target_nM + target_conc_nM) + dose / (kd_e3_nM + e3_conc_nM)
        ternary = min(target_conc_nM, e3_conc_nM) * target_bound_fraction * e3_bound_fraction * alpha / binary_competition
        degradation = 100.0 * (degradation_rate * ternary) / (degradation_rate * ternary + resynthesis_rate * target_conc_nM + 1e-9)
        curve.append({"dose_nM": round(dose, 5), "ternary_nM": round(ternary, 5), "degradation_percent": round(degradation, 3)})
        if ternary > best_ternary:
            best_ternary = ternary
            peak_dose = dose
    dmax = max(row["degradation_percent"] for row in curve)
    dc50 = None
    for row in curve:
        if row["degradation_percent"] >= 50.0:
            dc50 = row["dose_nM"]
            break
    hook = None
    after_peak = False
    for row in curve:
        if row["dose_nM"] >= peak_dose:
            after_peak = True
        if after_peak and row["ternary_nM"] <= 0.75 * best_ternary and row["dose_nM"] > peak_dose:
            hook = row["dose_nM"]
            break
    active_doses = [row["dose_nM"] for row in curve if row["degradation_percent"] >= 0.8 * dmax and dmax > 0]
    width = round(max(active_doses) / min(active_doses), 3) if active_doses else 0.0
    if hook and hook < max_dose_nM:
        warnings.append("Hook-effect risk detected: ternary complex declines at high PROTAC concentration.")
    status = "SUPPORTED" if dmax >= 50.0 else "REVISE"
    return DoseResponseResult(
        status=status,
        dc50_pred_nM=dc50,
        dmax_pred_percent=round(dmax, 2),
        hook_concentration_nM=hook,
        ternary_peak_concentration_nM=round(peak_dose, 5),
        dose_window_width=width,
        curve=curve,
        parameter_sensitivity={
            "alpha": round(min(1.0, abs(math.log10(alpha)) / 2.0 + 0.25), 3),
            "target_conc_nM": round(min(1.0, target_conc_nM / (target_conc_nM + e3_conc_nM)), 3),
            "kd_balance": round(min(kd_target_nM, kd_e3_nM) / max(kd_target_nM, kd_e3_nM), 3),
        },
        warnings=warnings,
    )

