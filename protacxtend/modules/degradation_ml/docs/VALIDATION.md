# Validation — PROTAC Degradation ML

`pytest protacxtend/modules/degradation_ml/tests/` → 8 passed.

| Check | Result |
|---|---|
| Curated dataset loads; real published pDC50 labels (n>=50); prob labels == 0 (honest) | PASS |
| Split definitions present incl. scaffold/unseen-target/unseen-e3; aligned to rows | PASS |
| RDKit featurization deterministic; invalid SMILES returns ok=False zero vector; dims 8+1024 | PASS |
| Grouped evaluation returns per-split model metrics (mean/ridge/RF) | PASS |
| Train artifact (ridge) → predict roundtrip: interval contains prediction, prob None, tasks disabled labels | PASS |
| Missing artifact → explicit DegradationModelError | PASS |
| Version metadata in schema | PASS |

Live demo results (64 rows): grouped test-set R2/MAE are modest or negative
(e.g., random mean R2=-4.4 MAE=1.7 pDC50 units; scaffold ridge R2=0.41 MAE=0.73)
— the curated set is too small for reliable generalization, which is reported
rather than hidden. In-sample RF fit: R2≈0.95, MAE≈0.21 (train fit only).

Post-audit demo row (lowest-pDC50 training row, entity codes live): pDC50 5.13
(DC50 ≈ 7.4 µM vs published 16.8 µM), empirical interval ≈ 2.90–18.65 µM,
OOD score ≈ 24.9 (flag False).
