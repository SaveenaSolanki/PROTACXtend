# Module 4 — PROTAC Degradation ML Model

**Entry point:** `predict_degradation(smiles, target=None, e3=None, model_path=None)`

## Curated dataset (real, reproducible)
`outputs/benchmark/benchmark_predictions.csv` — 64 published PROTAC records
(name/target/E3/SMILES/published DC50 nM) previously curated from PROTAC-DB by
the project's benchmark pipeline; 32 rows carry published Dmax. Labels are the
published values; none are inferred. E3 vocabulary: CRBN/VHL only (2 groups →
unseen-E3 is a 2-fold demonstration).

## Model
Target pDC50 = -log10(DC50/M). Features: 8 RDKit descriptors + ECFP4 (1024) +
train-only ordinal target/E3 codes. Baseline order: mean → ridge → RandomForest
→ XGBoost → (GP reserved). Grouped split evaluation: random / scaffold (Murcko)
/ unseen-target / unseen-E3 / unseen-PROTAC; entity encoders are fit on the
training fold only (no leakage). Artifact stores fitted estimator + conformal-
style residual quantiles + training descriptor space for OOD (kNN distance).

## Honest task availability
* pDC50: enabled (64 labels).
* Dmax: labels sparse (32) — Dmax artifact separate; None until provided.
* **degradation probability: no measured binary labels exist → output is None
  and the task is reported disabled. Never fabricated.** A classifier can be
  added only when measured degradation-outcome labels are curated.
* OOD: enabled (kNN distance vs training descriptors; flag when > 3× mean).

Target/E3 context given to predict_degradation is forwarded to feature_matrix:
a seen entity is coded with its training-fold code; an absent/unknown entity
maps to the out-of-vocabulary code.

## Demo
`python -m synglue_agent.modules.degradation_ml.examples.train_demo` trains the
production model (models/pdc50_model.joblib), prints grouped benchmarks and a
prediction with interval + OOD.

See VALIDATION.md, LIMITATIONS.md.
