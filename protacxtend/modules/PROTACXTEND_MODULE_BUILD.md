# PROTACXtend sequential module build — tracker

Layout (the `protacxtend` distribution's code package is `protacxtend`, so the
requested `protacxtend/modules/<name>/` layout maps to
`protacxtend/modules/<name>/` with separated `configs/ docs/ tests/ examples/`):

```
protacxtend/modules/<module_name>/
    config.py, core.py, schemas.py, __init__.py
    configs/<module>.json
    docs/{README,ARCHITECTURE,USAGE,VALIDATION,LIMITATIONS,REFERENCES}.md
    tests/test_<module>.py
    examples/...
agent tool (LangGraph): protacxtend/tools/<module>_tool.py  (JSON in/out, graph-safe)
```

Every module follows the 8-step workflow: literature → specification →
data pipeline (no fabricated labels) → scientific baseline → advanced model
only if it beats the baseline → validation (unit/sanity/benchmark/uncertainty/
edge cases) → agent integration → documentation + status report. Modules are
built strictly sequentially; each must pass tests, produce a demo output,
document limitations and be agent-connected before the next starts.

## Build order & status

| # | Module | Entry point | Status |
|---|---|---|---|
| 1 | Hook Effect Modeler (three-body equilibrium/QSP, hook onset & severity) | `simulate_hook_effect()` | ✅ DONE (QA passed 2026-09-02) |
| 2 | Lysine Ubiquitination Feasibility Scorer | `score_lysine_ubiquitination()` | ✅ DONE v1.0.0 (2026-09-02; static-geometry baseline, synthetic-fixture validation, real-PDB benchmark pending) |
| 3 | Cooperativity α Predictor | `predict_cooperativity()` | ✅ DONE v1.0.0 (2026-09-02) — data-audit-honest: surrogate mode until curated experimental α dataset exists; benchmark harness ready (constant/ridge/RF/XGB/GP, grouped splits) |
| 4 | PROTAC Degradation ML (pDC50 + Dmax/OOD; honest disabled prob task) | `predict_degradation()` | ✅ DONE v1.0.0 (2026-09-02) — curated 64/32 published labels; grouped splits (random/scaffold/unseen-target/E3/PROTAC); prob task disabled (no measured binary labels); audit approved 2026-09-02 (9/9 tests) |
| 5 | Cell-Context / Proteotype Selectivity (DepMap/CCLE features) | `predict_cell_context()` | ✅ DONE v1.0.0 (2026-09-02) — curated PROTAC-Degradation-DB (1913 rows; DC50 1181/Dmax 761; DepMap 24Q4 transcriptomics on 1512 rows); grouped A–G; leg D beats leg B on unseen-PROTAC pDC50 (R² 0.605 vs 0.513) → cell-context-aware; transcriptomic unseen-line transfer NOT claimed; proteotype NOT claimed (no proteomics); artifact + tool + 16 tests; **status report gated — Module 6 not started until audited** |
| 6 | Novel E3 Ligase Opportunity Engine | `rank_e3_ligases()`, `evaluate_e3_ligandability()` | ✅ DONE v1.0.0 (2026-09-02) — 30-gene catalog x 8 evidence axes; ranked verdicts (SUPPORTED needs direct precedent; expression-only never recommended); grouped retrospective benchmark (RF AUROC .98 easy→.93 unseen-E3; recruiter ablation −.52); 17 tests + tool run_e3_opportunity; **status report gated — Module 7 not started until audited** |
| 7 | Active Learning / Experiment Selection (multiobjective BO + feedback) | `select_next_experiments()`, `update_models()` | pending |

Target pipeline: ternary geometry → lysine feasibility → cooperativity → hook
effect → degradation prediction → cell context → candidate ranking → active
learning → experimental feedback.

## Module 1 — status summary

- **Completed**: mechanistic three-body equilibrium solver (log10-space bounded
  least-squares, relative mass-balance residuals), dose-sweep metrics (peak /
  max occupancy / hook onset / severity / window), seeded Monte-Carlo
  uncertainty, typed schemas + config + version metadata.
- **Files added**: `protacxtend/modules/hook_effect_modeler/` (core, schemas,
  config, __init__, configs JSON, examples, docs ×6), tests (13), agent tool
  `tools/hook_effect_modeler_tool.py` + `tool_spec()`.
- **Data used**: none external (validated equations); parameters are typed
  inputs. References: Douglass 2013 JACS; Gadd 2017; Hughes & Ciulli 2017;
  Riching 2018 (docs/REFERENCES.md).
- **Validation**: 13/13 tests pass (~18 s): mass balance, zero-dose exactness,
  interior-peak/hook behaviour, α scaling, E3-limiting severity, MC
  reproducibility & bounds, schema/metadata, input rejection.
- **Demo**: alpha=30, T=E=100 nM, Kds 50 nM → peak 153 nM PROTAC, occupancy
  0.773, hook onset 3132 nM, severity 0.747 (severe); MC peak p5–p95
  73.9–79.9 nM.
- **Remaining limitations**: equilibrium only (no kinetics/DC50 — Module 4),
  parameters must come from experiment/upstream modules, single-cell global
  concentrations, MC assumes user-supplied lognormal σ (see docs/LIMITATIONS.md).
- **Next module**: Lysine Ubiquitination Feasibility Scorer
  (`score_lysine_ubiquitination()`).

## Module 4 — audit & approval (2026-09-02)

Independent audit of the Module 4 status report before Module 5 may start
(sequential audit rule). Verdict: **APPROVED** after two fixes.

Verified: curated dataset provenance (`outputs/benchmark/benchmark_predictions.csv`,
64 published DC50 rows / 32 Dmax, E3 CRBN+VHL, dc50 0.019–16840 nM); honest
labels (prob labels == 0, no fabrication); leakage-safe grouped evaluation
(train-only entity encoding); reproducible grouped metrics (random-split
negative R²; scaffold ridge R²=0.41/MAE=0.73); demo row numbers
(pDC50≈5.13, DC50≈7.4 µM vs pub 16.8 µM, interval≈2.90–18.65 µM, OOD≈24.9,
flag False); agent tool + docs + artifact present; lint clean.

Fixes applied during audit: (1) `predict_degradation` silently dropped the
caller-provided target/E3 (inference always used the OOV entity code) — now
forwarded so a seen entity uses its training-fold code and absent/unknown maps
to OOV; regression test added. (2) In-sample RF R²≈0.98 corrected to actual
≈0.95 (train-fit-only, already labelled honest). Tests now 9/9; Modules 1–4 +
research layer green (91 passed).
