# Validation report — Hook Effect Modeler

Run: `python -m pytest synglue_agent/modules/hook_effect_modeler/tests/` → **13 passed** (~18 s).

| # | Check | Result |
|---|---|---|
| 1 | Mass balance: solve conserves T,E,L (relative residual < 1e-9) | PASS |
| 2 | Zero dose ⇒ exactly zero binary/ternary complex | PASS |
| 3 | Strong cooperativity ⇒ interior peak; ternary at window edges below peak; high-dose hook ≤ 50% peak | PASS |
| 4 | Hook onset reported above the peak; onset > optimal dose | PASS |
| 5 | α↑ ⇒ peak occupancy and max ternary ↑ | PASS |
| 6 | E3-limiting case more severe hook than E3-excess **in the tested regime** (equal Kds 50/50 nM, alpha=20, window 0.01..1e4 nM) — not asserted as universal | PASS |
| 7 | α=1 flat/mild behaviour within capped window | PASS |
| 8 | Zero uncertainty ⇒ no MC path | PASS |
| 9 | MC reproducibility with fixed seed (identical percentiles) | PASS |
| 10 | MC p5 ≤ median ≤ p95; > 0 | PASS |
| 11 | Result schema + model-version metadata; grid length exact; log-spaced | PASS |
| 12 | Invalid inputs (negative conc/Kd, inverted grid) rejected with clear errors | PASS |

Scientific sanity demo (alpha=30, T=E=100 nM, Kds=50 nM): optimal [PROTAC]
153 nM, max ternary occupancy 0.773, hook onset 3132 nM, severity 0.747
(severe); MC peak p5/median/p95 73.9/77.3/79.9 nM — a bell-shaped ternary
dose-response with a real high-dose hook, as expected for strong cooperativity
at balanced stoichiometry.

## Audit addendum (deterministic vs Monte-Carlo consistency)

Finding resolved: the deterministic "optimum 153 nM" and the MC interval shown
in the first demo were **different quantities** — the deterministic optimum is
the optimal PROTAC dose (x-axis argmax, nM PROTAC) while the demo-printed MC
interval (73.9–79.9 nM) was the *peak ternary-complex concentration* (y-axis
maximum, nM ternary), which correctly brackets the deterministic peak ternary
77.3 nM. Both use identical nominal parameters (α=30, T=E=100 nM, Kd=50 nM);
MC perturbs only Kd and α (lognormal, median = nominal, i.e., centred in
multiplicative-median terms; units nM throughout). A second real defect found
and fixed: the MC optimum-dose scan used a coarse 24-point log grid whose
~1.8× spacing quantised per-sample optima; the optimum is now estimated with a
two-stage coarse+fine (sub-grid) scan in both the deterministic metrics and
every MC sample, and `reference_optimum_nM` + `fraction_within_25pct` are
reported in the schema.

Measured (α=30, T=E=100 nM, Kd 50 nM, kd σ=15 %, α σ=20 %, seed 42, n=100):
- deterministic optimum dose (refined): **150.42 nM** PROTAC (peak ternary 77.30 nM)
- MC optimum-dose p5/median/p95: **142.0 / 149.2 / 156.9 nM** (median within 0.8 %)
- MC peak-ternary p5/median/p95: **73.9 / 77.3 / 80.0 nM** (brackets nominal peak)
- MC optimum within ±25 % of the nominal solution: **100 %**

## Post-QA status: 24/24 tests pass (Cmax/ternary-max separation, thermodynamic-cycle path independence, alpha limiting cases incl. alpha=0 and POI/E3 symmetry, hook-90/hook-50/hook:Cmax, binary+free species exposure, DOI display hardening for the research layer).
