# ASSET MANIFEST — excluded & external assets (v0.3.0-agentic-core)

Reproduction rule: `git clone` gives you a runnable-but-degraded tree. Run
`./scripts/bootstrap_assets.sh` to restore full functionality (retrosynthesis
routes, SE3 ternary). Everything below is either in git, downloadable, or
locally generated with a documented procedure.

| # | Asset | Source URL | Expected location | Version / checksum |
|---|---|---|---|---|
| 1 | USPTO expansion policy (Keras hdf5) | https://ndownloader.figshare.com/files/23086454 (figshare article 12334577, "full_uspto_03_05_19_rollout_policy.hdf5") | `data/retrosynthesis/models/aizynth/uspto_policy.hdf5` | USPTO model 03_05_19; SHA256 recorded by bootstrap → `ASSET_MANIFEST.checksums.json` |
| 2 | USPTO reaction templates | https://ndownloader.figshare.com/files/23086457 ("full_uspto_03_05_19_unique_templates.hdf5", 42.6 MB) | `data/retrosynthesis/models/aizynth/uspto_templates.hdf5` | USPTO templates 03_05_19; SHA256 via bootstrap |
| 3 | ZINC stock (purchasable) | https://ndownloader.figshare.com/files/23086469 ("zinc_stock_17_04_20.hdf5", 632.5 MB) | `data/retrosynthesis/models/aizynth/zinc_stock.hdf5` | ZINC stock 17_04_20; SHA256 via bootstrap |
| 3b | USPTO stereo policy + templates (ONNX) | https://zenodo.org/records/10548209 (uspto_stereo_expansion_model.onnx, 4.7 MB; uspto_stereo_unique_templates.csv.gz) | `data/retrosynthesis/models/aizynth/uspto_model.onnx` + `uspto_templates.csv.gz` | official aizynthfinder-team stereo model; preferred by code (works on ONNX-only installs); SHA256 via bootstrap |
| 4 | SynGlue multitask transformer | **committed to git** (35 MB, `SynGlue_Py/models/multitask_transformer.pt`) | `SynGlue_Py/models/multitask_transformer.pt` | locally trained (SynGlue architecture, 9M params); in-repo |
| 5 | GROVER fixed checkpoint | **not committable** (409 MB > GitHub limit) — locally trained | `SynGlue_Py/models/grover_fixed.pt` | locally generated; re-train via SynGlue_Py GROVER pipeline or copy from original machine; bootstrap warns if absent |
| 6 | GROVER E3 embeddings csv | **committed to git** (6.2 MB) | `SynGlue_Py/data/grover_e3.csv` | in-repo |
| 7 | GROVER warhead embeddings csv | **committed to git** (58 MB) | `SynGlue_Py/data/grover_warhead.csv` | in-repo |
| 8 | SE3-PROTACs repo + pretrained weights | https://github.com/drugparadigm/SE3-protacs (git clone) | `data/protac_repos/repos/SE3-protacs/` | upstream `SE(3)-PROTACs.pt`; clone via bootstrap |
| 9 | Chemprop trained degradation models | **committed to git** (≈1.3 MB each) | `outputs/benchmark/chemprop_multitarget/`, `outputs/benchmark/chemprop_cal_ensemble_seed{0,1,2}/` | trained on PROTAC-DB 3.0 (train/benchmark-excluded splits); in-repo |
| 10 | PROTAC-DB 3.0 dataset | **committed to git** (6 MB xlsx) | `data/benchmark/PROTAC-DB_3.0_protacs.xlsx` | PROTAC-DB 3.0 (15,502 PROTACs); in-repo |
| 11 | E3 expression evidence | builtin curated table in `synglue_agent/tools/e3_context_engine.py` (CSV optional) | `data/benchmark/e3_expression_evidence.csv` (optional) | literature/CCLE-derived; engine falls back to builtin |
| 12 | Conda environments (.venvs, envs) | NOT downloadable — created from specs | `.venvs/*`, `data/synthesis_prediction/envs/*` | `conda env create -f data/protac_repos/env_specs/<name>__environment.yml` per env (see INSTALL_STATUS.md) |
| 13 | SynGlue large trie dumps (Lean_MagnetDB_Trie.pkl, Clean_Metadata_Hash.pkl) | NOT hosted — generated artifacts (upstream has only builder scripts) | `SynGlue_Py/data_copy/` | re-generate via the upstream builder: https://github.com/the-ahuja-lab/SynGlue/blob/main/Architecture_Code/03_TRIE_Index_build_trie.py (not present in the local SynGlue_Py subset — use the upstream file); used by SynGlue training notebooks only — NOT needed by synglue_agent runtime |
| 14 | (superseded by #3b) | — | — | — |

## Checksum policy

- Files that are **in git** are integrity-protected by git itself (see `git log
  --format=%H -- <path>`).
- Downloadable files (#1–3, #8): `bootstrap_assets.sh` computes SHA-256 on
  first download and records it in `ASSET_MANIFEST.checksums.json` (committed
  after first full run so future clones verify against it).
- Because the v0.3 history-hygiene purge removed the original local copies,
  checksums for #1–3 are computed at first bootstrap (sources are the official
  figshare mirrors; sizes verified 42.6 / 286.2 / 632.5 MB).

## Degradation behavior when assets are missing

| Asset missing | Effect |
|---|---|
| aizynth (#1–3) | `aizynth_route_search` returns `tool_failed: aizynth_policy_missing`; pipeline uses RAscore/SAScore proxy — documented, tested |
| SE3-protacs (#8) | ternary stage uses geometric proxy + P4ward only |
| grover_fixed.pt (#5) | SynGlue degradation falls back to chemprop → synglue-heuristic chain (labelled) |
| E3 csv (#11) | builtin curated table used |
