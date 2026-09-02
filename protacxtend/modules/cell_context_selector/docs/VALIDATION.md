# Validation — Module 5 (cell-context degradation model)

`pytest protacxtend/modules/cell_context_selector/tests/` → 16 passed.
Reproduction: `python -m ...examples.train_demo` (full config:
n_estimators=250, n_jobs=4, n_splits=5, seed 42) rewrites
`data/benchmark_results.json` and the artifact deterministically.

All pre-processing (entity/lineage encoders, median imputation, scaling) is
fit on training folds only. Grouped folds never share a compound/target/E3/
cell line across train/test in the corresponding regime. "random" is a plain
row split (an optimistic ceiling — the same compound may appear in both).

## Dataset after QC
2,141 → −62 viability-only → 2,079 → −166 exact duplicates → **1,913 curated
rows** (180 cell lines, 121 targets, 8 E3s, 231 DOIs). Measured DC50 1,181;
Dmax 761; both 479. Derived-active (documented AND rule, pDC50≥6 & Dmax≥60)
defined on 775 rows (394 positive). QA vs shipped `Active`: 700/857 agree —
shipped column never used. Expression context: 1,512 rows (935 with measured
DC50). No value fabricated.

## Cell-line mapping & omics coverage
| axis | result |
|---|---|
| Raw cell-line names | 180 |
| Mapped to DepMap 24Q4 | 137 (incl. 2 ambiguous noted) |
| Unmapped | 41 (7 are qualitative assay descriptions; remainder e.g. HEK293T, SRD15, TMD8, WI38 absent from DepMap 24Q4) |
| Transcriptomics coverage | 130 cell lines / 1,512 rows (DepMap 24Q4 TPM-log1p, 142-gene curated panel + POI genes) |
| Proteomics coverage | **0** (no DepMap 24Q4 proteomics matrix) → proteotype claims disabled |

## Split-specific results (pDC50 regression; R² best model per leg/regime)

| regime | A mol-only | B +tgt/e3 | C +cell-id | D +transcriptomics | best (R²) |
|---|---|---|---|---|---|
| random (n=1,181) | ET 0.583 | RF 0.663 | XGB 0.677 | **XGB 0.685** | D |
| unseen-PROTAC (n=1,181) | RF 0.503 | RF 0.513 | RF 0.523 | **RF 0.605** | D (+0.092 vs B) |
| scaffold (n=1,181) | RF 0.502 | RF 0.513 | RF 0.525 | **RF 0.603** | D |
| unseen-target (n=1,181) | RF 0.271 | RF 0.272 | RF 0.263 | RF 0.154* | B/A ≈ |
| unseen-E3 (n=1,181) | RF −0.018 | RF −0.033 | RF −0.024 | RF 0.015 | ≈ (all weak) |
| unseen-cell-line (n=1,181) | XGB 0.296 | XGB 0.294 | XGB 0.305 | XGB 0.219 | C marginally > B |
| unseen-PROTAC+cell (n=878) | RF 0.158 | RF 0.155 | RF 0.153 | RF 0.120 | ≈ (all modest) |

\* unseen-target: transcriptomic POI features do not help when the *target* is
absent from training; ridge is rescued by D in several regimes (e.g.,
unseen-PROTAC ridge −0.48 → 0.06; unseen-E3 −6.25 → −4.00).

Full per-model metrics (R²/MAE/RMSE/Spearman/Pearson, n) for every
endpoint × leg × regime are in `data/benchmark_results.json`.

## Dmax (regression, 761 rows; RF)
| regime | B | D |
|---|---|---|
| random | 0.521 | **0.548** |
| unseen-PROTAC | 0.476 | **0.519** |
| unseen-cell-line | −0.152 | −0.021 (RF), ridge −2.19 → −4.99 |
| scaffold | 0.445 | **0.514** |

## Derived-activity view (classification; threshold-derived label, 775 rows)
| regime | leg B | leg D |
|---|---|---|
| random | RF AUROC 0.904 | RF 0.900 (logistic 0.883) |
| unseen-PROTAC | RF 0.884 | **RF 0.894** |

## Ablation answer — does cellular context improve degradation prediction?
**Potency (pDC50): YES.** Adding DepMap transcriptomic cell state (leg D)
improves held-out pDC50 prediction for **unseen PROTACs** (R² 0.513 → 0.605,
Δ+0.092), scaffold-unseen (0.513 → 0.603) and random splits (0.663 → 0.685
best-family), and rescues linear baselines. Improvement is consistent for
Dmax (unseen-PROTAC 0.476 → 0.519).
**Transfer to a completely unseen cell line: NOT yet robust.** On
unseen-cell-line splits, transcriptomic context (D) does not beat PROTAC-only
(B) for the best families (RF 0.269 → 0.161; XGB 0.294 → 0.219); identity
codes (C) give at most +0.011 (XGB) and are **not** claimed as selectivity
evidence. ExtraTrees/ridge improve on that regime, so the picture is mixed —
flagged as future work (larger panel + line-matched assay data).
**Proteomics & Modules 1–3: not available at dataset scale** (no DepMap
proteomics; 22 rows reference a ternary structure) — leg E/F not run; no
proteotype/mechanistic claim.

## Claim gating (final, stored in the artifact)
| claim | value | evidence |
|---|---|---|
| cell_context_aware | **True** | leg D > leg B on unseen-PROTAC pDC50 (Δ+0.092) |
| transcriptomics_generalises_to_unseen_lines | **False** | leg D < leg B on unseen-cell-line (Δ−0.076) |
| proteotype_aware | **False** | no validated proteomics features |
| selectivity_from_identity_only | **False** | never claimed |

## Uncertainty / OOD
Demo row (worst-pDC50 training row; leg D production artifact): predicted
pDC50 4.61 (DC50 ≈ 24.7 µM vs published 100 µM), Dmax 72.8, derived-activity
prob 0.077, DC50 empirical interval 7.8–81.6 µM, RF spread 0.95 pDC50 units;
all OOD flags False → applicability SUPPORTED. When expression context is
absent (e.g., unmapped cell line) the API raises the cell-context OOD flag
and returns CAUTION (never fabricated context).
