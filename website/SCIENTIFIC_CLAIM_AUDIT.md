# SCIENTIFIC_CLAIM_AUDIT.md

Audit of every numerical / capability claim carried on the PROTACXtend website
(`website/index.html`) as of the v2 scientific-coherence rewrite.

Method: each claim was traced to source code or committed docs. **Never infer completion
from a file existing** — status comes from the module tracker
(`synglue_agent/modules/PROTACXTEND_MODULE_BUILD.md`) and
`config/scientific_status.yaml`, cross-checked against tests/CI.

Status codes: ✅ SAFE (code-backed) · ⚠️ CONDITIONAL (safe with qualifier) · ❌ REMOVED (was on the
site, now removed or reworded).

| # | Website claim (new wording) | Source file / code | Implementation | Validation | Public-display verdict |
|---|---|---|---|---|---|
| 1 | "evidence-grounded autonomous research system" | `synglue_agent/research/*` + `agents/graph.py` | retrieval clients live; governed graph present | CI smoke + full-offline | ✅ SAFE (positioning, not a metric) |
| 2 | "23-node core scientific workflow + 8 controlled-search/feedback extensions = 31 documented agent nodes" | `agents/graph.py` `LocalSynGlueWorkflowGraph.nodes` (31 registered) | yes — all 31 registered | import-tested (md/00-INDEX documents 23 core; RankingAgent runs twice) | ✅ SAFE with the 23+8 wording (production graph stops only at terminal gates) |
| 3 | "5 live retrieval APIs" (Europe PMC, PubMed, OpenAlex, Crossref; SearXNG configurable) | `research/sources.py` (`SCIENTIFIC_FIRST`, `GRAPH_SOURCES`, `WEB_SOURCES`) | europepmc/pubmed/openalex/crossref default; searxng optional | live-API smoke + tests | ✅ SAFE (SearXNG labelled configurable) |
| 4 | "73-method chemistry engine" | `tools/protac_toolbox.py` (`PROTACMasterToolbox`) | yes | unit tests | ✅ SAFE (method count from engine, docs ARCHITECTURE.md) |
| 5 | Hook Effect Modeler — "validated baseline; equilibrium; hook onset/severity; MC uncertainty" | `modules/hook_effect_modeler/` | yes | 13/13 tests; QA 2026-09-02 | ✅ SAFE (explicitly equilibrium-only, no kinetics) |
| 6 | Lysine ubiquitination feasibility — "static-geometry surrogate; real-PDB pending" | `modules/lysine_ubiquitination_feasibility/` | yes | synthetic fixtures | ✅ SAFE only with "structural surrogate / partial" qualifier — applied |
| 7 | Cooperativity — "feasibility, not trained experimental-α; data-gated" | `modules/cooperativity_alpha_predictor/` | surrogate mode | harness ready; no curated α labels | ✅ SAFE only as feasibility/data-gated — applied (NOT "α prediction") |
| 8 | Module 4 degradation ML — "pDC50/Dmax, curated 64/32 published labels, grouped splits" | `modules/degradation_ml/` (`pdc50_model.joblib`) | yes | audit approved 2026-09-02 (9/9); grouped splits | ✅ SAFE |
| 9 | Module 5 cell context — "transcriptomic; DepMap 24Q4; 1913-row DB" | `modules/cell_context_selector/` (`dataset.py` → PROTAC-Degradation-DB.csv) | yes | 16 tests; grouped A–G; leg D beats B (R² 0.605 vs 0.513) | ✅ SAFE with qualifiers applied (proteotype NOT claimed, unseen-line transfer NOT claimed) |
| 10 | "7 committed ML artifacts" | joblib/pt files listed in docs Modules pane | yes | CI artifact-availability job | ✅ SAFE (7 model files: pdc50, cell_context, tack×3, rf_dc50, rf_dmax = 7; transformer/grover also present but counted separately) |
| 11 | "Independent models never averaged silently; unified engine under evaluation" | `config/scientific_status.yaml`; ranking/`degradation_node.py` | integration not production | — | ✅ SAFE (engine labelled UNDER EVALUATION) |
| 12 | Walkthrough values (pDC50 12.4 nM, ternary 0.88 …) | browser-only `website/app.js` | hard-coded | n/a | ✅ SAFE only as ILLUSTRATIVE — every value and the whole widget carry the ILLUSTRATIVE DEMO badge; title is "walkthrough", not "live simulator" |
| 13 | "v0.3 core release · active research development" | pyproject/release lineage | — | — | ✅ SAFE (removed "final") |
| 14 | Retrosynthesis present | `tools/retrosynthesis.py`, `retrosynthesis_engines.py`, `retrosynthesis_filter.py` | yes (backends guarded) | CI smoke includes retrosynthesis tests | ✅ SAFE |
| 15 | "PyPI publishing on the roadmap" (install = git/docker) | PyPI returns 404 for `protacxtend` (checked 2026-09-02) | not published | n/a | ✅ SAFE — pip claim removed |
| 16 | REST endpoints POST /design · POST /mode · GET /health | `backend/api_routes.py` | yes | smoke checks /health | ✅ SAFE |
| 17 | "proteotype / proteomics" coverage | Module 5 | none | — | ❌ REMOVED — replaced by explicit "proteotype not claimed" |
| 18 | "active learning" as shipped capability | Module 7 pending; CLI `/learn` surface exists | partial | — | ⚠️ CONDITIONAL → "CLI surface exists; BO loop planned (Module 7)" — applied |
| 19 | "novel E3 discovery" as shipped capability | Module 6 | not built | — | ❌ REMOVED → listed as PLANNED in validation matrix |
| 20 | "Feynman-grade", "zero black boxes", "AI magic", "Every invisible interaction…" | — | marketing | — | ❌ REMOVED (replaced by the scientific contract + explicit evidence badges) |
| 21 | "Live agent pipeline simulator / exactly as the CLI would report" | — | hard-coded | — | ❌ REMOVED → "Interactive pipeline walkthrough", ILLUSTRATIVE DEMO banner, honest disclaimer |

Open items tracked in the validation matrix: real-PDB benchmark for ubiquitination
feasibility; curated experimental cooperativity dataset; unified degradation engine
integration; Module 6 and Module 7.
