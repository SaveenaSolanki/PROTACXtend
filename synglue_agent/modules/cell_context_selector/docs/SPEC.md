# Module 5 — Cell-Context / Proteotype Selectivity: specification + data audit

Status: **SPEC PHASE — awaiting approval before implementation** (sequential
audit rule, same gate as Modules 1–4). Entry point per tracker:
`predict_cell_context()`.

---

## 1. Task statement

A PROTAC's degradation potency is cell-context dependent: the E3 machinery,
target abundance, and degradation capacity vary across cell lines/patients.
Module 5 predicts **per-cell-line degradation outcome** for a query PROTAC:

- given: PROTAC SMILES (+ optional target/E3) **and** a cell line (identity /
  expression context),
- return: expected degradation in that cell line — DC50/Dmax where trainable,
  a documented threshold-derived activity view, cell-context applicability /
  expression caveats,
- and a **selectivity view**: predicted outcome contrast across the supported
  cell-line panel (proteotype selectivity), never an absolute clinical claim.

Position in pipeline: after Module 4 degradation ML (potency from PROTAC alone)
and before candidate ranking / active learning. Reuses Module 4's RDKit
featurizer + grouped-evaluation pattern.

## 2. Literature / context audit (step 1, done — pointers)

- PROTAC-Degradation-Predictor — “Predicting PROTAC degradation activity with
  machine learning” (arXiv 2406.02637). Ships the largest machine-readable
  PROTAC degradation database we found, **with a per-row Cell Type**.
- DepMap / CCLE provide cell-line expression context (E3 ligase and POI
  transcript/protein levels) used to *explain* context effects; DepMap/CCLE
  provide descriptors (features), never labels.
- Published context biology to encode as priors: CRBN-high haematological lines
  (e.g., MM1.S) ↔ IMiD/lenalidomide-type degraders; VHL vs CRBN availability;
  target dependence.

## 3. Data audit (step 2 — done, honest numbers)

Source file (already verified in this project’s cloned-repo set, used for the
G6 reproduction):
`data/protac_repos/repos/PROTAC-Degradation-Predictor/data/PROTAC-Degradation-DB.csv`.

| Audit item | Result |
|---|---|
| Total rows | 2,141 |
| Cell lines | 180 (K562 140, HeLa 102, MCF-7 97, …) |
| Targets / E3s | 121 parsed / 8 canonical E3s (CRBN, VHL, MDM2, FEM1B, RNF114, UBR1, IAP, XIAP) |
| Source DOIs | 231 |
| Viability/cytotox-only rows (Comments flag, strict assay-level rule) | 62 → excluded (the earlier “154” was a broad IC50-mention scan; 92 of those carry real degradation endpoints + ligand-IC50 notes and are kept) |
| Rows after viability exclusion | 2,079 |
| Exact-duplicate rows (same smiles/target/E3/cell/DOI) | 166 → dropped |
| **Curated rows** | **1,913** |
| Measured DC50 (>0 nM) | 1,181 rows |
| Measured Dmax | 761 rows |
| Measured DC50 AND Dmax | 479 rows (pre-dedup: 522) |
| Binary “Active” column | **threshold-derived, NOT independently measured**: `Active = (pDC50 ≥ 6.0 → DC50 ≤ 1 µM) AND (Dmax ≥ 60 %)`, per the paper’s `is_active()` AND rule; recomputed in-module. QA vs shipped column: 700/857 agree → shipped column never used |
| Derived-active rows (rule decides) | 775 (True 394 / False 381) |
| Cell-line mapping (DepMap 24Q4) | 137 mapped / 2 ambiguous / 41 unmapped (7 qualitative descriptions); 1,512 of 1,913 rows have transcriptomic context; proteomics: none in DepMap 24Q4 |
| Provenance of shipped file | Research clone; DOI-cited rows from PROTAC-DB + PROTAC-Pedia entries compiled by the paper pipeline |

**Honesty decisions carried into the build**
1. No label is invented. Measured DC50/Dmax come from the cited papers.
2. The binary activity view is documented **as threshold-derived** with the
   exact rule above (same convention the paper publishes); it is *not* called
   “measured degradation probability” — this also keeps Module 4’s statement
   (no independent measured binary outcomes in its curated set) consistent.
3. Viability-only rows never enter degradation labels.
4. Exact duplicates (same smiles/target/E3/cell/DOI) are dropped; distinct
   measurements of the same series from *different DOIs* are kept as separate
   rows (optional geometric-mean merge available via
   `build_curated(merge_same_series=True)`, provenance aggregated).
5. Cell-line imbalance and target/E3 concentration are reported per split, not
   hidden; grouped folds never share a compound across train/test.

## 4. Feature plan

- **Molecular** (reuse Module 4 `features.py`): 8 RDKit descriptors + ECFP4
  (1024) of the full PROTAC — deterministic.
- **Cell-context descriptor** (features only, never labels):
  - v1: curated E3/POI expression priors already in-repo
    (`data/benchmark/e3_expression_evidence.csv`, `expression_context.csv`) +
    cell-line entity code (train-fold-fitted, OOV-safe — Module 4 pattern);
  - v1.1 (pending, not blocking): static cell-line representation from the
    paper artifact (`cell2embedding.pkl`, provenance to be documented) or a
    DepMap/CCLE expression vector the user must supply (large/download-gated,
    licensing note) — never bundled silently.
- **No leakage**: cell descriptors are fit/mapped on train folds only; labels
  are per-row measured values from the DB.

## 5. Models & evaluation (steps 4–6, planned order)

Scientific baseline order (no DL jump): mean → ridge → RandomForest → XGBoost;
GP reserved. Targets:
- `log10 DC50` per (compound, cell line) — core regression (522 clean rows;
  larger DC50-only set 1,342 for a pDC50 regressor with missing-Dmax rows
  excluded from Dmax tasks);
- Dmax regression (809 rows);
- threshold-derived binary activity (documented rule) as a secondary
  classification view with its own honest metrics.

Grouped split regimes: random / unseen-PROTAC (compound) / unseen-target /
unseen-E3 / **unseen-cell-line** (the true context-generalisation question).
Metrics: R²/MAE/RMSE/Spearman (regression); AUROC/AUPR/accuracy (binary);
per-cell-line coverage report. Uncertainty: conformal-style residual intervals
+ descriptor-distance OOD (Module 4 pattern). Selectivity view = prediction
contrast across supported panel with applicability flags; no multi-cell-line
row → explicit “context-naive” note.

## 6. Deliverables (after approval)

- Module dir `synglue_agent/modules/cell_context_selector/` with `dataset.py`
  (curated subset copy + provenance manifest), `features.py` (reuse +
  cell-context), `models.py`, `predict.py` (`predict_cell_context()`),
  `schemas.py`, `__init__.py`; docs (README/ARCHITECTURE/VALIDATION/
  LIMITATIONS/REFERENCES); tests; `examples/`.
- Agent tool `tools/cell_context_tool.py` (`run_cell_context_predictor`,
  LangGraph-safe, JSON in/out).
- Tracker + CHANGELOG update; honest status report for Module 6 gate.

## 7. Known limitations (to be stated in the module)

Small clean core (522 with both labels); cell-line imbalance; derived binary
label definition is assay/potency-threshold dependent; no patient/PDX context;
DepMap/CCLE integration is user-supplied or v1.1 pending; inter-lab DC50
heterogeneity across 98 DOIs.

## 8. Decision gate

Proceed to build Module 5 (`predict_cell_context()`) on this specification
(curated subset of PROTAC-Degradation-DB + in-repo expression priors), with
labels kept measured-or-documented-derived and grouped unseen-cell-line
evaluation, per Sections 3–5?
