# Validation — Cooperativity alpha predictor

`python -m pytest synglue_agent/modules/cooperativity_alpha_predictor/tests/` → 18 passed.

| Area | Checks |
|---|---|
| alpha semantics | ln/exp roundtrip; alpha=0↔−∞; negative rejected; class boundaries (1.25/0.8); class-from-log |
| features/surrogate | deterministic & reproducible; chains present; missing-chain error; malformed structure error; molecular descriptors incl. invalid SMILES |
| predict API | no-evidence → explicit failure; surrogate mode never claims alpha (predicted_alpha None, class not_assessed, surrogate uncertainty label, "NOT experimental alpha" limitation); missing model artifact → surrogate + note; call reproducibility (identical model_dump) |
| data audit | empty curation → supervised path stops (dataset_empty, no-training note); duplicate/conflict reporting on records; leakage-safe grouped splits verified disjoint |
| benchmark harness | grouped (unseen-series) folds; models reported incl. mean/ridge/RF/XGB/GP(GP optional); metrics R2/MAE/RMSE/Spearman/Pearson/sign-accuracy (synthetic harness check) |

Surrogate demo on synthetic two-chain pose: feasibility score computed with
positive contacts/BSA evidence; agent tool success; no-evidence path raises.
