"""Tests: Module 1 — Hook Effect Modeler (equilibrium + metrics + uncertainty)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from synglue_agent.modules.hook_effect_modeler import (
    HookEffectResult,
    HookModelError,
    simulate_hook_effect,
    solve_ternary,
)
from synglue_agent.modules.hook_effect_modeler.config import ModelerConfig


def _mc_config(enabled: bool, seed: int = 42, samples: int = 40) -> ModelerConfig:
    cfg = ModelerConfig.load()
    cfg.uncertainty.enabled = enabled
    cfg.uncertainty.seed = seed
    cfg.uncertainty.n_samples = samples
    return cfg


class TestEquilibrium:
    def test_mass_balance_holds(self):
        """Bounded least-squares solve must conserve every species."""
        cfg = ModelerConfig.load()
        sol = solve_ternary(T0=100.0, E0=100.0, L0=250.0, K_T=50.0, K_E=50.0,
                            alpha=10.0, cfg=cfg)
        assert sol["residual"] < 1e-9

    def test_invalid_inputs_rejected(self):
        with pytest.raises(HookModelError):
            simulate_hook_effect(poI_conc_nM=-1.0)
        with pytest.raises(HookModelError):
            simulate_hook_effect(kd_poi_protac_nM=0.0)
        with pytest.raises(HookModelError):
            simulate_hook_effect(max_dose_nM=0.01, min_dose_nM=0.02)

    def test_solve_at_zero_dose(self):
        cfg = ModelerConfig.load()
        sol = solve_ternary(100.0, 100.0, 0.0, 50.0, 50.0, 10.0, cfg=cfg)
        assert sol["tle"] == pytest.approx(0.0, abs=1e-9)


class TestBellCurveAndHook:
    def test_strong_cooperativity_peaks_inside_window(self):
        r = simulate_hook_effect(alpha=20.0, max_dose_nM=10_000.0, points=150)
        peak = r.metrics.optimal_concentration_nM
        assert r.metrics.max_ternary_nM > 0
        assert peak is not None and peak > 0
        # peak is interior: ternary at window edges is below the peak
        assert r.curve[0].ternary_nM < r.metrics.max_ternary_nM
        assert r.curve[-1].ternary_nM < r.metrics.max_ternary_nM
        assert r.curve[-1].ternary_nM <= 0.5 * r.metrics.max_ternary_nM  # hook at high dose

    def test_hook_onset_and_severity_present_when_poi_and_e3_balanced(self):
        r = simulate_hook_effect(poI_conc_nM=100.0, e3_conc_nM=100.0, alpha=50.0,
                                 points=150)
        assert r.metrics.hook_onset_nM is not None
        assert 0.0 < r.metrics.hook_severity <= 1.0
        assert r.metrics.hook_label in ("moderate", "severe")
        assert r.metrics.optimal_concentration_nM < r.metrics.hook_onset_nM

    def test_alpha_strengthens_peak_occupancy(self):
        low = simulate_hook_effect(alpha=0.3, points=120)
        high = simulate_hook_effect(alpha=30.0, points=120)
        assert high.metrics.max_occupancy_fraction > low.metrics.max_occupancy_fraction
        assert high.metrics.max_ternary_nM > low.metrics.max_ternary_nM

    def test_e3_limiting_severity_regime_specific(self):
        """REGIME-SCOPED claim (NOT a universal invariant): for equal Kds
        (50/50 nM), alpha=20 and the SAME tested window (0.01..1e4 nM), the
        E3-limited stoichiometry gives a more severe hook than E3 excess.
        The generality of this ordering depends on Kd balance and window, and
        is not asserted beyond this regime."""
        limiting = simulate_hook_effect(poI_conc_nM=500.0, e3_conc_nM=20.0, alpha=20.0,
                                        min_dose_nM=0.01, max_dose_nM=10_000.0)
        excess = simulate_hook_effect(poI_conc_nM=500.0, e3_conc_nM=2000.0, alpha=20.0,
                                      min_dose_nM=0.01, max_dose_nM=10_000.0)
        assert limiting.metrics.hook_severity > excess.metrics.hook_severity

    def test_flat_occupancy_without_cooperativity(self):
        """alpha=1 & very low dose window: ternary grows then gently declines;
        severity stays small across a capped window."""
        r = simulate_hook_effect(alpha=1.0, e3_conc_nM=1000.0,
                                 max_dose_nM=1000.0, points=120)
        assert r.metrics.hook_severity < 0.9  # mild within this window


class TestUncertaintyAndRepro:
    def test_no_mc_when_zero_uncertainty(self):
        r = simulate_hook_effect(alpha=10.0, uncertainty_pct={"kd": 0.0, "alpha": 0.0})
        assert r.uncertainty.enabled is False

    def test_mc_reproducible_with_seed(self):
        kw = dict(alpha=10.0, uncertainty_pct={"kd": 10.0, "alpha": 15.0}, points=60)
        a = simulate_hook_effect(seed=7, config=_mc_config(True, seed=7), **kw)
        b = simulate_hook_effect(seed=7, config=_mc_config(True, seed=7), **kw)
        assert a.uncertainty.enabled is True
        assert a.uncertainty.n_samples > 0
        assert a.uncertainty.peak_ternary_nM == b.uncertainty.peak_ternary_nM
        assert a.uncertainty.optimal_concentration_nM == b.uncertainty.optimal_concentration_nM

    def test_mc_bounds_contain_nominal_peak(self):
        r = simulate_hook_effect(alpha=10.0,
                                 uncertainty_pct={"kd": 20.0, "alpha": 25.0},
                                 config=_mc_config(True, seed=11, samples=80))
        lo, med, hi = (r.uncertainty.peak_ternary_nM["p5"],
                       r.uncertainty.peak_ternary_nM["median"],
                       r.uncertainty.peak_ternary_nM["p95"])
        assert lo <= med <= hi
        assert lo > 0.0


class TestSchemaAndCurve:
    def test_result_schema_metadata(self):
        r = simulate_hook_effect(alpha=5.0, points=80)
        assert isinstance(r, HookEffectResult)
        assert r.model.startswith("hook_effect_modeler-v")
        assert len(r.curve) == 80
        assert all(p.occupancy_fraction >= 0.0 for p in r.curve)
        assert r.metrics.max_occupancy_fraction <= 1.0

    def test_curve_dose_grid_log_spaced(self):
        r = simulate_hook_effect(points=50)
        xs = [p.dose_nM for p in r.curve]
        assert xs[0] < xs[-1]
        assert all(xs[i] < xs[i + 1] for i in range(len(xs) - 1))


class TestDeterministicVsMonteCarloConsistency:
    """Regression guard for the audit finding: the deterministic optimum (x-axis
    optimal PROTAC dose) must agree with the MC optimum-dose distribution, and
    the MC peak-ternary interval must bracket the deterministic peak ternary
    (a different quantity — the y-axis maximum)."""

    PARAMS = dict(poI_conc_nM=100.0, e3_conc_nM=100.0,
                  kd_poi_protac_nM=50.0, kd_e3_protac_nM=50.0,
                  alpha=30.0, uncertainty_pct={"kd": 15.0, "alpha": 20.0})

    def test_mc_optimum_dose_matches_deterministic(self):
        kw = dict(self.PARAMS, seed=7, points=90)
        cfg = ModelerConfig.load()
        cfg.uncertainty.seed = 7
        cfg.uncertainty.n_samples = 60
        r = simulate_hook_effect(config=cfg, **kw)
        det = r.metrics.optimal_concentration_nM
        med = r.uncertainty.optimal_concentration_nM["median"]
        assert det is not None and med is not None
        ratio = max(det, med) / min(det, med)
        assert ratio < 1.35, f"MC median optimum {med} vs deterministic {det}"
        assert r.uncertainty.fraction_within_25pct >= 0.8

    def test_mc_peak_ternary_brackets_deterministic_peak(self):
        kw = dict(self.PARAMS, seed=11, points=90)
        cfg = ModelerConfig.load()
        cfg.uncertainty.seed = 11
        cfg.uncertainty.n_samples = 60
        r = simulate_hook_effect(config=cfg, **kw)
        p5 = r.uncertainty.peak_ternary_nM["p5"]
        p95 = r.uncertainty.peak_ternary_nM["p95"]
        assert p5 <= r.metrics.max_ternary_nM <= p95

    def test_deterministic_optimum_grid_independent(self):
        a = simulate_hook_effect(alpha=30.0, points=60, max_dose_nM=10_000.0)
        b = simulate_hook_effect(alpha=30.0, points=160, max_dose_nM=10_000.0)
        ratio = max(a.metrics.optimal_concentration_nM, b.metrics.optimal_concentration_nM) / \
                min(a.metrics.optimal_concentration_nM, b.metrics.optimal_concentration_nM)
        assert ratio < 1.05, "optimum must not depend on dose-grid resolution"


class TestThermodynamicConsistency:
    """alpha definition + path independence (checks 2 and 3 of the QA pass)."""

    def test_detailed_balance_two_paths_equal(self):
        """TLE computed via path 1 (E binds TL) must equal TLE via path 2
        (T binds EL) at the solved equilibrium, and both must equal the shared
        identity alpha*T*E*L/(K_T*K_E)."""
        cfg = ModelerConfig.load()
        sol = solve_ternary(100.0, 120.0, 800.0, 40.0, 60.0, 12.0, cfg=cfg)
        t, e, l, tl, el, tle = (sol["t"], sol["e"], sol["l"],
                                sol["tl"], sol["el"], sol["tle"])
        path1 = 12.0 * tl * e / 60.0
        path2 = 12.0 * el * t / 40.0
        identity = 12.0 * t * e * l / (40.0 * 60.0)
        assert abs(path1 - path2) / max(tle, 1e-12) < 1e-9
        assert abs(path1 - identity) / max(tle, 1e-12) < 1e-9
        assert abs(tle - path1) / max(tle, 1e-12) < 1e-9

    def test_alpha_zero_kills_ternary_everywhere(self):
        r = simulate_hook_effect(alpha=0.0, points=40)
        assert r.metrics.ternary_max_nM == 0.0
        assert all(p.ternary_nM == 0.0 for p in r.curve)
        assert r.metrics.hook_label == "no_hook"

    def test_zero_poi_or_e3_vanishing_ternary(self):
        """Limiting case T0 -> 0 or E0 -> 0: ternary vanishes (schema enforces
        strictly positive concentrations, so we approach zero with eps)."""
        a = simulate_hook_effect(poI_conc_nM=1e-6, e3_conc_nM=100.0, alpha=10.0, points=40)
        b = simulate_hook_effect(poI_conc_nM=100.0, e3_conc_nM=1e-6, alpha=10.0, points=40)
        assert a.metrics.ternary_max_nM < 1e-3
        assert b.metrics.ternary_max_nM < 1e-3

    def test_poi_e3_symmetry(self):
        """Model is symmetric under (POI <-> E3) + (Kd_POI <-> Kd_E3): the
        ternary curve is identical."""
        a = simulate_hook_effect(poI_conc_nM=120.0, e3_conc_nM=60.0,
                                 kd_poi_protac_nM=25.0, kd_e3_protac_nM=70.0,
                                 alpha=8.0, points=80)
        b = simulate_hook_effect(poI_conc_nM=60.0, e3_conc_nM=120.0,
                                 kd_poi_protac_nM=70.0, kd_e3_protac_nM=25.0,
                                 alpha=8.0, points=80)
        for pa, pb in zip(a.curve, b.curve, strict=True):
            assert pa.ternary_nM == pytest.approx(pb.ternary_nM, rel=1e-6)  # noqa: B905
        assert a.metrics.cmax_nM == pytest.approx(b.metrics.cmax_nM, rel=1e-6)

    def test_tight_kd_peaks_at_low_dose_high_occupancy(self):
        r = simulate_hook_effect(kd_poi_protac_nM=0.5, kd_e3_protac_nM=0.5,
                                 alpha=5.0, min_dose_nM=1e-3, points=120)
        assert r.metrics.cmax_nM < 300.0
        assert r.metrics.max_occupancy_fraction > 0.8


class TestExplicitHookMetrics:
    """Cmax, ternary max, hook-90/hook-50 and ratio (QA check 6)."""

    def test_metric_fields_and_definitions(self):
        r = simulate_hook_effect(alpha=30.0, max_dose_nM=10_000.0, points=160)
        m = r.metrics
        # Cmax (PROTAC dose) and ternary_max (ternary concentration) are
        # different quantities with different units of interpretation
        assert m.cmax_nM is not None and m.ternary_max_nM > 0
        assert m.hook_90_nM is not None and m.hook_50_nM is not None
        assert m.hook_90_nM <= m.hook_50_nM                  # 90% cross before 50% cross
        assert m.cmax_nM < m.hook_90_nM                       # both strictly post-Cmax
        assert m.hook_cmax_ratio is not None and m.hook_cmax_ratio < 1.0
        # refined ternary_max is >= any sampled curve value
        assert m.ternary_max_nM >= max(p.ternary_nM for p in r.curve) - 1e-9
        row = min((p for p in r.curve), key=lambda p: abs(p.dose_nM - m.cmax_nM))
        assert row.ternary_nM <= m.ternary_max_nM * 1.001 + 1e-6

    def test_hook_onset_on_descending_limb(self):
        r = simulate_hook_effect(alpha=30.0, max_dose_nM=10_000.0, points=200)
        cmax = r.metrics.cmax_nM
        ys = [p.ternary_nM for p in r.curve if p.dose_nM > cmax]
        xs = [p.dose_nM for p in r.curve if p.dose_nM > cmax]
        # any threshold crossing must occur only after the curve has peaked
        assert ys and max(ys) <= r.metrics.ternary_max_nM * 1.0001
        assert r.metrics.hook_90_nM >= xs[0]

    def test_binary_species_exposed(self):
        r = simulate_hook_effect(alpha=30.0, points=80)
        row_high = r.curve[-1]
        # at high dose the binary complexes dominate (hook regime)
        assert row_high.poi_protac_binary_nM > 0 and row_high.e3_protac_binary_nM > 0
        assert row_high.ternary_nM < row_high.poi_protac_binary_nM
        # species balance holds at every point
        for p in r.curve:
            tot = (p.free_poi_nM + p.poi_protac_binary_nM + p.ternary_nM)
            assert tot == pytest.approx(r.inputs.poI_conc_nM, rel=1e-6)
