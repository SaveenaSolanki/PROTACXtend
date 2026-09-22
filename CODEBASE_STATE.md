# PROTACXtend — Codebase State of the Union

> **Purpose of this file:** a single navigable entry point that says what is
> **committed**, what is **done**, what is **uncommitted on disk**, **where we
> are left**, and **where every pointer lives**.
>
> Generated from a direct inspection of the working tree (git history, file
> census, audit artifacts). Where a number comes from an audit artifact, the
> artifact is cited. No performance number is asserted here that is not stored
> in a file on disk.

---

## Snapshot

| Field | Value |
|---|---|
| Repository | `the-ahuja-lab/PROTACXtend` (local `/storage/saveena/protacpilot`) |
| Current branch | `sprint-2` |
| **HEAD commit** | `c4af830` — *feat(memory): PROTACpilot cognitive memory + opt-in host adapter* |
| HEAD date | 2026-09-12 22:07 +0530 |
| Working tree | **89 modified, 129 untracked** (not committed) |
| Package version | `protacxtend` 0.3.0 (`pyproject.toml`) |
| Branches | ~28 local / 30 remote-tracking |
| Total commits on current branch | 93 (`git rev-list --count HEAD`) |

> **Key fact:** the entire uncommitted frontier below (tpdeval, audit_nextgen,
> new scientific backends, toolkit, validation, memory upgrades) is **not in git
> yet**. The last committed work is the cognitive-memory drop of 2026-09-12.

---

## 0. TL;DR

- **Committed & working:** a large, real PROTAC-discovery platform — deterministic
  design pipeline, cheminformatics, docking/MD, degradation predictors, 7
  scientific modules, an agentic control layer, CLI/API/TUI/Streamlit surfaces,
  a governed 48-task benchmark spec, and a standalone cognitive-memory subsystem.
- **Committed but scientifically restricted:** most scientific modules are
  surrogates or data-gated; ternary predicted structure is explicitly
  `NOT_VALIDATED`; there is no scored head-to-head benchmark result for any system.
- **Uncommitted frontier (the current work):** the `tpdeval/` head-to-head
  evaluation instrument, the `audit_nextgen/` full-platform audit, a
  capability-first scientific-backend layer, an external-toolkit provisioning
  system, a scientific-validation layer, and major memory/benchmark upgrades.
- **Where we are left (headline gaps):** author + verify benchmark ground truth,
  wire the missing comparator/baseline systems, fix the NL entity parser, harden
  `shell=True`/`pickle` security, and unify the two parallel agent stacks. Full
  register: `audit_nextgen/csv/gap_analysis.csv` (G01–G16) and
  `tpdeval/docs/02_BLUEPRINT.md` (P0–P3).

---

## 1. Canonical sources of truth (read these first)

| Topic | File |
|---|---|
| Scientific status of every module/model | `config/scientific_status.yaml` |
| External toolkit inventory + exact versions | `TOOLKIT_TRUTH.md` (+ `analysis/inventory/PROTACXtend_Toolkit_Truth.xlsx`) |
| Committed benchmark spec / protocol / blindness | `benchmark/README.md`, `benchmark/BENCHMARK_PROTOCOL.md`, `benchmark/BLINDNESS_RULES.md`, `benchmark/SCORING_RUBRIC.md` |
| Measured scientific results | `results/SCIENTIFIC_VALIDATION.md`, `results/BENCHMARK_RESULTS*.md`, `results/CAPABILITY_CLAIM_TABLE*.md` |
| Known limitations | `results/LIMITATIONS.md` |
| Head-to-head benchmark design + verdict | `tpdeval/docs/00_AUDIT.md` → `01_DESIGN.md` → `02_BLUEPRINT.md` → `03_VERDICT.md` |
| **Benchmark & audit-sheet audit (done/scorable/scored)** | `BENCHMARK_AUDIT.md` |
| **Project closeout (what's left · TUI · server install · Biomni-level depth)** | `PROJECT_CLOSEOUT.md` |
| Full-platform audit + gap register | `audit_nextgen/PROTACXTEND_NEXTGEN_AUDIT.md`, `audit_nextgen/csv/gap_analysis.csv` |
| Distribution / packaging | `documentation/DISTRIBUTION_PLAN.md` |
| Capability-first backends | `documentation/SCIENTIFIC_BACKENDS.md` |
| Architecture | `documentation/ARCHITECTURE.md`, `docs/PROTACXTEND_RUNTIME_ARCHITECTURE.md` |

---

## 2. What the project is

PROTACXtend is a local, tool-augmented AI-agent platform for component-aware
PROTAC design, ternary-complex feasibility modelling, and degradation prediction.

- Natural-language objective → structured workflow state → governed agent graph
  (**23-node core + 8 extensions = 31 documented nodes**) → deterministic tools /
  mechanistic modules / ML models → ranked candidate records + reports.
- Framework: **KNOW → REASON → DESIGN → DISCOVER**.
- Every executed step records input, output, evidence source, model version and
  limitation (`protacxtend/run_records.py` → `AgentRunRecord` / `run.json`).
- The default workflow is **deterministic and local**; hosted LLMs are optional
  and configured via `protacxtend llm` / `protacxtend auth` / `protacxtend model`.

---

## 3. Repository map (top level)

| Path | What it holds | State |
|---|---|---|
| `protacxtend/` | Main package — 465 `.py` files, ~91k LOC | committed + heavy uncommitted edits |
| `protacpilot-memory/` | Standalone cognitive-memory subsystem — 112 `.py`, ~18.7k LOC | committed core + uncommitted upgrades |
| `tpdeval/` | TPD head-to-head evaluation framework (500-task design) — 19 `.py`, ~2.1k LOC | **untracked** |
| `audit_nextgen/` | Next-gen audit: 15 CSV tables, 10 plots, 12 wireframes, 65KB report | **untracked** |
| `benchmark/` + `benchmark_runner/` | Governed 48-task benchmark + fail-closed runner/freeze | committed |
| `sota/`, `SOTA/` | SOTA comparison, blueprint, audit pack, closure runs | untracked / partial |
| `sota/eval/eval500/` | 500 template-generated + 100 adversarial tasks (design mock) | uncommitted |
| `tests/` | Root test layer — 32 `.py`, ~3.3k LOC (incl. `test_tpdeval.py`) | mixed |
| `scripts/` | 47 `.py`, ~12.8k LOC — audits, validation runners, release/packaging | uncommitted |
| `analysis/` | Capability inventory + plots + failure-escalation audit | uncommitted |
| `results/`, `validation_runs/` | Measured validation outputs, figures, tables, provenance | mixed |
| `documentation/`, `docs/` | Architecture, workflows, API, runtime, distribution | mixed |
| `website/`, `site/` | Static landing page / built site | committed / built output |
| `tui/` (`tui/src/app.ts`) | TypeScript TUI sources | uncommitted edits |
| `synglue_agent/`, `SynGlue_Py/` | Legacy names kept for compatibility / vendored model | legacy |
| `data/`, `config/`, `outputs/`, `runtime/` | Data, config, generated runs, runtime state | mixed |
| `papers/`, `notes/`, `.agents/` | empty placeholders | empty |

---

## 4. Committed history — what is DONE in git

### 4.1 Timeline by era (newest first)

| Era | Commits | What landed |
|---|---|---|
| **Cognitive memory** | `c4af830` | Standalone `protacpilot-memory` (phases 1–6) + opt-in host adapter `protacxtend/memory/cognitive_bridge.py`; 84 memory tests + 18 bridge tests; runtime hook `PROTACPILOT_COGNITIVE_MEMORY=1` (default OFF) |
| **Benchmark sprint 2** | `4855e22`, `142ceec`, `e6a8822` | Runner + scoring + freeze provenance (dev fixtures only); authored all 48 cases + frozen ground truth; benchmark spec/protocol/blindness/schemas/rubric/baselines |
| **Sprint 1** | `e31314a`, `64402b2` | Provider manager, auth/model CLI, provider-aware doctor, frozen result schema 1.0.0, six-BRD4 smoke; acceptance + regression evidence |
| **Global CLI + workflows** | `18ecfa7`, `4efe5f9`, `bb942b4`, `f0fdb10`, `e733423`, `87f3477`, `8e6854d`, `154ee43` | Global CLI, `/doctor` diagnostics, standardized scientific result schema, BRD4-VHL six-PROTAC benchmark, benchmark infra |
| **Structural engine** | `736d848`, `b5ab90b`, `02cbc09`, `4fb1227`/`1f7f9a2` | PROTACpilot structural pipeline blueprint + honest external gating; conformer fix; auto-derived 5T35 docking site; modern ternary pose engine |
| **Pi runtime** | `9812a58`/`840a9dd`, `7d19427`/`3235c98`, `f564f19`/`5bf2268`, `907c5f2` | Runtime slices A–E (persistent worker, tools, workflow handoff), E–H (launcher, live streaming, project/session store, artifact lineage), installation-anchored launcher, runnable blueprint |
| **Conversational agent** | `bc952a0`/`4296e4f`, `b38f430`, `b70ba02`/`4f15250` | Conversational agent loop + strict tool registry + graph handoff; agent architecture doc; startup LLM picker + assistant chat |
| **TUI** | `f65d840`/`811b19c` | Published launcher + TUI source for the one-line installer |
| **Module program** | `801d345`, `1fddf4f`, `d147645`, `8c1b9a8` | M7 active-learning optimizer; M6 E3-opportunity engine (RF AUROC .93 unseen-E3); claim register; M5 cell-context degradation model (leg D R² 0.605 vs 0.513) |
| **E3 / linker / ternary** | `378ff64`, `25f04b5`, `e827862`, `3085253`, `f4b940b`, `87c5328` | 114-row/19-E3 cited ligand library; generative char-GRU linker model; Link-INVENT scoring + REINFORCE optimizer; TACK degradation cross-check; real ternary ensemble; real retrosynthesis |
| **Production wiring / deploy** | `541b43f`, `a3aa02f`, `f4f213b`, `7621349`, `fb81d54`, `3e2039d`, `086aadd` | Postgres checkpointer + job queue + tracing + docker-compose; LLM role harness; three-store memory; HERUKA.AI run-bundle export |
| **Foundation / release tree** | `25470b8`, `7f8e116`, `c945ecd`, `926ff9b` | “Final release tree v0.3+” agentic 23-node core / 31-node platform; v0.3 snapshot; initial commits |
| **Rename + hygiene** | `9a18fd3`, `b6b01ac`, `b4ed39b`, `4a259ea`, `d147645` | `synglue_agent` → `protacxtend`; gitignore repairs; untrack generated outputs; gitleaks allowlist |

### 4.2 Scientific modules (M1–M7) — committed, with honest status

Status is governed by `config/scientific_status.yaml`. Summary:

| Module | Status | Note / validation |
|---|---|---|
| M1 Hook-effect modeler | `VALIDATED BASELINE` | Mass-action three-body equilibrium; 24/24 tests |
| M2 Lysine-ubiquitination feasibility | `STRUCTURAL SURROGATE` | Static-geometry scorer; real-PDB benchmark pending |
| M3 Cooperativity α | `DATA-GATED SURROGATE` | Benchmark harness ready; no curated experimental labels |
| M4 Degradation ML | `TRAINED` | pDC50 + Dmax regression; curated 64/32 labels; grouped splits; 9/9 tests |
| M5 Cell-context | `TRAINED` | Transcriptomic cell-context pDC50; leg D beats B on unseen-PROTAC (R² 0.605 vs 0.513); 16 tests |
| M6 Novel-E3 engine | `PARTIAL` | 30-gene × 8 axes; verdicts SUPPORTED/PROMISING/EXPLORATORY/INSUFFICIENT; RF AUROC .93 unseen-E3; 17 tests; prospective validation open |
| M7 Active learning / experiment selection | `PARTIAL` v1.0.0 | Multiobjective BO (RF surrogate, EI/UCB, µ+λ evolution); synthetic benchmark only; `public_claim: false` |

> **Claim discipline:** `results/CAPABILITY_CLAIM_TABLE.md` separates *supported*
> from *not yet supported* claims, each tagged to evidence.

### 4.3 Agentic core (committed)

- Seven layers in `protacxtend/agentic/`: perception, reasoning, goal setting,
  decision-making, execution, learning/adaptation, orchestration.
- Agent graph `protacxtend/agents/graph.py` — deterministic state-machine with
  LangGraph when installed, local fallback otherwise.
- Specialist agents: target, binder, warhead, E3, linker, construction,
  prediction, ADME/Tox, novelty, ternary, ranking, reflection, report, memory.
- `protacxtend/tools/*.py` — 34 registered agent tools (see §6).
- `run_records.py` — canonical `AgentRunRecord` + `run.json` provenance.

---

## 5. Uncommitted frontier — what is on disk but NOT in git

`git status`: **89 modified, 129 untracked**. Grouped by area, with pointers.

### 5.1 `tpdeval/` — TPD head-to-head benchmark instrument (**new, untracked**)

`TPD-HEADTOHEAD/1.0.0`. Compares PROTACXtend vs Biomni, an independent TPD
agent, a general LLM, retrieval-only (E), tool-only (F) and hybrids (G/H).

- Modules: `taxonomy.py` (16 domains, L1–L7, 300/150/50 split, 100 stress tags),
  `taskmodel.py`, `allocation.py`, `toolenv.py`, `evidence.py`, `mechanism.py`,
  `trajectory.py`, `calibration.py`, `temporal.py`, `failure.py`,
  `dimensions.py` (deterministic 11-dimension machine+expert scoring),
  `reproducibility.py`, `stats.py`, `ablation.py`, `systems.py`, `adapters.py`,
  `provenance.py`, `scoring.py`, `reporting.py`.
- Generated: `tpdeval/config/allocation_500.json` (500-task **design** manifest).
- Docs: `tpdeval/docs/00_AUDIT.md`, `01_DESIGN.md`, `02_BLUEPRINT.md`, `03_VERDICT.md`.
- Tests: `tests/test_tpdeval.py` (20/20 documented).
- **Status:** instrument built; **0/500 tasks scorable**, no system wired, every
  verdict cell = `NOT YET MEASURED`.

### 5.2 `audit_nextgen/` — full-platform audit (**new, untracked**)

- `PROTACXTEND_NEXTGEN_AUDIT.md` (~65 KB) — technical/scientific/agentic/product audit.
- `audit_nextgen/csv/*.csv` (15 tables: repo census, tool inventory, capability
  matrix, test results, gap analysis, verdict table, …).
- `audit_nextgen/plots/` (10 PNG+SVG), `audit_nextgen/wireframes/`,
  `audit_nextgen/measurements/measured_facts.json`.
- Generators: `audit_nextgen/make_csv.py`, `audit_nextgen/make_plots.py`.

### 5.3 New `protacxtend` subsystems (**untracked**)

| Area | Path |
|---|---|
| Capability-first scientific backends | `protacxtend/scientific_backends/` (`registry.py`, `dispatch.py`, `consensus.py`, `capabilities.py`, `doctor.py`, `evidence.py`, `licenses.py`, `validation.py`, `backends/`, `optional_backends/`) |
| External toolkit provisioning | `protacxtend/toolkit/` (`catalog.py`, `provision.py`, `environments.py`, `bridge.py`, `status.py`, `truth.py`, `registry.py`, `schema.py`) |
| Scientific validation layer | `protacxtend/validation/` (docking, energetics, ternary, pocket, ppi, dimensions, claims, datasets, curation, crosswalk, reproducibility, figures, report, runtime, services, io, fallback) |
| Runtime recipes / audit | `protacxtend/runtime/` (`registry.py`, `recipes.py`, `executor.py`, `agent_tools.py`, `audit.py`, `e2e.py`, `acquisition.py`) |
| Escalation / audit | `protacxtend/escalation/`, `protacxtend/audit/`, `protacxtend/audit_report.py` |
| New scientific modules | `modules/brd_bet_intelligence/`, `modules/chameleonicity_3d/`, `modules/neosubstrate_risk/`, `modules/resistance_mechanisms/`, `modules/cooperativity_alpha_predictor/calibration.py` + `data/calibration_report.json` + `cooperativity_provenance.json` |
| New workflows | `workflows/convergence.py`, `workflows/md_runner.py`, `workflows/validation_pipeline.py` |
| Schemas / resources | `schemas/protac_candidate.py`, `resources.py` |
| LLM setup | `llm/setup_wizard.py`; modified `llm/manager.py`, `llm/providers.py` |
| Web / evaluator | `app/web_capability.py`, `evaluator.py` |
| Tooling | `tools/linker_char_gru.py`; modified most `tools/*.py` |
| Data assets | `data/benchmark/`, `data/case_study/`, `data/linkers/`, `data/tack/`, `data/toolkit/` |

### 5.4 Modified (tracked) `protacxtend` files

`cli.py`, `diagnostics.py`, `results/io.py`, `run_records.py`,
`case_study/brd4_vhl_six.py`, `agentic/registry.py`, `tui/app.py`,
`tui/styles.tcss`, `tui_bridge/server.py`, `app/streamlit_app.py`,
`backend/api_routes.py`, `backend/schemas.py`, `memory/cognitive_bridge.py`,
`modules/active_learning/search_space.py`, `modules/e3_opportunity/*`,
`modules/cooperativity_alpha_predictor/*`, `toolkit/{__init__,registry}.py`,
and most of `tools/*.py`.

### 5.5 `protacpilot-memory/` upgrades (**untracked + modified**)

- New: `benchmarks/{ablation,baselines,benchmark_h,benchmark_i,bounded_candidates,metrics,performance}.py`,
  `benchmarks/results/`, `evaluation/`, `paper/`,
  `src/protacpilot_memory/cognitive/state_machine.py`,
  `src/protacpilot_memory/retrieval/candidates.py`.
- New tests: `test_ablation`, `test_benchmark_h`, `test_benchmark_i`,
  `test_bounded_candidates`, `test_context_fields`, `test_evaluation`,
  `test_paper_artifacts`, `test_pattern_completion`, `test_performance`,
  `test_procedures`, `test_scientific_metrics`, `test_state_machine`.
- Modified: 13 core files (encoder, retriever, consolidation, reconsolidation,
  pattern_completion, config, db, api, errors, mcp, retrieval, store, util) +
  `PROTACPILOT_COGNITIVE_MEMORY_AUDIT.md`, `README.md`.

### 5.6 Other uncommitted artifacts

- `sota/` additions: `closure/`, `runtime_closure/`, `impl/`, `eval/`,
  `data/`, `plots/`, `wireframes/`, `PROTACXTEND_AUDIT.md`,
  `PROTACXTEND_BLUEPRINT.md`, `SOTA_COMPARISON.md`, `TPD_WINNING_PLAN.md`,
  `NEW_VS_OLD.md`, `PROTACXtend_SOTA_Audit_Pack.xlsx`.
- `SOTA/` (biomini/robin/ai_scientist notes + `ranking_prompt.txt`).
- `analysis/` (inventory + plots + `audit/`), `results/`, `validation_runs/`,
  `benchmark_results/`, `outputs/{audits,capabilities,escalation,gap_completion,reports}/`.
- `scripts/` (audit/validation/release/packaging), `tests/` new tests
  (`test_tpdeval`, `test_scientific_backends`, `test_validation_pipeline`,
  `test_escalation`, `test_evaluate_protac_candidate`, `test_scientific_outcomes`,
  `test_agent_tool_exposure`, `test_cognitive_integration_safety`,
  `test_investigate_persistence`, `test_toolkit_subsystem`,
  `test_degradation_fallback_provenance`).
- Root docs: `TOOLKIT_TRUTH.md`, `SESSION_SUMMARY.md`,
  `TECHNICAL_REVIEW_AND_STATUS_2026-09-04.md`, `MANIFEST.in`,
  `documentation/{DISTRIBUTION_PLAN,SCIENTIFIC_BACKENDS,TECHNICAL_COHERENCE_AND_AGENT_TOOLKIT_AUDIT}.md`,
  `config/capability_backend_crosswalk.yaml`, `data/ternary_benchmark_six.json`.
- Large transient caches: `.p.npy`, `.score.npy`, `.so3_*.npy` (~430 MB),
  `build/`, `dist/`, `site/`.

---

## 6. Verification status

### 6.1 Tests

| Layer | Test files | Test functions |
|---|---|---|
| `protacxtend/tests/` | — | ~583 |
| `protacpilot-memory/tests/` | 26 | ~171 |
| `tests/` (root) | 32 | ~208 |
| **Total** | | **~962** |

> The audit records (`audit_nextgen/csv/test_results.csv`) note the suite does
> not complete in <25 min and had failures/timeouts — see gap **G11**.

### 6.2 Benchmarks

| Benchmark | Tasks | Ground truth | Scorable | State |
|---|---|---|---|---|
| `benchmark/` (Sprint-2 governed) | 48 (12 KNOW / 12 REASON / 12 DESIGN / 12 DISCOVER) | 48 files, frozen (100-entry `FREEZE_MANIFEST.json`) | 0 — `expected_answer: null` in every case | specification only; not scientifically validated |
| `sota/eval/eval500/` | 500 core + 100 adversarial | template-generated | ~only hard-coded UniProt “exact” | **MOCK / SCIENTIFICALLY UNVALIDATED** |
| `tpdeval/` (head-to-head) | 500 (design) | 0 authored | 0 | instrument built, no measurement |
| BRD4-VHL six-PROTAC | 6 | case study | prospective | smoke/prospective case study |

Known authoring bug documented in `benchmark/ERRATUM_v1.0.1.md`
(`KNOW-01` froze wrong UniProt id `Q60885` instead of `O60885`).

### 6.3 Scientific validation (measured, from `results/`)

- Docking pose recovery vs crystal (see `results/SCIENTIFIC_VALIDATION.md`):
  DiffDock top-1 median RMSD 1.22 Å; GNINA 1.045 Å; Vina 4.0855 Å (6-complex
  subset). The larger 40-complex redocking audit reports Vina median RMSD
  **2.356 Å** (`audit_nextgen/`).
- Pocket detection (fpocket, 6 complexes): top-1 recovery 0.167 — reported as a
  **negative result**.
- MM/PBSA on the OpenFF system **not scored** (ParmEd export limitation);
  MM/GBSA explicitly `NOT_VALIDATED`.
- Scientific Validation Rate (SVR): **0.333** over capabilities with a
  meaningful benchmark.
- Ternary predicted-structure DockQ: **NOT_VALIDATED** (`results/claims`).

### 6.4 Toolkit readiness (`TOOLKIT_TRUTH.md`, generated 2026-09-16)

| Metric | Value |
|---|---|
| toolkit tools | 115 (30 installed & callable, 47 installable, 13 commercial, 13 web-only, 21 repo-required) |
| agent tools | 34 ready |
| datasets | 59 (53 present) |
| capabilities | 27 (20 ready) |

---

## 7. Where we are left — gap register

### 7.1 P0 (blocking any comparison) — from `tpdeval/docs/02_BLUEPRINT.md`

| # | Deliverable | Status |
|---|---|---|
| P0.1 | Author 500 ground truths with citations | NEXT |
| P0.2 | Task authoring/validation CLI (refuses unscorable tasks) | NEXT |
| P0.3 | Independent TPD-agent comparator (system C) | BLOCKED (external choice) |
| P0.4 | Retrieval-only (E) + tool-only (F) adapters | NEXT |
| P0.5 | Hybrid G/H adapters | NEXT |
| P0.6 | Matched-tool environment guard | NEXT |
| P0.7 | Fault-injection hook in runner | NEXT |
| P0.8 | Freeze + hash the 500 tasks and GT | NEXT |
| P0.9 | Multi-provider model control | NEXT |
| P0.10 | Publish the fairness manifest for every system | NEXT |

### 7.2 Priority gaps — from `audit_nextgen/csv/gap_analysis.csv`

| ID | Pri | Problem | Fix |
|---|---|---|---|
| G01 | P0 | Entity parser mis-identifies target (`'degrade BRD4'`→`DEGRADE`) | NER/gene-symbol resolver + intent parser + tests |
| G02 | P0 | No authored 500-task benchmark (0/500 scorable) | author citation-backed GT + expert review |
| G03 | P0 | Ground truth absent/unaudited (48 × `expected_answer=null`) | GT authoring + independent verification protocol |
| G04 | P0 | No independent comparator/baselines (C/E/F/G/H unwired) | wire Biomni + TPD agent + retrieval/tool-only + hybrids |
| G05 | P0 | No temporal freeze/leakage control | TemporalEvidenceStore / FrozenIndex / LeakageAuditor |
| G06 | P0 | Per-claim evidence grounding absent | claim schema + evidence graph + grounding scorer |
| G07 | P1 | ~~No typed `TherapeuticStrategy` output~~ **DONE** | `protacxtend/canonical/`: `TherapeuticStrategy.v1` with target validation, E3/warhead/linker/candidate fields, structure/degradation/ADME/safety/resistance, experimental plan, go/no-go, evidence/contradictions/uncertainty, run manifest — persisted as `therapeutic_strategy.json` |
| G08 | P1 | Multi-agent reasoning is single-pass | hierarchical planner + specialists + critics |
| G09 | P1 | Tools execute on canned fixtures (`CCO`, synthetic pose) | require validated inputs; fail closed |
| G10 | P1 | Failure recovery rate 0.0 | unified failure taxonomy + repair controller |
| G11 | P1 | Test suite >25 min + failures | split fast/slow, mark heavy, fix failures |
| G12 | P1 | Security: `shell=True` + `pickle.load` | arg lists only; safe loaders; sandbox installs |
| G13 | P2 | No biomarker/combination capability | omics/biomarker + synergy modules |
| G14 | P2 | ADME/PK lacks PK | PK/clearance model or explicit boundary |
| G15 | P2 | Ternary predicted structure unvalidated | validate predicted-pose DockQ or restrict claim |
| G16 | P3 | UI lacks investigation-graph/decision/benchmark screens | new UI screens + API |

### 7.3 Structural findings (from `audit_nextgen`)

- 🟢 **Parallel agent stacks collapsed** (`protacxtend/canonical/`, ADR-001):
  one parser, task graph, evidence ledger, critic and decision engine around
  both engines. See `documentation/CANONICAL_STACK.md`.
- **115 toolkit tools are registered but not executable** (only 30 callable).
- **Natural-language front door broken** at
  `protacxtend/tools/protac_toolbox.py::parse_user_request`.
- **No system has ever produced a scored result on a full benchmark** — this is
  the single most important standing finding.

---

## 8. Quick reference — entry points & commands

### 8.1 CLI (`PROTACXtend` / `protacxtend`)

```bash
protacxtend run                       # unified runtime
protacxtend design ...                # deterministic design → report/CSV/JSON
protacxtend validate <SMILES>         # validate + score a PROTAC
protacxtend ternary <SMILES>          # ternary feasibility
protacxtend structure ...             # pose-backed ubiquitination geometry
protacxtend dose ...                  # dose–response + hook risk
protacxtend context ...               # cell-context degradation adapter
protacxtend proteome ...              # proteome/cell-context selectivity
protacxtend learn --action lock|recommend
protacxtend contract ...              # scientific contracts & dossiers
protacxtend tui | ui | api            # surfaces
protacxtend pilot                     # PROTACpilot structural workflow
protacxtend llm | auth | model        # LLM config
protacxtend doctor                    # provider-aware system checks
protacxtend backends                  # capability-first backend readiness
protacxtend toolkit --action plan|provision|verify|truth
protacxtend escalation ...            # failure diagnosis + fallback
protacxtend case-study                # six BRD4–VHL blinded smoke
protacxtend install --recipe ...      # approved isolated-env capability
```

### 8.2 Tests / audits / pipelines

```bash
pytest -q                                                 # all tests
pytest protacxtend/tests protacpilot-memory/tests tests -q
python -m tpdeval.allocation                              # regenerate 500-task design manifest
python -m pytest tests/test_tpdeval.py -q                 # 20 tpdeval tests
python -c "from tpdeval import validate_taxonomy; print(validate_taxonomy())"
python scripts/run_scientific_audit.py                    # scientific audit
python scripts/run_full_validation.py                     # full validation
python scripts/audit_benchmarks.py                        # benchmark audit
python scripts/capability_maturity.py                     # maturity report
python scripts/build_claim_table.py                       # claim table
python audit_nextgen/make_csv.py && python audit_nextgen/make_plots.py
cd protacpilot-memory && python -m pytest tests -q
ppmemory init && ppmemory doctor                          # memory CLI
```

### 8.3 Memory subsystem

```bash
cd protacpilot-memory
python -m pip install -e .
ppmemory --help
```
Design pipeline: `EXPERIENCE → ATTENTION/SALIENCE → ENCODING → EPISODIC →
REPLAY → CONSOLIDATION → SEMANTIC → RETRIEVAL → PREDICTION → OUTCOME →
PREDICTION ERROR → RECONSOLIDATION`.
Host integration is opt-in: `PROTACPILOT_COGNITIVE_MEMORY=1`.

---

## 9. Pointer index by topic

### Architecture & runtime
- `documentation/ARCHITECTURE.md`
- `docs/PROTACXTEND_RUNTIME_ARCHITECTURE.md`
- `docs/SESSION_AND_ARTIFACT_MODEL.md`
- `docs/CONVERSATIONAL_AGENT_ARCHITECTURE.md`
- `docs/PI_INTEGRATION.md`, `docs/SKILLS.md`, `docs/PERMISSIONS.md`
- `documentation/WORKFLOWS.md`, `documentation/API_REFERENCE.md`

### Science / modules / validation
- `config/scientific_status.yaml` ← **source of truth**
- `protacxtend/modules/PROTACXTEND_MODULE_BUILD.md`
- `protacxtend/modules/*/docs/` + `*/VALIDATION.md`
- `protacxtend/modules/*/LIMITATIONS.md`
- `protacxtend/modules/e3_opportunity/docs/CLAIMS.md` (Module-6 per-verdict claim register)
- `results/benchmarks/claims/CLAIMS.md`
- `results/SCIENTIFIC_VALIDATION.md`, `results/LIMITATIONS.md`
- `results/BENCHMARK_RESULTS.md`, `results/BENCHMARK_RESULTS_V2.md`
- `results/CAPABILITY_CLAIM_TABLE.md`, `results/CAPABILITY_CLAIM_TABLE_V2.md`
- `results/PAPER_RESULTS_SUMMARY.md`, `results/USECASE_VALIDATION.md`
- `results/REPRODUCIBILITY.md`, `results/TOOL_AUDIT.md`
- `results/FIGURE_INDEX.md`, `results/TABLE_INDEX.md`

### Benchmark
- `benchmark/README.md`, `benchmark/BENCHMARK_PROTOCOL.md`,
  `benchmark/BLINDNESS_RULES.md`, `benchmark/SCORING_RUBRIC.md`,
  `benchmark/BASELINES.md`, `benchmark/TASK_SCHEMA.json`,
  `benchmark/RESULT_SCHEMA.json`, `benchmark/FREEZE_MANIFEST.json`,
  `benchmark/ERRATUM_v1.0.1.md`, `benchmark/SPRINT2*_*.md`
- `benchmark_runner/runner.py`, `benchmark_runner/freeze.py`
- `tpdeval/docs/00_AUDIT.md` … `03_VERDICT.md`

### Audits
- `audit_nextgen/PROTACXTEND_NEXTGEN_AUDIT.md` + `csv/`, `plots/`, `wireframes/`
- `audit_nextgen/csv/gap_analysis.csv`, `benchmark_readiness.csv`, `verdict_table.csv`
- `analysis/audit/` (`PROTACXTEND_STATUS.md`, `INVENTORY_AUDIT.md`, `ESCALATION_AUDIT.md`)
- `sota/PROTACXTEND_AUDIT.md`, `sota/PROTACXTEND_BLUEPRINT.md`,
  `sota/SOTA_COMPARISON.md`, `sota/NEW_VS_OLD.md`, `sota/TPD_WINNING_PLAN.md`
- `TECHNICAL_REVIEW_AND_STATUS_2026-09-04.md`,
  `documentation/TECHNICAL_COHERENCE_AND_AGENT_TOOLKIT_AUDIT.md`
- `NP_HARD_AGENT_DESIGN.md`, `TOOLKIT_TRUTH.md`, `SESSION_SUMMARY.md`

### Memory
- `protacpilot-memory/README.md`
- `protacpilot-memory/PROTACPILOT_COGNITIVE_MEMORY_AUDIT.md`
- `protacxtend/memory/cognitive_bridge.py`
- `protacpilot-memory/benchmarks/`, `protacpilot-memory/evaluation/`, `protacpilot-memory/paper/`

### Distribution / ops
- `documentation/DISTRIBUTION_PLAN.md`, `documentation/SCIENTIFIC_BACKENDS.md`
- `documentation/GETTING_STARTED.md`, `documentation/GITHUB_AND_COLLABORATION.md`
- `scripts/package_release.sh`, `scripts/distribution_smoke.sh`, `scripts/install.sh`
- `scripts/setup_scientific_envs.sh`, `scripts/universal_setup_report.py`
- `Dockerfile`, `deploy/`, `requirements.txt`
- `website/`, `site/`, `tui/`

---

## 10. Definition of “next” (recommended order)

1. **Commit or discard the uncommitted frontier.** The working tree is 89/129
   files ahead of `c4af830`; decide per bundle (`tpdeval/`, `audit_nextgen/`,
   `scientific_backends/`, `toolkit/`, `validation/`, memory upgrades).
2. **P0.2 + P0.1** — build the authoring/validation CLI, then author and
   independently verify ground truth (kills G02/G03).
3. **G01** — fix the entity/intent parser (unblocks every NL task).
4. **P0.3/P0.4/P0.5** — wire systems C/E/F/G/H, then P0.10 fairness manifest.
5. **P0.6/P0.7/P0.8/P0.9** — matched-tool guard, fault injection, freeze, model control.
6. **G12** — remove `shell=True` / unsafe `pickle.load` before any external release.
7. Re-run `scripts/run_full_validation.py` and publish from measured data only.

> Standing rule for the whole project: *code present ≠ imports ≠ executes ≠
> schema-valid ≠ scientifically meaningful ≠ experimentally validated.* Every
> status in this document follows that rule, and every performance cell stays
> `NOT YET MEASURED` until a scored run exists.
