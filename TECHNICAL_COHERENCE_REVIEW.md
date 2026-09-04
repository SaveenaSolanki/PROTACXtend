# TECHNICAL_COHERENCE_REVIEW.md — what we built, the logic, and the code audit

**Internal review companion — read this BEFORE presenting PROTACXtend publicly.**
Purpose: a single place that (1) presents everything we have built with the logic of each
piece, and (2) audits code ↔ docs ↔ website coherence so you can critically verify every
claim yourself. Every table row gives the exact file to open. Nothing here is "trust me" —
each row ends with a **verify command** you can run locally.

- Author: audit pass by lead dev workspace · 2026-09-03
- Repo: `the-ahuja-lab/PROTACXtend` (HEAD after fix commit `010958b` + uncommitted release staging)
- Source of truth files: `config/scientific_status.yaml` (scientific statuses) ·
  `protacxtend/modules/PROTACXTEND_MODULE_BUILD.md` (module build) · `protacxtend/agents/graph.py` (node registry)

**Verdict legend:** ✅ SAFE (verified) · ⚠️ CHECK (needs your eyes/decision) · ❌ GAP (contradiction or missing) · 🔒 BLOCKED (needs admin/access) · ⏳ OPEN (science/data-gated)

---

## 1. What we have built — one-screen map

PROTACXtend = a local, tool-augmented **agentic research platform for PROTAC design**:
evidence retrieval → component-aware design → mechanistic modeling → degradation/cell-context
prediction → Pareto ranking → dossier. Deterministic ReAct-style agents (no external LLM in the
default path), governed by a 31-node graph that runs as a **deterministic state machine** and can
run through **LangGraph** from the same registry.

| Layer | What exists | Code (open these) |
|---|---|---|
| KNOW — retrieval | Europe PMC · PubMed · OpenAlex · Crossref clients + SearXNG (guarded) + full-text crawl | `protacxtend/research/sources.py` (`SCIENTIFIC_FIRST`, `GRAPH_SOURCES`, `WEB_SOURCES` lines 37–39; clients 223–233) |
| REASON — agents | target/binder/warhead/E3/exit-vector resolution, applicability domain, critic gates | `protacxtend/agents/{supervisor,design_planner,search_control,safety,target,binder,warhead,e3,exit_vector}*.py` |
| DESIGN — chemistry | 74-method engine (`ProtacDesignToolbox`), curated + rule + generative linkers, retrosynthesis engines+filter, stereochemistry, ADMET | `protacxtend/tools/protac_toolbox.py`, `retrosynthesis*.py`, `stereochemistry_engine.py`, `generative_linker.py`, `admet_*` |
| MECH — modules M1–M5 | hook effect (M1) · lysine ubiquitination (M2) · cooperativity (M3) · degradation ML (M4) · cell context (M5); M6 (E3 engine) code-done report-gated; M7 planned | `protacxtend/modules/{hook_effect_modeler,lysine_ubiquitination_feasibility,cooperativity_alpha_predictor,degradation_ml,cell_context_selector,e3_opportunity}/` |
| DISCOVER — predictors | M4 · M5 · TACK (DC50/Dmax/bin) · SynGlue (transformer) · chemprop checkpoint; unified engine under evaluation | `protacxtend/tools/{degradation_ml_tool,cell_context_tool,tack_degradation,synglue_degradation,chemprop_degradation,degradation_node?}` · artifacts in §4 |
| Ranking | initial + final Pareto ranking, diversity clustering, evolution refinement | `protacxtend/agents/{ranking,proximity_diversity,evolution,reflection}*.py`, `tools/pareto_ranking.py` |
| Memory/report | workflow logs, dossiers, CSV/JSON export, memory update | `tools/{report_generator,memory_manager,workflow_logger}.py`, `agents/checkpointer.py` |
| Interfaces | CLI (18 subcommands) · FastAPI (:8001) · Streamlit UI (:8501) · Python API | `protacxtend/cli.py`, `backend/api_routes.py`, `app/streamlit_app.py` |
| Deploy | Dockerfile, compose, CI (`ci.yml`), Pages workflow (`pages.yml` → uploads `website/`) | `.github/workflows/`, `Dockerfile`, `deploy/` |

Verify: `ls protacxtend/agents/*.py | wc -l` → 38 · `ls protacxtend/tools/*.py | wc -l` → 93 · `ls protacxtend/research/*.py | wc -l` → 10 · tests: 76 files / 626 `def test_*`.

---

## 2. Logic map — how a run actually flows

### 2.1 The 31-node graph (exact order = `protacxtend/agents/graph.py` lines 66–97)

```
CORE 1–4   parse_user_request → create_design_plan → control_np_hard_search → safety_precheck
CORE 5–9   resolve_target → retrieve_target_binders → select_warheads → select_e3_ligands → detect_exit_vectors
CORE 10–14 generate_linkers → construct_protacs → expand_stereoisomers → validate_protacs → score_cell_context
CORE 15–23 predict_admet → check_novelty → assess_applicability_domain → cheap_filter_candidates →
           predict_degradation → initial_ranking → diversity_clustering → reflection_review → evolution_refinement
EXT 24–31  select_expensive_modeling_finalists → optional_ternary_feasibility → predict_cooperativity →
           predict_hook_effect → final_ranking → active_learning_update → generate_report → update_memory
```

**Control logic to review carefully** (`graph.py` 100–134):
- Run = for-each node in order; after each node, retry once if the planner's `repeat_policy` lists the step and budget remains; then stop if `design_plan.status == "needs_user_input"` or any error contains one of the terminal markers: *"Planner requires a target protein/gene", "No warheads selected", "No E3 ligands selected", "No PROTAC candidates assembled", "No valid or unverified candidates"*.
- ⚠️ **Review question 1:** ranking runs twice (`initial_ranking` node 20, `final_ranking` node 28) via `RankingAgent(final=False/True)` — confirm the "final" flag actually changes behaviour (weights? evidence used?) and that the 23-core/8-ext accounting (23+8=31 with RankingAgent counted in both phases) is the story you want to present.

### 2.2 KNOW → REASON → DESIGN → DISCOVER mapping

| Loop stage | Nodes | Logic essence | Evidence type recorded |
|---|---|---|---|
| KNOW | 1–3 (+research layer) | retrieval clients + DOI/title verification + claim grading; SearXNG only if configured | RETRIEVED |
| REASON | 4–9 | target resolution, binder ranking (pChembl), E3 recruitment, exit vectors, AD/OOD checks, critic | CALCULATED / RETRIEVED |
| DESIGN | 10–14 | linker gen (74-method), construction, stereoisomers, RDKit validation, early cell-context score | CALCULATED |
| DISCOVER | 15–31 | ADMET/novelty/AD → degradation M4 → rank → cluster → reflect → evolve → expensive-modeling gate → ternary/coop/hook → final rank → report/memory | CALCULATED + LEARNED PREDICTION |

### 2.3 Mechanistic logic (the parts a reviewer must interrogate)

| Module | Logic implemented | What it does NOT do (limitation, stated) | Files |
|---|---|---|---|
| M1 Hook effect | three-body mass-action equilibrium over binary+ternary species; peak/max occupancy, hook onset/severity/window; seeded MC uncertainty | not kinetics; no DC50 from this module | `modules/hook_effect_modeler/core.py`; refs Douglass 2013, Gadd 2017, Hughes & Ciulli 2017, Riching 2018 |
| M2 Lysine Ub | static-geometry scorer: E2 site geometry vs POI lysines — Shrake–Rupley SASA, distance, approach angle, steric occlusion, ensemble productive fraction | static baseline; real-PDB benchmark pending (synthetic fixtures only) | `modules/lysine_ubiquitination_feasibility/` |
| M3 Cooperativity | feasibility score / surrogate; grouped harness (constant/ridge/RF/XGB/GP) ready | NOT a trained experimental-α predictor (data-gated — no curated α labels) | `modules/cooperativity_alpha_predictor/` |
| M4 Degradation ML | pDC50 + Dmax regression; curated 64/32 published labels; grouped splits (random/scaffold/unseen-target/E3/PROTAC); prob-task honestly disabled | small label set; OOD via grouped splits + domain checks | `modules/degradation_ml/` (artifact `models/pdc50_model.joblib`) |
| M5 Cell context | cell-context pDC50 conditioned on transcriptomics (DepMap 24Q4); grouped A–G; leg D beats leg B on unseen-PROTAC pDC50 R² 0.605 vs 0.513 | transcriptomic only; proteotype NOT claimed; unseen-cell-line transfer NOT claimed | `modules/cell_context_selector/` (artifact `models/cell_context_model.joblib`) |
| M6 E3 opportunity | 30-gene catalog × 8 evidence axes → verdicts SUPPORTED/PROMISING/EXPLORATORY/INSUFFICIENT (expression-only never recommends; SUPPORTED needs direct precedent); grouped retrospective RF AUROC .93 unseen-E3 | status report gated — code done, **not public-claimed** | `modules/e3_opportunity/` + `docs/CLAIMS.md` |
| M7 Active learning | CLI `/learn` surface only | BO + feedback loop not built | `protacxtend/agents/active_learning_agent.py` |

**Critical file for M4/M5 honesty:** `protacxtend/modules/PROTACXTEND_MODULE_BUILD.md` (audit section: entity-context forwarding fix, honest in-sample R² ≈0.95 not 0.98, prob labels == 0).

### 2.4 Predictor independence & the unified engine

Independent, never silently averaged: M4 · M5 · TACK (dc50/dmax/bin) · SynGlue (transformer) · chemprop. The "unified degradation engine" is a **heuristic integration layer, UNDER EVALUATION** — code path `agents/degradation_node.py` / ranking; it must stay labelled non-production.

⚠️ **Review question 2:** What exactly does the *shipped* SynGlue path do? `tools/synglue_degradation.py` loads `multitask_transformer.pt` (line 127) and reads GROVER-encoded CSVs (`data/synglue/data/grover_{warhead,e3}.csv`); the `rf_dc50/rf_dmax.joblib` + `grover_fixed.pt` entries in `MODEL_PATHS` (lines 67–69) are **guarded optionals that are not committed** (404 on repo). Website copy now says exactly this. Confirm the transformer fallback produces the DC50/Dmax the tool reports when RF/grover are absent — or state clearly which backend is authoritative.

---

## 3. Code audit register — claim → file → verification → verdict

### 3.1 Architecture & counts

| # | Claim | Evidence to check | Verified | Verdict |
|---|---|---|---|---|
| A1 | "23 core + 8 extensions = 31 documented agent nodes" | `agents/graph.py:66–97` — count tuples | 31 names, order matches site | ✅ |
| A2 | Workflow runs as deterministic state machine; LangGraph shares registry | `graph.py` `LocalSynGlueWorkflowGraph.run` + `add_node` (line ~159) | both paths present | ✅ |
| A3 | Agents are deterministic ReAct (no hosted LLM by default) | `agents/base_agent.py`, `agentic_core.py`; README §LLM | no external call found in default path | ✅ (⚠️ confirm no silent OpenAI/Anthropic keys required anywhere — grep `openai|anthropic|gemini|groq` in `protacxtend/`) |
| A4 | "5 live retrieval APIs" | `research/sources.py:37–39` (3 + crossref + searxng guarded) | 5 incl. guarded SearXNG | ✅ (SearXNG clearly labelled configurable) |
| A5 | Chemistry engine "74 methods" | `tools/protac_toolbox.py` — AST count of public callables = 74 (2026-09-03); class `ProtacDesignToolbox` | 74 public / 96 total defs | ✅ (rule: "public callables defined in the file") |
| A6 | Module test counts | M1: 24 pass (2026-09-03 re-run) · M2: 8 · M3: 21 · M4: 9 · M5: 16 · M6: 17 | site/tracker/YAML aligned after fix commit | ✅ |
| A7 | "7 committed ML artifacts" | repo-presence 200-check: `pdc50_model.joblib` · `cell_context_model.joblib` · `tack_{dc50,dmax,bin}_model.joblib` · `multitask_transformer.pt` · `chemprop_multitarget/model_0/best.pt` | exactly 7 | ✅ (list definition now documented) |
| A8 | CLI surface on site matches code | site lists design/structure/dose/context/validate/ask/learn/contract/api/ui + verify cmds | `cli.py` has these **plus** `run`, `ternary`, `external`, `proteome`, `tui` (not surfaced on site) | ⚠️ decide whether to surface or intentionally omit |
| A9 | REST endpoints | `backend/api_routes.py` — GET /health, POST /design, POST /mode (+ POST /agentic-design not on site) | present | ⚠️ same surfacing decision |
| A10 | Install = git/docker, PyPI on roadmap | PyPI `protacxtend` 404; Dockerfile present | true | ✅ |
| A11 | Release "v0.3 core release" | `pyproject.toml:7` → **version = "0.1.0"** | mismatch | ❌ **reconcile** (bump pyproject to 0.3.x or change messaging) |
| A12 | Version/status claims consistent everywhere | README badges, site footer, YAML release block, CHANGELOG | consistent among themselves after v2.11 | ✅ |

### 3.2 Scientific claims (config/scientific_status.yaml is the source of truth)

| Capability | Status in YAML (open `config/scientific_status.yaml`) | Site row says | Verdict |
|---|---|---|---|
| Deep-research retrieval | TRAINED-API ×4, SearXNG PARTIAL | YES | ✅ |
| Hook effect M1 | VALIDATED BASELINE · 24/24 | YES | ✅ |
| Lysine Ub M2 | STRUCTURAL SURROGATE (real-PDB pending) | PARTIAL | ✅ |
| Cooperativity M3 | DATA-GATED SURROGATE | DATA-GATED | ✅ |
| Degradation ML M4 | TRAINED · audit 9/9 | YES | ✅ |
| Cell context M5 | TRAINED · transcriptomic only | YES (with qualifiers) | ✅ |
| Unified engine | UNDER EVALUATION | NO | ✅ |
| Novel E3 M6 | PARTIAL, implemented true, **public_claim true** (audit-approved 2026-09-03, `e3_opportunity/docs/AUDIT.md`) | PARTIAL (retro-validated; prospective open; per-verdict claims via CLAIMS register) | ✅ audit closed — prospective claims still barred |
| Active learning M7 | PARTIAL, implemented true (optimizer v1.0.0, synthetic-benchmarked), public_claim false | PARTIAL / not public-claimed | ✅ wording aligned |

### 3.3 Data integrity (row counts re-measured 2026-09-03)

| Dataset | Claimed | Measured | Verdict |
|---|---|---|---|
| `cell_context_selector/data/context_joined.csv` | 1913 rows | 1913 | ✅ |
| M4 curated labels | 64 pDC50 / 32 Dmax | tracker + `benchmark_predictions.csv` | ✅ (verify yourself: open CSV, count) |
| `data/tack/tack_dc50.parquet` | calibration | 4184 rows | ✅ |
| `data/tack/tack_bin.parquet` | calibration | 6561 rows | ✅ |
| `tack_dmax.parquet` | (previously implied) | **does not exist** | ✅ wording fixed to "meta + DC50/binary calibration" |
| `grover_warhead.csv` / `grover_e3.csv` / `e3_ligand.csv` | SynGlue caches | 1104 / 117 / 117 rows | ✅ |
| M6 catalog | 30 genes | `e3_catalog.csv` 30 | ✅ |

---

## 4. Critical review checklist — interrogate these before presenting

1. **`pyproject` 0.1.0 vs "v0.3 core release"** (A11) — pick one and make pyproject, README, site, YAML agree.
2. **RankingAgent twice** — what does `final=True` change? (`agents/ranking_agent.py`).
3. **SynGlue authoritative path** — transformer vs (absent) RF regressors (Q2 in §2.4).
4. **Cell-context claims** — leg D > leg B metric is *internal*; is R² 0.605 on pDC50 the metric you want public? Read `modules/cell_context_selector/docs/VALIDATION.md` + `M4_FOLLOWUP.md` before any slide.
5. **M4 honestly**: label set 64/32 is small — grouped-split metrics, OOD flags; don't let "TRAINED" read as production-grade. Limitations must stay adjacent (they are on the site).
6. **M6**: audit **closed 2026-09-03** (17/17, claims register reviewed) — engine/methodology claimable; **prospective** SUPPORTED/PROMISING performance still barred until the prospective set is scored (`FOLLOW_UP_TASKS.md` intake spec).
7. **M2/M3** are structural surrogates/feasibility only — any demo using them must carry the badge (site does; CLI output must too — verify `protacxtend structure` output wording).
8. **Hook-effect demo numbers** in `website/app.js` are illustrative (badged); confirm CLI `protacxtend dose` doesn't echo the *site* demo numbers as if model output.
9. **Live site** — still 404; Pages enablement is a repo-admin action (`admin:false` for the lead-dev account). Don't present the URL as live until deployed.
10. **Search for leftover hosted-LLM/secret expectations**: `grep -rnE "api_key|OPENAI|ANTHROPIC|GEMINI|GROQ" protacxtend/ config/ | grep -v test` — confirm nothing in the default workflow silently requires a key.
11. **Offline reproducibility**: run `python -m pytest -m "not slow and not network"` and the full suite per CI (`ci.yml`) — confirm "91 passed" style numbers before quoting suite size.
12. **Retrosynthesis guard rails**: `tools/retrosynthesis*.py` — confirm heavy backends are guarded and CLI falls back cleanly.
13. **TUI/CLI wording** — after the Feynman-string fix, grep for any remaining brand overclaim (`Feynman|zero black boxes|AI magic|final build`).
14. **API_REFERENCE.md** — flagged as still carrying some legacy surface; reconcile before publishing docs.
15. **Spreadsheet assets** (`Agent_Toolkit.xlsx`, `TOOL_AUDIT.xlsx`, registry xlsx) — open each; ensure contents match what docs claim about them.

---

## 5. Interfaces & deployment for the presentation

| Surface | How to demo | Notes |
|---|---|---|
| CLI design run | `protacxtend design --target BRD4 --e3 CRBN --num-candidates 16` | deterministic; writes md+csv+json |
| Mechanistic | `protacxtend dose` (M1) · `structure` (M2/M3) · `context` (M5) | badges in output |
| Dossier | `protacxtend contract --target BRD4 --e3 CRBN` | KNOW-REASON-DESIGN-DISCOVER trace |
| REST | `POST /design`, `POST /mode`, `GET /health` on :8001 | FastAPI |
| UI | `protacxtend serve` (:8501 Streamlit); static site = `website/index.html` | Pages blocked until admin enable |
| CI | `ci.yml` — smoke, offline units, full offline, gitleaks, ruff, artifact checks | last push state? see Actions tab |

Deploy note: `pages.yml` uploads `website/`; its verify step checks `index.html/styles.css/app.js/assets/00_PROTACXtend_hero_visual.png` — all tracked now (AA.png/webp/logo-mark staged in fix commit).

---

## 6. Open items that are NOT bugs (do not "fix" by editing copy)

Tracked in `protacxtend/modules/FOLLOW_UP_TASKS.md`: M2 real-PDB benchmark · M3 curated experimental-α dataset · M5→M4-v2 retrain + proteomics leg + unseen-line transfer + mechanistic leg · M6 prospective validation + UniProt/PDB refresh · unified-engine validation. Changing their status in `config/scientific_status.yaml`/site before the underlying work exists would be overclaiming.

---

## 7. Reproduce-everything appendix (run in repo root)

```bash
# statuses + structure
python -c "import yaml; d=yaml.safe_load(open('config/scientific_status.yaml')); print(d['modules'].keys())"
grep -c '^\s*(' protacxtend/agents/graph.py          # node tuples
python - <<'EOF'                                      # chemistry method count (74)
import ast; s=ast.parse(open('protacxtend/tools/protac_toolbox.py').read())
print(sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and not n.name.startswith('_')
          for n in ast.walk(s)))
EOF
# module test suites (M1 = 24, M5 = 16, M6 = 17 …)
python -m pytest protacxtend/modules/hook_effect_modeler/tests -q
python -m pytest protacxtend/modules/cell_context_selector/tests -q
python -m pytest protacxtend/modules/e3_opportunity/tests -q
# offline unit scope used by CI
python -m pytest -m "not slow and not network" -q
# artifact presence (must all exist)
for f in protacxtend/modules/degradation_ml/models/pdc50_model.joblib \
         protacxtend/modules/cell_context_selector/models/cell_context_model.joblib \
         data/tack/tack_dc50_model.joblib data/tack/tack_dmax_model.joblib data/tack/tack_bin_model.joblib \
         data/synglue/models/multitask_transformer.pt outputs/benchmark/chemprop_multitarget/model_0/best.pt; do
  test -f "$f" && echo "OK  $f" || echo "MISSING  $f"; done
# leftover brand overclaims
grep -rniE "feynman|zero black boxes|ai magic|final build" protacxtend/ config/ documentation/ website/index.html README.md
# hosted-LLM key expectations
grep -rniE "api_key|OPENAI_API|ANTHROPIC|GEMINI|GROQ" protacxtend/ | grep -v test
```

---

## 8. Recommended next step (presentation-readiness)

1. Resolve ❌ A11 (version) and the two ⚠️ surfacing decisions (A8/A9) + M7 wording.
2. Complete your **uncommitted release staging** as its own commit (1 188 files currently staged — do not mix with future fix commits).
3. Enable GitHub Pages (admin) and confirm the deploy at `https://the-ahuja-lab.github.io/PROTACXtend/`.
4. Re-run the appendix commands and paste outputs into this file's tables to close every ⚠️/CHECK before any public talk.



 Surface decision: CLI has 6 extra subcommands (run, ternary, external, proteome, tui) and REST has POST /agentic-design not shown on the site                                                                     
 - Confirm what RankingAgent(final=True) changes at the final-ranking node                                                                                                                                           
 - Confirm the shipped SynGlue path (transformer vs absent RF regressors) before presenting     