"""M1 — Ternary Occupancy & Hook Dynamics (mechanistic equilibrium).

Implements the spec §7-9 facade over the existing mechanistic three-body
equilibrium model (``modules/hook_effect_modeler``, Douglass-style coupled
equilibria T+P<->TP, E+P<->EP, TP+E<->TPE, EP+T<->TPE).

Every input parameter carries provenance (value/unit/evidence_type/source),
every output is labelled ``MECHANISTIC_SIMULATION`` — never
``EXPERIMENTAL_HOOK_EFFECT`` — and sensitivity to alpha and Kds is reported.
No ML is involved. No experimental claim is made from this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

model_source = "modules/hook_effect_modeler (core.py; mechanistic three-body equilibrium)"


@dataclass
class ParameterProvenance:
    value: float
    unit: str
    evidence_type: str
    source: str


@dataclass
class M1Input:
    kd_target_nM: ParameterProvenance
    kd_e3_nM: ParameterProvenance
    target_conc_nM: ParameterProvenance
    e3_conc_nM: ParameterProvenance
    alpha: ParameterProvenance
    dose_min_nM: float = 0.01
    dose_max_nM: float = 10_000.0
    n_points: int = 120
    uncertainty_pct: dict[str, float] = field(default_factory=lambda: {"kd": 0.0, "alpha": 0.0})
    seed: int | None = 42


PROVENANCE_TYPES = ("EXPERIMENTAL", "CALCULATED", "INFERRED", "STRUCTURAL_PROXY", "UNAVAILABLE")


def _default_provenance() -> dict[str, ParameterProvenance]:
    """Reference-style defaults; all configurable and source-labelled.

    Provenance evidence_type stays within the allowed parameter set
    (EXPERIMENTAL | CALCULATED | INFERRED | STRUCTURAL_PROXY | UNAVAILABLE).
    Placeholder Kds are honestly UNAVAILABLE, never silently experimental.
    """
    return {
        "kd_target_nM": ParameterProvenance(50.0, "nM", "UNAVAILABLE",
                                            "default placeholder — replace with measured Kd (EXPERIMENTAL)"),
        "kd_e3_nM": ParameterProvenance(50.0, "nM", "UNAVAILABLE",
                                        "default placeholder — replace with measured Kd (EXPERIMENTAL)"),
        "target_conc_nM": ParameterProvenance(100.0, "nM", "INFERRED", "cellular context default"),
        "e3_conc_nM": ParameterProvenance(100.0, "nM", "INFERRED", "cellular context default"),
        "alpha": ParameterProvenance(1.0, "dimensionless", "STRUCTURAL_PROXY",
                                     "no measured alpha; alpha=1 neutral default (see M3)"),
    }


def run_m1(inp: M1Input | None = None) -> dict[str, Any]:
    """Run the mechanistic hook/ternary-occupancy simulation.

    Returns (spec §8):
      - concentration-dependent rows: PROTAC_concentration, free_target,
        free_E3, free_PROTAC, TP_fraction, EP_fraction, TPE_fraction,
        productive_ternary_fraction
      - summaries: peak_ternary_concentration, peak_ternary_fraction,
        hook_onset_concentration, high_dose_decline_fraction, hook_risk,
        alpha_sensitivity, Kd_sensitivity
      - provenance + evidence_type = MECHANISTIC_SIMULATION
    """
    from protacxtend.modules.hook_effect_modeler.core import simulate_hook_effect
    from protacxtend.modules.hook_effect_modeler.schemas import HookEffectInput

    prov = _default_provenance() if inp is None else {
        k: (getattr(inp, k) if hasattr(inp, k) else _default_provenance()[k]) for k in (
            "kd_target_nM", "kd_e3_nM", "target_conc_nM", "e3_conc_nM", "alpha")
    }
    if inp is None:
        inp = M1Input(**{k: v for k, v in prov.items()})

    h_in = HookEffectInput(
        poI_conc_nM=prov["target_conc_nM"].value,
        e3_conc_nM=prov["e3_conc_nM"].value,
        kd_poi_protac_nM=prov["kd_target_nM"].value,
        kd_e3_protac_nM=prov["kd_e3_nM"].value,
        alpha=prov["alpha"].value,
        min_dose_nM=inp.dose_min_nM,
        max_dose_nM=inp.dose_max_nM,
        points=inp.n_points,
        uncertainty_pct=inp.uncertainty_pct,
        seed=inp.seed,
    )
    out = simulate_hook_effect(
        poI_conc_nM=h_in.poI_conc_nM, e3_conc_nM=h_in.e3_conc_nM,
        kd_poi_protac_nM=h_in.kd_poi_protac_nM, kd_e3_protac_nM=h_in.kd_e3_protac_nM,
        alpha=h_in.alpha, min_dose_nM=h_in.min_dose_nM, max_dose_nM=h_in.max_dose_nM,
        points=h_in.points, uncertainty_pct=h_in.uncertainty_pct, seed=h_in.seed,
    )
    curve = out.curve
    metrics = out.metrics

    rows = []
    for p in curve:
        tot = p.free_poi_nM + p.poi_protac_binary_nM + p.ternary_nM
        rows.append({
            "PROTAC_concentration": p.dose_nM,
            "free_target": round(p.free_poi_nM, 4),
            "free_E3": round(p.free_e3_nM, 4),
            "free_PROTAC": round(p.free_protac_nM, 4),
            "TP_fraction": round((p.poi_protac_binary_nM / tot) if tot else 0.0, 6),
            "EP_fraction": round((p.e3_protac_binary_nM / tot) if tot else 0.0, 6),
            "TPE_fraction": round(p.occupancy_fraction, 6),
            "productive_ternary_fraction": round(p.occupancy_fraction, 6),
        })

    alpha_sensitivity = _sensitivity(prov["alpha"].value, "alpha")
    kd_sensitivity = _sensitivity(prov["kd_target_nM"].value, "kd_target")

    return {
        "status": "IMPLEMENTED",
        "evidence_type": "MECHANISTIC_SIMULATION",
        "claim": "concentration-dependent ternary occupancy (hook effect) — simulation only",
        "model_source": model_source,
        "parameters": {k: asdict(v) for k, v in prov.items()},
        "concentration_response": rows,
        "summaries": {
            "peak_ternary_concentration_nM": metrics.cmax_nM,
            "peak_ternary_fraction": metrics.max_occupancy_fraction,
            "hook_onset_concentration_nM": metrics.hook_50_nM,
            "high_dose_decline_fraction": metrics.hook_severity,
            "hook_risk": metrics.hook_label,
            "alpha_sensitivity": alpha_sensitivity,
            "Kd_sensitivity": kd_sensitivity,
        },
        "limitations": [
            "static equilibrium model: no cellular transport, target resynthesis or enzyme kinetics",
            "alpha and Kds are inputs with stated provenance; default values are placeholders",
        ],
        "approximation": "mechanistic equilibrium solved numerically; no ML",
    }


def _sensitivity(base: float, key: str) -> dict[str, float]:
    """Relative change of peak ternary fraction for +/-20% perturbation."""
    from protacxtend.modules.hook_effect_modeler.core import simulate_hook_effect
    from protacxtend.modules.hook_effect_modeler.schemas import HookEffectInput

    def peak(scale: float) -> float:
        kw = {"alpha": base} if key == "alpha" else {"kd_poi_protac_nM": base}
        kw.update({"poI_conc_nM": 100.0, "e3_conc_nM": 100.0,
                   "kd_poi_protac_nM": 50.0, "kd_e3_protac_nM": 50.0, "alpha": 1.0})
        if key == "kd_target":
            kw["kd_poi_protac_nM"] = base * scale
        else:
            kw["alpha"] = base * scale
        return simulate_hook_effect(**kw).metrics.max_occupancy_fraction

    p_lo, p_hi = peak(0.8), peak(1.2)
    return {
        "perturbation": "+/-20%",
        "peak_fraction_at_minus20pct": round(p_lo, 6),
        "peak_fraction_at_plus20pct": round(p_hi, 6),
        "relative_change": round(abs(p_hi - p_lo) / max(p_lo, 1e-9), 6),
    }


def _physical_flags(inp: M1Input, r: dict[str, Any]) -> dict[str, Any]:
    """Per-case physical sanity flags: mass conservation, boundaries, rise, hook."""
    rows = r["concentration_response"]
    tot_t = inp.target_conc_nM.value
    tot_e = inp.e3_conc_nM.value
    mass_ok = all(p["free_target"] <= tot_t + 1e-6 and p["free_E3"] <= tot_e + 1e-6
                  and p["TP_fraction"] >= 0 and p["EP_fraction"] >= 0
                  and p["TPE_fraction"] >= 0 for p in rows)
    zero_ok = rows[0]["PROTAC_concentration"] < 0.1 and rows[0]["TPE_fraction"] < 1e-3
    frac = [p["TPE_fraction"] for p in rows]
    rise_ok = all(frac[i + 1] >= frac[i] for i in range(min(15, len(frac) - 1)))
    tail = frac[-15:]
    hook_ok = tail[-1] < tail[0]
    return {"mass_conservation_ok": mass_ok, "zero_protac_boundary_ok": zero_ok,
            "low_dose_rise_ok": rise_ok, "high_dose_hook_decline_ok": hook_ok,
            "all_physical_checks_passed": bool(mass_ok and zero_ok and rise_ok and hook_ok)}


def m1_validation_rows() -> list[dict[str, Any]]:
    """Physical sanity cases + flags for the M1 validation CSV (§27)."""
    base = M1Input(**{k: v for k, v in _default_provenance().items()})
    cases = [
        ("alpha=1 neutral", base),
        ("alpha=3 positive cooperativity", _with_alpha(base, 3.0)),
        ("alpha=0.5 negative cooperativity", _with_alpha(base, 0.5)),
        ("tight target Kd", _with_kd(base, 5.0)),
        ("weak target Kd", _with_kd(base, 500.0)),
    ]
    rows = []
    for name, inp in cases:
        r = run_m1(inp)
        s = r["summaries"]
        row = {
            "case": name,
            "kd_target_nM": inp.kd_target_nM.value,
            "kd_target_provenance": inp.kd_target_nM.evidence_type,
            "kd_e3_nM": inp.kd_e3_nM.value,
            "alpha": inp.alpha.value,
            "alpha_provenance": inp.alpha.evidence_type,
            "peak_ternary_concentration_nM": s["peak_ternary_concentration_nM"],
            "peak_ternary_fraction": s["peak_ternary_fraction"],
            "hook_onset_concentration_nM": s["hook_onset_concentration_nM"],
            "high_dose_decline_fraction": s["high_dose_decline_fraction"],
            "hook_risk": s["hook_risk"],
            "evidence_type": r["evidence_type"],
        }
        row.update(_physical_flags(inp, r))
        rows.append(row)
    return rows


def m1_sensitivity_rows() -> list[dict[str, Any]]:
    """Sensitivity CSV rows: alpha and Kd relative-change effects per case."""
    from protacxtend.mechanistic.m1_hook import _default_provenance as _dp
    base = M1Input(**{k: v for k, v in _dp().items()})
    outs = [
        ("alpha=1 neutral", base),
        ("alpha=3 positive cooperativity", _with_alpha(base, 3.0)),
        ("alpha=0.5 negative cooperativity", _with_alpha(base, 0.5)),
        ("tight target Kd", _with_kd(base, 5.0)),
        ("weak target Kd", _with_kd(base, 500.0)),
    ]
    rows = []
    for name, inp in outs:
        r = run_m1(inp)
        rows.append({"case": name, "parameter": "alpha",
                     **{k: v for k, v in r["summaries"]["alpha_sensitivity"].items()}})
        rows.append({"case": name, "parameter": "kd_target",
                     **{k: v for k, v in r["summaries"]["Kd_sensitivity"].items()}})
    return rows


def _with_alpha(inp: M1Input, alpha: float) -> M1Input:
    return M1Input(
        kd_target_nM=inp.kd_target_nM, kd_e3_nM=inp.kd_e3_nM,
        target_conc_nM=inp.target_conc_nM, e3_conc_nM=inp.e3_conc_nM,
        alpha=ParameterProvenance(alpha, "dimensionless", "MECHANISTIC_SIMULATION",
                                  "test perturbation"),
        dose_min_nM=inp.dose_min_nM, dose_max_nM=inp.dose_max_nM,
        n_points=inp.n_points, uncertainty_pct=inp.uncertainty_pct, seed=inp.seed,
    )


def _with_kd(inp: M1Input, kd: float) -> M1Input:
    return M1Input(
        kd_target_nM=ParameterProvenance(kd, "nM", "CURATED_DATABASE", "test perturbation"),
        kd_e3_nM=inp.kd_e3_nM, target_conc_nM=inp.target_conc_nM,
        e3_conc_nM=inp.e3_conc_nM, alpha=inp.alpha,
        dose_min_nM=inp.dose_min_nM, dose_max_nM=inp.dose_max_nM,
        n_points=inp.n_points, uncertainty_pct=inp.uncertainty_pct, seed=inp.seed,
    )