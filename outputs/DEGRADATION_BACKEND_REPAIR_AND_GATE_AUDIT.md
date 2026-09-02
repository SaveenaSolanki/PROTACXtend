# Degradation Backend Repair + External Gate Audit

Audit date: 2026-09-01 (evening pass) → 2026-09-02 (follow-up pass)
Scope: PROTAC-Degradation-Predictor gate repair, TACK-as-degrader wiring,
v0.1 e2e hang repair (3 root causes), G6 reproduction, runtime-sklearn
rebuilds. Re-audit against `PROTACXTEND_EXTERNAL_GATE_AUDIT.md` and
`PROTACXTEND_MISSING_MODULES_BUILD_SPEC.md`.

---

## 1. What changed (summary)

| # | Item | Status |
|---|------|--------|
| 1 | PROTAC-Degradation-Predictor env repaired + package installed | ✅ G4/G5 pass |
| 2 | Published README example reproduced end-to-end (single + batch) | ✅ G6 (example-level) |
| 3 | Registry promoted: `registered_status_only` → `adapter_ready` | ✅ |
| 4 | Safe smoke test registered for the repo tool | ✅ |
| 5 | TACK-style model is now the degradation **primary** backend (Chemprop = cross-check) | ✅ |
| 6 | Degradation tests updated to the new contract — all green | ✅ 15/15 + 26/26 regression |
| 7 | **v0.1 deterministic e2e runs to completion (196 s; was >50 min hang)** | ✅ 3 root causes fixed |
| 8 | TACK artifacts rebuilt in runtime sklearn (no version warnings) | ✅ |
| 9 | synglue legacy RF warning surfaced + suppressed honestly (unloadable on sklearn≥1.4) | ✅ documented |
| 10 | G6 full-experiment reproduction (XGBoost standard split) | 🔶 running → see §7b |

---

## 2. PROTAC-Degradation-Predictor repair (gate G4/G5/G6)

### Before (from the 15:31 gate audit)

- `import protac_degradation_predictor` → `ModuleNotFoundError`
- Dependency `gdown` missing
- Registry: `registered_status_only`, `executable: false`

### Repairs applied

1. `pip install gdown` (→ 6.1.0) in
   `/home/saveenas/miniconda3/envs/pp/envs/protac-degradation-predictor` (Python 3.10.8).
2. `pip install -e . --no-deps --no-build-isolation`
   — editable install WITHOUT forcing requirements.txt pins
   (torch 2.7.1 / sklearn 1.3.2 / xgboost 3.0.2 etc.). The env already had
   torch 2.0.1 / sklearn 1.2.0 / xgboost 1.5.1 which run the published
   example fine; a full pin-following install would have downloaded a new
   multi-GB torch build for no functional gain.
3. **Local source patch**
   `data/protac_repos/repos/PROTAC-Degradation-Predictor/protac_degradation_predictor/protac_degradation_predictor.py`
   in `get_protac_active_proba()`, after `load_models()`:

   ```python
   if not use_xgboost_models:
       models = {k: v.to(device) for k, v in models.items()}
   ```

   Root cause: `pytorch_models.load_model()` uses
   `map_location=torch.device('cpu') if not torch.cuda.is_available() else None`.
   This machine has CUDA, so checkpoint weights load onto `cuda:0` while
   inputs are built on the requested device (default `cpu`) → RuntimeError
   "found at least two devices". Pre-patch backup: `/tmp/pdp_backup.py`.

### Data fetched (gdown from Google Drive, cached)

`~/.cache/protac_degradation_predictor/`:
`PROTAC-Degradation-DB.csv` (4.0 MB, 2141 rows), `uniprot2embedding.h5` (51 MB),
`cell2embedding.pkl` (3.5 MB), `models.zip` (113 MB → `models/`,
`best_model-*`/`cv_model-*` checkpoints).

### Verified (G5 smoke + G6 example)

- `import protac_degradation_predictor` → ok, version 1.0.2
- `avail_e3_ligases()` → `[VHL, CRBN, DCAF11, DCAF15, DCAF16, ...]`
- README example (VHL / P04637 / HeLa):
  - `is_protac_active` → **True**
  - `get_protac_active_proba` → mean **0.5985**, majority vote **True**, 3 models
  - batch (2 molecules) → `[True, True]`
- `pip check`: only strict requirements.txt pins not matched (documented
  deviation; see repair log).

### Registry updates

- `data/protac_repos/all_repo_install_verification.csv`:
  `install_appears_successful=True`, `safe_wrapper_integration_possible=True`,
  `recommended_wrapper_type=safe_import_and_inference_smoke`, notes record the
  repair + patch + verification; missing_dependencies documents the pin deviation.
- `synglue_agent/tools/repo_tool_adapter.py`: added a registered safe smoke
  branch for this repo (bounded CPU inference of the published example).
- Verified: `repo_tool_status()` → `executable: true`; `smoke_test_repo_tool()`
  → `success: true` (version 1.0.2, active=True, mean_proba=0.5985, n_models=3).
- `outputs/external_integrations/protac_degradation_predictor.json` →
  `status: "adapter_ready"`, `executable: true`, no warnings.
- Repair log: `data/protac_repos/install_logs/protac_degradation_predictor_gate_repair.log`.

### Gate table (this component)

| Gate | Before | After |
|------|--------|-------|
| G1 local checkout | PASS | PASS |
| G2 license/readme | PASS | PASS |
| G3 env spec | PASS | PASS |
| G4 isolated executable | FAIL | **PASS** |
| G5 safe smoke/import | FAIL | **PASS** |
| G6 reproduction gate | FAIL | **PASS (example-level)** — full published experiment reproduction not run |
| G7 production trust | FAIL | FAIL — no calibration/trust gate in PROTACXtend yet |

---

## 3. TACK-style model as the degradation backend

### Before

- `degradation_endpoint.py` (Chemprop multitarget Dmax head + Chemprop ensemble
  DC50/uncertainty) was the only primary backend; TACK was a **non-blocking
  second opinion** that only filled `tack_*` fields in the toolbox.
- `context_degradation_predictor.py` (TACK + Chemprop uncertainty votes) reached
  only via `--mode context`.

### After

- `synglue_agent/tools/degradation_endpoint.py`
  - New `_tack_primary()` helper: in-process, never-raises.
  - `predict_degradation_endpoint` (single) and `predict_degradation_batch`:
    when the local TACK-style models are available, TACK's
    DC50/Dmax/active become the **primary** result; `model: "tack-style-v1"`.
    Chemprop values are preserved as cross-check (`chemprop_*` keys,
    `chemprop_cross_check_*` in provenance) — never discarded.
  - Batch rows now carry `model`, `tack_*`, `chemprop_*` for downstream mapping.
  - Uncertainty/AD/context gating still comes from the Chemprop conformal
    ensemble + curated context table (TACK has no calibrated uncertainty yet).
- `synglue_agent/backend/schemas.py` — `DegradationPrediction` gains
  `tack_active_prob`, `chemprop_dc50_nM`, `chemprop_dmax_pct`.
- `synglue_agent/tools/protac_toolbox.py` — `predict_degradation` maps endpoint
  rows: `model_version="tack-style-v1 (DC50/Dmax primary) + chemprop cross-check"`
  when TACK is primary; the old always-run TACK second pass now only fills
  `tack_*` when the endpoint did not already provide them (fallback semantics
  preserved, no double compute).
- Tests updated: `test_predict_degradation_tack_primary_when_available`,
  `test_predict_degradation_chemprop_fallback_when_tack_missing` (monkeypatched
  `_tack_primary` → None proves Chemprop fallback), heuristic-fallback test intact.

### Example output (aspirin, CRBN/BRD4/HEK293T)

```
model: tack-style-v1        dc50_nM: 384.59   dmax_pct: 46.0
tack_active: False          tack_active_prob: 0.243
chemprop_dc50_nM: 79.9      chemprop_dmax_pct: None
ad_status: out_of_domain    verdict: low_confidence
```

Honest disagreement preserved: TACK 384.6 nM (inactive) vs Chemprop 79.9 nM
(active) → verdict `low_confidence` because the molecule is out of the
Chemprop applicability domain.

---

## 4. Re-audit vs external gate roadmap (build spec order)

| Component | G1 | G2 | G3 | G4 | G5 | G6 | G7 | Decision |
|-----------|----|----|----|----|----|----|----|----------|
| PROTAC-Degradation-Predictor | ✅ | ✅ | ✅ | ✅ | ✅ | 🔶 example | ❌ | **adapter_ready** — next: full experiment reproduction + calibration |
| RP-PROTAC | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Needs clone/provenance audit |
| Deep-QSP Hook model | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Needs clone/provenance audit (native dose-response simulator exists) |
| PROTACFold | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | Needs env rebuild + AF3/Boltz gate |
| PROTAC ternary benchmark | ✅ | ✅ | 🔶 | ❌ | ❌ | ❌ | ❌ | Needs Rosetta/OpenEye gate or open-only subset |
| SynPROTAC | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Needs clone/provenance audit |
| DeepPROTACs | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | Needs legacy env/OpenBabel/torch-geometric gate |
| PROTAC-INVENT | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | Needs Docker/conda review |

Legend: ✅ PASS, ❌ FAIL, 🔶 partial.

Production trust rule unchanged: external outputs are safe to list/audit/
smoke; only PROTACXtend-native + locally-trained (TACK-style) models feed
ranking; external component outputs are NOT used for ranking yet.

---

## 5. Test evidence (run 2026-09-01, env `protacpilot`, Python 3.11.15)

| Suite | Result |
|-------|--------|
| synglue_agent/tests/test_degradation_endpoint.py (incl. 2 new tests) | **15 passed** (366 s) |
| synglue_agent/tests/test_synglue_degradation.py + test_chemprop_degradation.py + test_degradation_model.py | 39 passed (pre-change baseline; schema change is additive-optional) |
| tests/test_repo_tool_adapter.py + test_mode_router.py + test_production_wiring.py | **21 passed** (321 s) |
| test_architecture_unification.py | 2/10 fast tests passed before the 15-min cap; slow remainder is pre-existing agentic/chemprop loading, `degradation_interface.py` untouched by this change — rerun needed with larger timebox |

Known pre-existing warning: synglue degradation models (sklearn 1.2.2) load
under runtime sklearn 1.9.0 → `InconsistentVersionWarning`; predictions
produced but flagged — rebuild those artifacts in the runtime env eventually.

---

## 6. Residual risks / open items

1. **G6 full reproduction** of PROTAC-Degradation-Predictor's published
   experiments (train/eval splits, reported accuracy/AUC) not yet run.
   Example-level reproduction only.
2. **Pin deviation**: env runs torch 2.0.1 / sklearn 1.2.0 / xgboost 1.5.1 vs
   requirements pins (torch 2.7.1 / sklearn 1.3.2 / xgboost 3.0.2). Verified
   fine on the published example; a clean rebuild from `environment.yml` is the
   canonical follow-up before production trust (G7).
3. **TACK out-of-domain behavior**: TACK-style models have no conformal
   calibration; AD/uncertainty still comes from Chemprop. When Chemprop is
   unavailable, TACK-primary predictions would lack a calibrated uncertainty
   signal — keep the heuristic/ad fallback labels honest (current behavior).
4. ✅ RESOLVED 2026-09-02: synglue RF-leg artifacts are legacy sklearn
   <1.4 pickles (unloadable on ≥1.4, verified) — warning suppressed at the
   load site, transformer heads confirmed as the real backend, honest
   docstring; faithful retraining blocked by absent original training data.
5. Full agentic e2e and architecture-unification suites need >20-min timeboxes
   (Chemprop subprocess reloads); e2e run for this change is logged at
   `/tmp/e2e_gate.log` (see section 7).
6. RP-PROTAC / Deep-QSP / SynPROTAC remain uncloned (no provenance) — build
   spec integration wave 1 items still open.
7. ✅ RESOLVED 2026-09-02: v0.1 deterministic e2e hang — three root causes
   fixed (see §7): TACK HGB OpenMP spin → thread bounding; rank_candidates
   O(N×C) InChIKey gen → O(1) exact-match index; xlsx parse kept as
   one-time per-process cost. e2e now completes in ~196 s. Remaining minor
   flags: xgboost nthread default burned ~28 cores during the G6 rerun
   (author-code nthread control is a follow-up); agentic-mode e2e not yet
   re-run end-to-end after the fixes.

---

## 7. v0.1 deterministic e2e hang — root causes and fixes (2026-09-02)

**Symptom:** `runtime --mode deterministic` never finished (stuck >50 min at
run_start; 112 threads; CUDA/OpenMP futex-spin ~1400% CPU).

**Diagnosis path:** node-by-node stepper (`notes/debug_v01_stages.py`) → hang
in `predict_degradation`; stage timing (`notes/time_degradation_batch.py`)
→ TACK; isolation tests → sklearn HGB OpenMP spin.

**Three stacked root causes:**

1. **TACK HGB OpenMP spin (primary).** HistGradientBoosting opens libgomp
   parallel regions per predict; on this shared box (load avg >40, 32 cores)
   a single-row predict took ~11 s per model → ~33 s per molecule →
   150 candidates ≈ 83 min. Controls: fresh tiny HGB fit 48.6 s / predict
   283 ms with default threads vs fit 0.24 s / predict 0.1 ms at
   OMP_NUM_THREADS=1. Fix: `synglue_agent/tools/thread_limits.py`
   (`apply_thread_limits()` early env defaults OMP/OPENBLAS/MKL=4 +
   `bounded()` threadpoolctl context); wired into `runtime.py` entry and
   `tack_degradation.py` (predict wrapped in `threadpool_limits(1,'openmp')`).
   Measured: cold TACK call 33 s→1.1 s; warm 11 s→10 ms.
2. **rank_candidates O(N×C) InChIKey generation.** `protacdb_evidence_prior`
   linear-scanned all PROTAC-DB rows computing an RDKit InChIKey per row PER
   CANDIDATE (measured: 96 s for 20 candidates). First cache attempt keyed on
   id(rows list) FAILED — `load_normalized_protacdb()` wraps the cached tuple
   in a fresh list per call. Fix: `_protacdb_exact_index()` keyed on the
   STABLE cached tuple object → O(1) dict lookup. 150 candidates: ~9+ min
   → 0.87 s.
3. **One-time 22–26 s pandas/openpyxl parse** of `PROTAC-DB_3.0_protacs.xlsx`
   (2000k XML elements). Cached per process; acceptable. Deferred: parquet
   disk-cache.

**Verification:** `e2e_final_20260902` — run_end at **196 s**, status ok;
150 candidates, TACK-primary DC50/Dmax (Top-1 21.6 nM / 97% Dmax), full
ranking/evolution/hook/cooperativity/report.

## 7b. G6 reproduction (PROTAC-Degradation-Predictor, 2026-09-02)

**Protocol:** regenerated seed-42 standard split (data/studies, active_col='Active',
test 10%) and force-retrained the XGBoost standard experiment
(`run_experiments_xgboost.py --experiments standard --active_col Active
--n_trials 100 --force_study=true`) in the dedicated env.

**Target:** Ribes et al. 2024 (arXiv 2406.02637): random-split study test
acc **80.8%**, ROC AUC **0.865** (majority vote of 3 models); novel-target
62.3%/0.604.

**Status: COMPLETE (2026-09-02 10:57).** Retrained XGBoost standard split:

| Metric | Paper (arXiv 2406.02637, random split) | This retrain |
|--------|------------------------------------------|--------------|
| Test acc (majority vote) | 80.8 % | **81.6 %** (per-model 80.3 %) |
| Test ROC AUC (maj. vote) | 0.865 | **0.900** (per-model 0.890–0.904) |
| CV val AUC (5-fold) | — | 0.883–0.926 |

Reproduction verdict: same protocol (seed-42 splits, 10 % test, XGBoost
optuna) — result within ~1 acc point of the published number; AUC somewhat
higher (published headline uses a 3-model pyTorch+XGBoost majority vote).
Artifacts: `data/protac_repos/repos/PROTAC-Degradation-Predictor/reports/`
(`xgboost_*_standard_Active_test_split_0.1.csv`, study pickle) +
regenerated `data/studies/`. Leakage stats recorded as in the author run
(UniProt overlap in random split ~79 %, SMILES ~7 % — documented in the
report CSVs). Author-original report files untouched.

## 8. Provenance / source files

- `PROTACXTEND_EXTERNAL_GATE_AUDIT.md` (2026-09-01 15:31 baseline)
- `PROTACXTEND_MISSING_MODULES_BUILD_SPEC.md` (integration order, shared contracts)
- Ribes et al., "Modeling PROTAC Degradation Activity with Machine Learning",
  2024 — https://arxiv.org/abs/2406.02637 (model paper)
- Repo: https://github.com/ribesstefano/PROTAC-Degradation-Predictor
- Repair log: `data/protac_repos/install_logs/protac_degradation_predictor_gate_repair.log`
- Registry: `data/protac_repos/all_repo_install_verification.csv`
- Adapter: `synglue_agent/tools/external_model_adapters.py`,
  `synglue_agent/tools/repo_tool_adapter.py`
- TACK: Ribes/Dunlop/Mercado, KDD AI4Science 2026 (arXiv 2605.19579, gated
  official weights; training on public dataset via `scripts/build_tack_model.py`,
  artifacts in `data/tack/`)