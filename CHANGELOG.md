# PROTACXtend Changelog

## 2026-09-22 — Collapse parallel agent stacks into one canonical execution stack (ADR-001)

- **New `protacxtend/canonical/` control plane** implementing the requested
  pipeline: Scientific Request Parser → Orchestrator → Task Graph → 9
  Specialized Scientific Modules → Tool Executor → Evidence Store → Critic /
  Verifier → Decision Engine → typed `TherapeuticStrategy`.
  - `modules.py`: Target & Disease, TPD Tractability, E3 Selection,
    Chemistry/Warhead, Structure/Ternary, Degradation, ADME/Safety,
    Resistance/Biomarker, Experimental Design.
  - `tool_executor.py`: single gateway; the historical deterministic
    (`agents/graph.py`) and adaptive (`agents/agentic_core.py`) graphs are now
    pluggable *engines*, not parallel stacks. Legacy `protacxtend/agentic/`
    remains deprecated.
  - `critic.py`, `decision.py`, `evidence.py`: one verdict, one typed decision,
    one evidence ledger per run (benchmark attribution via stable `module_id`).
- **Runtime integration**: `agents/runtime.run_protacpilot` now attaches
  `canonical.{critic,module_results,task_graph}` and a top-level
  `therapeutic_strategy` to every run; `CanonicalOrchestrator.review_engine_state`
  reuses the already-computed engine state so science still runs once.
- **Parser hardening**: fail-closed guard drops low-confidence gene-shaped
  English words (e.g. `suggest`) unless they are known gene symbols or contain
  a digit; explicit config overrides now win over NLP constraints.
- **Tests**: `tests/test_canonical_stack.py` (27 fast, offline tests).
- **Docs**: `documentation/CANONICAL_STACK.md` (ADR-001); architecture/
  closeout/state docs updated.

## 2026-09-22 — Typed scientific output `TherapeuticStrategy.v1`

- **Every discovery run now emits a fully typed `TherapeuticStrategy`** (not
  prose) with: `target`, `disease_context`, `target_validation`,
  `tpd_tractability`, `recommended_e3`, `alternative_e3s`, `rejected_e3s`,
  `warheads`, `attachment_vectors`, `linker_hypotheses`, `candidate_protacs`,
  `binary_structure_assessment`, `ternary_complex_assessment`,
  `degradation_prediction`, `adme_risks`, `safety_risks`,
  `resistance_mechanisms`, `biomarkers`, `combination_strategy`,
  `experimental_plan`, `go_no_go_criteria`, `evidence`, `contradictions`,
  `uncertainty`, `run_manifest`.
- **Typed sub-models** added to `canonical/schemas.py` (`TargetValidation`,
  `TPDTractabilityAssessment`, `E3Recommendation`, `TernaryComplexAssessment`,
  `DegradationPredictionSummary`, `ADMERisk`, `SafetyRisk`,
  `ResistanceMechanism`, `Biomarker`, `CombinationStrategy`,
  `ExperimentalPlan`, `GoNoGoCriterion`, `EvidenceBundle`, `Contradiction`,
  `UncertaintyDecomposition`, `RunManifest`); `STRATEGY_SCHEMA_VERSION =
  "TherapeuticStrategy.v1"`.
- **`decision.py`** populates every field from module results + shared engine
  state: measured/predicted separation (`claim_allowed`), explicit
  `go_no_go_criteria`, contradictions, uncertainty decomposition, and a
  `run_manifest` linking strategy → modules → evidence → versions.
- **Artifact**: `agents/runtime.run_protacpilot` writes
  `outputs/runs/<run_id>/therapeutic_strategy.json`; run record exposes
  `strategy_file`.
- **Tests**: typed-output coverage added (27 canonical tests total).
- Backward-compatible aliases (`recommended_candidates`, `e3_ligase`,
  `indication`, `recommended_experiments`, …) remain populated.

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
- Tests: +10 offline (protacxtend/tests/test_research_reporting.py); suite green.

### Module 1 — Hook Effect Modeler (`simulate_hook_effect()`)
- Mechanistic three-body equilibrium/QSP model in `protacxtend/modules/
  hook_effect_modeler/` (maps requested `protacxtend/modules/...` layout — the
  protacxtend distribution's code package is protacxtend).
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

New low-cost, production-ready retrieval+synthesis stack: `protacxtend/research/`
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
- New protacxtend/tests/test_deep_research.py — 18 offline + 1 network:
  dedup/merge, canonical URLs, scoring monotonicity, lexical rerank ordering,
  sufficiency/reformulation, no-fabrication verification, deterministic
  synthesis, full LangGraph run with stub clients (incl. reformulation loop),
  disk cache roundtrip, live EPMC search (network-marked).

## 2026-09-02 (pm) — Retrosynthesis toolkit engines: ASKCOS + AiZynthFinder + RDKit/OpenNMT

Three retrosynthesis engines are now integrated as **working toolkits** behind the
`run_retrosynthesis` stage (spec text: ASKCOS/MIT portal+Docker, AiZynthFinder
MCTS, RDKit+OpenNMT seq2seq workflows).

### New: protacxtend/tools/retrosynthesis_engines.py
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
- New `protacxtend/tests/test_retrosynthesis_engines.py` (18 offline tests):
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
   - NEW `protacxtend/tools/thread_limits.py`: `apply_thread_limits()`
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
- `python -m protacxtend.agents.runtime "Design CRBN PROTACs for BRD4 degradation"
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
- **`protacxtend/tools/learning_memory.py`** (590 lines): validated, structured learning DB.
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
- **`protacxtend/agents/learning_integration.py`** (240 lines): persist_run_learnings (auto-distills
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
- **Job queue**: protacxtend/queue/job_queue.py — redis (if available) /
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
- Canonical AgentRunRecord (protacxtend/run_records.py): run.json +
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
- protacxtend/tools/tack_degradation.py: inference (Morgan 1024 + descriptors
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

## 2026-09-23/24 — Manuscript strategy + source-verified literature package (outputs/manuscript_strategy/)

- Produced a source-verified literature & manuscript strategy per request: `outputs/manuscript_strategy/PROTACXTEND_MANUSCRIPT_STRATEGY.md` + `tables/{bibliography,competitor_matrix,claim_evidence}.md`.
- First-hand probe: `python -m protacxtend.cli --execution-mode scientific strategy "Design a VHL PROTAC against BRD4"` completes + emits typed strategy/manifest; **0 candidates** (demo warheads correctly filtered in SCIENTIFIC mode; live binder→warhead path not populating in the deterministic engine — the key gap for any "designed PROTACs" claim; agentic path documented to do live ChEMBL retrieval).
- Manifest runtime accounting bug reproduced (F-13: `finished−started`=0.004 s vs `runtime_s`=66.5; module_runtimes 0.0).
- Verified load-bearing literature first-hand (2026-09-23): PROTAC-DB 3.0 (NAR 2025, 10.1093/nar/gkae768; site now branded v4.0, no paper), TPDdb (NAR 2026, 10.1093/nar/gkaf996), DeepPROTACs (Nat Commun 2022, 10.1038/s41467-022-34807-3), DiffLinker (Nat Mach Intell 2024, 10.1038/s42256-024-00815-9), DeepTernary (Nat Commun 2025, 10.1038/s41467-025-61272-5), PROTAC-Model (J Med Chem 2021, 10.1021/acs.jmedchem.1c01576), P4ward (JCIM 2025, 10.1021/acs.jcim.5c00614), PRosettaC (JCIM 2020, 10.1021/acs.jcim.0c00589, PMID 32976709), Rovers/Schapira benchmark (JCIM 2024, 10.1021/acs.jcim.4c00426), PRosettaC>AF3 (Sci Rep 2025, 10.1038/s41598-025-21502-8), Biomni (bioRxiv 10.1101/2025.05.30.656746; Eval1=433 instances), TACK (KDD'26/arXiv 2605.19579), PROTAC-Bench (arXiv 2605.11764), vepdegestrant FDA approval (2026-05-01).
- Key positioning facts: degradation prediction plateaus at LOTO AUROC ≈0.67 / pDC50 R²=0.66 / Dmax R²=0.36 across all published methods (PROTAC-Bench/TACK) — M5 grouped-split results sit at ceiling, not above. No published end-to-end PROTAC-specific agent benchmark found as of 2026-09-23.
- Citation corrections flagged: (1) "PROTAC-Degradation-DB (arXiv 2406.02637)" is actually Ribes et al. "Modeling PROTAC degradation activity with ML" (ailsci 2024); (2) TACK venue = main KDD'26 proceedings, HF asset ships dataset not gated weights; (3) "MBMD" unverifiable — do not cite; (4) arXiv 2602.10163 withdrawn — do not cite.
- Not committed; review before use. NOTE: files written under outputs/manuscript_strategy/ (gitignored generated outputs).

## 2026-09-24 — Paper draft v0.1 (outputs/manuscript_strategy/PROTACXTEND_PAPER_DRAFT.md)

- Full manuscript draft: Title options, Abstract, Introduction, Results (workflow/modules/benchmarks/harness/ablations/case studies/negative results), Discussion, Methods, Data + Code Availability, and a 17-row manuscript-claims table (P01–P17) with file-level evidence and remaining experiments (F1–F8).
- Every quantitative claim re-verified 2026-09-23/24 against artifacts: module VALIDATION docs (M1 24/24 + MC 149.2 [142.0–156.9] nM; M4 n=64/32; M5 1,913 rows, unseen-PROTAC R2 0.605 vs 0.513, derived-active AUROC 0.894; M6 270 pairs, RF AUROC 0.9841 random/0.93 unseen-E3, −recruiter −0.517), BENCHMARK_RESULTS_V2 (Vina 2.356 Å, 0.375 [0.225,0.525]; pocket 0.381; PPI DockQ 0.0134; ternary bridging 0.0; MM/GBSA NOT_VALIDATED), benchmark500 (476/524/0; 500 real tool calls), parser gate (125, 1.0000), case-study JSONs (BRD4–VHL six: rank1 mol1 8.0; 1a46 run TIER_3).
- 10 explicit [RESULT REQUIRED] markers; no invented results; 48/48 "0.885" self-grade and random-split comparators explicitly excluded; no wet-lab claims (CS1 locked-but-unmeasured stated).
- Fixed redocking CI cells (GNINA/DiffDock ≤5 Å) to match source.

## 2026-09-24 — Challenge mapping: 10 PROTAC challenges × agent-tool architecture (challenge/)
- Probe run: `python3 -m protacxtend.backend.main --mode design "Design CRBN-based PROTACs for BRD4. Generate 10 candidates using PEG linkers." --stem challenge_probe` → 16 assembled candidates; verified per-candidate state (admet/ternary/e3context/degradation/novelty/AD rows).
- Built runnable scorecard: `challenge/experiments/challenge_scorecard.py` maps any workflow JSON candidate onto the 10 challenge dimensions with evidence levels (ml_model / rule_descriptor / geometry_stub / no_evidence). Verified: candidate SGA-VERIFIED-MZ1_st1 = 10/10 dimensions covered; only in_vivo_efficacy uses a trained-ML backend; ternary is geometry_stub; ADMET is rule/descriptor (ADMET-AI weights not bootstrapped here).
- Canonical artifact: `challenge/outputs/PROTAC_CHALLENGES_AGENT_TOOLKIT.md` — per-challenge table (hard problem → PROTACXtend files+probe evidence → third-party add-ons with URLs → agent behavior), best-practice agent graph (planner → specialists → cost-gated ternary/P4ward → retrosynthesis gate → Pareto → critic → human gates), P0/P1/P2 roadmap with exact file paths, and explicit requires_experiment limits.
- Key gaps recorded for next campaigns: Caco2/HIA/PAMPA not in ADMET_AI_KEY_ENDPOINTS; no microsomal-stability endpoint; neosubstrate/proteome-selectivity modules not wired into default scorecard; P4ward/PRosettaC/ASKCOS not run on shortlist in default mode.

## 2026-09-24 — Scientific-system closeout (zero-candidate fix, claims audit, gold draft, figures)

- Root-caused and fixed the scientific-mode zero-candidate defect (4 code defects, no filter relaxation):
  (1) warhead_agent ignored state.retrieved_binders; (2) binder-agent ChEMBL records missing needs_exit_vector_hypothesis; (3) e3_agent/toolbox passed real DOI-cited E3 rows without attachment markers (construction requires markers on all 3 components); (4) _load_local_binders leaked demo rows into scientific mode via source='local_curated'.
- Added provenance-tracked disk cache (data/live_cache/) + replay warnings + DOI-cited local warhead-table tier (protacSpace warhead.csv, BRD4 rows w/ DOIs) used only when live sources fail (ChEMBL was HTTP-500 during the session). Abstention behavior verified under outage (stage census in SyntheticInputNotAllowed).
- Identical case re-executed: 90 live ChEMBL binders -> 6 warheads -> 3 DOI-cited VHL ligands -> 17 linkers -> 300 assembled -> 150 valid -> 50 ranked (strategy_49bb27c13e.*; critic REVISE). E2E trace + before/after JSONs in outputs/manuscript_strategy/.
- Claims audit P01-P17 recomputed from raw artifacts (scripts/audit_manuscript_claims.py): M6 AUROC 0.9841/0.9295/0.9922/0.9318; Vina 2.356/0.375[0.225,0.525]; pocket 0.381; PPI 0.0134/0.0191 (n=48); harness 476/524/0 exact; ternary bridging median 0.0 (3/12 non-zero) -> paper corrected. 0.885 self-grade excluded everywhere.
- Gold draft: gold_48_objective_draft.tsv (19 objective tasks, machine-read, PENDING human); demo run KNOW-01/03+DISCOVER-01 (KNOW-01 now contains O60885) labeled machinery-only.
- 6 closeout figures generated from frozen tables (scripts/closeout_figures.py) + mermaid architecture.
- Tests: focused 144 passed; broad offline 1000 passed/14 failed (2 isolated failures pre-existing on HEAD: launcher-e, llm-layer).
- Deliverables: outputs/manuscript_strategy/closeout/CLOSEOUT_REPORT.md (+ e2e trace, claims audit, gold draft, figures). Blockers B1-B10 listed with the exact manuscript sentences gated by each.

## 2026-09-24 — P0 implementation: ADMET-AI permeability panel + 3 new tools + deep audit

- **ADMET-AI endpoint expansion (verified live, GPU):** `protacxtend/tools/admet_integration.py` `ADMET_AI_KEY_ENDPOINTS` 13→18 keys (+`Caco2_Wang`, `HIA_Hou`, `PAMPA_NCATS`, `Clearance_Microsome_AZ`, `Half_Life_Obach`) + `ADMET_AI_PERCENTILE_ENDPOINTS` + `_bRo5_flags_from_admet_ai()` (derived permeability/efflux/metstab/solubility/oral-F flags; AZ clearance flags percentile-driven because raw values are log-scale). Verified on probe candidate: Caco2 −5.55 log cm/s, PAMPA 0.41, HIA 0.97, P-gp 0.86 (percentile 91.8), half-life 77.4 h, AqSolDB −5.10, DILI 0.98 (pct 96.7). 104 endpoints available in ADMET-AI 2.0.1.
- **New tools (registered + CLI):** `tools/challenge_scorecard.py` (10-dimension typed evidence levels + aggregate + optional live `--enrich-admet`), `tools/feynman_summary.py` (deterministic TL;DR/brief, candidate+campaign), `tools/literature_synthesis.py` (bounded deep-research anchors; blocked-on-failure). RegistryTool entries `challenge.scorecard`/`summary.feynman`/`literature.anchors`. New CLI: `protacxtend scorecard --json <wf.json> [--candidate ID] [--enrich-admet] [--literature Q] [--dimensions a,b,c] [--out p]` + `--literature-only`.
- **Verified:** `--enrich-admet` lifts scorecard coverage from 1/10 → 5/10 trained-ML rows (probe2, candidate SGA-VERIFIED-MZ1_st1); literature anchors returned 3 real DOIs with claim verification (6/9 unsupported, honest); fresh deterministic design run intact (10 valid candidates, top 0.759). Tests: 12 passed (`tests/test_challenge_scorecard.py` 4 new + toolkit registry/status).
- **OpenADMET truth recorded:** installed = `openadmet-models` 0.2.0 training framework, partially broken (missing `class_registry`), no `load_model` prediction API; live code does not depend on it (old build/lib import obsolete). ADMET-AI is the working ML backend.
- **Audit doc:** `challenge/outputs/TOOL_AUDIT_10_CHALLENGES.md` (per-challenge files/functions/backends/live evidence/gaps + open/needs-engine/needs-wet-lab verdict matrix). Remaining gaps: P4ward/PRosettaC/DeepTernary not run (Docker present), retrosynthesis engines unprovisioned (AiZynth assets staged), neosubstrate/proteome modules not wired into default scorecard, chameleonicity not in default run.

## 2026-09-24 — Executed PROTAC design walkthrough (BRD4 × CRBN) + main-env ADMET-AI + plots
- Verified `admet_ai 2.0.1` imports and runs directly in the MAIN env (GPU, 5.8 s load) using the `.venvs/admet` model weights (`ADMETModel(models_dir=...)`) — no duplicate install, no torch conflict (main env torch 2.10). Used live for PROTAC analysis.
- `challenge/experiments/design_analysis.py`: top-N candidates → live ADMET-AI enrichment (endpoints + bRo5 flags) → 10-dim scorecards → 2 plots (evidence maturity bar; log DC50 vs Caco-2) → analysis.json. Verified on `design_demo` run (26 assembled, top score 0.766).
- Key finding: all top-5 candidates P-gp-efflux high + DILI 0.93–1.00, Caco-2 −5.1..−5.6 — bRo5 wall quantified; generative-linker candidate (gen_5) best perm/metstab compromise but DILI 1.00.
- Literature anchors for ternary/permeability returned COMPASS (ChemMedChem 2026, 10.1002/cmdc.70385) + 2 papers with index-mismatched DOIs (Gadd 2017 Nat Chem Biol canonical 10.1038/nchembio.2329; KLHDC2 Nat Commun 2024) — recorded honestly; next step: Crossref DOI normalization in literature_synthesis.
- Walkthrough artifact: `challenge/outputs/HOW_TO_DESIGN_A_PROTAC.md` (10-step recipe + executed run + scorecard + findings + next steps + plots + literature + limits).
- E3-ligase-library (600+) task still OPEN: UniProt stream API verified reachable (GO:0004842×9606), design ready, build pending.
- REINVENT status: Link-INVENT prior assets exist under SynGlue_Py/repos/reinvent/models/linkinvent.prior; requires separate REINVENT v3 env — not provisioned; documented as open.

## 2026-09-24 (late) — Evidence-driven reporting, blocker execution, field-ceiling slice

- NEW protacxtend/reporting/ (run_record.py, reporter.py, landscape.py, build_record.py) + CLI `protacxtend report --strategy|--manifest|--trace` and `protacxtend landscape [--record ...]`.
  - Run record: EvidenceRunRecord.v1 (question, inputs, tool_calls w/ version/params/output/error/timestamps/sources/artifacts, final output, raw JSON preserved, provenance, validation). Reports: plain summary (default stdout), technical.md (methods/numbers/units/provenance/limitations/intermediate files), CSV tables (tool_calls/candidates/degradation/evidence), raw_strategy.json preserved beside run.json.
  - Landscape M1-M12: rubric-gated scores only (level 0-6), evidence file + reviewer + date + reason recorded; unassessed unless evidence filed; coordinates deterministic + sha256-pinned; `M9` and `M12` unassessed; M10/M11 provisional level-3.
  - Verified on 3 real runs (BRD4 success; BTK partial: 1 warhead, E3 mismatch CRBN-vs-requested VHL + request=None fidelity wrinkle recorded; NONEXISTENTGENE123 missing-evidence abstention): scripts/verify_report_traceability.py all checks pass (summary==record==raw; tool calls cover modules; landscape reproducible, pinned hash matches).
- B1: froze gold protocol (19 objective tasks; PENDING_HUMAN), 19 blinded adjudication sheets + separate GT keys; machinery runs on 6 agent tasks (KNOW-01..05, DISCOVER-01) with abstention policy (13 abstained), Wilson CI, empty-answer baselines; NEVER presented as passed (gold_draft/B1_results_machinery.md).
- B6 security: safe_io.py allowlisted loader; shell=True x3 -> arg lists; pickle.load x4 -> safe_pickle_load; tests/test_closeout_g12_b10.py (7 tests) + admet/mode/outcomes => 32 passed.
- B3 field-ceiling slice executed: TACK DC50 subset scaffold-cluster 5-fold RF pDC50 R2~0.63/RMSE~0.74 vs published 0.66/0.633 (scripts/field_ceiling_audit.py; closeout/field_ceiling_audit.json); paper Discussion updated with the sentence.
- Invalid-assembly audit: 300 assembled -> 150 valid (RDKit-validity + duplicate elimination per validate_candidates); all 25 strategy candidates parse and carry hypothetical_exit_vector_requires_chemist_review; E3 attachment markers + capped confidence verified; live-source variance re-demonstrated (BindingDB monomers, smiles_ok=false -> 0 assemblies on a rerun) [B5 evidence].
- Figures regenerated purely from frozen artifacts (M5 table regex-parsed from VALIDATION.md; fallback parsed from V2 md; harness from predictions.jsonl; demo scores from pilot JSONs).
- closeout additions: BLOCKER_REGISTER.md (B1-B10 owner/artifact/criterion/evidence/manuscript impact), SENTENCE_DECISIONS.md (retain/qualify/remove per sentence with artifacts + failing gates), field_ceiling_audit.json, invalid_assembly_audit.json, updated CLOSEOUT_REPORT pointers.

## 2026-09-24 — Comparison-only enforcement + SYNTHESIS + next-experiment gate

- run_quarantine.py: added run_status (INVALID/COMPARISON_ONLY/OK), citation_claim (precise, replaces bare citeable bool), serve_payload (single source for TUI/API/search/reports/ENGRAM), comparison_only detection from manifest role/scientific_evidence.
- TUI handle_report: corrected replay now returns status=comparison_only + banner; response fields sourced from the run record (run.json else manifest.json), not report.md.
- API: GET /runs/{run_id} serves classification + record (fallback manifest/corrected_run).
- Search: _find_candidate_record flags comparison_only rows with precise claim; invalid runs skipped.
- Reports: `protacxtend report` prints citation_claim.
- ENGRAM/cognitive bridge: ingest guards non-OK runs with quarantined/comparison_only reasons.
- SYNTHESIS.md (corrected run) + stage-by-stage audit with persisted-evidence links; quote boundary = reference reconstruction only.
- NEXT_EXPERIMENT_VERIFIED.md (BRD4-VHL run): verified + corrected pending protocol (dose/time/VHL-dependence/proteasome/epimer controls); status PENDING, no results.
- Tests: tests/test_run_quarantine.py 15 passed (all five surfaces); closure+fault-injection combined 43 passed.

## 2026-09-24 (final) — test isolation fix + verification sweep
- tests/test_closeout_g12_b10.py rewritten to scope execution mode via `modes.execution_mode()` context managers (a global-mode leak from an earlier fixture version polluted test_execution_modes.env-default; root cause: ContextVar + reset(token) semantics).
- Verified combined: tests/test_closeout_g12_b10 + gate_b + canonical + execution_modes + mode_router + scientific_outcomes + agent_tool_exposure = 105 passed, 0 failed.
- Re-ran claim audit + report traceability + landscape reproducibility after all changes: PASS (pinned hash 044c439229cd5bcf).

## 2026-09-24 — Researcher-facing explanation pipeline (typed answer record)

- New package `protacxtend/explain/`:
  - `answer_record.py` — ExplanationAnswer.v1: direct_answer, established_facts (evidence-linked), mechanistic interpretation with causal chain (binding → ternary → ubiquitination → degradation; each step measured|computed|hypothesized|unavailable + measurement_context in_this_run|literature), missing links, alternative explanations, next discriminating experiment, status, mode (KNOW/REASON/DESIGN/DISCOVER), citation claim, artifact IDs.
  - `builder.py` — builds the answer ONLY from persisted run records (run.json, evidence.jsonl, provenance.json, manifest/corrected_run); invalid runs → invalid_error with zero facts; comparison-only replays → comparison_only; facts restricted to validation_state=valid; downstream steps never upgraded by chemical validity/ranking.
  - `renderer.py` — concise default + expandable Why / Evidence / What could be wrong / Next experiment; plain and technical variants of the same conclusion; DESIGN technical block (target/E3 identity, product SMILES/InChIKey or exact missing-input brief, component + attachment provenance, funnel, outcome class).
- Surfaces: TUI `handle_explain` (emits typed answer + rendered sections), API `GET /runs/{run_id}/explain`, CLI `protacxtend explain --run <id> [--section concise|plain|technical|why|evidence|wrong|next]`.
- MZ1 control verified: says KNOWN reference reconstruction, links 5T35/DOI structural evidence, marks literature DC50/Dmax (8 nM/98%, HeLa 24h) as measured(literature) and NOT measured in this run, ubiquitination hypothesized, proposes discriminating PENDING experiment.
- Tests: tests/test_explanation_pipeline.py — 9 case-based checks (KNOW answerable, REASON conflicting, MZ1 reconstruction, missing-attachment design brief, invalid run, no-inference-from-validity guard, TUI/report/API parity, comparison-only labelling). 38 passed with run_quarantine + scientific_closure.
- Example rendered answers: outputs/explain/examples/{mz1_reconstruction,comparison_only_replay,invalid_historical,know_answerable,design_missing_attachment,reason_conflicting}/ (answer.json + concise/plain/technical.md) + INDEX.md.

## 2026-09-24 — Run-ID separation; malformed-regression claim; MZ1 SYNTHESIS; search default

- run_quarantine: CLAIM_CORRECTED_REPLAY = "comparison-only malformed-input regression; no candidate or scientific result." reserved for run_e4e21ccd_corrected_v1 (and any manifest-described malformed-input regression); CLAIM_MZ1_RECONSTRUCTION reserved for run_brd4_vhl_scientific_v1; citation_claim() is per-run and never conflates the two IDs.
- MZ1 run: structure/sources re-verified (InChIKey PTAMRJLIOCHJMQ-PYNGZGNASA-N, C49H60ClN9O8S2; measured warhead/E3 records w/ DOIs; calculated InChIKey match; measured literature DC50 8.0 nM/Dmax 98% w/ model predictions explicitly unavailable; MT-802 rejected). SYNTHESIS.md written (evidence-linked answer, mechanistic limits, contradictory/missing evidence, pending next experiment).
- Corrected replay: SYNTHESIS citation boundary changed to malformed-input regression (no reconstruction; no candidate evidence).
- Scientific search (agentic/registry._find_candidate_record): excludes invalid AND comparison-only runs by default; include_comparison_only=True opt-in flags rows for audit only.
- Explanation builder: comparison-only direct answer mirrors the malformed-regression claim; MZ1 direct answer uses the reserved reconstruction wording.
- Tests updated/added (search default exclusion + opt-in; MZ1-only reconstruction claim; neither invalid nor comparison-only citeable as reconstruction/evidence; MZ1 structure/source verification; MZ1 SYNTHESIS presence; claim text parity). Full run: tests/test_explanation_pipeline.py + tests/test_run_quarantine.py + tests/test_scientific_closure.py -> 42 passed.

## 2026-09-24 — Explanation: render_status vs scientific_outcome split; MZ1 evidence audit

- answer_record: ExplanationAnswer now splits render_status (ok/comparison_only/invalid_error/error) from scientific_outcome (reference_reconstruction/distinct_candidate/design_brief/abstention/conflicting_evidence/missing_evidence/comparison_only/invalid/unassessed); status kept as backward-compat alias.
- builder: comparison-only branch no longer injects RECONSTRUCTION classification (replay mode=DISCOVER; claim and direct answer say "comparison-only malformed-input regression; no candidate or scientific result."); a rendered design brief now yields render_status=ok + scientific_outcome=design_brief with direct answer "not a completed design and not a candidate"; design block outcome synced.
- CausalStep gains exact_evidence (molecule, domain/isoform, assay, cell context, time, metric, unit, value, source_record, distinguish) + measured_in_this_run; MZ1 audit table keyed to 5T35 (BRD4 BD2 crystal; Gadd 2017) vs formation measured in this run (explicitly NOT), binding BD1/BD2 (Zengerle 2015), degradation HeLa/24h/8.0nM/98% (PROTAC-DB, 10.1021/acs.jmedchem.6b01912) all source-cited, never in-run.
- renderer: technical view now emits per-step "Exact-evidence audit" block; concise header shows render+outcome.
- Tests: render/outcome splits, no-inherited-reconstruction (mode != DESIGN, claim free of "reconstruction"), design-brief never "completed design", MZ1 audit assertions (domain/cell/time/metric/unit/source + 5T35-vs-formation distinction), TUI/API parity on render_status/scientific_outcome. 42 passed (explanation_pipeline + run_quarantine + scientific_closure).
- Examples regenerated: outputs/explain/examples/{mz1_reconstruction,design_missing_attachment,comparison_only_replay}/…

## 2026-09-24 — /plan target-understanding fix (deterministic planner)

- Root cause: Node TUI /plan routed free text to the LLM chat agent (tui/src/app.ts:435-438 -> handle_chat -> ConversationalAgent); blanket gate chat_agent.py:64-65 ("if target or E3 is ambiguous ... return clarification first") + model clarification action (chat_agent.py:176-184) produced freeform questions ("what does EFRG mean", "EGFR or EFRG?", "preferred E3"); no canonical resolution, no session correction, unspecified E3 blocked.
- Fix: new protacxtend/planning/planner.py — intent parsed separately from entities; canonical resolution (curated table + reviewed UniProt) returning symbol/UniProt/species/aliases/method/confidence; typo suggestion only when unresolvable (never silent conversion, never ambiguous auto-pick); session-persisted target with "latest explicit correction wins" (unresolved EFRG discarded); decision-rule clarification (only blocking inputs ask; unspecified E3 -> "to be evaluated"); E3 ranking evidence from packaged measured context (target-specific precedent); abstains specific E3 recommendation when no target precedent exists; /plan emits interpretation line then target/binders-warheads/E3/linker-exit-vector/validation evidence, citing only retrieved sources.
- Surfaces: tui_bridge handle_plan + "plan" command (PROTACXTEND_PLANNER_OFFLINE env supported); Node TUI /plan -> ask("plan",...); next free-text after a pending plan clarification routes to plan (conversationId "tui-default"); tsc clean.
- Tests: tests/test_plan_dialogue.py (10 tests) — exact two-turn exchange, /plan EGFR protac, aliases (HER1/ErbB1/ERBB1), ambiguous (BRD), unknown (ZZZZ9), valid->valid correction (BRD4->GSPT1); asserts EGFR cases proceed without "what is EGFR" or E3 demand. 10/10; with explanation+quarantine+conversational suites: 32/32 passed.

## 2026-09-24 — Request-understanding rebuild (all research commands, starting /plan)

- NEW protacxtend/request/ package: model.py (shared RequestUnderstanding: raw text preserved, target mentions, organism, mutation/isoform, supplied ligands, constraints, delegated choices; E3 modes explicit|delegated|unspecified), resolver.py (tool-backed: accession direct path, curated-then-reviewed-UniProt within organism, alias/protein-name search, alternatives + match types, fuzzy=suggestion only, versioned local cache data/request_cache/ with live-vs-cache reporting, organism guard so the human curated table never serves mouse/rat requests), parser.py (raw-token parsing; fixed the first-token-stripping bug that silently dropped targets on corrections/aliases; mutation regex; named-E3 tokens excluded from POI mentions in recruiter context), decision.py (ask only when a missing fact changes the entity/workflow: verified->proceed; one fuzzy->precise 'did you mean X' question, never auto-converted; several->question listing candidates; unknown->one exact-symbol question; delegated/unspecified E3 = research task, never blocking), corrections.py (session state; latest explicit correction replaces the unresolved slot, clears pending clarification, resumes original action, logs state before/after), controller.py (bounded reasoning: model may interpret/propose; tools verify; controller decides continue/ask/limitation; plan reaches evidence stages labelled observed/computational/missing and never invents an E3 recommendation).
- planner.py rewired onto the controller (bridge contract preserved: plan_answer kinds, interpretation line, evidence_steps with has_evidence); tui_bridge handle_research routes investigate/reason/compare/design/optimize/structure/selectivity/degradation/admet/synthesis/experiment/evidence/run through the same understanding layer; new CLI `protacxtend understand [--action] [--offline] [--json]`.
- Verification: tests/test_request_understanding_e2e.py (21 scenarios: symbols, accessions, aliases, misspellings, ambiguity, unknown, nonhuman, mutations, explicit/delegated/unspecified E3, corrections after clarification with state-before/after, provenance, workflow-reaches-retrieval, shared understanding across commands) + all 10 existing dialogue tests = 48 passed with gate-b + g12 suites. Live checks: mouse BRD4 -> Brd4 Q9ESU6 via UniProt live; accession O60885 live -> cache replay reports uniprot_cache; bridge two-turn EFRG->"EGFR target of interest..." -> clarification then plan_ready (resolved P00533), EFRG cleared, state transition logged.
- Transcript artifact: scripts/record_request_conversations.py -> outputs/manuscript_strategy/request_conversations/transcript.md + conversations.jsonl (13 records; headless screenshot-equivalent of the reported exchange).
- Key design rule (implemented): model reasons about what to investigate; verified identifiers and evidence come from tools; the controller decides whether enough is known to proceed. No EGFR-specific rule, no spelling-correction patch.

## 2026-09-24 — /plan regression fixed (stale compiled TUI routed /plan into chat)

- Faulty condition: tui/dist/app.js was stale (built 14:24 vs src 16:03) and ran the old /plan handler `handleChat("Build an evidence-grounded research plan for: " + args)` — the general chat clarification gate intercepted, emitting kind=clarification -> events.ts renders "CLARIFICATION NEEDED". The plan bridge (handle_plan -> plan_request) was never reached; EGFR (P00533, curated_table, verified) never got a chance to bypass.
- Fix: rebuilt tui/dist with tsc from the corrected src (dist/app.js now routes /plan -> ask("plan", ["plan_answer","plan_complete"]) and sets pendingPlanClarification; old chat-intercept string count = 0).
- Boundary asserts: verified target bypasses target clarification (test_verified_target_bypasses_pending_clarification_in_same_session); missing preferred_e3 -> "to be evaluated" + e3_evidence stage, never clarification (existing tests + plan payload); pending plan preserved when user answers a genuine clarification (EFRG->EGFR two-turn test).
- Regression guard: test_shipped_tui_routes_plan_to_planner_not_chat rebuilds dist and asserts compiled routing (planner path present, chat path absent).
- Results: python -m pytest tests/test_plan_dialogue.py -> 12 passed; cd tui && npm test -> 57 passed/0 failed; first planning result for EGFR: plan_ready, "Target: EGFR [P00533]; objective: PROTAC strategy; E3: to be evaluated."

## 2026-09-24 — /plan -> goal-driven investigation planner; command contracts

- /plan now returns an EXECUTABLE INVESTIGATION PLAN (protacxtend/planning/goal_planner.py) on top of the shared request layer (protacxtend/request: parser/resolver/decision/corrections/controller):
  - deterministic target resolution stays the entry step (curated table -> supplemental map -> reviewed UniProt; aliases; ambiguity lists; fuzzy = suggestion only);
  - interpreted objective + assumptions; per-task why_for_this_request; inputs/outputs/dependencies/evidence gates; explicit branches with triggers (pass/fail); executor = /investigate T<n> / agent:<role> / /design / /report;
  - tools and data sources dynamically probed (34 ready agent tools + packaged data files) and reported in toolkit_discovery — plans are constructed from objective+toolkit, not a template (asserted by EGFR vs KRAS differing on binder census, E3 precedent, structures);
  - plan NEVER executes compound design and NEVER presents a design result (executed_design=False; no candidates payload).
- /investigate executes one evidence task and writes outputs/plans/<plan_id>/artifacts/<task>.jsonl; unavailable/failed tools emit kind=open_question + revised_plan (never a fabricated result).
- Command contracts: /plan decides; /investigate gathers/evaluates; /design generates/assesses; /report summarizes (boundary tests).
- KRAS plan shows biological differentiation: no curated record (supplemental map P01116), no packaged binders -> covalent/allele-specific ligand question (sotorasib/adagrasib DOIs), no E3 precedent -> exploratory + abstained recommendation, no structures -> AlphaFold/predicted structural question; plan_with_open_questions.
- Tests: tests/test_plan_dialogue.py rewritten (15 tests: two-turn exchange, /plan EGFR protac contract, capability trace determinism, EGFR vs KRAS differentiation, aliases/ambiguous/unknown/correction, E3 delegation never blocks, unavailable-tool -> revised plan, /investigate unavailable -> open_question, command-contract boundaries). Combined targeted suites: 52 passed.

## 2026-09-24 — Mechanistic diagnostics milestone (EGFR end-to-end)

- /plan is now an evidence-driven task graph: protacxtend/planning/tasks.py (mechanistic question, tool+input, expected artifact, evidence required, branches positive/negative/conflicting/unavailable) embedded in InvestigationPlan as tasks_graph; plan_difference explains why EGFR's plan differs from GSPT1's (18 measured rows + 500 count-only binders vs no precedent).
- Shared causal evidence record: protacxtend/planning/causal.py — 6-step chain (engagement -> E3 recruitment -> ternary -> ubiquitination -> proteasome loss -> phenotype/selectivity), each item tagged measured/computed/inferred/proposed/missing with compound/variant/cell/dose/time/endpoint/source; validation stage label corrected computational -> proposed (PENDING).
- Diagnosis engine: protacxtend/planning/diagnose.py + bridge handle_diagnose for /reason /experiment /optimize. Strong-binding/absent-degradation EGFR case -> H1 ternary impaired / H2 permeability / H3 E3-ubiquitination, each with evidence for/against; single discriminating measurement (ternary engagement + cellular uptake) with per-result next actions; linker change explicitly gated (never before diagnosis). Tests flip observations and assert next action changes (not stage names).
- Row-level evidence audit: protacxtend/planning/row_audit.py — 18 EGFR rows with record IDs/DOI/cell/assay/dedup(unique smiles|e3|cell|doi), 10 usable for a VHL objective; 500-binder count flagged count-only (no row sources in package) -> retrieval task, counts never pass gates.
- UniProt: data/uniprot/P00533_EGFR_HUMAN.json (EGFR_HUMAN, 1210 aa, Homo sapiens) fetched via REST API.
- TUI build is part of release/startup: tui/package.json prestart=node scripts/ensure-dist.mjs; tui/scripts/ensure-dist.mjs rebuilds dist when src is newer; launch.sh + distribution_smoke.sh invoke it and node --check dist/app.js; regression test rebuilds dist and asserts planner routing (no chat interception).
- Tests: tests/test_mechanistic_milestone.py (8), plan_dialogue (15), explanation (12), quarantine (15), closure (14) = 64 passed. Trace: outputs/manuscript_strategy/closeout/mechanistic_milestone/trace.json.

## 2026-09-24 — Code-backed technical atlas (docs/architecture/)

- Verified every headline count with live probes: workflow nodes 34 (prev displayed 31; +design_path, capability_answer, reasoning_answer), LLM-callable tools 34, external toolkit registry 115 (30 callable), scientific backend capability classes 19, TPD capability classes 27 (20 ready), catalogued functionalities 108 (12/11/44/15 + 26 CROSS) vs E1-executed adapters 12/7/9/6. Non-addable denominators documented.
- scripts/build_technical_atlas.py writes docs/architecture/tables/*.csv (+sha256): workflow_nodes(34), agent_tools(34), toolkit_tools(115), scientific_backends(19), tpd_capabilities(27), functionalities(108), crosswalk(34), dataflow_edges(26). Every name re-verified against its registry.
- PROTACXTEND_TECHNICAL_ATLAS.md: system map (function/class/file per arrow), complete inventories, crosswalk + 12/11/44/15 reconciliation, pillar depth with evidence levels and next experiments, agent core (memory/retrieval/provenance/self-healing/contamination safeguards), three real traces (A /plan EGFR + /investigate T3; B MZ1 reconstruction; C unavailable-evidence/ChEMBL-outage/comparison-only), 7 Mermaid diagrams + existing SVGs, claim/gap audit (B1-B10, F/G) with prioritized repairs and manuscript claims, corrected figure data + replacement text, one-page summary. alphaXiv added to tool inventory (login-gated this session).
- Trace dossiers: docs/architecture/traces/TRACE_{A,B,C}*.md + raw JSON.

## 2026-09-24 — 14-command mechanistic research system (evidence-gated)

- Shared evidence graph: protacxtend/evidence/graph.py — claim kinds observed/computed/inferred/proposed over 9 axes (target_engagement, e3_recruitment, ternary_formation, ubiquitination, degradation, cellular_context, selectivity, exposure, synthesis); provenance/tool+query+source_ids/artifact mandatory (fabrication guard); assay context, uncertainty, conflicts; degradation kind=observed rejected (wet-lab only).
- Command contracts (14 distinct scientific questions + output schemas; overlap guard): workflows/contracts.py + classify_goal + build_goal_plan — goal-typed DAG with capabilities resolved from the toolkit, dependencies, evidence gates, alternatives, effort, artifacts. EGFR vs KRAS-G12C plans differ in node set AND dependency map (mutation_context + allele_specific_binder_search + target-specific notes); optimize/investigate/design on the same target give 3 different signatures. /plan never executes design.
- Per-command implementations: investigate (binder census + measured precedent + E3 families into evidence graph), reason (6 competing hypotheses mapped to axes; every hypothesis inferred; discriminating tests), compare (RDKit descriptors, computed-only), optimize (series CSV → exposure proxies + ternary-loss risk; measured/computed/inferred labels), degradation (endpoint predictions labeled predicted; OOD flagged), admet (risk flags; PK out of scope), synthesis (engine status, honest availability), experiment (protocol with mandatory controls), evidence (graph query incl. empty-reported-empty), structure (honest tool_failed: ternary_engine module absent, DockQ NOT_VALIDATED stated), design (routed only: deterministic engine exists, api branch pending).
- /run executor (workflows/executor.py): topological DAG execution with real tools (binder retrieval, degradation endpoint, admet); replans on Dmax<60%/OOD and failed tools with alternatives (demonstrated: aspirin candidate → Dmax 39.7% + out_of_domain + ternary missing → completed_with_replan, 2 replans). Trace persisted; evidence graph per run.
- CLI: protacxtend workflow <command> "<input>" [--series/--smiles/--offline/--json]; bridge handle_research dispatches per-command.
- E2E: scripts/e2e_mechanistic_cases.py -> outputs/manuscript_strategy/mechanistic_cases/CASES_REPORT.md + traces/ (plan EGFR vs KRAS G12C, reason, optimize series, run re-plan), machine log cases_log.json.
- Tests: tests/test_workflow_contracts.py (12): contract overlap guard, plan diversity (not template), no-design-execution, fabricated-evidence guard, degradation-never-observed, predicted labels, reason inferred+tests, experiment controls, run replan. Combined 48 passed with request-understanding + dialogue suites; the original 119 remain the request-understanding/gates bucket.
- Audit: outputs/manuscript_strategy/closeout/COMMAND_AUDIT.md — 14-row table (status working/exercised vs implemented-unverified vs routed-only vs missing; code location; next task) + honest classification: 12 exercised, structure implemented-but-unverified (backend missing), design routed-only. Not calling the 14 complete.

## 2026-09-24 — Benchmark verification (code-backed counts + executed runs)

- Verified every benchmark count from on-disk artifacts with commands: 48 cases/48 GT (types 5/10/20/4/9), FREEZE_MANIFEST 2A.1 100/100 (assert_frozen OK), SCORABLE_MANIFEST 48/48 auto + 29 expert + 0 not-scorable, gateC gold 48×PENDING_ADJUDICATION, benchmark500 1000 tasks (500+500, sha-pinned), probe 476 executed / 524 abstained / 0 failed (replayed identical), capability run 500 real calls, tpdeval validate_taxonomy OK (500/16 domains/300+150+50, stress 100), closed48_v3 144 runs (state-stable 48/48, hash-stable 42/48). 0.885 offline self-grade excluded (circular).
- Ran this session: freeze integrity OK; fresh deterministic pilot KNOW-06/REASON-03/REASON-05/DISCOVER-04 → 0.0/0.0/0.0/0.5 (mean 0.125, real execution, machinery-graded); benchmark500 score+report replay regenerated identically (general 50.0%, temporal 45.2%); tpdeval validator.
- Finding: deterministic engine under-scores KNOW/REASON (design-first routing; F-02 class) — matched retrieval/LLM path is the required P1 repair before any correctness display.
- Deliverable: docs/architecture/BENCHMARK_VERIFICATION.md (counts table, definitions/overlaps, run outputs, corrected figure text, artifact paths).

## 2026-09-24 — Benchmark run + genome-scale E3 resolver (Biomni-level push)

- B1 benchmark (frozen 19-task objective gold): 12 tasks executed end-to-end via the real bridge/planner routing (KNOW-01..08, REASON-03/05, DISCOVER-01/04; latest-run dedup), 7 abstained (protocol: excluded from mean). Results: mean 0.188; correct(>=0.5) 4/12 Wilson95 [0.138,0.609]; per-capability KNOW 0.156 (n=8), REASON 0.000 (n=2), DISCOVER 0.500 (n=2). Honest negative: the deterministic engine is design-oriented and under-scores KNOW/REASON (LLM path required). Gold remains PENDING_HUMAN; machinery-only. Artifacts: outputs/benchmark_run_b1/{results_aggregate.csv, summary.json, figures/fig_b1_*}.
- Genome-scale E3 resolver: data/e3_catalog_v2.csv (391 genes = 374 UniProt GO:0061630 reviewed human + module-6 + curated rows), data/e3_cell_context_stats.csv (377 genes x median/p75/p90/breadth/top10 lines over 1,673 DepMap 24Q4 lines); protacxtend/tools/e3_resolver.py (resolve_e3 with aliases, unresolved guard, cell-context card); scripts/build_e3_catalog_v2.py + scripts/e3_catalog_report.py; plots in outputs/e3_catalog_report/ (top20 median, breadth, exemplar depth, sources). Resolver checks: CRBN Q96SW2, VHL P40337, DCAF15 Q66K64, KEAP1 Q14145, MDM2 Q00987, RNF114 Q9Y508, BIRC3 Q13489 all resolved w/ 1673-line context; unknowns unresolved.
- Cain/note: family/mode fields in catalog v2 are currently unclassified (module-6 csv header mismatch) — to enrich next iteration; ~600-count in E3Atlas includes adaptors beyond the GO-annotated 374.

## 2026-09-24 — Clarification-loop control-flow fix (bridge-level, real qwen2.5:7b)
- Reproduced the five transcript CLARIFICATION exchanges through the REAL TUI bridge (server.handle_plan/handle_research/handle_chat). First incorrect transition: exchange 2 (/plan BDR4 protac) — single-candidate distance-2 typo looped ("never auto-converted"); second bug: '/plan BRD4 in mice' parsed 'mice' as target and downgraded canonical BRD4 to unknown.
- Fixes (control-flow, not prompt phrases): resolver constrained-typo tier (≤2 edits, single candidate → tentative auto-resolve w/ assumption; weaker fuzz still asks); organism words excluded from target tokens (parser); primary-target selection by resolution-quality rank (controller); only genuinely-unresolved mentions kept (corrections); non-human canonical symbols → live UniProt ortholog first, tentative human-ortholog fallback; new /design branch in workflows/api.py with E3 OPTIONAL + evidence comparison (precedent rows + DOI-cited ligand families + cell-context limitation) + executed_design=False; bridge handle_chat injects resolved-session context, bare recognized target → deterministic target card (planning/target_card.py), LLM clarification cannot override a resolved target+runnable workflow (clarification_overridden=True fallback); InvestigationPlan clarifies surface target; reset_session pops tuple-keyed controllers.
- Verified offline: 64 tests, incl. tests/test_bridge_regression.py (15 deterministic bridge tests: five exchanges + HER1/ERBB1/ambiguous/unknown/correction BRD4→HER1/mice/design E3-optional/bounded investigate) + 1 real-LLM test (qwen2.5:7b: post-/plan BRD4 chat returns kind=answer, never clarification). Live mouse ortholog check: BRD4@Mus musculus → Brd4 Q9ESU6 verified (uniprot_live).
- Artifacts: challenge/outputs/CLARIFICATION_LOOP_FIX.md, pre_fix_trace.json, post_fix_tui_transcript.md; scripts challenge/experiments/{trace_pre_fix,transcript_post_fix}.py.

## 2026-09-24 — KNOW/REASON routing + evidence-use repair; adjudication packet; hash audit

- Verified inventory: docs/architecture/BENCHMARK_VERIFICATION.md (48 cases/GT, freeze 100/100 OK, scorable 48/48 + 29 expert, gold 48×PENDING, 1000-task 476/524/0, tpdeval 500 OK, closed48_v3 144 runs).
- Root cause (traced KNOW-06/REASON-03/REASON-05): design graph halted on resolution/design-terminal stop markers because route capability never reached design_plan.structured_seed; graded answer was a design-strategy JSON; no KNOW/REASON evidence surfaced.
- Repair (smallest, general): graph KNOW/REASON routes now include capability_answer/reasoning_answer; run() propagates capability into structured_seed and skips design-terminal stop markers on retrieval routes; runtime honors config["capability"] + detects fallback; pilot passes case capability, surfaces scientific_answer, and ABSTAINS when KNOW/REASON evidence is absent or off-topic (relevance gate over grounded content, immune to question-echo).
- Before/after four-case pilot (identical frozen tasks, full traces in docs/architecture/benchmark_traces/four_case_{before,after}.json): KNOW-06 0.0→abstained; REASON-03 0.0→0.0 (grounded, rubric-incomplete); REASON-05 0.0→abstained; DISCOVER-04 0.5 unchanged. Baselines: empty 0.0/0.0/0.0/0.5; retrieval-only 0.0×3; engine-before 0.0×3+0.5; after = 3 abstentions + 0.5.
- Six hash-unstable cases audited from retained closed48_v3 rows: DESIGN-03 (32/34/40), DESIGN-06/12 (36/36/38) via stochastic char-GRU linker sampling (all hypothetical, 0 verified); DESIGN-01/02/05 vary only in assembled-count text (17/18/20). State-stable 48/48; hash-stable 42/48.
- 48-case adjudication packet generated (docs/architecture/adjudication_packet/): 48 blinded sheets + separate key + INDEX; status PENDING_ADJUDICATION; machine answers marked provisional (derived overlays).
- Report: docs/architecture/BENCHMARK_REPAIR_REPORT.md (per-instrument, provisional-vs-signed-gold, per-case failure table with missing adapters, reproduction commands). No new benchmark cases; no benchmark accuracy advertised.
- Regressions: 61 passed (plan_dialogue + explanation + brd4 case + canonical stack).

## 2026-09-24 — TargetTherapeuticsAssessment (typed pre-design stage)

- New protacxtend/therapeutics/{record,evidence,decision,api}.py: TargetTherapeuticsAssessment.v1; five evidence blocks (disease / dependency / normal_tissue / binder_structure / e3_opportunity) with tier discipline (genetic_association vs curated_template; dependency functional-only; expression never implies ligase activity). Open Targets + HPA live adapters attempted (DNS-blocked on this host -> recorded unavailable with experiment_to_change); DepMap dependency matrix absent in-repo (transcriptomics only) -> recorded unavailable; curated disease template with DOIs; E3 precedent from context_joined.
- Modality decision: identity fail -> unsuitable; chemistry fail -> uncertain (chemistry gate block; no blanket "unsuitable"); causal/precedent + E3 -> justified; else uncertain. Gates identity/chemistry/therapeutic_window; design cannot bypass (run_protacpilot -> design_gate -> typed TherapeuticallyUnsuitable -> status blocked; require_assessment blocks when missing).
- Wiring: TUI /therapeutics (handle_therapeutics typed payload); /plan adds T1b_therapeutic_assessment stage; /investigate T1b executes and persists outputs/assessments/<TARGET[_VARIANT]>.json; Node /therapeutics command; every conclusion carries source_ids/assay_context/conflicting/missing_data/experiment_to_change.
- Demos (real TUI path, offline): EGFR -> justified (all gates pass); KRAS G12C (variant parsed) -> uncertain (chemistry block, window pass_with_uncertainty); BRD4 -> justified. Design run for KRAS G12C -> status blocked (no bypass).
- Expert evaluation: docs/architecture/tables/expert_cases_therapeutics.tsv (3 cases, PENDING_SIGNOFF) + expert_comparison_therapeutics.tsv (18 dimension rows, agree/discrepancy) — comparison, not self-scored prose.
- Docs: docs/architecture/THERAPEUTICS_ASSESSMENT.md. Tests: tests/test_therapeutics_assessment.py 15 passed (build/persist, kras variant, conclusion contract, association!=causality, expression!=function, gates incl. no-bypass runtime check, bridge, plan/investigate integration, unavailable-not-fabricated).

## 2026-09-25 — Challenge chemistry/provenance audit + evidence-gated /design run

- Audit (outputs/manuscript_strategy/challenge_audit/): 5 challenge structures canonicalized (InChIKeys), attachment-atom maps (warhead nbr-atom 17 @ map1; E3-ligand nbr-atom 12 @ map1), all RDKit-valid; DC50 values are PREDICTED (tack-style/chemprop; requires_experiment); SGA-VERIFIED-MZ1_* names are misleading (dBET1/CRBN constructs, not MZ1/VHL) -> annotate; 26-vs-5 subset NOT verifiable (26 set not persisted) - recorded gap; plots unverified against data (no x/y layer in analysis.json; PNG-only); ternary/synthesis unevaluated (backend absent; proxies flagged). DOI audit: 313 unique -> 312 resolve; repaired CRBN_ligand_88 patent-in-DOI-field; 43/43 curated DOIs resolve; jacs.8b06155 unresolvable (not cited). E3: e3_catalog_v2.csv = 391 rows, NO cell-context columns (old "377 cell-context" claim unsupported); enriched WITHOUT duplication -> data/e3_catalog_v2_enriched.csv (recruiter_doi_row_count, has_curated_recruiter, in_e3_opportunity_catalog).
- Evidence graph corrected: degradation kind=observed allowed only with measured_source=True + DOI/PMID source id(s) + assay; ML predictions enforced computed/predicted (tests).
- /design wired to the EXISTING deterministic engine (run_protacpilot; adapter in protacxtend/workflows/designer.py - no second implementation): stage timeline executed/unevaluated, non-PROTAC rejection gate before degradation/ADMET, nomination gated, resume_state + artifacts, evidence gates (ternary/synthesis unevaluated).
- Real-bridge E2E: e2e_bridge_transcript.md for "Design a CRBN-recruiting PROTAC for BRD4": 10 executed stages (100 binders -> 9 warheads -> 3 E3 -> 18 linkers -> 180 assembled -> 150 valid -> 150 degradation -> 150 ADMET -> ranking), 2 unevaluated (ternary_coordinates, synthesis_route), gates non_protac_rejection=passed, degradation=predicted, nomination=gated.
- Tests: tests/test_design_bridge.py (7) + updated test_workflow_contracts (12); 57 passed across design-bridge + contracts + request-understanding + dialogue suites.
- Open: cross-process candidate identity on resume (generative linker sampling non-seed-stable; runtime resume does not restore candidate table) - next implementation task.

## 2026-09-24 — Four-case reconciliation; grader ranked fix; retrieval-only abstention (v2)

- Empty-baseline 0.5 audit: DISCOVER-04 (ranked) rank_score returned max(0,(0+1)/2)=0.5 for empty/mismatched predictions. Fixed benchmark_runner/scoring.py:rank_score (empty -> 0.0 no_prediction; len-mismatch -> 0.0 undefined) and grader ranked branch (empty -> status unanswered). Verified grade_answer(DISCOVER-04,"") -> 0.0/unanswered.
- Query->evidence machinery (protacxtend/evidence/trace.py): capability-aware queries, per-tool retrieval w/ status+top results, relevance judgments vs required concepts, answer claims derived ONLY from retrieved supporting results, missing support; wired into pilot KNOW/REASON. Abstention rule v2: KNOW/REASON answer only if retrieval claims exist (strategy/binder text never counts). Traces: outputs/evidence_traces/{KNOW-06,REASON-03,REASON-05}.json + dossiers docs/architecture/benchmark_traces/evidence/*.
- Re-ran frozen four-case pilot: AFTER v2 = KNOW-06 abstained, REASON-03 abstained, REASON-05 abstained, DISCOVER-04 0.0 (scored). Denoms: n_total 4 / n_scored 1 / n_abstained 3 / n_failed 0; scored-only mean 0.0 (1 task) - NOT comparable; supported correctness 0/4; NO performance-gain claim.
- Blinded sheets regenerated without provisional scores (48; keys separate). Report appends §9-12.
- Tests: tests/test_reconciliation_four_case.py (6) + grader + therapeutics + plan + scorecard: 49 passed.

## 2026-09-24 — Therapeutics audit: missing-evidence gates, context keys, no-bypass

- Missing-evidence decisions: dependency + normal-tissue unavailable -> therapeutic_window REQUIRES_REVIEW for every target (never silent pass); decision split into mechanism_rationale (verdict) vs therapeutic_suitability (supported/requires_review/not_supported) with separate reasons.
- Context-keyed assessments: outputs/assessments/<SYM[_VAR]>__<fprint>.json + index.json; fingerprint = sha256(target|variant|disease|cell|source_versions|schema); load rejects stale/mismatched records (verified: variant/disease mismatch, tampered source hashes, schema change).
- No-bypass across all public design entry points: run_protacpilot, canonical/run_canonical (strategy CLI), workflows/api.run_command (/design + run-design incl. resume) all gate (KRAS G12C chemistry block -> status blocked; BRD4 proceeds with pass_with_requires_review flag; strict allow_requires_review=False blocks). Tool-level api_routes routes documented as low-level.
- KRAS G12C chemistry-block diagnosis: binder_structure partial (curated binder census 0, structures none) -> chemistry_readiness against_degradation -> chemistry gate block; mechanism stays uncertain.
- BRD4 (AML/OCI-AML3) TUI design run with assessment attached: docs/architecture/traces/THERAPEUTICS_BRD4_AML.md; expert comparison regenerated with mechanism+suitability columns, all PENDING sign-off.
- Audit tests: tests/test_therapeutics_audit.py (14) + updated assessment/reconciliation tests. Full affected suites pass.

## 2026-09-24/25 — Gold-free retrieval pipeline + Europe PMC/ChEMBL/PubChem repair + snapshot fallback + fixed-denominator pilot
- REMOVED gold from the agent path: pilot runner no longer loads ground truth during execution; trace.py no longer injects GT evidence refs or hard-coded required concepts into queries/relevance/claims. Gold permitted ONLY post-run (benchmark_runner.grader.grade_answer + new protacxtend/evidence/evaluate.py). Trace version evidence-trace-v2-gold-free; requires are inert metadata + gold_access_note.
- KNOW-06/REASON-03 Europe PMC repair (raw-response inspection): default search omits abstractText; exec_europe_pmc now requests resultType=core and parses title/abstract/doi/pmid/pmcid/journal. Old tracer emitted title==id ("EPMC:42376709") because it read sources strings; _normalise_records now consumes structured payloads incl. ChEMBL/PubChem SMILES.
- ChEMBL/PubChem diagnosed by cause: tracer passed query/q while dispatchers read term -> empty-param 400 ("No search query provided") / "Compound name is required."; fixed via _TOOL_PARAMS mapping; live-verified (dimethylisoxazole -> CHEMBL6145996 / PubChem CID 328257).
- Versioned source-attributed snapshot: protacxtend/evidence/snapshot.py (data/evidence_snapshots/evidence-snapshot-v1/<tool>/<hash>.json; schema/fetched_at/live-source/records), zero-hit successes snapshotted; trace rows labelled snapshot=True + version + fetched_at + live_source. Scripts/build_evidence_snapshot.py.
- Pilot re-run KNOW-06,REASON-03,REASON-05,KNOW-01: gold_access.during_execution=false; 4/4 answered (was: abstained), mean score 0.1875 (post-run grader); fixed-denominator buckets: answered 4/4, source_unavailable 0/4, no_relevant_evidence 0/4, answer_failed 0/4. Provenance chains (raw record -> passage/structure -> claim -> answer) in outputs/pilot_gold_free/PROVENANCE_REPORT.md.
- /design upgraded (per test contract): workflows/api.py design branch now executes the deterministic engine (workflows/designer.run_design) with E3 optional semantics (explicit honored; unspecified -> evidence comparison); candidate_evidence_table + evidence_gates.ternary_coordinates=unevaluated.
- Tests: 55 passed (reconciliation/e2e/plan-dialogue/scorecard/registry/status) + bridge suite incl. real-engine design E3 tests. Artifact: challenge/outputs/GOLD_FREE_PILOT_FIX.md.

## 2026-09-24 — Technical atlas regenerated (current repo state)

- Re-verified every headline count with live probes (COUNT_VERIFICATION.txt): workflow nodes 34 (frozen snapshot 31 kept historical; routes KNOW 11/REASON 15/DESIGN 28/DISCOVER 16), LLM-callable tools 34, external toolkit 115, backend capability classes 19, TPD classes 27, catalogued functionalities 108 (12/11/44/15 + 26 CROSS) vs E1-executed adapters 12/7/9/6, universal registry 296 rows across 6 sections. Non-addable denominators and corrected figure text in the atlas.
- Regenerated machine tables (build_technical_atlas.py): workflow_nodes(34), agent_tools(34), toolkit_tools(115), scientific_backends(19), tpd_capabilities(27), functionalities(108), crosswalk(34), dataflow_edges(26), all SHA-pinned.
- Regenerated atlas doc (scripts/build_technical_atlas_doc.py): system map incl. request layer / goal planner / TargetTherapeuticsAssessment + design gates / evidence trace; inventories; crosswalk + 12/11/44/15 reconciliation; pillar depth; agent core; three real traces (A /plan EGFR; B BRD4-VHL MZ1 reconstruction; C unavailable evidence incl. ZZZZ9, ChEMBL outage, comparison-only replay); 8 Mermaid diagrams (incl. plan_investigate_therapeutics); claim/gap audit; one-page summary; appendix with test outputs.
- Real traces: docs/architecture/traces/ATLAS_TRACES_A_C1.json + TRACE_A_and_C_RERUN.md + TRACE_B_RERUN.md.
- Acceptance: every inventory name re-validated against its registry (none missing); 93 tests passed (plan, therapeutics x2, explanation, quarantine, grader, reconciliation, BRD4 case) — outputs in docs/architecture/TEST_OUTPUT.txt.

## 2026-09-26 — TUI response contract: raw→rendered trace, field-loss fixes, real-TUI visible tests

- Verified executable identity first: commit 82a0e4d (+ uncommitted session edits), version 0.3.0, import paths (protacxtend/__init__.py, tui_bridge/server.py, planning/goal_planner.py); `protacxtend` on PATH is the Node launcher.
- Traced /plan HMGB2, /investigate AR protac, /reason which protac work for EGFR in fresh processes. Field losses found: /plan renderer showed only interpretation+question (tasks/stages/artifacts dropped); /investigate renderer read scientific_findings but producer sent findings dict (key mismatch -> blank panel); /reason renderer dropped recommended_action/gated/case; RESOURCE REASONS log could render as answer.
- Shared contract: protacxtend/tui_bridge/contract.py (classify: plan|blocker|ok|hypothesis|no_scientific_answer; annex: stage statuses + artifacts; answer_text mirror; strip_logs removes H ? and resource-reason language). Producers attach contract+annex (handle_plan, handle_research, handle_diagnose); handle_diagnose now answers row-level questions via _evidence_rows.py (EGFR = 18 packaged measured rows, DOI-cited; 0-row case -> explicit evidence-gap conclusion; case_source honesty marker).
- Node renderer: renderPlanAnswer (tasks/blockers/stage status/artifacts), renderResearchAnswer findings-or-gap with contract fallback, renderDiagnosisAnswer (direct evidence rows, gap, case source, hypotheses, tests, action, gated); RESOURCE REASONS debug-only; H ? placeholder impossible.
- Fixed ask() event correlation (new match predicate): concurrent /reason could steal /investigate's research_answer (real-TUI test caught double-render of investigate + no diagnosis).
- Real TUI tests: tui/tests/visible_output.test.ts spawns real src/index.ts + real python bridge in a fresh process and asserts VISIBLE text (4 passed, ~14 s). Python contract tests: tests/test_tui_response_contract.py (8 passed). Outputs: docs/architecture/tui_contract/{NODE_VISIBLE_TEST_OUTPUT,PY_CONTRACT_TEST_OUTPUT}.txt.
- Artifacts: docs/architecture/tui_contract/TUI_RESPONSE_CONTRACT.md, raw_vs_displayed.md, transcripts/{plan_hmgb2,investigate_ar,reason_egfr}.{raw.json,rendered.txt} + manifest.json; generator scripts/trace_tui_contract.py.

## 2026-09-26 — Integrity verification: input parser, canonical core, scientific mode

- Input integrity: ran request-understanding/plan-dialogue/target-resolution suites (58 passed in 20m42s, output saved docs/architecture/integrity/input_parser_tests.txt); fresh blind probe of 10 unseen phrasings (docs/architecture/input_integrity_blind_cases.txt) — no exceptions, unresolved/ambiguous inputs return typed clarification and never execute. FLAGGED 2 residuals: multi-target ("BRD4 and MYC") narrows to primary without a typed warning; noisy primary-token choice (HSP90 "hybrid" -> HYBRID) still fails safe via clarification.
- Canonical core: verified single engine — TUI /design|/structure|/rank|/report -> bridge "run" -> workflows.api.run_command -> workflows.designer.run_design -> agents.runtime.run_protacpilot -> CanonicalOrchestrator.review_engine_state (both modes). LocalSynGlueWorkflowGraph referenced only by resource_audit (registry audit) + tests; legacy CLI `pilot` (workflows/pilot_runner.py) reachable only from cli.py pilot command and tests, never TUI/API/canonical. benchmark_runner defaults mode=SCIENTIFIC (runner.py:203) and refuses DEV fixture adapters in scientific mode (runner.py:220).
- Scientific-mode integrity: verified modes.py guardrail layer (DEMO/TEST/SCIENTIFIC contextvar; PLACEHOLDER_SMILES includes CCO; validate_scientific_params raises on CCO; scan flags demo source + synthetic artifact; filter_scientific_rows drops demos: e3 95->88, warheads 6->0; agents raise SyntheticInputNotAllowed with census). Ran 5 scientific-integrity suites: 78 passed (docs/architecture/integrity/scientific_mode_tests.txt). Real-run evidence audit: run_brd4_vhl_scientific_v1 evidence.jsonl DOI-cited only; [*:1] markers are explicit attachment annotations; "cco" hits are inside MZ1 PEG linker SMILES, not placeholders; MZ1 InChIKey matches. Documented limits: interactive default mode is DEMO (labeled demos allowed interactively; guaranteed boundary is SCIENTIFIC), dummy-attachment linkers not placeholder-gated (flagged hypothetical).
- Report: docs/architecture/INTEGRITY_VERIFICATION.md.

## 2026-09-26 — Mechanistic Capability Closure M1-M4 (spec-driven, honest statuses)

- Added protacxtend/mechanistic/: evidence_types (9-type taxonomy + non-equivalence guard), m1_hook (mechanistic equilibrium facade w/ parameter provenance, concentration-response, alpha/Kd sensitivity, MECHANISTIC_SIMULATION label), m2_lysine (per-residue lysine SASA/geometry + configurable threshold registry + aggregates; Shrake-Rupley reused), m2_benchmark (RCSB ternaries: PROTAC-shotgun catalog + TERNARY_V1; 40 attempted / 38 recovered, recovery 0.95; E2 reference absent in set -> productive-geometry recall/E2 distances honestly UNAVAILABLE), m3_cooperativity (MEASURED_ALPHA ingestion 46 DOI-cited records; CALCULATED_ALPHA w/ documented convention; STRUCTURAL_COOPERATIVITY_PROXY never alpha; calibration BLOCKED_BY_DATA (0 measured-proxy pairs)), m4_registry (registry: DeepPROTACs/DegradeMaster/TACK/SynGlue/local; persisted local benchmark only: grouped R2 0.605, scaffold 0.41, random -4.4; endpoints + applicability domain), ternary_benchmark (native vs P4ward vs score-only proxy), integrate (mechanistic_evidence block, separate rank dimensions, nomination policy: gates only).
- Runner scripts/run_mechanistic_closure.py -> outputs/mechanistic_capability_closure/ (report.md, m1..m4 CSVs, m2 metrics+examples, ternary backend CSV, evidence matrix, candidate example, 6 figures).
- Tests: tests/test_mechanistic_closure.py 36 tests (M1 9, M2 9, M3 5, M4 7, integration) + core module suites -> 91 passed (test_results.md).
- Status: M1 IMPLEMENTED; M2 BENCHMARKED (E2 fields BLOCKED_BY_DATA); M3 IMPLEMENTED (proxy descriptive; calibration BLOCKED_BY_DATA); M4 BENCHMARKED (local). No validated claims; no external scores copied.

## 2026-09-27 — Module-close deliverables outputs/mechanistic/{m1,m2,m3,m4}

- M1: outputs/mechanistic/m1/ -> validation.csv (5 cases + physical flags all pass: mass conservation, zero-PROTAC boundary, low-dose rise, high-dose hook decline), sensitivity.csv (10 rows alpha/Kd +/-20%), report.md, test_results.md, figures/fig4. Parameter provenance now restricted to EXPERIMENTAL|CALCULATED|INFERRED|STRUCTURAL_PROXY|UNAVAILABLE (placeholder Kds UNAVAILABLE, never silently experimental).
- M2: benchmark over RCSB ternary set (PROTAC-shotgun catalog + TERNARY_V1): outputs/mechanistic/m2/{benchmark.csv (40 rows incl. runtime_s), per_lysine_results.csv, failures.csv, report.md, test_results.md, figures/}. 38/40 recovered (0.95); runtime 61.9s total / 1.63s median; productive-geometry recall + top1/top3 lysine recovery + FPR honestly not_computable (0 E2-bearing complexes, no labels); fixed E3-chain tuple to exclude POI chain (zero-distance artifact removed); module named Ubiquitination Geometry & Lysine Accessibility, never predictor; thresholds configurable.
- M3: alpha_dataset.csv (46 MEASURED_ALPHA DOI-cited), structural_proxy.csv (descriptive proxy; components UNAVAILABLE without structure; never labelled alpha), calibration.csv (BLOCKED_BY_DATA 0 pairs), report/test_results; no trained alpha predictor invented.
- M4: model_registry.csv (6 models), benchmark_results.csv (6 persisted local rows; external scores never copied), domain_results.csv (IN_DOMAIN local / UNASSESSABLE external; OUT_OF_DOMAIN never nominable), report/test_results.
- Final mechanistic suite: 40 new closure tests + core suites -> 105 passed (test_results.md refreshed in all four trees).

## 2026-09-28 — TUI Scientific Command Semantics Repair (P0/P1)

- Reproduced 4 failures into outputs/tui_semantic_repair/before/: /plan EGFR CRBN (plan without stage contract), /investigate why EGFR (counts only), /reason why BRD4 and CRBN works and /reason EGFR good target (BOTH returned the canned EGFR no-degradation failure template; CRBN misparsed as POI).
- Implemented semantics layer protacxtend/tui_bridge/{semantics,evidence_synthesis}.py: reasoning-intent classifier (9 intents; WHY_WORKS causal chain vs WHY_FAILS hypothesis families, COMPARE by precedent, EVIDENCE_SYNTHESIS), role resolver (E3 families = recruiter role; unresolved tokens never targets), conversation ContextStore (per-conversation target/E3; 'use <E3>' updates E3 only; no leakage), per-section evidence with tiers (✓◆~?!×), investigate synthesis (14 dynamic sections incl. row-level degraders with DC50/Dmax/cell/DOI, gaps, bottom line), plan contract (9 ordered stages, gates, tools, evidence required, persistence plan_object.json), /run plan_<id> executing evidence stages with expensive stages deferred to /design.
- Server rewiring: reason -> handle_reason (intent-driven), investigate -> synthesis, plan -> contract+persist+context record, run plan id, context command; Node renderer: renderSections w/ tier glyphs, plan stages with run-only marks, MECHANISTIC REASONING + intent badge + CONCLUSION, context interception; response contract gains kind=reasoning (sections+conclusion).
- Quality tests tests/test_tui_semantic_repair.py (16) + response-contract (8) + TUI visible-output (65 npm) + 52-pytest batch pass; generic-template trio cannot leak (audit CSV + tests).
- Artifacts: outputs/tui_semantic_repair/{report.md, before/, after/, command_contracts.json, reasoning_intents.json, routing_matrix.csv, regression_queries.csv, context_tests.csv, generic_template_audit.csv, test_results.md}.

## 2026-09-28 — Fresh current-code health audit (baseline freeze, discovery only)

- scripts/audit_agent_health.py probes every workflow unit from CURRENT code (no historical docs as truth): 34 graph nodes + agent classes + canonical modules/orchestrator (82 units). Per unit: reachability, EMPTY + representative seeded execution ("Design a CRBN PROTAC for BRD4" via SupervisorAgent), state read/write (AST + runtime diff), tool/backend usage (live registry names), real-data markers (demo/fixture/CCO scan), failure behavior, contract satisfaction (evidence or typed abstention; silent no-op = fail).
- Results (frozen in outputs/audits/agent_health/): 0 unreachable; 66/66 executed units pass cleanly; 0 silent-pass; 2 timeouts (generate_linkers/linker agent, 15s probe); 13 canonical modules import clean; orchestrator instantiates. Demo-marker scan: 6/8 diagnostic ("N demo rows dropped in SCIENTIFIC mode"), 2/8 REAL FINDING — report ledger records "heuristic synglue-demo degradation predictor" / "heuristic_stub" under SCIENTIFIC mode (fix phase item). 3 duplicate candidates flagged (ReActAgent x2, pilot_runner vs runtime, structural engine vs ternary backend) — functional diff required, none fixed.
- Artifacts: agent_health_matrix.csv, unreachable_components.csv (0 rows), stale_or_duplicate_components.csv, state_read_write_matrix.csv, tool_backend_mapping.csv, marker_context_classification.csv, report.md, baseline.txt, baseline_inventory.json. NO code fixed during discovery.

## 2026-09-28 — Agent health audit (machine-derived, runtime-evidenced)

- scripts/build_agent_health_audit.py: inventory from live registries (34 workflow nodes via LocalSynGlueWorkflowGraph, 34 LLM-callable tools via agentic registry, 5 decision gates, 20 canonical functions); AST-derived state R/W matrix, call traces, upstream callers, tests; runtime probes per node (init, positive, missing-input, production chain run with trace on 'Design BRD4 PROTAC with CRBN', real packaged data).
- outputs/agent_health_audit/ (10 required files + agent_final_table.csv): tiers from runtime evidence only — 28 REAL_DATA_VALIDATED (executed in real chain with 150 real candidates), 6 EXECUTABLE (probe-passed; not reached in single DESIGN chain: design_path, evolution_refinement, select_expensive_modeling_finalists, active_learning_update, capability_answer, reasoning_answer), 0 DEFINED_ONLY; SCIENTIFICALLY_VALIDATED reserved (no adjudicated gold).
- Reconciliation: 23-entry AGENT_PIPELINE (tui_bridge/events.py) is display-only metadata; authoritative runtime agent set = 34 graph nodes + 34 tools + canonical plane + gates. No subagents exist in-repo.
- Contract probes: /plan PASS (9 ordered stages, gates, tools, plan persisted), /investigate PASS (8 sections, 10 row-level evidence, gaps), /reason PASS (intent WHY_WORKS/WHY_FAILS routed; no generic-template leakage). Blockers recorded: evidence dict empty in DESIGN route, TACK sklearn-version warnings, admet_ai probe timeout.

## 2026-09-28 — Closure: heuristic_stub reporting, deadline-safe linkers, duplicate classification, command-contract audit

- heuristic_stub: generate_pipeline_status_table degradation row now derives from actual records (MODEL_PREDICTED / UNAVAILABLE_heuristic_fallback_excluded / not_connected; no "Synglue-demo" naming); generate_candidate_table renders heuristic DC50/Dmax as "UNAVAILABLE (heuristic fallback excluded)" + Degradation evidence type column. Tests: TestHeuristicStubMasquerade (6) pass. STATUS: CLOSED.
- linker deadline: LinkerGenerationAgent checks run deadline (<=3s -> typed abstention) and bounds the SoTA panel call via daemon-thread timeout (min(deadline,20s)); timeout -> typed deadline_exceeded, no linkers claimed. Tests: TestDeadlineSafeLinkers (3) pass. STATUS: CLOSED.
- duplicates: DUPLICATE_CLASSIFICATION.md+csv — chat_agent vs base_agent = NOT_A_DUPLICATE (false positive; no ReActAgent in chat_agent), pilot_runner vs runtime = LEGACY_ISOLATED, structural/engine vs ternary backend = LEGACY_VS_REGISTERED. No removals.
- command contracts: scripts/audit_command_contracts.py — 8 rows (design/run/optimize/experiment/validate x2/compare x2) all PASS/PASS-with-finding; findings: optimize+experiment legacy canned diagnose; compare without sectioned synthesis; design offline 0 candidates; validate empty-input returns calculated row (review). Fixed during audit: UnboundLocalError sf in handle_research (design crash), contract classify run_answer, load_plan scan for plan_id<->run-dir mismatch. Report: outputs/audits/command_contracts/{command_contract_audit.csv,report.md}.

## 2026-09-28 — Live manifests + inventory-drift gate

- scripts/build_system_manifest.py generates: docs/architecture/system_manifest.yaml (live counts: 34 nodes / 34 agent tools / 115 toolkit / 19 backend capabilities / 27 TPD classes / 108 functionalities / 296 universal; canonical modules, agent classes, mechanistic M1-M4, semantic layers; key-file SHA fingerprints; non-addable-denominators note) and docs/architecture/capability_backend_crosswalk.yaml (capability->best/registered/usable backends from live BackendRegistry, TPD readiness 27, tool->capability heuristic mapping flagged).
- Drift elimination: pinned count expectations (fail loudly on change) + `--check` mode regenerating from live registries and diffing committed YAMLs (generated_at normalized); verified pass (check exit 0). Sota workflow_nodes.csv still documented as the historical frozen 31-node snapshot.

### manifest verification (same day)
- capability_backend_crosswalk.yaml now sourced from the LOADED BackendRegistry capability_matrix (live)= 19/19 ready (e.g., chemistry best=rdkit usable rdkit+openbabel; ligand_docking usable consensus_docking,diffdock,autodock_vina,gnina,geometric_placement) + 27 TPD readiness + 34 tool->capability heuristic rows.
- `python scripts/build_system_manifest.py --check` -> exit 0 (no drift; generated_at normalized for comparison). Pinned count expectations: nodes 34, tools 34, toolkit 115, backend caps 19, TPD 27, functionalities 108, universal 296.

## 2026-09-28 — FINAL CLOSURE MODE: PHASE 0 baseline (freeze + live inventory)

- No production changes; new machine-derived inventory only (scripts/final_closure_phase0.py).
- Baseline frozen: HEAD 82a0e4d + 306 dirty files; python 3.13.5, rdkit 2026.03.4, torch 2.10 CUDA, RTX 5000 Ada.
- canonical live census: 34 nodes / 34 LLM tools / 19 backend capability classes / 115 toolkit entries / 27 TPD classes / 7 model weight files / 42 CLI + 41 TUI commands / 7 memory components; benchmark500 = general_500 + temporal_500 (500 each, gold uncurated).
- Contradictions recorded (126 raw hits grouped): 31→34 nodes, 23-agent display metadata vs 34-node runtime, "0.885" excluded self-grade, benchmark500 label ambiguity.
- P0 scan: degradation 3-state fallback provenance implemented (41 tests pass this phase); GAP = hidden-benchmark memory isolation (no memory_mode/write_global_memory/ground_truth_visibility flags); replay hash-only; claim-evidence graph classes exist (per-run JSON P1); plan persistence + design gates implemented; benchmark gold blocked (uncurated).
- Ordered closure plan P0..P9 with per-phase files + completion tests in sota/final_closure/PHASE0_BASELINE.md; inventory JSON/MD in sota/final_closure/baseline_inventory.{json,md}.

## 2026-09-28 — Environment & capabilities audit (BioMNI-E1 style)

- outputs/environment_audit/PROTACXTEND_ENVIRONMENT_AUDIT.md + environment_audit.json: machine-derived environment audit mirroring Stanford BioMNI-E1 structure (unified action space, software/compute, models, databases health, setup recipe, evaluation, governance, gaps).
- Headline: 34 LLM tools / 34 nodes / 19 backend classes / 115 toolkit entries / 23 skills / 14 databases / 7 model weights (sha256 recorded); compute env snapshot with torch/sklearn/scipy requirements-vs-live skew flagged; resources: RCSB LIVE, ChEMBL DEGRADED-recovered, DrugBank LICENSE, 485K warhead-seed MISSING (doc-vs-code gap); benchmark500 2x500 uncurated; 0 externally validated.

## 2026-09-28 — Tool-count diagnosis + mechanistic-evidence plan

- Diagnosis (live code): agentic action space = curated whitelist (TOOL_SPECS via _spec builder, 34 ready specs); tools/*.py = 99 implementation modules, 13 fuzzy-covered by specs; toolkit 115 = resource inventory, not action space. 7 of the 34 specs are mechanistic (ternary, lysine/ubiq, cooperativity, hook, degradation, cell context, ADMET).
- Gap audit artifact: outputs/environment_audit/tool_registration_gap.csv (99 modules, spec coverage, role, priority; ~20 mechanistic modules not first-class agent tools).
- Plan: outputs/mechanistic_evidence_plan/PROTACXTEND_MECHANISTIC_EVIDENCE_PLAN.md — Part A why 34 (mechanism), B registration recipe (wrapper→_spec→dispatch→readiness→contract→manifest; wave-1 ~8 mechanistic tools to ~42), C E0-E5 "best mechanistic evidence tool" plan (evidence-first agent core, claim-evidence graph, decomposed confidence, controls/benchmarks, comparative eval, publication packaging) with gates, deliverables, blocker guardrails.
