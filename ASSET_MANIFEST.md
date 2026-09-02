# ASSET_MANIFEST.md

Committed scientific assets in the PROTACXtend final repository (mirror of
`config/scientific_status.yaml` paths). Model/weight files are committed so offline tests
and inference run without re-downloads.

## ML artifacts (committed)

| Asset | Purpose | Source |
| --- | --- | --- |
| `synglue_agent/modules/degradation_ml/models/pdc50_model.joblib` | Module 4 — pDC50/Dmax | curated 64/32 published labels |
| `synglue_agent/modules/cell_context_selector/models/cell_context_model.joblib` | Module 5 — transcriptomic cell context | PROTAC-Degradation-DB + DepMap 24Q4 |
| `data/tack/tack_dc50_model.joblib` · `tack_dmax_model.joblib` · `tack_bin_model.joblib` (+ calibration parquet) | TACK degradation predictors | TACK dataset |
| `data/synglue/models/multitask_transformer.pt` | SynGlue multitask transformer | SynGlue (Ahuja Lab) |
| `data/synglue/models/rf_dc50.joblib` · `rf_dmax.joblib` (optional, if present) | SynGlue RF regressors | SynGlue (Ahuja Lab) |
| `outputs/benchmark/chemprop_multitarget/model_0/best.pt` | Chemprop benchmark model | benchmark suite |

## Curated data (committed)

| Asset | Use |
| --- | --- |
| `data/synglue/data/grover_e3.csv` · `grover_warhead.csv` · `e3_ligand.csv` | SynGlue encodings + E3 ligand library (117 rows / 20 E3 groups) |
| `data/benchmark/PROTAC-DB_3.0_protacs.xlsx` | benchmark + training provenance |
| `data/tack/*.parquet` | TACK calibration |
| `synglue_agent/modules/cell_context_selector/data/context_joined.csv` | Module 5 features (DepMap 24Q4) |

## Spreadsheet registries

`Agent_Toolkit.xlsx` · `data/toolkit/Agent_Toolkit_EXPANDED.xlsx` · `TOOL_AUDIT.xlsx` ·
`data/protac_repos/protac_repo_registry.xlsx`

## Website assets

`website/assets/logo.png` · `logo-square.png` · `00_PROTACXtend_hero_visual.png` ·
`og-cover.png` (deployed by `.github/workflows/pages.yml`).

## Status source of truth

`config/scientific_status.yaml` — module/model/validation statuses; the website and claim
audit are verified against it.
