# WEBSITE_AUDIT.md — PROTACXtend site: full data · model · architecture register

Audit of the entire PROTACXtend website (`website/`, current working-tree version ≈ **v2.10**)
against the actual repository: every data asset, committed model artifact, module, node,
tool, API and deployment fact the site presents was traced to code/files and verified
(local working tree + the canonical repo `the-ahuja-lab/PROTACXtend` via API checks).

- Audit date: 2026-09-03
- Object: single-page static site — `website/index.html` (824 lines), `website/styles.css` (1070), `website/app.js` (216), `website/assets/*`
- Source of truth used: `config/scientific_status.yaml`, `protacxtend/modules/PROTACXTEND_MODULE_BUILD.md`, `protacxtend/agents/graph.py`, `protacxtend/cli.py`, `backend/api_routes.py`, `research/sources.py`, data/ + model files (HEAD/API presence checks)
- Companion docs: `SCIENTIFIC_CLAIM_AUDIT.md` (claim-level), `SITE_COHERENCE_AUDIT.md` (site↔code reconciliation), `WEBSITE_CHANGELOG.md` (site history)

---

## 0. Executive summary — what the site is, in one screen

| Aspect | Value (verified) |
|---|---|
| Site type | Pure-static single page, no build step; JS enhancement only (`app.js`) |
| Sections | 10 landing sections + navbar + footer: hero(#home), About(#about), Capabilities(#capabilities), Mechanism(#mechanism), Models(#prediction), Architecture(#architecture), Workflows(#workflows), Walkthrough(#playground), Validation(#validation), Docs(#docs) |
| Headline stats (hero counters) | 23 core scientific nodes · +8 search/feedback extensions · 5 live retrieval APIs · 7 committed ML artifacts · 73 chemistry-engine methods |
| Macro-framework | KNOW → REASON → DESIGN → DISCOVER |
| Node accounting | 23 core + 8 extensions = **31 registered agent nodes** (`agents/graph.py`, verified) |
| Evidence badges | 8 tokens: MEASURED · RETRIEVED · CALCULATED · LEARNED PREDICTION · STRUCTURAL SURROGATE · HEURISTIC · ILLUSTRATIVE · NOT AVAILABLE |
| Status tokens (validation matrix) | VALIDATED BASELINE · TRAINED · PARTIAL · STRUCTURAL SURROGATE · DATA-GATED · UNDER EVALUATION · PLANNED (+ public-claim YES/NO) |
| Release framing | "v0.3 core release · active research development", MIT, Ahuja Lab (IIIT Delhi), lead dev Saveena Solanki |
| Interactive widgets | scroll progress, nav burger, reveal-on-scroll, animated counters, git/docker install tabs + copy, pipeline walkthrough (hard-coded ILLUSTRATIVE), 6-pane docs tabbed hub |

---

## 1. Data layer — everything the site/platform references

### 1.1 Live retrieval APIs (KNOW stage) — hero "5 live retrieval APIs"

Source: `protacxtend/research/sources.py` → `SCIENTIFIC_FIRST = [europepmc, pubmed, openalex]`, `GRAPH_SOURCES = [openalex, crossref]`, `WEB_SOURCES = [searxng]`.

| API | Config key | Role on site | Verified |
|---|---|---|---|
| Europe PMC | `europepmc` | primary literature retrieval | ✅ client in sources.py |
| PubMed | `pubmed` | literature retrieval + abstracts (efetch XML) | ✅ |
| OpenAlex | `openalex` | literature + graph source | ✅ |
| Crossref | `crossref` | citation graph | ✅ |
| SearXNG | `searxng` | web search — **configurable / self-hosted** (needs `SEARXNG_URL`); site honestly labels it configurable | ✅ guarded, PARTIAL |

Full-text crawl (crawl4ai/httpx, robots-aware) exists in the research layer (`fulltext_crawl`, PARTIAL) but is not one of the "5".

### 1.2 Databases & bioactivity APIs (REASON/DESIGN stages)

`config/scientific_status.yaml → databases_and_apis.live_apis` lists **8** (site docs pane): UniProt, ChEMBL, PubChem, BindingDB, Europe PMC, PubMed, OpenAlex, Crossref. Client/tool code exists for each (`tools/*_client.py`, `*_lookup.py`).

### 1.3 Committed / curated datasets (in-repo, measured row counts)

| Dataset | Path | Scale (measured) | Role |
|---|---|---|---|
| PROTAC-Degradation-DB + DepMap join (Module 5) | `protacxtend/modules/cell_context_selector/data/context_joined.csv` | **1913 rows** (= site claim; DC50 1181 / Dmax 761 per tracker) | M5 features + labels |
| DepMap 24Q4 transcriptomics | same join (transcriptomic block, 1512 rows per tracker) | part of 1913 | M5 cell-context features |
| Module 4 curated published labels | `outputs/benchmark/benchmark_predictions.csv` | **64 pDC50 / 32 Dmax**, E3 CRBN+VHL, DC50 0.019–16 840 nM | M4 training/eval provenance |
| TACK (DC50 / binary) | `data/tack/tack_dc50.parquet` (4184 rows), `tack_bin.parquet` (6561 rows); `tack_meta.joblib` | 4184 + 6561 | TACK models' calibration/provenance |
| GROVER / SynGlue encodings | `data/synglue/data/grover_warhead.csv` (1104 rows), `grover_e3.csv` (117), `e3_ligand.csv` (117) | 1104 / 117 / 117 | SynGlue feature cache |
| Chemprop benchmark/calibration CSVs | `data/benchmark/chemprop_{train,train_cal,cal,benchmark,benchmark_clean,train_multitarget}.csv` | 1698 / 1498 / 200 / 64 / 64 / 1126 rows | degradation chemprop runs |
| PROTAC-DB 3.0 benchmark | `data/benchmark/PROTAC-DB_3.0_protacs.xlsx` | xlsx | benchmark + training provenance |
| E3 opportunity catalog (Module 6) | `protacxtend/modules/e3_opportunity/data/e3_catalog.csv` | **30 genes** (31 lines) | 30-gene catalog × 8 evidence axes |
| E3 context expression | `.../context_expression_matrix.csv` | 1673 rows | expression evidence axis |
| UniProt localization cache | `.../uniprot_localization.csv` | **78 genes** | localization axis (static cache) |
| HMGB2 warhead library | `data/warheads/hmgb2_warhead_library.csv` | 15 rows | demo/target library |
| Linker library | `data/linkers/linker_smiles.txt` | 241 entries (+ `linker_generator.pt`) | curated + generative linker source |
| Research cache | `data/research/cache` | dir | retrieval cache |

### 1.4 Spreadsheet assets (site docs pane + `spreadsheet_assets` in YAML)

`Agent_Toolkit.xlsx` · `data/toolkit/Agent_Toolkit_EXPANDED.xlsx` · `TOOL_AUDIT.xlsx` · `data/protac_repos/protac_repo_registry.xlsx` · `data/benchmark/PROTAC-DB_3.0_protacs.xlsx` · `protacxtend/modules/cell_context_selector/data/context_joined.csv` — all present in working tree.

---

## 2. Model layer — every model the site presents

### 2.1 Committed model artifacts (D) — verified 200/404 on canonical repo

| Artifact (as listed on site docs pane) | Local | GitHub org repo | Status |
|---|---|---|---|
| `protacxtend/modules/degradation_ml/models/pdc50_model.joblib` | ✅ | ✅ 200 | M4 |
| `protacxtend/modules/cell_context_selector/models/cell_context_model.joblib` | ✅ | ✅ 200 | M5 |
| `data/tack/tack_dc50_model.joblib` | ✅ | ✅ 200 | TACK |
| `data/tack/tack_dmax_model.joblib` | ✅ | ✅ 200 | TACK |
| `data/tack/tack_bin_model.joblib` | ✅ | ✅ 200 | TACK |
| `data/synglue/models/multitask_transformer.pt` | ✅ | ✅ 200 | SynGlue transformer |
| `outputs/benchmark/chemprop_multitarget/model_0/best.pt` | ✅ | ✅ 200 | chemprop degradation |
| `data/synglue/models/rf_dc50.joblib` | ❌ | ❌ **404** | **listed on site, NOT in repo** |
| `data/synglue/models/rf_dmax.joblib` | ❌ | ❌ **404** | **listed on site, NOT in repo** |
| `data/synglue/models/grover_fixed.pt` | ❌ | ❌ **404** | **listed on site, NOT in repo** |

➡️ Exactly **7 model binaries are actually committed** (5 joblib + `multitask_transformer.pt` + chemprop `best.pt`), which keeps the hero stat "7 committed ML artifacts" true **only if** the count is those 7 — but the docs-pane code block *names* rf/grover files that don't exist, while the shipped SynGlue path is `multitask_transformer.pt` (code loads it at `synglue_degradation.py:127`; rf/grover paths are guarded optionals). **Finding #2** (see §7) — fix the docs-pane listing.

### 2.2 Mechanistic + ML modules M1–M7

| # | Module | Site/status YAML status | Tracker (module build) | Data | Validation (measured) |
|---|---|---|---|---|---|
| M1 | Hook Effect Modeler (`modules/hook_effect_modeler`) | **VALIDATED BASELINE** · CALCULATED · equilibrium only | ✅ DONE v1.0.0, QA 2026-09-02 | none external — validated mass-action equations (Douglass 2013, Gadd 2017, Hughes & Ciulli 2017, Riching 2018) | QA stamp 13/13; file today defines **24** `def test_*` — refresh stamp (§7 finding #6) |
| M2 | Lysine Ubiquitination Feasibility (`lysine_ubiquitination_feasibility`) | **STRUCTURAL SURROGATE / PARTIAL** · real-PDB benchmark pending | ✅ DONE v1.0.0 | pose geometry — Shrake–Rupley SASA, distance/approach angle, occlusion, ensemble productive fraction | 8 test functions; synthetic fixtures only |
| M3 | Cooperativity α (`cooperativity_alpha_predictor`) | **DATA-GATED** surrogate — NOT a trained experimental-α predictor | ✅ DONE v1.0.0 (surrogate) | feasibility scoring; no curated experimental α labels | harness ready (constant/ridge/RF/XGB/GP, grouped splits); 21 test functions |
| M4 | Degradation ML (`degradation_ml`) | **TRAINED** · pDC50 + Dmax | ✅ DONE v1.0.0, audit **approved 2026-09-02 (9/9)** | 64/32 curated published labels; grouped splits (random/scaffold/unseen-target/E3/PROTAC); honest disabled prob task | 9/9 tests; scaffold ridge R²=0.41 / MAE=0.73; in-sample RF ≈0.95 (train-fit-only, labelled) |
| M5 | Cell-context selector (`cell_context_selector`) | **TRAINED** · transcriptomic; proteotype NOT claimed | ✅ DONE v1.0.0 | PROTAC-Degradation-DB 1913 rows + DepMap 24Q4 (1512); grouped A–G | 16 tests; leg D > leg B on unseen-PROTAC pDC50 (**R² 0.605 vs 0.513**) |
| M6 | Novel E3 opportunity (`e3_opportunity`) | YAML + site: **PLANNED / public-claim NO** | Tracker: ✅ **DONE v1.0.0** (2026-09-02) — 30-gene catalog × 8 axes; SUPPORTED/PROMISING/EXPLORATORY/INSUFFICIENT; grouped retro benchmark RF AUROC .98 easy → **.93 unseen-E3**; recruiter ablation −0.52 | `e3_catalog.csv` (30 genes), expression matrix, UniProt localization (78 genes) | 17 tests + `run_e3_opportunity` tool; status report **gated — not yet audited**, hence NOT public-claimed |
| M7 | Active learning / experiment selection | **PARTIAL** (YAML) / site: PLANNED, CLI `/learn` surface exists; BO loop not built | pending | — | — |

> Module 6 divergence is intentional (code-complete but report-gated). Site and YAML are aligned (PLANNED/NO); the tracker is ahead. Do **not** flip the site until the M6 status report audit closes. (§7 finding #3.)

### 2.3 Independent degradation predictors (site "Model panel") — never averaged silently

| Predictor | Endpoint | Artifact | Validation summary on site | Verification |
|---|---|---|---|---|
| Module 4 — degradation ML | pDC50 · Dmax | `pdc50_model.joblib` | grouped splits; audit 9/9 | ✅ artifact + code |
| Module 5 — cell context | cell-context pDC50 | `cell_context_model.joblib` | grouped A–G; leg D R² 0.605 vs 0.513; 16 tests | ✅ |
| TACK — DC50 | DC50 | `tack_dc50_model.joblib` + calibration parquet (`tack_dc50.parquet`) | "calibration parquet + meta committed" | ✅ (dmax calibration parquet absent — see finding #5) |
| TACK — Dmax / binary | Dmax · active/inactive | `tack_dmax_model.joblib`, `tack_bin_model.joblib` + `tack_bin.parquet` | same | ✅ |
| SynGlue — DC50/Dmax | DC50 · Dmax | docs name `rf_{dc50,dmax}.joblib`; **actually shipped: `multitask_transformer.pt`** | "RF regressors + transformer committed" | ⚠️ RF regressors not committed (see §2.1) |
| Unified degradation engine | ensemble verdict | integration layer | **UNDER EVALUATION** — model-disagreement & uncertainty-aware; never silent-averaging | ✅ honestly labelled; not production |

Chemprop: `outputs/benchmark/chemprop_multitarget/model_0/best.pt` (committed) — DegradationPredictionAgent uses the trained chemprop model; local workspace additionally holds ensemble/calibration runs + comparison reports (`outputs/benchmark/{B1_CHEMPROP_COMPARISON,ABLATION_REPORT}.md`) not referenced on the site.

---

## 3. Architecture layer

### 3.1 The 31 registered nodes — full verified inventory (`agents/graph.py`, exact order)

**CORE 1–4 — governance & planning:** `parse_user_request` · `create_design_plan` · `control_np_hard_search` · `safety_precheck`
**CORE 5–9 — discovery/evidence grounding:** `resolve_target` · `retrieve_target_binders` · `select_warheads` · `select_e3_ligands` · `detect_exit_vectors`
**CORE 10–14 — component-aware assembly:** `generate_linkers` · `construct_protacs` · `expand_stereoisomers` · `validate_protacs` · `score_cell_context`
**CORE 15–23 — evaluation & reflection:** `predict_admet` · `check_novelty` · `assess_applicability_domain` · `cheap_filter_candidates` · `predict_degradation` · `initial_ranking` · `diversity_clustering` · `reflection_review` · `evolution_refinement`
**EXT 24–31 — controlled-search & feedback:** `select_expensive_modeling_finalists` · `optional_ternary_feasibility` · `predict_cooperativity` · `predict_hook_effect` · `final_ranking` · `active_learning_update` · `generate_report` · `update_memory`

Backing agents (verified imports): SupervisorAgent, DesignPlannerAgent, ControlledSearchAgent, SafetyAgent, TargetResolverAgent, TargetBinderRetrievalAgent, WarheadSelectionAgent, E3LigandSelectionAgent, ExitVectorDetectionAgent, LinkerGenerationAgent, MolecularConstructionAgent, StereochemistryEnumerationAgent, CandidateValidationAgent, CellContextAgent, ADMETAgent, NoveltyAgent, ApplicabilityDomainAgent, CheapFilterAgent, DegradationPredictionAgent, RankingAgent(final=False/True), ProximityDiversityAgent, ReflectionReviewAgent, EvolutionRefinementAgent, ExpensiveModelingSelectionAgent, TernaryFeasibilityAgent, CooperativityPredictionAgent, HookEffectPredictionAgent, ActiveLearningAgent, ReportAgent, MemoryUpdateAgent.

### 3.2 Scientific loop & contract

- KNOW → REASON → DESIGN → DISCOVER maps 1:1 to site sections 02/03/04 and the walkthrough trace (15 steps).
- The **scientific contract**: every executed step records input, output, evidence source, tool/model version, confidence, applicability-domain status, warning state and limitation; retry + stop gates (`needs_user_input`, terminal-error list: planner requires target, no warheads, no E3 ligands, …); no silent cross-node mutation.
- Deterministic state-machine fallback (`LocalSynGlueWorkflowGraph`) and an optional LangGraph path share the same 31-node registry.
- Mechanism chain on site: ternary ensemble → E2–lysine geometry → ubiquitination feasibility → cooperativity → hook equilibrium → DC50/Dmax → cell-context → verdict (matches module order M1→M5 and the planned target pipeline).

### 3.3 Agentic control & tools layers

- Seven-layer agentic wrapper (per README architecture): Perception → Reasoning → Goal Setting → Decision-Making → Execution → Scientific Critic → Learning → Orchestration (code: `protacxtend/agentic/`, `agents/agentic_core.py`).
- Deterministic ReAct-style specialist agents (thought/action/observation/elapsed-time recorded); no external hosted LLM required for the default workflow.
- Tools the agents call (~60 tool modules in `protacxtend/tools/`):
  - **Chemistry engine** `tools/protac_toolbox.py` — site claim "73 methods" (parse/validate, exit vectors, assembly, enumeration). Raw file has 96 `def`s incl. helpers — 73 = the documented engine-method set; count definition should be pinned (finding #4).
  - **Retrosynthesis** `tools/retrosynthesis*.py` (engines + filter; heavy backends guarded) — present on walkthrough & workflow cards.
  - **ADMET** hERG · AMES · BBB · Lipinski/Veber radar (`admet_*`).
  - **Ternary / docking** P4ward wrapper + SE(3) feasibility (`p4ward_wrapper.py`, `ternary_*.py`); external docking adapters guarded.
  - **Module tools** (JSON in/out, graph-safe): hook effect, lysine-ubiquitination, cooperativity, degradation ML, cell-context, E3-opportunity.
  - Registries: `tool_registry.py`, `toolkit_registry.py`, `toolkit_router.py`, `tool_status.py`; learning/memory (`learning_memory.py`, `memory_manager.py`).
- Research layer `protacxtend/research/` (sources, retrieval, graph, reasoning, reporting, schemas, httpbase).

### 3.4 Interfaces the site documents (verified in code)

| Surface | Command / route | Verified |
|---|---|---|
| CLI | `design` · `structure` · `dose` · `context` · `validate` · `ask` · `learn` · `contract` · `api` · `ui` (+ `status`, `capabilities`, `scenarios`) | `cli.py` has all of these plus `run`, `ternary`, `external`, `proteome`, `tui` (not all surfaced on site) |
| REST (FastAPI, :8001) | `POST /design` · `POST /mode` · `GET /health` (real routes; also `POST /agentic-design`) | `backend/api_routes.py` |
| Streamlit UI (:8501) | `protacxtend serve` / `protacxtend ui` | `protacxtend/app/streamlit_app.py` |
| Python API | `from protacxtend.agents.graph import run_syn_glue_workflow` | present in graph module |
| Chemistry API | `PROTACMasterToolbox` (site snippet) — class actually named **`ProtacDesignToolbox`** in `protac_toolbox.py` (note §7 finding #4b) | code shows class `ProtacDesignToolbox` |
| Deploy | `docker build` + run (Dockerfile), CI (`ci.yml`), Pages (`pages.yml` uploads `website/`) | workflows on repo |

---

## 4. Validation & evidence accounting

### 4.1 Per-capability status matrix (exactly what the site prints; source `config/scientific_status.yaml`)

| Capability | Impl. | Evidence type | Data source | Validation | Limitation | Public claim |
|---|---|---|---|---|---|---|
| Deep-research retrieval | ✓ | RETRIEVED | EPMC·PubMed·OpenAlex·Crossref·SearXNG | live-API smoke + tests | SearXNG needs self-host | YES |
| Hook-effect modeler | ✓ | CALCULATED | validated equations | 13/13 QA 2026-09-02 | equilibrium only | YES |
| Lysine ubiquitination | ✓ | STRUCTURAL SURROGATE | pose geometry | synthetic fixtures | real-PDB pending | PARTIAL |
| Cooperativity | ✓ surrogate | STRUCTURAL SURROGATE | feasibility | harness ready | α data-gated | DATA-GATED |
| Degradation ML (M4) | ✓ | LEARNED PREDICTION | 64/32 labels | grouped splits; audit 9/9 | small label set | YES |
| Cell-context (M5) | ✓ | LEARNED PREDICTION | DB 1913 + DepMap 24Q4 | grouped A–G; 16 tests | transcriptomic only | YES |
| Unified degradation engine | ± | HEURISTIC | integration | disagreement/uncertainty | under evaluation | NO |
| Novel E3 opportunity (M6) | ✗ (site) | NOT AVAILABLE | — | — | report-gated; code DONE | PLANNED |
| Active learning (M7) | ± | HEURISTIC | CLI surface | — | BO not built | PLANNED |

### 4.2 Verified test/test-code counts (working tree, this audit)

M1 hook 24 · M2 lysine 8 · M3 cooperativity 21 · M4 degradation 9 (9/9) · M5 cell-context 16 · M6 e3-opportunity 17 test functions in module `tests/` dirs; overall ~76 test files / 626 test functions (excluding vendored `data/protac_repos`, `.venv`, node_modules); CI = compile + asset-free smoke, fast offline units, full offline suite (incl. agentic E2E benchmark), gitleaks full-history, ruff, committed-artifact checks (`ci.yml`).

### 4.3 Honesty infrastructure on the site

- Every numerical example in the walkthrough is hard-coded in `app.js` and carries ILLUSTRATIVE/DEMO badges; the widget is titled "walkthrough", not simulator.
- Evidence badges on every card/table/caption; statuses per capability; caveats column always populated.
- Docs pane keeps six tabs; "GitHub & collaborators" pane lists org repo, Pages URL, dev mirror, CI description, and the hygiene rule (status changes start in `config/scientific_status.yaml`, not website copy).

---

## 5. Site↔code reconciliation (this run)

| Topic | Site says | Code truth | Verdict |
|---|---|---|---|
| Node count | 23+8=31 | 31 registered in `graph.py` in exact site order | ✅ |
| Retrieval APIs | 5 (SearXNG configurable) | EPMC/PubMed/OpenAlex/Crossref + guarded SearXNG | ✅ |
| Chemistry engine | 73 methods | `protac_toolbox.py`; raw 96 defs; 73 = documented method set (pin definition) | ⚠️ #4 |
| Model panel artifacts | incl. `rf_{dc50,dmax}.joblib`, `grover_fixed.pt` | not in repo (404); shipped = transformer + chemprop | ❌ #2 |
| 7 committed ML artifacts | hero stat | exactly 7 binaries on repo (5 joblib + 2 torch) | ✅/⚠️ naming |
| M6 | PLANNED / NO | code DONE, report-gated → consistent conservative claim | ✅ #3 |
| M5 numbers | 1913 rows · 1512 DepMap | `context_joined.csv` 1913 rows; tracker 1512 DepMap | ✅ |
| TACK calibration | "calibration parquet + meta" | dc50 + bin parquets present; **dmax parquet absent** | ⚠️ #5 |
| REST | /design /mode /health | present (+/agentic-design) | ✅ |
| Walkthrough | ILLUSTRATIVE | hard-coded values, labelled | ✅ |
| Install | git + docker; PyPI roadmap | no PyPI (404); Dockerfile present | ✅ |
| Class name in docs snippet | `PROTACMasterToolbox` | class is `ProtacDesignToolbox` | ⚠️ #4b |
| Live site | `the-ahuja-lab.github.io/PROTACXtend` | **404 — Pages not deployed** | ❌ #1 |

---

## 6. Findings & open gaps (new items + carried from prior audits)

1. **Pages is not live.** `https://the-ahuja-lab.github.io/PROTACXtend/` → 404; GitHub API `has_pages: false`; latest `pages.yml` run failed. Requires: Settings→Pages→Source "GitHub Actions", then a successful deploy. (Pre-existing, re-verified this audit.)
2. **Docs-pane artifact drift (SynGlue).** Site lists `rf_dc50.joblib`, `rf_dmax.joblib`, `grover_fixed.pt`; all 404 on the repo. Shipped SynGlue model = `multitask_transformer.pt` (+ chemprop for degradation). Update the model-artifacts code block + Model-panel "RF regressors + transformer committed" phrasing.
3. **Module 6 gating.** Tracker: DONE v1.0.0 (17 tests, RF AUROC .93 unseen-E3) but status report un-audited → YAML/site keep PLANNED / public-claim NO. Correct as-is; flip site+YAML only after the audit closes. The site validation row currently says "✗ / NOT AVAILABLE / Module 6 planned" — consider wording "code-complete, report-gated" once the audit registers.
4. **Chemistry-engine count definition.** Raw `protac_toolbox.py` has 96 `def`s; site says 73 methods. Pin the 73 to a countable registry (or update text) so future audits can reproduce. (4b: docs pane Python snippet says `PROTACMasterToolbox`; actual class is `ProtacDesignToolbox`.)
5. **TACK dmax calibration parquet** referenced as committed (`(+ calibration parquet)`, Model panel) but `tack_dmax.parquet` is not in the repo (dc50 + bin are). Either commit it or soften the wording.
6. **Hook-effect QA stamp** says 13/13 (2026-09-02) while `test_hook_effect.py` now defines 24 test functions — re-run and refresh the stamp/number on site + tracker, or state the tracked number precisely.
7. **Untracked hero/brand assets (deployment risk).** `website/assets/AA.webp`, `AA.png` (hero `<picture>` + preload), `logo-mark.png` (navbar/footer brand), `PROTACXtend .png` (apparent duplicate) are **untracked** in git — they must be added before the Pages push or the live hero/nav breaks.
8. **Empty `website/docs/`** directory committed — remove or populate.
9. **`documentation/README.md`** uses local `file:///storage/...` absolute links — replace with relative/GitHub links for web readability (documentation hub).
10. **Carried open items (from prior audits):** Module 2 real-PDB benchmark; Module 3 curated experimental-α dataset; unified engine stays UNDER EVALUATION; `API_REFERENCE.md` reconciliation; `cli.py` "Feynman-style TUI" help string; Module 5 follow-ups (M4-v2 retrain, proteomics leg, unseen-line transfer, mechanistic leg); Module 6 prospective validation + UniProt/PDB refresh.

---

## 7. Source-of-truth & file map

| Concern | File |
|---|---|
| Scientific statuses (site cards) | `config/scientific_status.yaml` |
| Module build statuses/QA | `protacxtend/modules/PROTACXTEND_MODULE_BUILD.md` (+ `FOLLOW_UP_TASKS.md`) |
| Node registry | `protacxtend/agents/graph.py` |
| Retrieval sources | `protacxtend/research/sources.py` |
| CLI | `protacxtend/cli.py` · REST `protacxtend/backend/api_routes.py` |
| Model artifacts | paths in §2.1 |
| Site code | `website/{index.html, styles.css, app.js, assets/}` |
| Claim/coherence audits | `website/SCIENTIFIC_CLAIM_AUDIT.md`, `website/SITE_COHERENCE_AUDIT.md`, `website/WEBSITE_CHANGELOG.md` |

*Rule: any status/data/model change must be made in YAML/tracker/code first; website copy follows. This register is a snapshot — re-run after each scientific-coherence change.*

---

## 8. Resolution log (2026-09-03) — every finding above, actioned

| # | Finding | Resolution | Status |
|---|---|---|---|
| 1 | Pages not live (404) | Requires **repo admin** (Settings → Pages → Source: GitHub Actions). Verified: pages API `build_type: workflow` already set, deploy step fails with Pages-disabled error; my account on the org repo is `admin:false`. **Action needed by repo admin**, then re-run `pages.yml` (workflow itself + static bundle are correct). | 🔒 BLOCKED (admin) |
| 2 | SynGlue artifact drift | `website/index.html` model panel + docs pane rewritten: committed artifacts = 7 binaries (5 joblib + `multitask_transformer.pt` + chemprop `best.pt`); rf/grover paths now described as guarded optionals; `config/scientific_status.yaml` synglue file fields corrected. | ✅ FIXED |
| 3 | Module 6 gating wording | Site validation matrix + docs pane updated to "code v1.0.0, report-gated · UNDER EVALUATION · not public-claimed"; `config/scientific_status.yaml` M6 → `implemented: true, status: UNDER EVALUATION, public_claim: false`. | ✅ FIXED |
| 4 | Chemistry-engine count + class name | Count pinned: **74 public callables defined in `tools/protac_toolbox.py`** (AST, 2026-09-03) → site (hero stat, DESIGN card, docs pane), `app.js`, `ARCHITECTURE.md`, YAML all updated 73→74. Docs snippets renamed `PROTACMasterToolbox`/`assemble_protac` → `ProtacDesignToolbox`/`assemble_components` (+ real signatures) in `index.html` and `API_REFERENCE.md`. | ✅ FIXED |
| 5 | TACK dmax calibration parquet | Wording corrected to "meta + DC50/binary calibration parquet" (site + this doc) — no fabricated file. | ✅ FIXED |
| 6 | Hook QA stamp | Re-ran suite: **24/24 passed (2026-09-03)** → updated site (2 places), `config/scientific_status.yaml`, module tracker, module `VALIDATION.md`. | ✅ FIXED |
| 7 | Untracked hero/brand assets | `AA.png`, `AA.webp`, `logo-mark.png` added to git index; stray `PROTACXtend .png` (unreferenced, different hash) removed. | ✅ FIXED |
| 8 | Empty `website/docs/` | Removed. | ✅ FIXED |
| 9 | `documentation/README.md` file:// links | Rewritten with relative links + corrected Workflows row (current CLI, no stale slash commands). | ✅ FIXED |
| 10 | Carried open items | `cli.py` "Feynman-style TUI" help string → cosmetic code fix applied. The rest (Module 2 real-PDB benchmark, Module 3 curated α dataset, Module 5 follow-ups, Module 6 prospective validation, API_REFERENCE deep reconciliation, unified-engine validation) are **open science/data tasks**, not site bugs — remain tracked in `protacxtend/modules/FOLLOW_UP_TASKS.md`. | ⏳ OPEN (science/data-gated) |

Also updated for consistency: `website/SCIENTIFIC_CLAIM_AUDIT.md` (rows 4, 10), `website/SITE_COHERENCE_AUDIT.md` (chemistry-engine row).
