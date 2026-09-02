# Module 1 — Hook Effect Modeler

**Status:** implemented, tested, integrated (agent tool `run_hook_effect_modeler`).

Location: `synglue_agent/modules/hook_effect_modeler/` (the `protacxtend`
distribution's code package is `synglue_agent`, so the requested
`protacxtend/modules/...` layout maps here; modules stay separated from
`tools/`, `agents/`, `tests/`).

## Inputs (typed, pydantic — all concentrations in nM)

| Field | Meaning | Default |
|---|---|---|
| `poI_conc_nM` | total POI/target concentration | 100 |
| `e3_conc_nM` | total E3-ligase concentration | 100 |
| `kd_poi_protac_nM` | POI–PROTAC binary Kd | 50 |
| `kd_e3_protac_nM` | E3–PROTAC binary Kd | 50 |
| `alpha` | ternary cooperativity (≥0). Dimensionless multiplicative enhancement of the affinity of the *second* binary arm: TLE = α·TL·E/K_E = α·EL·T/K_T (path-independent by detailed balance); α=1 no cooperativity, α>1 positive, α=0 ternary cannot form | 1.0 |
| `min_dose_nM`, `max_dose_nM`, `points` | log-spaced dose grid | 0.01 / 10⁴ / 120 |
| `uncertainty_pct` | {kd, alpha} % 1-σ lognormal noise (0 ⇒ no MC) | {0,0} |
| `seed` | reproducible RNG | 42 |

## Outputs

`HookEffectResult`:

* `curve[]` — dose → **all species**: ternary (TLE), binaries TL and EL, free
  POI/E3/PROTAC, occupancy fraction, POI-bound fraction
* `metrics.cmax_nM` — PROTAC dose (nM) at the ternary peak (x-axis argmax)
* `metrics.ternary_max_nM` — ternary-complex concentration (nM) AT Cmax (y-axis)
* `metrics.max_occupancy_fraction`; `metrics.occupancy_window_fold`
* `metrics.hook_90_nM` / `hook_50_nM` — first dose **strictly above Cmax**
  (descending/post-maximum limb) at which ternary ≤ 0.90/0.50 × ternary_max
* `metrics.hook_cmax_ratio` = cmax / hook_50 (closer to 1 ⇒ hook nearer Cmax)
* `metrics.hook_severity` (0–1): (ternary_max − min ternary over (Cmax, tested
  max_dose]) / ternary_max — an operational, window-explicit measure
  (`severity_reference_max_dose_nM` reports the window edge); monotonic post-peak
  decay ⇒ equals the drop at the window edge
* `metrics.hook_label` (`no_hook|moderate|severe`)
* `uncertainty` — MC percentiles (p5/median/p95) for Cmax and ternary max,
  severity p95, `reference_optimum_nM` and `fraction_within_25pct`
* `warnings`, `solver.max_residual` (mass-balance check), `model` version metadata

Cmax and ternary-max are different quantities — never compare the Cmax
percentiles with the ternary-max interval. MC Cmax p5–p95 brackets the
deterministic Cmax; MC ternary-max p5–p95 brackets the deterministic
ternary_max (validated by regression tests).

## Equations

Species T (POI), L (PROTAC), E (E3); binaries TL, EL; ternary TLE.

    TL  = T·L / K_T
    EL  = E·L / K_E
    TLE = α · TL·E / K_E        (detailed-balance-consistent with E→TL pathway)

Conservation: `T0 = T+TL+TLE`, `E0 = E+EL+TLE`, `L0 = L+TL+EL+TLE`.
Free concentrations (T,E,L) are solved **numerically** (bounded least-squares in
log10-space, relative mass-balance residuals) at every dose — no closed-form or
heuristic approximation of the ternary term. The hook effect emerges from the
model: at high PROTAC, L sequesters T and E into binaries, reducing TLE.

## Usage

```python
from synglue_agent.modules.hook_effect_modeler import simulate_hook_effect
r = simulate_hook_effect(poI_conc_nM=100, e3_conc_nM=100, alpha=30.0)
r.metrics.hook_severity            # 0.75
r.metrics.optimal_concentration_nM # ~153
```

```bash
python -m synglue_agent.modules.hook_effect_modeler.examples.quickstart
python -m pytest synglue_agent/modules/hook_effect_modeler/tests/
```

Agent/LangGraph: `synglue_agent.tools.hook_effect_modeler_tool.run_hook_effect_modeler(payload)` —
JSON-in/JSON-out, never raises to the graph.

## Dependencies / reproducibility

numpy, scipy (optimize), pydantic. Config JSON under `configs/` (env
`HOOK_EFFECT_MODELER_CONFIG`); every MC run uses a fixed seed; solver residuals
are reported for auditability.

See `ARCHITECTURE.md`, `VALIDATION.md`, `LIMITATIONS.md`, `REFERENCES.md`.
