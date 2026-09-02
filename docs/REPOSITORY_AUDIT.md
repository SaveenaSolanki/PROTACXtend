# REPOSITORY AUDIT — PROTACpilot / SynGlue Agent (2026-09-02)

Grounding rule: every statement traces to files/tests/commits in this
repository; unverifiable claims are marked UNKNOWN. **No modules were built or
modified during this audit.** Artifacts: `artifacts/repository_inventory.json`,
`artifacts/capability_matrix.csv`, `artifacts/backend_matrix.csv`,
`artifacts/gap_matrix.csv`; full 16-column table: docs/CAPABILITY_MATRIX.md.

## 1. What exists (verified inventory)
- **6 sequential scientific modules** (tracker: `modules/PROTACXTEND_MODULE_BUILD.md`)
  M1 hook (24 t) · M2 lysine (8 t) · M3 cooperativity (21 t) · M4 degradation ML
  (9 t, audit-approved) · M5 cell-context (16 t) · M6 E3 opportunity (17 t);
  Module 7 active learning = **not built** (only an agent exists).
- **Agents**: 30+ ReAct agents (`agents/*.py`) and two orchestration graphs:
  (a) deterministic 31-node `LocalSynGlueWorkflowGraph` (graph.py, default
  `runtime mode=deterministic`; e2e ~196 s, `outputs/runs/e2e_final_20260902`);
  (b) LangGraph agentic path (`agentic_core.py` + 17 legacy `real_nodes()`).
- **Tools**: 93 tool files; 9 toolboxes in `tools/protac_autopilot_toolbox.py`
  (TargetBiology/Component/ExitVector/LinkerDesign/ConstructionStrategy/
  PredictionAndADMET/Ternary/ReviewAndEvolution/ProtacXtend) + `ProtacDesignToolbox`.
- **Interfaces**: CLI (`protacxtend/cli.py`, ~19 subcommands incl. design,
  run, ask, ternary, dose, context, proteome, learn, tui, ui, api, status,
  capabilities), FastAPI backend (`backend/main.py`, `/design`, `/agentic-design`,
  `/mode`, `/health`), TUI (`tui/`), static web preview (`website/`), deploy/
  docker-compose + p4ward worker.
- **Deep research layer** (`research/`): EuropePMC/PubMed/OpenAlex/Crossref/
  SEARX/fulltext retrieval, evidence grading, publication-style reports; 29 tests.
- **Reference data**: `data/benchmark` (chemprop train/CSVs, PROTAC-DB xlsx,
  expression_context), `data/tack` (joblibs + parquet, 6,561 endpoints),
  `data/linkers` (GRU weights), `data/synglue/models` (transformer),
  `outputs/benchmark/chemprop_{ensemble,cal}*` trained checkpoints,
  `outputs/omics_cache` (DepMap 24Q4 raw, gitignored), module curated CSVs,
  ~30 external PROTAC repos cloned under `data/protac_repos/repos`.
- **ML models**: chemprop ensembles (DC50/Dmax/Active; 3 seeds + calibrated),
  TACK joblibs, linker char-GRU, M4 pdc50 joblib, M5 cell-context joblib,
  legacy multitask transformer; isolated `.venvs` (admet, ternify, degradomap,
  bellerophon, protacfold, splitter).
- **Case-study areas present but separate**: `casestudy/`, `robust/`,
  `ICM_HMGB2_Hypothesis_Testing/`, `website/SCIENTIFIC_CLAIM_AUDIT.md`,
  `work/boltz_output` (attempted Boltz run). Treated as FINAL CASE STUDIES,
  not build tasks.

## 2. Status summary by area (A–T; detail in CAPABILITY_MATRIX.md)
FULL: deterministic runtime graph (A1), target resolution (B1), DepMap
expression context (B5/J1), E3 opportunity engine (D1), recruiter library (D2),
linker generation+scoring (E1/E2), PROTAC assembly+validation (F1), lysine
geometry (H1), chemprop degradation + M4/M5 modules (I1/I2), novelty check
(P1), Pareto ranking (Q1), reports/provenance (T1).
PARTIAL/WRAPPER: localization breadth (B4, 78-gene cache), binder retrieval
(C1, network wrappers), exit-vector (C3 — graph node stub), ternary (G1 P4ward
docker WRAPPER; G2 proxy PARTIAL), ADMET-AI (M1, WRAPPER), safety endpoints
(N1), retrosynthesis (O1, ASKCOS/AiZynth WRAPPER), selectivity (K1 partial),
active-learning (S1 agent only), research (T2).
MISSING: target-selectivity of warhead (C4), neosubstrate/off-target (K3),
bRo5 exposure model (L1 depth), PK/PD-PBPK (R1), official Link-INVENT backend,
and (scientifically) proteomics leg.

## 3. Duplication audit
| Duplication | Verdict | Canonical owner |
|---|---|---|
| Degradation prediction in ~7 files (`degradation_predictor`, `_endpoint`, `chemprop_degradation`, `tack_degradation`, `synglue_degradation`, `context_degradation_predictor`, `backend/degradation_predictor`) + M4/M5 | PARTIAL-BAD: layered (agents → endpoint → models) but several heuristic wrappers predate chemprop; runtime must route to chemprop ensemble (history commit 13699d2) | `chemprop_degradation` endpoint (+ M5 for cell context) |
| E3 selection: `e3_selector.py`, `e3_context_engine.py` (heuristic CRBN/VHL) vs M6 `e3_opportunity` engine | BAD DUPLICATION (older heuristics still live in graph via e3_agent; M6 not yet wired as the e3 node) | M6 engine (CONNECT); freeze/retire older after parity tests |
| Linker: `generative_linker.py` + `linker_generator.py` + autopilot Linker toolbox | GOOD LAYERING (agent → toolbox → generator) + naming overlap | `generate_linkers_for_pair` (generative) |
| ADMET logic: `admet_integration.py` vs `admet_predictor(s).py` vs `admet_agent` | BAD DUPLICATION risk (3 files, same domain) | `admet_integration.py` canonical |
| Cell context: M5 `cell_context_selector` vs M6 `e3_opportunity/context.py` vs `tools/proteome_selectivity.py` | GOOD (M6 reuses M5) + legacy heuristic | M5 infra; retire proteome_selectivity seeds or mark frozen |
| Active learning: `agents/active_learning_agent.py` vs future M7 | GOOD layering once M7 exists | M7 module |
| External clients: `*_client.py` + `*_lookup.py` per source (ChEMBL, PubChem, BindingDB, UniProt) | BAD DUPLICATION (two layers per source) | keep one per source + DB registry |
| Orchestration: 31-node deterministic vs 17-node agentic graph | BAD DUPLICATION risk (different node sets; exit_vector stub in real_nodes) | reconcile to one node registry |
| Claims: per-module CLAIMS.md (M6) + website audits + config yaml | partial: config stale | config/scientific_status.yaml as machine source |

## 4. Runtime graph audit (actual, derived from graph.py + runtime.py)
Default (`mode=deterministic`, runtime.py): parse_user_request → create_design_plan
→ control_np_hard_search → safety_precheck → resolve_target →
retrieve_target_binders → select_warheads → select_e3_ligands →
detect_exit_vectors → generate_linkers → construct_protacs →
expand_stereoisomers → validate_protacs → score_cell_context → predict_admet →
check_novelty → assess_applicability_domain → cheap_filter_candidates →
predict_degradation → initial_ranking → diversity_clustering → reflection_review
→ evolution_refinement → select_expensive_modeling_finalists →
optional_ternary_feasibility → predict_cooperativity → predict_hook_effect →
final_ranking → active_learning_update → generate_report → update_memory.
Each node = an agent `.run()` on shared `WorkflowState`; deterministic;
retry policy for missing outputs (`resolve_target`, `retrieve_target_binders`,
`predict_degradation`, `predict_admet`, `optional_ternary_feasibility`).
Scientific backends per node: warhead/e3/linker/construction → toolbox/RDKit;
degradation → chemprop (uncertainty-aware) with ternary revision;
ternary → stage proxy + pLDDT gate (+ optional P4ward docker);
ADMET → ADMET-AI venv or rules; ranking → NSGA-II Pareto.
Agentic mode maps the same intent to the 17 real_nodes (exit_vector =
`not_run` placeholder; safety/supervisor pass-through). e2e determinism and
hang fixes are documented (`TASK_LEDGER_20260902`, `outputs/runs/`).

## 5. Test audit
- Collected: modules 95 · agent tests 414 · root tests 122 · research 29 (total 631 across layers; module count overlaps research run scope).
- Green this session (no network/slow): modules + research **124**; root `tests/` **122** (incl. agentic, chemistry, toolkit, phase11 docking, memory, provenance, honest-report labels). Module suites M1–M6 = 95 (24+8+21+9+16+17).
- Agent-layer 414-test suite: run was in progress at freeze; historical CI/regression evidence exists (e.g., commit 378ff64 "333 regression green"; e2e suites). Fresh full-suite numbers beyond the above: mark the remainder UNKNOWN until one clean full run is recorded.
- Coverage of special classes: deterministic/reproducibility ✓ (module feature determinism, e2e), leakage-safe grouped splits ✓ (M3/M4/M5/M6), OOD/uncertainty ✓ (M4/M5/M6, conformal), missing-artifact/error paths ✓ (module tests), external-tool failure/fallback ✓ (retrosynthesis/ADMET tests), network tests skipped by default (CI markers).
- Distinction kept: unit-green ≠ scientifically validated (see VALIDATION_DEBT.md).

## 6. Claims audit — see docs/CLAIMS_REGISTRY.md (20 consolidated claims).
Highlights: pDC50/Dmax and cell-context pDC50 and E3-retrieval = SUPPORTED
(retrospective); expression-only E3 ranking and proteotype and unseen-cell
transfer and prospective novel-E3 = NOT SUPPORTED; lysine surrogate,
cooperativity and permeability = PROMISING/EXPLORATORY.

## 7. Top true gaps — see docs/GAP_ANALYSIS.md (P0: prospective validation,
claims/status sync, real ternary in loop; P1: proteomics+context, selectivity
risk, permeability, ADME breadth, active-learning module M7, dual-graph
reconciliation).

## 8. Terminal summary numbers
Modules 6 (+M7 planned) · agent files 38 (graph chain of 31 agents; 17 real_nodes), clones of 29 external repos · tools 93 files / 9 toolboxes · tests collected 631 (modules 95 +
agent+research 414 + root 122; research ⊂ agent suite) · capability status:
FULL 20 · PARTIAL 13 · WRAPPER 5 · EXPERIMENTAL 2 · SKELETON 1 · UNKNOWN 1 ·
MISSING 3 (45 rows) · top duplication: degradation predictors, E3 selectors,
ADMET files, clients/lookups, dual graphs · actions: KEEP 21 · UPGRADE 12 ·
FREEZE 5 · CONNECT 3 · BUILD 2 · DEFER 1.
Next recommended action (see DEVELOPMENT_ROADMAP.md): CONNECT first — sync
claims/status (GAP02) + unify node registry (GAP09); then VALIDATE
prospective protocol (GAP01) before any BUILD.
