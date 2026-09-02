# Module 5 — Cell-Context / Proteotype-Aware Degradation Model

**Entry point:** `predict_cell_context(protac, poi, e3, cell_line)`
(dict output; pydantic `CellContextInput` schema; LangGraph tool
`run_cell_context_predictor`).

## What it does
Predicts degradation conditional on **PROTAC + POI + E3 + cell line** from a
data-rich supervised dataset (PROTAC-Degradation-DB, arXiv 2406.02637) with
DepMap 24Q4 transcriptomics as cell-state descriptors:

- `predicted_pDC50` / `predicted_DC50_nM` (regression on 1,181 measured DC50)
- `predicted_Dmax_pct` (regression on 761 measured Dmax)
- `degradation_probability` — **threshold-derived** activity view
  (`pDC50>=6.0 AND Dmax>=60`, the paper's documented rule); never described as
  an experimental probability.
- uncertainty (RF ensemble spread + residual interval), per-axis OOD flags
  (molecular / scaffold / target / E3 / cell line), applicability and claim
  gating.

## Data pipeline (reproducible)
`python -m synglue_agent.modules.cell_context_selector.dataset` writes
`data/cell_context_records.csv` + `provenance_manifest.json`:

| Stage | n |
|---|---|
| Source rows (PROTAC-Degradation-DB) | 2,141 |
| Viability-only assay records excluded (Comments flag) | −62 |
| Exact duplicate rows (same smiles/target/E3/cell/DOI) dropped | −166 |
| **Curated rows** | **1,913** |
| Measured DC50 / Dmax / both | 1,181 / 761 / 479 |
| Derived-active label defined (documented AND rule) | 775 (True 394) |
| Cell lines / targets / E3 ligases / DOIs | 180 / 121 / 8 / 231 |

QA vs the shipped `Active` column is recorded in the manifest (700/857 agree) —
the shipped column is **not** used as a label source; ours is recomputed from
the documented rule. DC50 is asserted nM before pDC50 conversion; no DC50/Dmax
value is ever fabricated.

## Cell-line normalisation + DepMap mapping
`cellline.py` maps the 180 dataset cell-line names onto DepMap 24Q4 `Model.csv`
identifiers (exact normalised match → alias → fuzzy): 137 mapped (130 with
expression), 2 ambiguous, 41 unmapped (7 of which are qualitative assay
descriptions, not cell lines). Coverage report in `prepare.enrich` output and
VALIDATION.md. **Proteomics coverage: 0** — DepMap 24Q4 has no
quantitative-proteomics matrix; the module never claims proteotype-awareness.

## Cell-context features (all descriptors, never labels)
DepMap 24Q4 TPM-log1p for a curated panel (E3/CRL machinery, E2s,
proteasome, DUB/ubiquitin, drug transporters — see `omics.PANEL_GENES`) plus
every POI gene present in the dataset + lineage one-hot + row POI expression.
**Mechanistic Modules 1–3 features are not usable at dataset scale** (only 22
rows reference a ternary PDB structure; Module 1 needs measured Kd
parameters) — reported as a census in LIMITATIONS.md, never included as
if-measured inputs.

## Models & validation
Order: global mean → cell-line mean → ridge → elastic net → RandomForest →
ExtraTrees → XGBoost (regression); RF/logistic for the derived-activity view.
Grouped splits with **train-only encoder/preprocessor fitting**: random,
unseen-PROTAC, scaffold, unseen-target, unseen-E3, unseen-cell-line,
unseen-PROTAC+cell. Endpoint masks: rows missing DC50 or Dmax contribute only
to the task they label. Metrics: R²/MAE/RMSE/Spearman/Pearson (+n);
AUROC/AUPRC for the derived task. Results and ablation in VALIDATION.md.

## Run
```
python -m synglue_agent.modules.cell_context_selector.examples.train_demo \
    [--quick]
```
trains the production artifact (`models/cell_context_model.joblib`) and prints
the benchmark + claims + a demo prediction. Tests:
`pytest synglue_agent/modules/cell_context_selector/tests/`.
