# Module 4 follow-up — should the larger curated dataset retrain Module 4?

Decision memo (Module 5 delivery, item 12 of its spec).

## State of the artifacts
- **M4-v1 (frozen, untouched)**: `degradation_ml/models/pdc50_model.joblib`,
  RandomForest on the 64-row PROTAC-DB benchmark extract. In-sample RF
  R²≈0.95/MAE 0.21 (train-fit only, labelled as such); grouped results modest
  (scaffold ridge R²=0.41/MAE 0.73; random-split negative). Audit-approved
  and frozen — Module 5 did not modify it.
- **M5 (this module)**: context-aware model on the large dataset (1,913
  curated rows; 1,181 measured DC50). Leg-D production artifact
  (`cell_context_selector/models/cell_context_model.joblib`).

## Three-way comparison (same-feature logic, different data/context)
A direct head-to-head on identical rows/splits is not possible: M4-v1's 64
rows are a different curated extract with its own splits. The honest
comparison uses Module 5's benchmark legs as proxies:

| model | data | held-out pDC50 R² (grouped, RF unless noted) |
|---|---|---|
| M4-v1 (frozen small-data) | 64 rows | scaffold ridge R² 0.41 (its best grouped); random-split negative |
| M5 leg A (molecular only — M4-style featurizer on the big set) | 1,181 rows | unseen-PROTAC 0.503; random 0.649 |
| M5 leg B (+target/E3, no cell context) ≈ future **M4-v2** candidate | 1,181 rows | unseen-PROTAC 0.513; random 0.663 |
| M5 leg D (+transcriptomic context) | 935 rows (context subset) | unseen-PROTAC **0.605**; random 0.685 |

Reading: the larger measured set (even context-independent, leg B) already
outperforms the M4-v1 small-data artifact on grouped unseen-compound
evaluation; adding cell context (leg D) adds a further margin on
unseen-PROTAC/scaffold/random. No neural model was needed (spec: build one
only if it beats baselines — tree ensembles won).

## Recommendation (gated on Module-5 report audit)
1. Keep **M4-v1 frozen** (it is the validated small-data baseline).
2. **Create M4-v2** as a separately-versioned, context-INDEPENDENT retrain on
   the large curated set: use Module 5's leg-B production fit (or an
   aggregated per-compound pDC50 if cell-line dependence should be averaged
   away) with the same documented grouped validation, stored as
   `degradation_ml/models/pdc50_model_v2.joblib` behind its own version field.
3. Then publish a three-way benchmark on a common held-out set
   (M4-v1 vs M5-context vs M4-v2) with the same grouped regimes — before any
   M4-v1 replacement is even considered.

## Constraints honoured here
- M4 artifact bytes untouched; no overwrite.
- Derived-activity labels in M5 are threshold-derived (documented), so M4-v2
  training on DC50/Dmax only uses measured endpoints.
- A future M4-v2 would reuse this module's cleaning (dataset.py) + provenance
  manifest rather than re-curating.
