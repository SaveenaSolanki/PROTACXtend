# Validation — Lysine Ubiquitination Feasibility Scorer

`python -m pytest synglue_agent/modules/lysine_ubiquitination_feasibility/tests/` → 8 passed.

| # | Check | Result |
|---|---|---|
| 1 | PDB heavy-atom parsing | PASS |
| 2 | Analytic Shrake–Rupley: isolated atom SASA ≈ 4π(r+1.4)² (n_dots=960, rel 1 %) | PASS |
| 3 | Occlusion reduces SASA | PASS |
| 4 | Proximal productive lysine ranked first; far lysine (>cutoff) never productive | PASS |
| 5 | Ensemble: per-lysine geometry across 3 poses; productive-pose fraction 1.0 | PASS |
| 6 | Missing E2 catalytic Cys → explicit REJECT error (no fabricated geometry) | PASS |
| 7 | Missing structure file → clear input error | PASS |
| 8 | Schema/version metadata + score bounds 0..1 | PASS |

Demo (synthetic 2-pose ensemble): LYS at 7.8 Å from E2 Cys-Sγ, productive in 2/2
poses (score 0.77); distal lysine at 22 Å non-productive (0.19); aggregate
feasibility 0.48 ("marginal" — distal lysine drags the mean).

NOTE: fixtures are synthetic geometry for deterministic testing, not scientific
claims. Real-structure benchmarking (e.g., published ternary complexes with
known ubiquitination sites) is the required next data step before reliability
claims.
