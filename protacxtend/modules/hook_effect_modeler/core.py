"""Hook Effect Modeler — mechanistic three-body equilibrium model.

Background
----------
Ternary-complex abundance underlies PROTAC pharmacology: an excess of PROTAC
over-saturates the two binary complexes, so fewer ternary (POI:PROTAC:E3)
complexes form at high dose — the "hook effect" (Douglass et al., J. Am. Chem.
Soc. 2013, 135, 6092; see docs/REFERENCES.md for the full bibliography).

Model (equilibrium, mass action, no steady-state approximations)
----------------------------------------------------------------
Species: T (POI), L (PROTAC), E (E3), binaries TL and EL, ternary TLE.

    TL  = T·L/K_T                        (K_T = Kd(POI–PROTAC))
    EL  = E·L/K_E                        (K_E = Kd(E3–PROTAC))
    TLE = alpha · TL·E / K_E             (path 1: E binds pre-formed TL with an
                                          effective dissociation constant K_E/alpha)
    TLE = alpha · EL·T / K_T             (path 2: T binds pre-formed EL, K_T/alpha)

Exact thermodynamic definition of alpha: alpha is the dimensionless
multiplicative enhancement of the affinity of the SECOND binary complex for its
free partner when the other arm is already bound (alpha = 1 -> no cooperativity;
alpha > 1 positive cooperativity; alpha = 0 -> ternary cannot form). The two
path expressions are equal at equilibrium by detailed balance, because
TL·E/K_E and EL·T/K_T are the same algebraic quantity T·E·L/(K_T·K_E), so the
model is path-independent (microscopic reversibility) by construction and this
is checked numerically (see tests). alpha is dimensionless, >= 0, and applies
symmetrically to both assembly paths.

Conservation:  T0 = T + TL + TLE,  E0 = E + EL + TLE,  L0 = L + TL + EL + TLE.

The three nonlinear equations are solved **numerically** for the free
concentrations (T, E, L) at every dose with a bounded least-squares solver —
no linearisation/heuristic is used for the ternary term.

Outputs: ternary-complex concentration curve, optimal (peak) concentration,
maximum occupancy, hook onset (first dose above the peak at which ternary drops
to <=50% of the peak), hook severity (relative loss over the tested window),
and an occupancy window. Optionally, Monte-Carlo uncertainty propagation over
Kd/alpha inputs returns percentile bounds for peak/optimal dose.

This module never fabricates experimental data: it is a validated equation
model whose parameters (Kds, alpha, concentrations) must come from experiment
or from upstream estimators (cooperativity module, docking, etc.).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from protacxtend.modules.hook_effect_modeler.config import ModelerConfig
from protacxtend.modules.hook_effect_modeler.schemas import (
    CurvePoint,
    HookEffectInput,
    HookEffectResult,
    HookMetrics,
    UncertaintySummary,
)

logger = logging.getLogger("protacxtend.hook_effect_modeler")


class HookModelError(ValueError):
    """Invalid input or failed numerical solve."""


def _grid_from_input(inp: HookEffectInput, cfg: ModelerConfig) -> np.ndarray:
    return np.logspace(np.log10(inp.min_dose_nM), np.log10(inp.max_dose_nM),
                       num=inp.points if inp.points else cfg.dose_grid.points)


def _solve_one(T0: float, E0: float, L0: float, K_T: float, K_E: float,
               alpha: float, cfg: ModelerConfig) -> dict[str, float]:
    """Scalar 3-variable solve in log10-space with relative residuals."""
    from scipy.optimize import least_squares

    T0, E0, L0, K_T, K_E, alpha = (float(v) for v in (T0, E0, L0, K_T, K_E, alpha))
    eps = cfg.numerical_damping
    if L0 <= 0.0:
        return {"t": T0, "e": E0, "l": 0.0, "tl": 0.0, "el": 0.0,
                "tle": 0.0, "residual": 0.0}
    bound = max(T0, E0, L0) * 2.0 + eps

    def residuals(z: np.ndarray) -> np.ndarray:
        t, e, l = 10.0 ** z
        tl = t * l / (K_T + eps)
        el = e * l / (K_E + eps)
        tle = alpha * tl * e / (K_E + eps)
        return np.array([(t + tl + tle - T0) / max(T0, eps),
                         (e + el + tle - E0) / max(E0, eps),
                         (l + tl + el + tle - L0) / max(L0, eps)])

    init = np.log10(np.array([max(T0 / 2.0, 1e-9), max(E0 / 2.0, 1e-9),
                              max(min(L0 * 0.5, max(T0, E0)), 1e-9)]))
    res = least_squares(residuals, init, bounds=([-14.0] * 3, [np.log10(bound)] * 3),
                        xtol=cfg.solver.xtol, ftol=1e-10, gtol=1e-10,
                        max_nfev=cfg.solver.max_nfev, method="trf")
    if not np.all(np.isfinite(res.x)) or res.cost > 1e-4:
        raise HookModelError(f"equilibrium solve failed (cost={res.cost:.2e})")
    t, e, l = (float(v) for v in 10.0 ** res.x)
    tl = t * l / (K_T + eps)
    el = e * l / (K_E + eps)
    tle = alpha * tl * e / (K_E + eps)
    residual = float(max(abs(t + tl + tle - T0) / max(T0, eps),
                         abs(e + el + tle - E0) / max(E0, eps),
                         abs(l + tl + el + tle - L0) / max(L0, eps)))
    return {"t": t, "e": e, "l": l, "tl": tl, "el": el, "tle": tle,
            "residual": residual}


def solve_ternary(T0: float, E0: float, L0: float, K_T: float, K_E: float,
                  alpha: float, cfg: ModelerConfig) -> dict[str, float]:
    """Solve the three-body equilibrium for one dose (concentrations in nM).

    Returns free/derived concentrations: t, e, l, tl, el, tle, residual.
    Raises HookModelError when the bounded least-squares solve fails."""
    return _solve_one(T0, E0, L0, K_T, K_E, alpha, cfg)


def simulate_hook_effect(
    poI_conc_nM: float = 100.0,
    e3_conc_nM: float = 100.0,
    kd_poi_protac_nM: float = 50.0,
    kd_e3_protac_nM: float = 50.0,
    alpha: float = 1.0,
    min_dose_nM: float = 0.01,
    max_dose_nM: float = 10000.0,
    points: int = 120,
    uncertainty_pct: dict[str, float] | None = None,
    seed: int | None = 42,
    config: ModelerConfig | None = None,
    **_: Any,
) -> HookEffectResult:
    """Full mechanistic hook-effect simulation.

    Public typed API (see schemas.HookEffectInput for units; concentrations in
    nM, Kds in nM, alpha dimensionless). Returns HookEffectResult with the
    ternary curve, metrics and optional Monte-Carlo uncertainty summary.
    """
    cfg = config or ModelerConfig.load()
    try:
        inp = HookEffectInput(
            poI_conc_nM=poI_conc_nM, e3_conc_nM=e3_conc_nM,
            kd_poi_protac_nM=kd_poi_protac_nM, kd_e3_protac_nM=kd_e3_protac_nM,
            alpha=alpha, min_dose_nM=min_dose_nM, max_dose_nM=max_dose_nM,
            points=points, uncertainty_pct=uncertainty_pct or {"kd": 0.0, "alpha": 0.0},
            seed=seed)
    except ValueError as exc:
        raise HookModelError(f"invalid hook-effect inputs: {exc}") from exc

    doses = _grid_from_input(inp, cfg)
    curve: list[CurvePoint] = []
    solver_info: dict[str, Any] = {"ok": True, "max_residual": 0.0}
    for dose in doses:
        sol = _solve_one(inp.poI_conc_nM, inp.e3_conc_nM, float(dose),
                         inp.kd_poi_protac_nM, inp.kd_e3_protac_nM, inp.alpha, cfg)
        solver_info["max_residual"] = max(solver_info["max_residual"], sol["residual"])
        occ = sol["tle"] / inp.poI_conc_nM
        bound_poi = (sol["tl"] + sol["tle"]) / inp.poI_conc_nM
        curve.append(CurvePoint(
            dose_nM=float(dose),
            ternary_nM=round(sol["tle"], 6),
            poi_protac_binary_nM=round(sol["tl"], 6),
            e3_protac_binary_nM=round(sol["el"], 6),
            free_poi_nM=round(sol["t"], 6),
            free_e3_nM=round(sol["e"], 6),
            free_protac_nM=round(sol["l"], 6),
            occupancy_fraction=round(float(occ), 6),
            ternary_bound_poi_fraction=round(float(bound_poi), 6)))

    metrics = _compute_metrics(curve, cfg.occupancy_fraction_threshold, inp=inp, cfg=cfg)
    warnings: list[str] = []
    if metrics.hook_severity > 0.05:
        warnings.append("Hook effect detected: ternary occupancy declines at high PROTAC dose.")

    uncertainty = UncertaintySummary(enabled=False)
    pct = inp.uncertainty_pct or {"kd": 0.0, "alpha": 0.0}
    if float(pct.get("kd", 0.0)) > 0 or float(pct.get("alpha", 0.0)) > 0:
        uncertainty = _monte_carlo_uncertainty(inp, cfg, metrics)

    return HookEffectResult(status="SUPPORTED", inputs=inp, curve=curve,
                            metrics=metrics, uncertainty=uncertainty,
                            warnings=warnings, solver=solver_info)


def _solve_range(T0: float, E0: float, kdT: float, kdE: float, alpha: float,
                 lo_nM: float, hi_nM: float, n: int, cfg: ModelerConfig,
                 ) -> tuple[np.ndarray, np.ndarray]:
    """Solve ternary over a log-dose range; returns (doses, ternary)."""
    lo = max(lo_nM, 1e-12)
    hi = max(hi_nM, lo * 2.0)
    doses = np.logspace(np.log10(lo), np.log10(hi), num=int(n))
    ys = np.array([_solve_one(T0, E0, float(d), kdT, kdE, alpha, cfg)["tle"]
                   for d in doses])
    return doses, ys


def _refine_peak_region(xs: np.ndarray, ys: np.ndarray, peak_idx: int,
                        evaluate, n_fine: int = 41) -> tuple[float, float]:
    """Refine (dose, ternary) around a coarse argmax to remove grid bias.

    ``evaluate(dose)`` returns ternary at a dose; fine scan runs between the two
    bracketing coarse neighbours of ``peak_idx``."""
    if 0 < peak_idx < len(xs) - 1:
        lo, hi = float(xs[peak_idx - 1]), float(xs[peak_idx + 1])
    elif peak_idx == 0 and len(xs) > 1:
        lo, hi = float(xs[0]), float(xs[1])
    elif peak_idx == len(xs) - 1 and len(xs) > 1:
        lo, hi = float(xs[-2]), float(xs[-1])
    else:
        return float(xs[peak_idx]), float(ys[peak_idx])
    fine = np.logspace(np.log10(max(lo, 1e-12)), np.log10(hi), num=n_fine)
    best_dose, best_val = float(fine[0]), float(evaluate(float(fine[0])))
    for d in fine[1:]:
        v = float(evaluate(float(d)))
        if v > best_val:
            best_val, best_dose = v, float(d)
    return best_dose, best_val


def _compute_metrics(curve: list[CurvePoint], threshold_frac: float, *,
                     inp: HookEffectInput | None = None,
                     cfg: ModelerConfig | None = None) -> HookMetrics:
    """Deterministic metrics (sub-grid-refined Cmax/ternary_max).

    Threshold doses (hook_90/hook_50) are the FIRST dose strictly ABOVE Cmax at
    which ternary has decayed to <= t x ternary_max — i.e., defined only on the
    descending/post-maximum limb. Severity is operational over the tested
    window: (ternary_max - min ternary on (cmax, max_dose]) / ternary_max; with
    monotonic post-peak decay this equals the drop at the tested window edge.
    """
    if not curve:
        raise HookModelError("empty dose grid")
    xs = np.array([p.dose_nM for p in curve])
    ys = np.array([p.ternary_nM for p in curve])
    peak_idx = int(np.argmax(ys))

    cmax, ternary_max = float(xs[peak_idx]), float(ys[peak_idx])
    if inp is not None and cfg is not None and len(curve) >= 3:
        cmax, ternary_max = _refine_peak_region(
            xs, ys, peak_idx,
            lambda d: _solve_one(inp.poI_conc_nM, inp.e3_conc_nM, d,
                                 inp.kd_poi_protac_nM, inp.kd_e3_protac_nM,
                                 inp.alpha, cfg)["tle"])

    occ_at_peak = min(ternary_max / inp.poI_conc_nM, 1.0) if inp else float(
        np.max([p.occupancy_fraction for p in curve]))

    def _cross(t: float) -> float | None:
        """First dose > cmax where ternary <= t*ternary_max (descending limb)."""
        for p in curve:
            if p.dose_nM > cmax and ternary_max > 0 and p.ternary_nM <= t * ternary_max:
                return p.dose_nM
        return None

    hook_90 = _cross(0.9)
    hook_50 = _cross(0.5)

    # severity over the tested post-Cmax window (explicit reference: min ternary
    # for doses in (cmax, max_dose_nM]); monotonic decay => endpoint value
    max_dose = float(curve[-1].dose_nM) if inp is None else float(inp.max_dose_nM)
    post = [p.ternary_nM for p in curve if p.dose_nM > cmax and p.dose_nM <= max_dose]
    tail_min = min(post) if post else ternary_max
    severity = 0.0 if ternary_max <= 0 else max(0.0, min(1.0, (ternary_max - tail_min) / ternary_max))
    label = "no_hook" if severity < 0.05 else ("moderate" if severity < 0.5 else "severe")

    max_occ_curve = float(np.max([p.occupancy_fraction for p in curve])) or occ_at_peak
    active = [p.dose_nM for p in curve if p.occupancy_fraction >= threshold_frac * max_occ_curve and max_occ_curve > 0]
    window = (max(active) / min(active)) if len(active) >= 2 else 0.0

    hook_cmax_ratio = (cmax / hook_50) if (hook_50 and cmax) else None

    return HookMetrics(
        cmax_nM=round(cmax, 6),
        ternary_max_nM=round(ternary_max, 6),
        max_occupancy_fraction=round(occ_at_peak, 6),
        hook_90_nM=round(hook_90, 6) if hook_90 else None,
        hook_50_nM=round(hook_50, 6) if hook_50 else None,
        hook_cmax_ratio=round(hook_cmax_ratio, 6) if hook_cmax_ratio else None,
        hook_severity=round(severity, 6),
        hook_label=label,
        occupancy_window_fold=round(window, 3),
        severity_reference_max_dose_nM=round(max_dose, 6),
    )


def _monte_carlo_uncertainty(inp: HookEffectInput, cfg: ModelerConfig,
                             nominal: HookMetrics) -> UncertaintySummary:
    """Two-stage (coarse -> fine-refined) per-sample optimum estimation.

    A coarse 24-point log scan brackets the ternary peak, then a fine scan
    between the two bracketing grid points recovers the per-sample optimum
    dose/peak free of coarse-grid quantization bias. Parameters are sampled
    lognormally around the NOMINAL inputs (median multiplier = 1).
    """
    rng = np.random.default_rng(inp.seed)
    pct = inp.uncertainty_pct or {}
    kd_pct = float(pct.get("kd", cfg.uncertainty.default_kd_pct)) / 100.0
    alpha_pct = float(pct.get("alpha", cfg.uncertainty.default_alpha_pct)) / 100.0
    n = int(cfg.uncertainty.n_samples)
    peaks: list[float] = []
    opt_doses: list[float] = []
    severities: list[float] = []
    for _ in range(n):
        kt = inp.kd_poi_protac_nM * float(rng.lognormal(0.0, kd_pct))
        ke = inp.kd_e3_protac_nM * float(rng.lognormal(0.0, kd_pct))
        al = inp.alpha * float(rng.lognormal(0.0, alpha_pct))
        # stage 1: coarse bracketing scan
        xs_c, ys_c = _solve_range(inp.poI_conc_nM, inp.e3_conc_nM, kt, ke, al,
                                  inp.min_dose_nM, inp.max_dose_nM, 24, cfg)
        idx = int(np.argmax(ys_c))
        coarse_peak = float(ys_c[idx])

        def evaluate(d: float, _kt=kt, _ke=ke, _al=al) -> float:
            return _solve_one(inp.poI_conc_nM, inp.e3_conc_nM, d, _kt, _ke, _al, cfg)["tle"]

        opt, peak = _refine_peak_region(xs_c, ys_c, idx, evaluate, n_fine=25)
        opt_doses.append(opt)
        peaks.append(peak)
        # severity approximated on the coarse scan relative to its coarse peak
        tail = float(np.min(ys_c[idx + 1:])) if idx < len(ys_c) - 1 else coarse_peak
        severities.append(max(0.0, (coarse_peak - tail) / max(coarse_peak, 1e-12)))

    def _q(a: list[float], q: float) -> float:
        return float(np.percentile(a, q)) if a else 0.0

    ref = nominal.optimal_concentration_nM
    frac25 = 0.0
    if ref and opt_doses:
        within = [d for d in opt_doses if abs(np.log10(d / ref)) <= np.log10(1.25)]
        frac25 = len(within) / len(opt_doses)

    return UncertaintySummary(
        enabled=True, n_samples=len(peaks),
        peak_ternary_nM={"p5": round(_q(peaks, 5), 4), "median": round(_q(peaks, 50), 4),
                         "p95": round(_q(peaks, 95), 4)},
        optimal_concentration_nM={"p5": round(_q(opt_doses, 5), 4),
                                  "median": round(_q(opt_doses, 50), 4),
                                  "p95": round(_q(opt_doses, 95), 4)},
        hook_severity_p95=round(_q(severities, 95), 4),
        reference_optimum_nM=round(ref, 4) if ref else None,
        fraction_within_25pct=round(frac25, 4),
    )
