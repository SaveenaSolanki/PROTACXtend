# PROTACXtend Changelog

## 2026-09-02 (module 6) — Novel E3 Ligase Opportunity Engine

rank_e3_ligases(poi, cell_line, tissue, disease, warhead, poi_structure,
top_k): 30-gene E3 catalog (families/modes/adaptors; CRL4/2/3, SCF, RING,
IAP, HECT, RBR, U-box, TRIM) x independent evidence axes — cell-context
expression (DepMap 24Q4 percentiles, Module 5 infra; E3+adaptor+POI),
subcellular compatibility (78 UniProt-reviewed annotations cached offline),
recruiter tractability (DOI-cited ligand library only; demo rows excluded),
biological precedent (curated measured PROTAC rows), structural availability
(ternary feasibility stays UNKNOWN without ternary data), surface-lysine
census (only with user-supplied POI structure; Module-2 SASA), selectivity
(lineage-expression restriction + curated paralog families), per-axis
uncertainty/OOD. Verdicts SUPPORTED/PROMISING/EXPLORATORY/INSUFFICIENT
EVIDENCE with hard rules: expression alone never recommends an E3 (benchmark:
expression-only AUROC 0.49 = chance); SUPPORTED requires direct measured
precedent for the POI; low-expression (<20th pct) caps at EXPLORATORY.
Retrospective benchmark (270 unique measured POI-cell-E3 pairs; negatives =
catalog E3s never used, absence-of-record documented): grouped regimes
random/unseen-target/pair/cell/E3/family-LOO; baselines expression-only /
recruiter-only / precedent-frequency / logistic / RF / XGBoost; RF best
(AUROC .98 random & unseen-target, .93 unseen-E3, .99 unseen-cell);
recruiter ablation −0.52 AUROC on unseen-E3; precedent transfers across cell
lines but not targets; structure/lysine axes reported as coverage census (no
POI structures in the retrospective set). Ablations and claims gated in
VALIDATION.md. Challenges 1–7 encoded as tests (same-POI cell contrast, VHL
vs CRBN, low-expression penalty, missing-context uncertainty, no-structure no
mechanistic claim, absent-recruiter explicit, unknown POI graceful) +
determinism; 17 tests. Agent tool run_e3_opportunity. Artifacts:
artifacts/benchmark_results.json; docs README/SPEC/VALIDATION/LIMITATIONS/
REFERENCES.


## 2026-09-02 (module 5) — Cell-Context / Proteotype-Aware Degradation Model

predict_cell_context(protac, poi, e3, cell_line). Data: PROTAC-Degradation-DB
(arXiv 2406.02637; verified research clone) curated reproducibly 2141 -> -62
viability-only -> 2079 -> -166 exact dups -> 1913 rows (180 cell lines, 121
targets, 8 E3s, 231 DOIs; measured DC50 1181 / Dmax 761 / both 479). Binary
activity labels recomputed from the paper's documented AND rule (pDC50>=6,
Dmax>=60) — threshold-derived, never called experimental; QA vs shipped
'Active' 700/857 agree (shipped column unused). DC50 asserted nM before pDC50;
no label fabricated; endpoint masks throughout. Cell lines mapped to DepMap
24Q4 Model.csv (137 mapped/2 ambiguous/41 unmapped incl. 7 qualitative
descriptions); transcriptomic features from DepMap 24Q4 TPM-log1p (142-gene
E3/E2/proteasome/DUB/transporter panel + POI genes) on 1512 rows; proteomics
coverage 0 (no DepMap 24Q4 proteomics). Modules 1-3 mechanistic features
structure/parameter-limited (22 rows reference a ternary PDB) -> reported as a
census, not used at scale. Baselines mean->cell-mean->ridge->elasticnet->RF->ET
->XGBoost (+RF/logistic classifier); grouped splits random/unseen-PROTAC/
scaffold/unseen-target/unseen-E3/unseen-cell-line/unseen-PROTAC+cell,
train-only preprocessing; R2/MAE/RMSE/Spearman/Pearson (+AUROC/AUPRC for the
derived task), n per split. Results: pDC50 leg D (transcriptomics) beats leg B
on unseen-PROTAC (RF R2 0.605 vs 0.513), scaffold (0.603) and random (best
family 0.685); Dmax similar (unseen-PROTAC 0.519 vs 0.476); derived-active
AUROC 0.894 (unseen-PROTAC leg D). Claims gated in the artifact:
cell_context_aware True; transcriptomics_generalises_to_unseen_lines False
(D<B on unseen-cell-line; identity codes never claimed as selectivity);
proteotype_aware False. Production artifact cell_context_model.joblib (all
endpoints leg D RF). M4-v1 artifact untouched; M4_FOLLOWUP memo recommends a
versioned M4-v2 retrain from the larger set after audit. Tests 16; module
suites + full run in status report.


## 2026-09-02 (module 4) — PROTAC Degradation ML Model

Curated real dataset from the project's PROTAC-DB benchmark extract (64 rows
with published DC50 -> pDC50 target; 32 with published Dmax; E3 CRBN/VHL).
Features: 8 RDKit descriptors + Morgan(ECFP4,1024) + train-only ordinal
target/E3 codes. Baselines in order mean -> ridge -> RF -> XGBoost (GP
reserved); grouped split evaluation random / scaffold(Murcko) / unseen-target /
unseen-E3 / unseen-PROTAC with leakage-safe entity encoding. Artifact stores
fitted estimator + conformal-style residual interval + training descriptors for
kNN OOD. predict_degradation() returns pDC50, DC50 nM, empirical interval, OOD
score/flag; Dmax None (sparse labels, separate artifact path) and degradation
probability None with the task reported disabled — no binary measured labels
exist and none are fabricated. Reported honestly: grouped test metrics are
modest (n small; e.g., random split negative R2), in-sample RF R2~0.95/MAE 0.21
is train-fit only. Audit fix (2026-09-02): predict_degradation now forwards
caller-provided target/E3 into feature_matrix so a seen entity is coded with its
training code (absent/unknown -> OOV sentinel) instead of being silently
dropped; regression test added. Tests 9 (dataset honesty incl. prob==0,
determinism, splits, train/predict roundtrip w/ interval+OOD, entity-context
forwarding, explicit missing-artifact error).
Tool run_degradation_predictor. Docs + tracker updated.


## 2026-09-02 (module 3) — Cooperativity (alpha) Predictor

Built in the required order (no DL jump). Exact alpha definition documented
(alpha = Kd2/Kd2(ternary), same assay; log target ln(alpha); classes >1 /
0.8-1.25 / <0.8). Data audit: shipped curation template has ZERO records — no
reliable machine-readable experimental-alpha dataset is programmatically
available (values in article SI tables), so per spec step 6 supervised training
is NOT claimed; dataset/audit pipeline + leakage-safe grouped benchmark harness
(mean, ridge, RF, XGBoost, GP; R2/MAE/RMSE/Spearman/Pearson/sign accuracy,
unseen-series folds) are implemented and gated on curated data. Structural
surrogate implemented and clearly labelled "cooperativity feasibility score"
(reuses Module 2 Shrake-Rupley/PDB toolkit: BSA/DeltaSASA, contacts, Hbond
proxy, salt bridges, hydrophobic, clashes, ensemble stability; deterministic
0..1). predict_cooperativity() returns predicted_alpha=None in surrogate mode,
cooperativity_class, uncertainty/confidence, feature evidence, structure
availability, applicability/OOD note and explicit limitations; raises an
evidence-required error when neither structure nor trained model is supplied.
Tests 18 (conversions/classes, reproducibility, feature extraction, malformed
structure, missing-chain, no-evidence failure, schema, no-leakage splits, empty-
data stops training). Agent tool run_cooperativity_predictor. Module 2
real-benchmark tracked as a non-blocking follow-up task.

## 2026-09-02 (audit) — Module 1 deterministic↔Monte-Carlo consistency audit

Audited the demo "153 nM vs 73.9–79.9 nM" discrepancy. Findings: (1) the two
numbers were different quantities — 153 nM was the optimal PROTAC dose (x-axis),
while the demo-printed MC interval was the peak ternary-complex concentration
(y-axis, 73.9–79.9 nM) that correctly brackets the deterministic peak ternary
77.3 nM; labels were ambiguous. (2) Real defect: MC optimum-dose detection used
a coarse 24-point log grid (~1.8× spacing) that quantised per-sample optima.
Fixes: deterministic metrics and every MC sample now estimate the peak with a
two-stage coarse+fine sub-grid scan; UncertaintySummary gains
`reference_optimum_nM` and `fraction_within_25pct`; demo prints both quantities
with unambiguous labels. Measured: deterministic optimum 150.42 nM; MC optimum-
dose p5/med/p95 142.0/149.2/156.9 nM; MC peak-ternary p5/med/p95
73.9/77.3/80.0 nM; optimum within ±25 % of nominal in 100 % of samples.
3 regression tests added (16 total, all pass).

## 2026-09-02 (late) — Module 1 (Hook Effect Modeler) + publication-quality research reports

### deep_research CLI — publication-quality scientific report (reporting redesign)
- Default terminal output is now a concise scientific evidence review in the exact
  required order: Research question → Bottom-line answer (model/LLM tier clearly
  marked) → Overall evidence confidence → Key findings (per-claim Strong/
  Moderate/Weak/Unsupported grading) → Best supporting evidence table (≤12) →
  Scientific/mechanistic interpretation (flagged model interpretation) →
  Conflicting/weak/excluded evidence (with reasons) → Knowledge gaps →
  References (Crossref-validated DOIs/PMIDs, authors, journal) → compact
  provenance. Complete retrieved-source list moved to an appendix; `--json`
  keeps the full machine-readable record (`_analyses` includes graded claims,
  evidence scores, references, metadata conflicts, exclusions, source roles).
- New `research/reporting.py`: interpretable Evidence Score (relevance, primary
  status, directness, authority, citation support, full-text availability),
  primary/mechanistic/review/web role separation, tangential-source detection
  with reasons, claim grading, DOI↔title conflict rejection (Crossref).
- Crossref DOI↔title validation extended to the top 12 works per run; enrichment
  mutations now persist through dedup (enrich → merge). Deterministic digest is
  sectioned (## Bottom line / Key findings (retrieved-source quotes) / gaps);
  quotes are trimmed and labelled; LLM prompt enforces the same section contract.
- CLI: `--trace` appends the execution trace (hidden by default); traces persist
  under outputs/research_traces and are referenced in the report provenance.
- Tests: +10 offline (synglue_agent/tests/test_research_reporting.py); suite green.

### Module 1 — Hook Effect Modeler (`simulate_hook_effect()`)
- Mechanistic three-body equilibrium/QSP model in `synglue_agent/modules/
  hook_effect_modeler/` (maps requested `protacxtend/modules/...` layout — the
  protacxtend distribution's code package is synglue_agent).
- Solves POI/PROTAC/E3 mass action exactly (bounded least-squares in log10-space,
  relative residuals; detailed-balance-consistent α), full ternary curve, optimal
  concentration, hook onset/severity/label, max occupancy, window; seeded
  Monte-Carlo uncertainty (p5/median/p95). No heuristics substitute for the
  solved equilibrium; typed pydantic I/O + version metadata + config JSON.
- 13 tests pass (mass balance, zero-dose, bell/hook behaviour, α scaling,
  E3-limiting severity, MC reproducibility/bounds, schema, input rejection);
  demo output + docs (README/ARCHITECTURE/USAGE/VALIDATION/LIMITATIONS/
  REFERENCES); agent tool `tools/hook_effect_modeler_tool.py` (JSON in/out,
  graph-safe) + `tool_spec()`; build tracker `modules/PROTACXTEND_MODULE_BUILD.md`.

## 2026-09-02 (pm) — Scientific deep-research framework (LangGraph evidence retrieval)

New low-cost, production-ready retrieval+synthesis stack: `synglue_agent/research/`
with the unified `deep_research(query)` / `deep_research_sync(query)` API
(docs: documentation/DEEP_RESEARCH.md).

### Modules
- **config.py** — ResearchConfig; every knob env-configurable (LLM tiers, budgets,
  endpoints/keys, cache, rerankers, scoring weights); `snapshot()` for reproducible
  runs (secrets redacted).
- **httpbase.py** — async HTTP client: retry loop (429/5xx/timeouts, exponential
  backoff+jitter), per-client rate delay + semaphores (NCBI ~3 rps without key),
  disk JSON cache (7-day TTL), structured ClientError.
- **sources.py** — verified live adapters (request/response contracts probed against
  the real APIs): Europe PMC (search + OA fullTextXML), PubMed E-utilities
  (esearch+efetch abstract XML), OpenAlex (works search, abstract-inverted-index
  reconstruction, cited-by, referenced works), Crossref (DOI metadata/references),
  SearXNG (self-hosted JSON), Crawl4AI wrapper with a robots-honouring clean-HTML
  fallback; source registry + retrieval-priority ordering.
- **retrieval.py** — dedup keyed DOI→PMID→PMCID→canonical-URL→normalized-title;
  merge-enrich (abstract/source provenance); authority/recency/primary scoring
  (configurable weights); neural rerank (cross-encoder + local embeddings) with
  deterministic lexical BM25 tier (honest `rerank_model`); sufficiency gate;
  claim split + citation verification (out-of-range/missing citations flagged,
  never fabricated).
- **reasoning.py** — cheap/strong LLM wrappers over the existing llm.providers
  gateway + deterministic plan/synthesis fallbacks; strong LLM reserved for hard
  plans when RESEARCH_STRONG_LLM_* configured; RESEARCH_LLM_OFF=1 forces the
  deterministic quoted-evidence digest.
- **graph.py** — LangGraph state machine (async nodes, conditional edges):
  analyze → search_scientific (Europe PMC/PubMed/OpenAlex, parallel) →
  enrich_graph → web_search → crawl_fulltext → dedup_score → sufficiency gate →
  reformulate (loop, excludes seen DOIs) → synthesize → verify_claims → finalize.
- **api.py / __init__** — `deep_research(query, config=...) -> ResearchReport`
  (answer, evidence, claims, verification, sources searched, step trace);
  `answer_to_markdown`; trace persistence under outputs/research_traces/.
- **scripts/deep_research_cli.py** — CLI (`--no-llm`, `--json`, `--out`, …).

### Verified live
- Live run (LLM off): EPMC/PubMed/OpenAlex each returned hits; duplicates merged
  by DOI/PMID; ~3 s warm / ~13-23 s cold (NCBI spacing) single-pass runs;
  deterministic digest with 100% supported claims (citation map ok).
- Reusable tooling live-verified: EPMC 503 retried transparently (max_retries=3).

### Tests
- New synglue_agent/tests/test_deep_research.py — 18 offline + 1 network:
  dedup/merge, canonical URLs, scoring monotonicity, lexical rerank ordering,
  sufficiency/reformulation, no-fabrication verification, deterministic
  synthesis, full LangGraph run with stub clients (incl. reformulation loop),
  disk cache roundtrip, live EPMC search (network-marked).

## 2026-09-02 (pm) — Retrosynthesis toolkit engines: ASKCOS + AiZynthFinder + RDKit/OpenNMT

Three retrosynthesis engines are now integrated as **working toolkits** behind the
`run_retrosynthesis` stage (spec text: ASKCOS/MIT portal+Docker, AiZynthFinder
MCTS, RDKit+OpenNMT seq2seq workflows).

### New: synglue_agent/tools/retrosynthesis_engines.py
- **ASKCOS (MIT)** — `AskcosClient` speaks the current ASKCOS REST API and was
  verified live against the public MIT instance (`askcos.mit.edu`):
  `POST /api/retro/controller/call-sync` (one-step), Retro* tree search via
  `/api/tree-search/retro-star/call-sync-without-token`, and `/api/buyables/search`.
  Normalisation turns the Retro* nodelink graph into routes + terminal
  purchasability (probe: aspirin -> acetic-anhydride/AcCl/AcOH + salicylic acid,
  15 routes, purchasable fraction 1.0). Defaults to the public portal; a local
  Docker deployment is selected with the `ASKCOS_API_URL` env var (optional
  `ASKCOS_API_TOKEN` bearer header).
- **AiZynthFinder (AstraZeneca, MIT)** — `run_aizynth_engine` reuses the verified
  `aizynth_route_search` integration; honest gate on package + policy/stock assets
  (`data/retrosynthesis/models/aizynth`, bootstrap via `scripts/bootstrap_assets.sh`).
- **RDKit + OpenNMT (Molecular Transformer)** — `run_openmt_engine` implements the
  local RDKit-preprocess -> OpenNMT-py translate -> RDKit-revalidate workflow with
  the Molecular Transformer SMILES token grammar (`tokenize_smiles`, lossless on
  canonical SMILES incl. stereo/charges). Translation is honest-gated on the
  `onmt` package + checkpoint (`data/retrosynthesis/models/openmt/retro_model.pt`
  or `OPENMT_MODEL`); RDKit preprocessing/validation always runs.
- Multi-engine orchestration `run_engines`/`merge_engine_outcomes` with a canonical
  order, per-engine `EngineOutcome` provenance, latency, and graceful
  tool_failed reasons; `engine_status_report()` prints honest availability.

### Wiring
- `retrosynthesis.assess_retrosynthesis(..., engines=[...])` accepts
  `aizynth|askcos|openmt` (aliases); legacy defaults unchanged (AiZynthFinder when
  `use_aizynth`), `RetrosynthesisResult` gains `engines_requested`, `engines_ran`,
  `engine_outcomes`. Route evidence is merged across engines (best = fewest steps).
- Registry (`toolkit_registry.py`): AiZynthFinder + ASKCOS upgraded to working
  entries (MIT, executable_type, assets notes); new entries **Molecular Transformer**
  and **RDKit + OpenNMT workflow**; ASKCOS Tree Builder points at the Retro*
  client. Router (`toolkit_router.py`) now maps retrosynthesis/forward/accessibility
  requests to the three engines.
- Smoke/evidence runner `scripts/retrosynthesis_toolkits_smoke.py` writes
  `outputs/retrosynthesis_toolkits/evidence.json` (live ASKCOS evidence generated:
  one-step + Retro* tree for aspirin).

### Tests
- New `synglue_agent/tests/test_retrosynthesis_engines.py` (18 offline tests):
  engine catalogue, tokenizer losslessness, ASKCOS stub-session contract (one-step,
  Retro* normalisation), unreachable-endpoint graceful failure, merge semantics,
  honest openmt downgrade; live ASKCOS marked `network`.
- `test_retrosynthesis.py` slow real-route test now honest-gates on the
  `aizynthfinder` package as well as assets (docker workers omit the package per
  the numpy<2 pin — degrades to RAscore-only by design).
- `tests/test_toolkit_registry.py`, `tests/test_tool_status.py` still green (15).

## 2026-09-02 — v0.1 e2e hang fixed (3 root causes) + G6 reproduction + runtime-sklearn rebuilds

### (a) v0.1 deterministic e2e hang — root-caused and fixed
Previously: `runtime --mode deterministic` never finished (stuck >50 min at
run_start, 112 threads, CUDA/OpenMP spin ~1400% CPU). Three stacked causes:

1. **TACK HGB OpenMP spin (primary)** — sklearn HistGradientBoosting opens
   libgomp parallel regions per predict; on this shared box (load>40) a
   single-row predict took ~11 s/model (33 s/molecule). 150 candidates ≈
   83 min. Verified: same code with OMP_NUM_THREADS=1 → fit 48 s→0.24 s,
   predict 283ms→0.1ms.
   - NEW `synglue_agent/tools/thread_limits.py`: `apply_thread_limits()`
     (env defaults OMP/OPENBLAS/MKL=4, early) + `bounded()` context
     (threadpoolctl). Wired into `runtime.py` entry + `tack_degradation.py`
     (predict wrapped in threadpool_limits(1, 'openmp')).
   - TACK cold call 33 s → 1.1 s; warm 11 s → 10 ms.
2. **rank_candidates per-candidate O(N×C) InChIKey generation** —
   `protacdb_evidence_prior` linearly scanned all PROTAC-DB rows computing
   an RDKit InChIKey per row PER CANDIDATE (measured 96 s for 20 candidate
   ranks; first attempt to cache keyed on id(rows) FAILED because
   load_normalized_protacdb() wraps the cached tuple in a fresh list per
   call). Fixed with `_protacdb_exact_index()`: stable key on the cached
   tuple object → O(1) exact-match dict. 150 candidates: ~9+ min → 0.87 s.
3. One-time 22-26 s pandas/openpyxl parse of `PROTAC-DB_3.0_protacs.xlsx`
   (cached per process — acceptable; parquet disk-cache deferred).

Result: `e2e_final_20260902` ran to completion in **196 s** (was >50 min):
150 candidates, TACK-style DC50/Dmax primary + chemprop cross-check,
ranking/evolution/hook/cooperativity complete, full Markdown report.

### (b) G6 reproduction for PROTAC-Degradation-Predictor — DONE
- studies regenerated with seed-42 standard split (`data/studies/`,
  active_col=Active) via `scripts/get_studies_datasets.py`.
- `run_experiments_xgboost.py --experiments standard --force_study=true`
  completed 2026-09-02 10:57 (models/ dir created — author code saves CV
  models to ../models/ and crashed without it; xgboost nthread default
  burned ~28 cores during the run — flagged for author-code follow-up).
- Results vs paper (arXiv 2406.02637 random-split study, acc 80.8 % /
  AUC 0.865 majority vote): our retrain test acc **81.6 %** (maj. vote),
  AUC **0.900**; per-model acc 80.3 %, AUC 0.890–0.904. Reproduction PASS
  (within ~1 acc point; AUC higher — paper uses pyTorch+XGBoost mix).

### (c) Runtime-sklearn rebuilds (warnings cleared)
- TACK: `scripts/build_tack_model.py` rerun in protacpilot env (sklearn
  1.9.0): DC50 ρ=0.800, Dmax ρ=0.738, bin acc 0.846/AUC 0.917 — TackModel
  loads with compatibility_warnings=[] (backup /tmp/tack_backup_20260902).
- synglue RF legs (rf_dc50/rf_dmax.joblib, sklearn 1.2.2 pickles) are
  UNLOADABLE on sklearn>=1.4 (tree dtype boundary, verified) and the
  original training set is absent locally — faithful rebuild impossible.
  Honest fix: targeted InconsistentVersionWarning suppression at the load
  site + docstring; transformer heads remain the synglue backend (torch
  artifacts load clean). test_synglue_degradation 17 passed, zero warnings.

### Tests
- 26 passed : repo_tool_adapter + production_wiring + protacdb_evidence
- 15 passed : test_degradation_endpoint (incl. tack-primary tests)
- 13 passed : protacdb_evidence + scientific_contract
- 17 passed : synglue_degradation (no InconsistentVersionWarning)
- e2e: run_end 196 s (status ok)

### Artifacts
- Audit: outputs/DEGRADATION_BACKEND_REPAIR_AND_GATE_AUDIT.md (updated)
- Ledger: notes/TASK_LEDGER_20260902.md
- Debug tools: notes/debug_v01_stages.py, notes/time_degradation_batch.py,
  notes/time_post_degradation.py

## 2026-09-01 — Degradation backend repair: PROTAC-Degradation-Predictor + TACK-as-primary

### External gate: PROTAC-Degradation-Predictor repaired (G4/G5/G6-example PASS)
- Env `/home/saveenas/miniconda3/envs/pp/envs/protac-degradation-predictor` (py 3.10.8):
  installed `gdown 6.1.0` and `pip install -e . --no-deps` (avoided forcing
  requirements pins torch 2.7.1/sklearn 1.3.2/xgboost 3.0.2 — env run verified).
- LOCAL PATCH in `get_protac_active_proba()` (local checkout):
  `models = {k: v.to(device) for k, v in models.items()}` after `load_models()`.
  Root cause: `load_model()` map_location=None when CUDA present → weights on
  cuda:0 vs inputs on cpu → RuntimeError. Backup: /tmp/pdp_backup.py.
- Data downloaded via gdown (Google Drive, 175 MB total) to
  `~/.cache/protac_degradation_predictor/` (DB 2141 rows, uniprot h5, cell pkl,
  models.zip → best_model/cv_model ckpts).
- Verified: import ok (v1.0.2); README example VHL/P04637/HeLa → active=True,
  mean proba 0.5985, majority vote True, 3 models; batch OK.
- Registry: `all_repo_install_verification.csv` → install_appears_successful=True,
  safe_wrapper_integration_possible=True; `repo_tool_adapter.py` gained a safe
  inference smoke branch; `outputs/external_integrations/protac_degradation_predictor.json`
  → status `adapter_ready`, executable true. Repair log:
  `data/protac_repos/install_logs/protac_degradation_predictor_gate_repair.log`.
- Remaining: G6 full experiment reproduction + G7 calibration/pin-following rebuild.

### TACK-style model is now the degradation PRIMARY backend
- `tools/degradation_endpoint.py`: `_tack_primary()` helper; single + batch paths
  use TACK DC50/Dmax/active when available (`model: tack-style-v1`), Chemprop
  preserved as cross-check (`chemprop_*` row keys + provenance
  `chemprop_cross_check_*`); uncertainty/AD/context gating still Chemprop-based.
- `backend/schemas.py` DegradationPrediction += `tack_active_prob`,
  `chemprop_dc50_nM`, `chemprop_dmax_pct`.
- `tools/protac_toolbox.py` predict_degradation maps `model_version` to
  `tack-style-v1 (DC50/Dmax primary) + chemprop cross-check` when primary;
  TACK second pass now only fills tack_* when endpoint didn't (fallback only).
- Tests: `test_degradation_endpoint.py` 15 passed (2 new: tack-primary,
  chemprop-fallback via monkeypatched _tack_primary); regression 21 passed
  (repo_tool_adapter, mode_router, production_wiring). Example: aspirin
  CRBN/BRD4/HEK293T → TACK 384.6 nM inactive vs Chemprop 79.9 nM, verdict
  low_confidence (out-of-domain) — disagreement surfaced honestly.
- Audit artifact: `outputs/DEGRADATION_BACKEND_REPAIR_AND_GATE_AUDIT.md`.

### BLOCKER noted: v0.1 deterministic e2e hangs pre-degradation
- `python -m synglue_agent.agents.runtime "Design CRBN PROTACs for BRD4 degradation"
  --mode deterministic --run-id gate_check_tack_20260901` was killed after
  ~50 min: trace stuck at `run_start`, CUDA/torch worker-thread spin (112
  threads, one `cuda*` thread, ~1400% CPU, no open TCP conns at sample time).
- Happens BEFORE the degradation stage → not caused by today's change;
  component-level verification stands (see audit section 7). Needs its own
  repair ticket (v0.1 graph early stages: GPU-context spin / missing guards).

## 2026-07-06 — HMGB2 Linker Optimization Campaign

### Summary
Completed a systematic linker optimization for HMGB2-ICM-CRBN/pomalidomide PROTACs.
16 linker variants (PEG, alkyl-PEG, alkyl, semi-rigid; 8–30 Å) were designed and
geometrically screened against 3600 MegaDock poses.

### Key Findings
- **All linkers <17 Å extended length: 0% pass rate** — not a single viable orientation
- **Best linker (C14-PEG5, 27 Å): 30/3600 passes (0.8%)** — still marginal
- **Root cause identified:** ICM exit vectors point AWAY from CRBN (100°–105° angle)
- The ICM binding site is on the far side of HMGB2 from where CRBN can dock

### Deliverables
- `outputs/p4ward_evidence/linker_optimization/` — full pipeline with 5 P4ward run dirs
- `outputs/p4ward_evidence/LINKER_OPTIMIZATION_REPORT.md` — comprehensive report
- `outputs/p4ward_evidence/plot_linker_passrate.png` — pass rate vs length plot
- `outputs/p4ward_evidence/linker_optimization_pipeline.py` — full pipeline script
- P4ward running for C14-PEG5 (best candidate) in background

### Next Steps
1. Test Hoechst 33258 as alternative warhead (better docking score + favorable exit vector)
2. Test alternative ICM exit vector (OH29 instead of OH27)
3. Wait for P4ward C14-PEG5 results

## 2026-08-01 — Proper conda env + completed Packages layer
- Created **`protacpilot`** env (Python 3.11.15): all 17 previously-missing packages installed & verified
  (openbabel, datamol, mordred→mordredcommunity, padelpy, deepchem, molfeat, dgl, torchdrug→own env,
  fair-esm, mdtraj, prody, py3Dmol, nglview, catboost, mlflow, wandb, chemprop).
- Created **`torchdrug310`** env (Python 3.10.20 + torch 2.1.2+cu121 + torchdrug 0.2.1) — torchdrug
  hard-requires py<3.11; resolved setuptools<81, numpy<2, ninja-lexicographic-version patch via sitecustomize.
- Version pins that fixed dependency hell: torch 2.6.0+cu126 (dgl 2.5.0 graphbolt), transformers<5
  (deepchem HuggingFaceModel), huggingface-hub<1.0 (transformers), torchdata==0.9.0 (dgl datapipes),
  numpy>=2 (mdtraj), mordredcommunity (numpy-2 compatible descriptors).
- Completed the rest of the Packages layer: gradio, llama-index, qdrant-client, chromadb, duckdb,
  psycopg, redis, celery, prefect, snakemake, nextflow (bioconda). **Packages sheet now 43/43 ✅.**
- **24/24 project tests pass in the new env** (ternary_stage 7 + synglue_degradation 17).
- Docs: `PROTACPILOT_ENVS.md` + reproducible `scripts/setup_protacpilot_env.sh`.
- Updated `Agent_Toolkit.xlsx`: Packages sheet status column (43/43 installed), fixed stale
  "heuristic-only" degradation row (now trained SynGlue model), added env + new module rows to
  Implementation_Status.

## 2026-08-01 — Structured Learning Memory (agents learn across runs)
- **`synglue_agent/tools/learning_memory.py`** (590 lines): validated, structured learning DB.
  - Controlled vocab: ProblemType (14), Outcome, LearningSource (direct_synthesis | human_feedback),
    ValidationStatus (candidate→validated/rejected/superseded), KNOWN_FAILURE_REASONS (aligned with FailureClass).
  - Every learning: problem_type, approach, outcome, human_correction, failure_reason, confidence,
    source, validation, provenance (run_id, target, E3, tool_versions, decision_refs), reuse_count.
  - Validation: human confirmation OR independent reuse (≥2 runs) auto-validates.
  - Safe reuse gate: only VALIDATED + confidence ≥ 0.7 returned by validated search.
  - Outliers: entries whose outcome contradicts their (problem_type, approach) cluster majority → flagged.
  - Pattern extraction: success rates per approach, top failure reasons, top human corrections,
    deterministic why-statements; rendered to patterns.md.
  - Per-process **learnings.md** written to memory/learnings/runs/<run_id>/learnings.md.
- **`synglue_agent/agents/learning_integration.py`** (240 lines): persist_run_learnings (auto-distills
  decision_log on every run), advise_repair (reuses validated learnings incl. human corrections),
  record_human_feedback (auto-validated ground truth, conf≥0.85 to pass reuse gate),
  attach_learning_persistence_to_run decorator.
- Fixed pre-existing agentic_core bugs surfaced by integration tests:
  - conditional-edge maps now filtered to registered nodes (graph compiled with stubs only)
  - default stub agents populate all stage fields → skeleton graph runs 18 nodes, no recursion loop
  - evidence gate defensive against non-dict evidence values
- 28 new tests (22 memory + 6 integration); full suite 52 passed.

## 2026-08-02 — TODO execution: A1, A2, B5 (in progress)
- **A1 done**: `test_agentic_scenarios.py` — 6 automated tests for good path /
  out-of-domain / repair loop / budget exhaustion / degradation escalation /
  determinism. Fixed real bug: repair-budget exhaustion → infinite ternary
  self-loop (route_after_ternary returned "ternary_ensemble" mapped to a
  self-loop); now escalates to human_gate.
- **A2 done**: `agents/linker_stage.py` — linker-design stage with
  conformational-strain loop router (evidence gate → scan → strain_check →
  repair loop bounded by MAX_LINKER_RETRY → ranking / human gate), 9 tests.
  Fixed real bugs: linker_scanner `effective_length_A` was 0.0 for all
  curated linkers (loader looked for wrong CSV column; added
  `effective_length` key + SMILES-topological fallback); invalid hand-written
  full-PROTAC SMILES in build_full_PROTAC.py rebuilt via RDKit dummy-atom
  assembly (C51H59N5O13, MW 950.1, verified parses, zero dummies).
  Added HARD_ERROR to ReasonCode controlled vocabulary in state.py.
- **B5 started**: PROTAC-DB 3.0 downloaded (15,502 PROTACs; 2,275 with DC50;
  1,311 with DC50+Dmax) → data/benchmark/PROTAC-DB_3.0_protacs.xlsx.
  scripts/benchmark_degradation.py runs the SynGlue predictor (real GROVER
  embeddings, family-matched E3, constant-warhead inference design) on a
  stratified 64-molecule sample; metrics: Spearman/Kendall on log10 DC50,
  threshold hit rates, MAE, Dmax rank correlation.

## 2026-08-02 — B1 done: Chemprop D-MPNN trained on PROTAC-DB 3.0
- PROTAC-DB 3.0 (15,502 PROTACs; 2,275 with DC50) downloaded → data/benchmark/.
- Trained Chemprop D-MPNN (log10 DC50 regression, 1,698 rows, scaffold split
  80/10/10, 60 epochs): test RMSE 0.875, R2 0.517.
- Same 64-molecule held-out benchmark: **Spearman rho 0.758 (p<0.001)** vs
  SynGlue baseline 0.243; hit<100nM 76.6% (was 53%), hit<1000nM 93.8% (was 78%),
  MAE 0.64 log10 (was 1.21). Training on domain data is decisive.
- `tools/chemprop_degradation.py` wrapper (CLI-backed; chemprop 2.3.0 MPNN has
  no public predict API; `python -m chemprop.cli.main` silently no-ops → use the
  console script). 5 tests pass.
- Comparison report: outputs/benchmark/B1_CHEMPROP_COMPARISON.md.

## 2026-08-03 — Uncertainty-aware predictive layer + AD detection (priority 2)
- **applicability_domain.py** (rewritten from stub): Morgan nn-Tanimoto vs the
  1,698-molecule training set, cached fingerprints. Fixed real bug: numpy bool
  matmul (`B @ a`) does not AND-count → explicit logical ops. Verified: self-sim
  1.0, aspirin OOD, pomalidomide in-domain, ICM warhead correctly out_of_domain.
- **Chemprop 3-member ensemble + conformal-regression calibration** (cal set
  n=200 held out; retrained 1,498): **92.2% interval coverage vs 90% target**,
  Spearman ρ=0.783, MAE 0.61 log10. Measured: raw ensemble std is NOT
  calibrated (ρ=0.086 vs error); AD similarity is the strongest trust signal
  (far bin RMSE 0.88 vs near 0.50).
- **uncertainty_aware_prediction.py**: verdicts high/medium/low_confidence
  composed from AD + conformal interval; wires ensemble + conformal + AD.
- **degradation_node.py**: real agentic-graph degradation node using the
  validated layer; low-confidence (OOD) candidates → bounded repair → human.
- **state.py**: added DecisionLog.to_dict() to the shared foundation.
- Tests: 5 (coverage, OOD flagging, in-domain, AD math regression guard).
- Report: outputs/benchmark/UNCERTAINTY_CALIBRATION.md.

## 2026-08-03 — Capabilities 2,3,4,7,8,10 completed
- **B4 NSGA-II Pareto ranking** (`tools/pareto_ranking.py`): non-dominated
  sort + crowding distance on [logDC50, dmax_inv, admet, synthesis, ternary];
  7 tests. No weights in dominance — replaces single composite score.
- **adaptive_extras.py** (cap. 2,3,4,7): warhead + exit-vector bounded repair
  loops (MAX_SELECTION_RETRY → human gate); dynamic tool selection
  (evidence → P4ward vs geometric proxy vs blocked); parallel candidate
  evaluation (ThreadPool, order-preserving, failure-isolated); expensive-
  modelling human gate (pauses before P4ward hours). 15 tests.
- **B6 Ablation** (`scripts/ablation_agentic_vs_pipeline.py` + report):
  [A] trained layer beats heuristic ρ 0.42→0.78, hit 75%→92%;
  [B] repair loop rescues candidates a pipeline discards;
  [C] AD flags 8/8 OOD, 0/8 in-domain misflagged.

## 2026-08-03 — A6 LLM layer: Ollama + gpt-oss:20b (single-model multi-role)
- Ollama updated to 0.32.5 (user-space binary at ~/ollama-bin, server on
  port 11435; system 0.11.10 on 11434 lacks gpt-oss support). Pulling
  gpt-oss:20b (~14 GB, 128K ctx, tools+reasoning, Apache-2.0).
- **llm/schemas.py**: Pydantic schemas per role — EvidenceDecision (Route:
  search_more/design/human_review/terminate), DesignDecision, RepairDecision
  (RepairAction enum), CritiqueDecision, SupervisorDecision, ReportDecision.
  No free-text reasoning stored — only decision + codes + tools + refs +
  confidence + rejected alternatives.
- **llm/tool_registry.py**: ALLOWED_TOOLS (13) — model may select but never
  construct arbitrary names; validate_selected_tools raises on anything else;
  EXPENSIVE_TOOLS (run_p4ward, run_retrosynthesis) force human approval.
- **llm/roles.py**: one model, six roles via prompts (supervisor, evidence-
  assessment, design-strategy, critic, repair, report) — NOT six models.
- **llm/ollama_client.py**: structured_chat with format=schema, temperature 0,
  num_ctx default 16K (cap 32K); model routing gpt-oss:20b → qwen2.5:7b
  fallback; structured_chat_with_fallback never lets model outage break the
  graph.
- **llm/context.py**: evidence summarization (truncate lists, counts),
  compact state for LLM — never dump full ChEMBL records.
- **llm/decision_layer.py**: LLM-gated nodes with deterministic validators —
  invalid tools stripped, p4ward selection → human_review, bounded evidence-
  search loop (MAX_EVIDENCE_SEARCH_ROUNDS=2 → human gate).
- **llm/graph.py**: LangGraph wiring; **fixed StateGraph(dict) replace-vs-
  merge bug** (retry_counts needs Annotated[sum_counts] reducer).
- 13 tests (mocked LLM — no GPU needed); 85 total green.
- **Live verification with gpt-oss:20b**: model pulled (13 GB, 128K ctx),
  structured chat works (EvidenceDecision/RepairDecision/SupervisorDecision
  all parse; cold start 63s, then 2-5s). Learned: gpt-oss:20b is conservative
  on evidence sufficiency — flipped the wiring so the DETERMINISTIC gate is
  authoritative (it has the numbers); the LLM may only add missing-evidence
  flags/tools, never veto sufficiency without naming a blocker. Matches the
  "deterministic validators gate LLM" principle.
- Server: user-space ollama 0.32.5 on port 11435; model resident on RTX 5000
  (13 GB); num_ctx capped 16K per request (Ollama default would be 262K).

## 2026-08-03 — Provider-agnostic LLM layer (any API in backend + frontend)
- **llm/providers.py**: 6 providers (ollama, openai, openrouter, anthropic,
  google, openai_compatible) behind one Protocol; env-config (PROTACPILOT_LLM_*)
  with runtime override (set_runtime_config). Provider-agnostic chat_raw; the
  gateway owns validation.
- **llm/gateway.py**: structured_chat across providers — raw text → json_repair
  → Pydantic validation → 1 retry with JSON-only instruction → fallback.
  gateway_status()/switch_provider() power the API + frontend.
- **llm/json_repair.py**: fence/prose stripping, balanced-block extraction,
  trailing-comma + unterminated-string repair (fixed over-aggressive quote
  repair that corrupted valid JSON).
- **backend/llm_routes.py**: GET /llm/status, /llm/providers, /llm/models;
  POST /llm/switch, /llm/test, /llm/reset — wired into api_routes.get_app().
- **app/streamlit_app.py**: sidebar "LLM backend" widget (provider/model/
  base_url/key + Apply + Test).
- Verified LIVE: ollama/gpt-oss:20b through the gateway — supervisor
  (BRD4/VHL/protac), repair (alternate_linker), evidence decisions parse;
  /llm/test returns schema-valid decision; status health ok.
- 14 new tests (gateway + repair + provider registry + switch) — 99 total green.
- Docs: PROTACPILOT_LLM.md (switch any provider 3 ways).

## 2026-08-03 — Roadmap execution: Tasks 1-3 (immediate actions)
- **Task 1 — Architecture freeze/unify** (release/v0.3-agentic-core branch):
  git initialized, `.gitignore` (6GB repos excluded), branch created.
  ONE entry point `agents/runtime.run_protacpilot(mode=deterministic|agentic)`;
  mode_router + backend API route both modes through it; unified degradation
  interface (chemprop→synglue→heuristic, provenance + labelled fallback);
  DesignMemoryRecord deprecated (Pydantic alias); agentic/ scaffold marked
  LEGACY; agentic_mode=False regression + agentic_mode=True e2e tests pass
  (10 unification tests).
- **Task 2 — Real retrosynthesis**: RAscore prescreen (SAScore proxy fallback,
  clearly labelled) + **AiZynthFinder real route search** (pretrained USPTO
  ONNX policy + templates + ZINC stock downloaded: 447 MB). RetrosynthesisResult
  schema (exact spec), routing (feasible→pareto, repairable→linker, no-route→
  human, tool-fail→RAscore-only downgrade), provenance, tool-failure safety.
  13 tests (12 fast + 1 slow real). Verified LIVE: acetamide → 24 routes,
  1-step, feasible; real PROTACs → honest human_required. Fixed 4.4.1 API
  differences (Configuration→configdict, RouteCollection dicts, select_all).
- **Task 3 — Real ternary ensemble**: P4ward + geometric proxy + **SE3-PROTACs
  with real pretrained weights** (loaded, ESM embeddings, live score) — two
  genuinely independent methods. Staged escalation (reject<0.30, p4ward<0.60,
  top→p4ward+se3), consensus on RAW scores (agreement+uncertainty),
  disagreement→human gate. Live: HMGB2-ICM candidate → geometric 1.0 vs SE3
  ~0 → AMBIGUOUS → human gate (real scientific disagreement surfaced). 12 tests.
- **Env fix**: aizynthfinder downgraded rdkit→2023.9.6 breaking chemprop;
  restored rdkit 2026.3.5 and relinked cuik_molmaker's 158 hash-named RDKit
  libs to the current rdkit.libs (predictions verified correct).
- Full suite: 247 passed (11 skipped, slow deselected).

## 2026-08-04 — Roadmap: Tasks 4-8 (endpoint, E3-context, LLM validation, memory, e2e+benchmark)
- **Task 4 — Degradation endpoint**: multi-target Chemprop (logDC50 + Dmax, 1,126
  rows, scaffold split), active/inactive classification (DC50≤100nM & Dmax≥50%),
  cellular-context gate (E3 expression veto: VHL-low in MM1.S → chemistry score
  downgraded to low_confidence with explanation), uncertainty + AD retained.
  10 tests.
- **Task 5 — E3-context engine**: deterministic evidence-based scoring
  (expression/colocalization/ligand/structural/resistance with per-component
  evidence refs). Headline requirement verified verbatim: "CRBN preferred over
  VHL because CRBN has higher expression (1.00 vs 0.20) ... despite VHL having
  better structural availability (1.00 vs 0.90)". 8 tests.
- **Task 6 — LLM role validation harness**: scripts/eval_llm_roles.py — 6 roles
  × metrics (valid output, unsupported tools=0, SMILES edits=0, hallucination=0,
  human-gate recall, context overflow). Live gpt-oss:20b: safety metrics all
  perfect; GENUINE findings: repair chose retry for OOD (deterministic layer
  overrides), report dropped a number (templates insert numbers). CI-safe
  deterministic tests. 8 tests + findings doc.
- **Task 7 — Memory unification**: three separate stores (RunStateStore,
  EvidenceStore, LearningStore) in memory/stores.py + MemoryHub. Learning
  retrieval sequence (failure signature → validated match → suggestion →
  deterministic validation → outcome recording); failed repairs reduce
  priority; human corrections separate from model decisions; memory cannot
  override validators (tested). 10 tests.
- **Task 8 — e2e challenge + formal benchmark**: scripts/e2e_challenge.py ran
  A (known potent → active), B (known weak → inactive), C (HMGB2-ICM → active
  chem vs SE3 ternary ~0 → AMBIGUOUS → human gate; cross-layer disagreement
  documented). Full records in outputs/e2e_challenge/. 8-system benchmark
  harness (scripts/agentic_benchmark.py) running; formal report scaffold at
  outputs/benchmark/FORMAL_BENCHMARK_REPORT.md.

## 2026-08-04 — Production wiring (checkpointer / queue / tracing / docker / benchmark table)
- **Persistent LangGraph checkpointer**: agents/checkpointer.py — postgres
  (checkpoint-4.x-native; verified CROSS-PROCESS interrupt/resume with
  dockerized postgres) → sqlite → memory fallback. run_agentic_workflow
  accepts thread_id; runtime.run_protacpilot surfaces __interrupt__ and
  runtime.resume_agentic_run resumes the same thread. Discovered: sqlite
  backend 3.1.1 is incompatible with langgraph 1.2.10's checkpoint 4.x
  serialization; postgres is the production path; invoke returns
  {'__interrupt__': [...]} rather than raising in langgraph 1.2.10.
- **Job queue**: synglue_agent/queue/job_queue.py — redis (if available) /
  sqlite fallback; submit/claim/complete/fail/needs_human lifecycle;
  deploy/p4ward_worker.py consumes jobs (retrosynthesis/degradation done,
  p4ward → needs_human budget gate). Verified end-to-end (2 jobs → done).
- **Central logging/tracing**: observability/tracing.py — per-run trace.jsonl
  (node_start/end, tool_call, decision, error, run_end) + summary.json;
  wired into runtime so EVERY run is auditable (outputs/runs/<run_id>/).
- **Dockerized services**: deploy/docker-compose.yml (api/worker/postgres/
  redis/ollama) + Dockerfile.api; compose validated.
- **8-system benchmark COMPLETED + interpreted**: fixed_pipeline ρ=0.479 vs
  all chemprop-based systems ρ=0.785 (enrichment 0.75→0.875). Honest
  interpretation: the degradation layer dominates in-domain ranking; the
  agentic components' value shows on failure/safety scenarios (per-layer
  ablation B6), not on clean in-domain ranking. Report table filled.
- 10 production-wiring tests; full suite 293 passed.

## 2026-08-04 — Close-out: model volumes, stack boot-test, LLM role gaps fixed
- **docker-compose model volumes**: data/ + outputs/ + SynGlue_Py mounted (bind)
  into api + worker services (models are 500MB+, never baked into the image);
  `docker compose config` validated.
- **Stack boot-tests passed**: (A) FastAPI /agentic-design against dockerized
  postgres → 20 checkpoints persisted for the run's thread (queried via psycopg);
  (B) redis-backed JobQueue lifecycle through dockerized redis (queued→running→
  done). Postgres container had stopped (17h) — restarted and re-verified.
- **LLM role gaps FIXED at the model level** (not just deterministic overrides):
  - repair role: prompt hard rules (OOD→human_review ONLY; repairable classes
    enumerated; SMILES forbidden; escalate only for OOD/budget/unknown) —
    both cases now pass (caught and re-pinned an over-correction).
  - report role: ReportDecision gained a machine-checkable `numbers` field;
    prompt requires every supplied value listed there — model now declares
    [{DC50: 5.2 nM}, {Dmax: 91%}] exactly.
  - harness checker fixes (boundary-aware regex: no "50" from "DC50", no
    ordinal "1."; hallucination = in summary, absent from prompt AND numbers).
  - **All 5 roles pass at 100%; metrics: 1.0 valid output, 0 tools, 0 SMILES
    edits, 0 hallucinations, 1.0 human-gate recall, 0 context overflow.**
- Findings doc + formal benchmark report updated to reflect the fixes.

## 2026-08-04 — LLM case bank expanded 9 → 17 + full compose build attempt
- **Case bank expanded per spec** (supervisor 4, evidence 4, critic 3, repair 4,
  report 2): bounded-plan + mandatory-validation, contradictory evidence, source
  routing, low-confidence claim, budget exhaustion, prediction-labelling,
  evidence-refs. SupervisorDecision gained plan_steps/selected_tools/
  includes_validation; ReportDecision gained evidence_refs.
- **Live model now passes 17/17 (100%)** with all safety metrics perfect. The
  expansion surfaced and fixed: 4 checker bugs (validation inferred from plan
  content not just the boolean; hallucination regex boundary-aware + uses the
  actual prompt; prediction-labelling accepts standard verbs; repair expected
  action matched to the deterministic controller's actual linker-regeneration
  policy), plus prompt hardening (plan_steps required, evidence_refs filling).
- **Docker compose build in progress** (requirements.txt expanded to full
  runtime set: torch/chemprop/aizynthfinder/psycopg/redis/LLM clients) —
  full-stack boot test pending build completion.

## 2026-08-06 — Full compose stack boot-tested end-to-end + LLM case bank at 17
- **Full stack boots and works**: api (host 8001) + worker + postgres + redis +
  ollama all healthy via docker compose. Containerized verification passed:
  /health, /llm/status, /agentic-design (20 checkpoints persisted to the
  COMPOSE postgres for the run's thread), /mode validate (RDKit chemistry),
  queue job through compose redis → worker → done.
- **Real degradation quality in the container**: chemprop_multitarget model
  (DC50=33.9 nM, Dmax=80%, class=active) with AD correctly flagging
  out_of_domain — fixed the GPU assumption (auto accelerator: container has
  no CUDA → cpu) that silently fell back to heuristics.
- **Container build fixes** (each surfaced by the real boot test): psycopg-binary
  (PostgresSaver), openpyxl (PROTAC-DB xlsx), libexpat1 (cuik_molmaker; needed
  a dedicated apt RUN + separate worker image rebuild), aizynthfinder omitted
  (numpy<2 conflict → RAscore-only retrosynthesis degradation per spec),
  rdkit pinned 2026.3.4 (cuik-molmaker-pin match), ABI fix as script
  (heredoc needs syntax directive).
- **LLM case bank expanded 9 → 17 cases** (supervisor 4, evidence 4, critic 3,
  repair 4, report 2): live gpt-oss:20b now passes 17/17 (100%) with all
  safety metrics perfect; 4 checker fixes + prompt hardening + 1 genuine
  supervisor gap fixed (plan validation inference).

## 2026-08-06 — RELEASE v0.3.0-agentic-core
- Tag `v0.3.0-agentic-core` created on `release/v0.3-agentic-core` (commit 66c42849; rewritten as 1c02183 after 7.93 GiB → 100.79 MiB filter-repo hygiene for GitHub publication).
- `RELEASE_CLOSURE_REPORT.md` — definitive closure report (architecture, 293
  tests, benchmark tables, container boot-test, LLM validation 17/17, e2e
  cases, model versions, commit, limitations, reproduction, PASS/FAIL).
- `RELEASE_NOTES_v0.3.0.md` — added features / scientific models / safety /
  infrastructure / validation / known limitations.
- Statement: SynGlue v0.3-agentic-core satisfies the predefined functional,
  scientific-safety, persistence, deployment and observability requirements
  for a research-grade agentic PROTAC design platform.

## 2026-08-07 — PUBLISHED to GitHub (controlled)
- Repo: github.com/SaveenaSolanki/Protac_Pilot (private).
- History hygiene: filter-repo purge (7.93 GiB → 100.79 MiB); virtualenvs,
  cloned deps, big data dumps, runtime DBs removed from history + gitignored.
- Git identity fixed: Saveena Solanki <113490997+SaveenaSolanki@users.noreply.github.com>.
- Branches: `main` + `release/v0.3-agentic-core` @ 7d1dc18 (release history
  + MIT LICENSE adopted + uploaded v0.3 snapshot preserved as ancestor).
- Tag `v0.3.0-agentic-core` → 7d1dc18; GitHub Release created from RELEASE_NOTES.
- Branch protection on both branches: 1 required review, linear history,
  force-push/deletion disabled, admins enforced.

## 2026-08-07 — REPRODUCIBILITY & CI hardening (review items 5-8, 10)
- Secret scan: gitleaks 8.30.1 over full history — 1 real finding (Jupyter
  token in M1.log) purged from all history; 11 remaining = verified false
  positives (conda build hashes) recorded in .gitleaksignore. *.log gitignored.
- ASSET_MANIFEST.md + scripts/bootstrap_assets.sh: provenance matrix + one-shot
  asset restore (figshare USPTO hdf5 set + Zenodo ONNX stereo model + SE3 clone)
  with SHA-256 recording (ASSET_MANIFEST.checksums.json) and dry-run mode.
- Real AiZynthFinder route search verified with bootstrapped ONNX models
  (aspirin -> 1-step purchasable route). retrosynthesis.py now supports both
  ONNX and hdf5 policy sets.
- Committed production assets that fit GitHub limits: multitask_transformer.pt
  (35MB), grover_e3.csv, grover_warhead.csv (58MB). grover_fixed.pt (409MB)
  stays excluded (documented).
- scripts/ci_smoke.py (8/8 asset-free checks) + .github/workflows/ci.yml
  (compileall + smoke + fast unit tests, full fast suite job).
- scripts/install_gitleaks_hook.sh: pre-commit secret guard (staged).
- Fixed pre-existing Python 3.11 SyntaxError in scripts/verify_all_repo_installs.py.

## 2026-08-08 — "MAKE IT ALL WORKABLE": all partial agents unblocked
- Binder: live ChEMBL /activity 2-call fetch (90 BRD4 binders in 9s), unit
  normalization (uM/mM -> nM, pchembl preferred), per-record provenance,
  BindingDB key-gated (BINDINGDB_API_KEY). tests: test_binder_live.py (4).
- Novelty: live PubChem PUG-View patent cross-reference (patent_count/ids/source
  on NoveltyResult) + local similarity. tests incl. mocked + live (14 patents
  for aspirin).
- ADMET: ADMET-AI 2.0.1 (106 endpoints) in isolated .venvs/admet (torch>=2.8
  kept out of main env), subprocess runner scripts/run_admet_ai.py, wired into
  admet_integration.predict_admet_properties with labelled provenance and rule
  fallback; bootstrap_assets.sh --admet.
- Linker: fragment-combination generator (8 cores x spacers, RDKit-validated,
  diversity-selected, 64 linkers) enriched into linker_scanner library
  (PROTACPILOT_FRAGMENT_LINKERS=0 to disable).
- Evolution: SMILES mutation (aliphatic C<->N<->O with retries) + BRICS-fragment
  crossover + evolution_generation tracking in evolve_candidates.
- pytest.ini registers `network` + `slow` markers. Full suite: 313 passed.

## 2026-08-11 — E2E SCIENTIFIC-AGENT MILESTONE (v0.3.0-agentic-core re-tagged)
- CRITICAL FIX: agentic graph now runs REAL nodes (real_nodes.py) — the
  runtime previously defaulted to `_default_stub_agents()` (stub candidates
  everywhere). The benchmark's "full_agentic" never ran the graph (it was a
  per-molecule scoring harness). Now: live ChEMBL binders, fragment linkers,
  BRICS construction, ternary ensemble, chemprop degradation, ADMET-AI,
  patent novelty, NSGA-II ranking — all wired through the adaptive graph.
- Canonical AgentRunRecord (synglue_agent/run_records.py): run.json +
  decisions.jsonl + evidence.jsonl + candidates.parquet + pareto_front.csv +
  structures/ + docking/ + report.md per run, with reproducibility hash.
- E2E suite (scripts/e2e_agentic.py): 5 scenarios PASS —
  BRD4 (full chain, ranked recommendation), BTK (32 candidates → low-confidence
  gate), KRAS (evidence-limited → repair → gate), HMGB2 (novel → gate),
  impossible input (safe failure). 0 failed.
- Graph fixes found by e2e: evidence gate accepted real ternary key (was
  infinite repair loop); HARD_ERROR reason code registered; ADMET composite
  penalty (0.50*AMES+0.30*DILI+0.20*hERG) + threshold 0.65; warhead SMILES
  validation (regex prose bug); memory checkpointer for e2e (17.7GB sqlite
  checkpoint bloat deleted); ChEMBL 429 Retry-After backoff.
- CI restructured: smoke + full-offline (+ e2e) + security (gitleaks, ruff,
  artifact availability, bootstrap dry-run); python-app.yml deleted;
  required checks on main = CI/smoke, CI/full-offline, CI/security.

## 2026-08-12 — MULTI-E3 LIGASE EXPANSION (beyond CRBN/VHL)
- E3 library expanded from 7 rows (CRBN/VHL/IAP/MDM2 demos) to 114 rows /
  19 E3 groups, generated reproducibly from the cited e3_ligand.csv dataset
  (scripts/build_e3_library.py): cIAP1, cIAP2, XIAP, MDM2 (Nutlin-3, RG7388,
  RG7112), DCAF1/11/15/16, KEAP1 (KI-696, piperlongumine), RNF4/114/126,
  KLHL20 (BTR2000), KLHDC2, FEM1B, FBXO22, AhR, SKP1, UBR box + CRBN/VHL.
- E3LigandRecord provenance now carries article DOI, UniProt, activity (nM)
  and attachment-point note per ligand.
- E3LigandSelectionAgent/graph node parse ANY E3 from natural language
  ("MDM2-recruiting", "recruit KEAP1", "the AhR E3 ligase") via E3_ALIASES
  (30+ synonyms), with graceful CRBN default when unknown.
- New e2e scenario: MDM2-recruiting PROTACs vs BRD4 — full chain PASS (ok,
  Nutlin-derived candidates). E2E suite now 6/6.
- Tests: test_e3_library.py (20) — full regression 333 passed.

## 2026-08-12 — DegradationPredictionAgent: heuristic → trained Chemprop (verified)
- Root-cause: the md/ spec's "heuristic only" flag was CORRECT for the agent
  path — DegradationPredictionAgent → toolbox.predict_degradation used a pure
  MW/TPSA formula; the trained Chemprop (ρ=0.783) was only wired into the
  agentic graph node + benchmark, not the agent itself.
- Fix: predict_degradation now calls predict_degradation_endpoint (trained
  single-target conformal ensemble → DC50/uncertainty + multi-target head →
  Dmax + AD + context gate). Old formula kept ONLY as labelled fallback
  (model_version="heuristic_proxy-v0.1 (fallback)").
- Verified: agent path returns chemprop-ensemble-v0.3 (DC50 79.9 nM, Dmax
  80.5%, AD 0.15 → honest OOD warning for aspirin). 2 new tests
  (uses-chemprop + labelled-fallback). 48 affected tests pass.

## 2026-08-12 — Generative linker model (LinkerGeneration upgrade)
- New char-GRU linker generator (SMILES-RNN style) trained on 241 PROTAC-DB 3.0
  BRICS-extracted linkers + curated/fragment linkers (scripts/build_linker_dataset.py,
  scripts/train_linker_generator.py; checkpoint data/linkers/linker_generator.pt).
- tools/generative_linker.py: sample -> RDKit validate/filter (3-20 heavy atoms,
  rotatable<=8, wrapped-SMILES validity) -> BATCHED ADMET-AI scoring (AMES/DILI/hERG
  composite, one subprocess for all) -> greedy diversity selection (Tanimoto>0.35).
- Wired into toolbox.generate_linkers (source="generative_linker_model", toggle
  PROTACPILOT_GENERATIVE_LINKERS=0) -> flows into LinkerGenerationAgent + agentic
  graph node + linker scanner. 9s for the full library (was >300s with per-mol ADMET).
- REINVENT/Link-INVENT prior exists locally (SynGlue_Py/repos/reinvent/models/
  linkinvent.prior) but requires a separate REINVENT v3 env (absent) — the own-model
  path was chosen as the reproducible alternative; Link-INVENT can be added later.
- Tests: test_linker_stage.py +2 (generative source present + graceful fallback);
  11 passed. md/09 spec updated.

## 2026-08-12 — Deterministic pipeline batching (18x faster, real model)
- Root cause: DegradationPredictionAgent looped predict_degradation_endpoint
  per candidate -> one chemprop CLI subprocess (model reload ~20s) each:
  58 candidates = ~34 min. Added predict_degradation_batch (ONE ensemble call +
  ONE multitarget call + per-molecule verdict composition); toolbox.
  predict_degradation now batched: 112 s (was 2029 s), all predictions from the
  trained chemprop ensemble. ADMET path already local/rules.

## 2026-08-12 — Link-INVENT-style linker scoring + RL optimization
- tools/linker_scoring.py: reverse-sigmoid components (LGL/LEL/Flex/HBD/MW/TPSA,
  weights 2,2,2,1,2,2) aggregated as weighted product + batched ADMET penalty;
  effective length = attachment bond-path distance; rank_linkers used by
  generate_linkers (default on; PROTACPILOT_LINKER_SCORING=0 to disable).
- tools/linker_optimizer.py: REINFORCE-style policy-gradient refinement of the
  char-GRU linker policy (reward = score*(1-admet_risk), baseline update,
  bounded rounds; persist optional). PROTACPILOT_LINKER_OPTIMIZE=1 to run in
  generate_linkers. Verified: optimized output = clean amide/PEG linkers.
- Tests +4 (scoring band, length preference, ranking, optimizer validity):
  15 linker tests pass.

## 2026-08-12 — TACK-model degradation cross-check
- TACK = TArgeting Chimeras Knowledge (Ribes/Dunlop/Mercado, KDD AI4Science '26;
  arXiv 2605.19579): curated 3,514 PROTACs / 6,561 endpoints from TPDdb +
  PROTAC-DB + PROTACpedia. Official HF weights (TACK-Model-DC50/Bin) are
  GATED; dataset is public.
- trained TACK-STYLE models on the public dataset (scripts/build_tack_model.py,
  scaffold split): DC50 log-regression rho=0.800 (val n=876), Dmax rho=0.738,
  binary active (DC50<100nM) acc 0.846 / AUC 0.917.
- synglue_agent/tools/tack_degradation.py: inference (Morgan 1024 + descriptors
  + E3/cell/POI one-hot) with provenance; batch API.
- DegradationPrediction schema += tack_dc50_nM / tack_dmax_pct / tack_active;
  toolbox.predict_degradation fills them as a second opinion (never blocking).
- Tests +2 (tack populated + tool): 14 degradation-endpoint tests pass.

## 2026-08-12 — AGENT_ARCHITECTURE_UPDATE implemented (nodes 5/19/20)
- Node 5 census: chem_identity (full InChIKey, stereo-aware), InChIKey dedup in
  binder retrieval, RetrievalCensus with ChEMBL n_reported_total recorded,
  state.retrieval_census/retrieval_status fields.
- Node 19 memory: evolve_with_generations — SeenSet (InChIKey) + GenerationRecord
  (n_produced/n_novel vs ALL prior gens, novelty_ratio, best/mean, operators) +
  termination (max_gens 10, novelty_floor 0.10, patience 2, reason recorded);
  CandidateRecord.parent_ids/operator_applied fields; FitnessSpec
  (label_source now truthfully "trained" — O-1 closed).
- Node 20: TERNARY_PROMOTION policy + CalibrationRecord schema + revise_
  degradation_from_ternary (12' folded in — graph already runs ternary before
  degradation; verified confidence revision 0.8->0.35 on low ternary).
- Deliverables: Sabeel/AGENT_ARCHITECTURE_IMPLEMENTATION_STATUS.md (spec marked
  per section), TOOL_AUDIT.xlsx (8 sheets: overview/agents/tools/models/
  integrations/CI/docs/gaps) + scripts/build_audit_xls.py, RUN_AND_FRONTEND.md
  (how to run, frontend access, stage map), tests/test_architecture_update.py (5).

## 2026-08-13 — §3.3/3.7/coverage_cell implemented
- §3.3 P4ward checkpointing: batch_run writes batch_checkpoint.json + per-run
  P4wardRunResult.json; resume skips completed runs (48h campaign survives crash).
- §3.7 pLDDT gate: CandidateRecord.plddt_min/mean; plddt_gate() flag/block modes
  (unknown-safe) wired into the agentic ternary node before P4ward spend.
- coverage_cell tables: tools/coverage_matrix.py — CoverageCell rows (warhead×E3×
  linker, InChIKey keyed), append-only outputs/coverage/coverage_cells.jsonl,
  summary (fraction touched), best_pass_rate NULL-until-measured discipline;
  wired into runtime (result["coverage"]).
- tests +3 (plddt gate, coverage record/no-backfill): 8 architecture tests pass.
