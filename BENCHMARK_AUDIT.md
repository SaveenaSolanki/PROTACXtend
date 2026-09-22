# Benchmark & Audit-Sheet Audit — how much is actually done

> **Scope:** every benchmark artifact and every audit "sheet" (XLSX/CSV) in the
> repository, audited against the files on disk.
>
> **Method (audit rules):** *listed ≠ authored ≠ frozen ≠ scorable ≠ executed ≠
> scored ≠ scientifically validated.* Every number below was computed from the
> actual files (`benchmark/`, `benchmark_runner/`, `benchmark_results/`,
> `sota/eval/`, `tpdeval/`, and the `.xlsx` sheets). No cell is filled by
> inference. Where a source is an audit artifact, it is cited.
>
> **Audit date:** against working tree at HEAD `c4af830`.

---

## 0. The one-line answer

| Question | Answer |
|---|---|
| How many benchmark tasks are authored & frozen? | **48** (Sprint-2 governed benchmark) + a **500-task design** manifest (tpdeval) + a **600-task template** set (Eval500) |
| How many are objectively scorable today? | **19 / 48 (40%)**; tpdeval **0/500**; Eval500 has **50 exact** answers across 600 records |
| How many have been executed against a system? | **4 tasks × 3 systems** (acceptance capture only) |
| How many have been *scored*? | **0** — no scored aggregate exists anywhere |
| Freeze integrity of the 48-task benchmark | **PASS** — 100/100 SHA-256 hashes match, 0 missing files |
| Real system adapters wired for the 48-task run? | **0 / 6** — all real adapters fail closed; only a DEV-fixture adapter runs |
| Overall 48-task benchmark readiness | **≈ 35–40%** (authoring solid, scoring bindings + execution + adapters missing) |

---

## 1. The "benchmark sheet" — what it claims vs what is true

The sheet is `sota/PROTACXtend_SOTA_Audit_Pack.xlsx`, tabs **`Benchmark_Tasks`**
(49 rows × 10 cols) and **`Benchmark_Axes`**.

### 1.1 What the sheet says

- **48 tasks**, 12 per stage (KNOW / REASON / DESIGN / DISCOVER).
- **`audit_status = READY` for all 48** — zero PARTIAL, zero REJECT.
- Ground-truth types: `exact 5`, `categorical 10`, `mechanistic_rubric 9`,
  `design_rubric 20`, `ranked 4`.
- **6 systems** per task: PROTACXtend, Biomni, AI-Co-Scientist-compatible,
  Base-LLM-control, DeepSeek-Flash-control, Local-Ollama-control.
- Difficulty distribution: KNOW 4/7/1, REASON 1/3/8, DESIGN 0/6/6, DISCOVER 0/3/9.
- `runtime_s = 600` for every task.

### 1.2 What the files actually show

| Sheet claim | Reality (measured) | Verdict |
|---|---|---|
| 48 tasks, 12 per stage | 48 case files, 12 per stage | ✅ matches |
| GT types (5/10/9/20/4) | computed exactly 5/10/9/20/4 | ✅ matches |
| Difficulty distribution | computed exactly matches | ✅ matches |
| 6 systems | 6 listed in every case; only **4** have configs; only **3** ever ran | ⚠️ partial |
| **`READY` = scorable + runnable** | `READY` here means *authored and frozen*, **not** scorable and **not** executed | ❌ misleading label |
| All tasks ready to score | **All 48 cases have empty scoring bindings** (`automatic_scoring_fields`, `expert_review_fields`, `failure_criteria`, `evidence_sources`); `expected_answer = null` | ❌ scoring not bound |
| Objective ground truth flag | Manifest marks **TRUE 24 / FALSE 24**, but **19 of 48 rows disagree** with the actual GT type | ❌ flag unreliable |

**Conclusion:** the sheet is an accurate *authoring manifest*, but its `READY`
must be read as **"authored/frozen"**, not "ready to score or run". The sheet has
no column for `scorable`, `executed`, or `scored` — so it cannot tell you where
the benchmark actually stands.

---

## 2. The 48-task governed benchmark — detailed audit

Location: `benchmark/` (+ `benchmark_runner/`).

### 2.1 Authoring & freeze — **DONE** ✅

| Check | Result |
|---|---|
| Cases | 48 (`benchmark/cases/*.json`) + 1 `_TASK_TEMPLATE.json` |
| Ground truth | 48 (`benchmark/ground_truth/*.json`) |
| Required case fields present | 48/48 (no missing fields) |
| Freeze manifest | `benchmark/FREEZE_MANIFEST.json` — 100 entries (48 cases + 48 GT + 4 support), freeze v2A.1 |
| SHA-256 drift | **0** |
| Missing frozen files | **0** |
| GT immutable + `frozen_at` set | 48/48 |
| GT with empty `expected_answer` | 0/48 |
| GT with 0 `evidence_sources` | 0/48 (35 have 1, 11 have 2, 2 have 3) |
| Fail-closed on drift | implemented (`benchmark_runner/freeze.py::assert_frozen`); tested |

### 2.2 Scorability — **PARTIAL (40%)** ⚠️

| GT type | Count | Objectively scorable? |
|---|---|---|
| `exact` | 5 | ✅ yes |
| `categorical` | 10 | ✅ yes |
| `ranked` | 4 | ✅ yes |
| `design_rubric` | 20 | ❌ expert rubric |
| `mechanistic_rubric` | 9 | ❌ expert rubric |
| **Objective total** | **19 / 48 (40%)** | |
| **Expert-rubric total** | **29 / 48 (60%)** | |

> The tpdeval readiness bar (`benchmark_readiness.csv`) is **≥80% objectively
> scorable**. The 48-task benchmark is at **40%** → **below target**.

### 2.3 Scoring bindings — **MISSING (0/48)** ❌

Across all 48 cases:

| Field | Empty in |
|---|---|
| `expected_answer` | 48/48 |
| `automatic_scoring_fields` | 48/48 |
| `expert_review_fields` | 48/48 |
| `failure_criteria` | 48/48 |
| `evidence_sources` | 48/48 |

The case file is a **blinded question only**; the answer lives in the separate
GT file. But the runner never loads the GT directory: `TaskInput.from_case()`
carries no ground-truth or scoring-field pointers. So **the case→GT scoring path
is unbound in code** — the deterministic scorers exist but are only exercised on
dev fixtures.

> **Update (this change):** the *scoring instrument* required before running
> comparisons now exists — `tpdeval/dimensions.py` implements 11 independent
> 0–5 dimensions (9 general + 2 temporal) with separate machine and expert
> components, deterministic machine scorers, temporal gating and per-dimension
> aggregation (no headline composite). Tests: `tests/test_scoring_dimensions.py`
> (25). It is **not yet wired to the 48-task runner** — the bindings above are
> still the blocker before a scored run.

### 2.4 Manifest consistency — **INCONSISTENT** ❌

`benchmark/benchmark_manifest.csv` has an `objective_ground_truth` flag:

| Flag | Actual GT kind | Rows |
|---|---|---|
| TRUE | objective | 12 |
| TRUE | rubric | **12** ❌ |
| FALSE | objective | **7** ❌ |
| FALSE | rubric | 17 |

**19 / 48 rows mismatch.** Example: every `DESIGN-*` row is flagged objective but
its GT is a `design_rubric`.

### 2.5 Missing referenced inputs — **2 hard gaps** ❌

Three cases reference an attached table; **two do not exist anywhere in the repo**:

| Task | References | Exists? |
|---|---|---|
| `DISCOVER-01` | `blinded_candidates_features.csv` | **NO** |
| `KNOW-08` | `blinded_components_sample.csv` | **NO** |
| `REASON-08` | warhead SMILES "report description" | soft prose reference |

This is the direct cause of the one acceptance failure (§2.7).

### 2.6 Execution — **NOT STARTED** ❌

| Check | Result |
|---|---|
| `benchmark/outputs/` | empty (only `.gitkeep` / README) |
| `benchmark/reports/` | empty |
| `run.json` / score files for the 48 tasks | **none** |
| Scored aggregates | **0** |
| `SPRINT2B_AUDIT.md` | states "Real 48-task execution — **NOT STARTED** (by design)" |

### 2.7 Acceptance smoke — **11/12 cells ok** (capture only)

From `benchmark_results/reports/acceptance_matrix.md` (2026-09-07):

- Design: 4 tasks × 3 systems = **12 envelopes**, capture-complete.
- **11/12 ok**; **1 failed**: `PROTACXtend × DISCOVER-01` returned
  `clarification_required` because `blinded_candidates_features.csv` is not
  attached.
- Capture-completeness criterion: **PASS**; functional "all 12 answer": **NOT PASS**.
- The definitive 144-run (48 × 3) was **not launched**.
- Client notes: `thinking:disabled`, temperature 0, seed 42; Biomni ~326–506 s
  per task (a 48-task Biomni arm ≈ 6–8 h).

### 2.8 Harness & adapters — **infra READY, real adapters locked** ⚠️

| Component | File | State |
|---|---|---|
| Freeze / provenance | `benchmark_runner/freeze.py` | ✅ implemented, tested |
| Runner + envelope + raw preservation | `benchmark_runner/runner.py` | ✅ implemented |
| Deterministic scoring (exact/categorical/ranked) | `benchmark_runner/scoring.py` | ✅ implemented, tested on fixtures |
| Rubric (0–4 anchors, blinding, 2 reviewers, kappa) | `benchmark_runner/rubric.py` | ✅ implemented |
| Dev fixtures (perfect/partial/incorrect/hallucinated/missing/malformed/timeout/tool_failure) | `benchmark_runner/fixtures.py` | ✅ 8 fixtures, non-overlapping |
| Tests | `tests/test_benchmark_runner.py` | ✅ **17/17 pass** |
| Real system adapters (6) | `runner.py::_StubAdapter` | ❌ **all fail closed** (`adapter ... not implemented`) |
| Case → GT binding | `runner.py::TaskInput` | ❌ **not wired** |

### 2.9 48-task scorecard

| Layer | Weight | Done | Basis |
|---|---|---|---|
| Specification (protocol, blindness, rubric, schemas) | 15% | **100%** | all files present & coherent |
| Authoring (48 cases) | 15% | **100%** | 48/48 complete fields |
| Ground truth (48 records) | 15% | **85%** | present & frozen, but 60% rubric-unaudited |
| Freeze / provenance | 10% | **100%** | 100/100 hashes match |
| Scorability (objective + bound) | 15% | **20%** | 40% objective × 0% bound in runner |
| Harness (runner/scoring/rubric) | 10% | **90%** | implemented, 17/17 fixture tests |
| Real adapters (6 systems) | 10% | **0%** | all fail closed |
| Execution + scored results | 10% | **5%** | 12 capture cells, 0 scored |
| **Overall (weighted estimate)** | 100% | **≈ 37%** | |

---

## 3. `sota/eval/eval500/` — PROTACXtend-Eval500 (600 tasks)

| Claim (`eval500/README.md`) | Measured | Verdict |
|---|---|---|
| 500 core + 100 adversarial = 600 | `tasks_all.csv` = 500 rows; dev jsonl 303 core + 57 adversarial; hidden 240 | ⚠️ counts exist across dev/hidden |
| dev 360 · hidden (SEALED) 240 | present | ✅ files exist |
| Ground truth scorable | `exact 36 / rubric 150 / constraint 104 / ranking 13` (dev: 303) + hidden `exact 14 / rubric 90 / constraint 81 / ranking 12` (197) | ❌ only **50 exact** answers in total; `rubric`/`constraint` are prose strings |
| Adversarial tasks | 57 dev rows, all `rubric` | ❌ stubs — `00_AUDIT.md`: "no injected fault, no payload" |
| SEALED partition | `hidden/tasks_hidden.jsonl` | ❌ reconstructible — `generate_eval500.py` is deterministic and in-repo |
| Scoring | `SCORING.md` + `RUN_SCHEMA.json` | ❌ **no grader implementation shipped** |
| Diversity | 14 templates × 24 targets × 18 E3 × 8 linkers | ❌ scientific diversity ≈ 14 problem types |

**Verdict:** a large but **template-generated** set; not scientifically scorable.
Classified `MOCK / SCIENTIFICALLY UNVALIDATED` in `tpdeval/docs/00_AUDIT.md`.

---

## 4. `tpdeval/` — TPD head-to-head (500-task design)

| Item | Result |
|---|---|
| Task design | 500 tasks in `tpdeval/config/allocation_500.json` |
| Partitions | controlled 300 / end-to-end 150 / temporal 50; 100 stress tags; 16 domains; L1–L7 |
| Authoring status | **all 500 have `status = None`** → `REQUIRES_AUTHORING` |
| Scorable tasks | **0 / 500** |
| Systems wired | **0 / 8** (A–H; C/E/F/G/H do not exist as executables) |
| Tests | `tests/test_tpdeval.py` — **20/20** |
| Verdict table | every cell **`NOT YET MEASURED`** (`docs/03_VERDICT.md`) |

**Verdict:** instrument built and unit-tested; **no measurement**. P0 blockers
listed in `docs/02_BLUEPRINT.md` (author GT, wire systems, matched-tool guard,
freeze, fairness manifest).

---

## 5. Audit sheets (XLSX) — claims vs code

| Sheet | Tabs | Headline claims | Audit finding |
|---|---|---|---|
| `Agent_Toolkit.xlsx` (repo root) | 11 tabs, 127 tools, 53 DBs, 47 pkgs, 30 skills, 41 modules | Dashboard: 23 agents (18 functional, 3 partial, 2 not built); 18,697 LOC | **Stale**: `Implementation_Status` lists 7 "Not Built" items (hook modeler, lysine scorer, cooperativity, trained degradation ML, novel-E3, proteotype, active learning) that are **now implemented** as Modules M1–M7 |
| `data/toolkit/Agent_Toolkit.xlsx` | 11 tabs | Implementation_Status = 39 rows (vs 53 root) | Two divergent copies of the same sheet → **version drift** |
| `data/toolkit/Agent_Toolkit_EXPANDED.xlsx` | 11 tabs | Tools 124, DBs 56, pkgs 50, skills 36, modules 24 + `Gap_Audit` 22 + `Missing_Component_Plan` 30 | Divergent counts again |
| `data/toolkit/protac_agent_gap_audit.xlsx` | `gap_audit` 18 rows | gap list | overlaps audit_nextgen G01–G16 |
| `analysis/inventory/PROTACXtend_Toolkit_Truth.xlsx` | 9 tabs | **115 tools**, 30 callable, 59 datasets, 27 capabilities (20 ready), 678 deps | ✅ matches `TOOLKIT_TRUTH.md` (the current source of truth) |
| `analysis/inventory/PROTACXtend_Capability_Inventory.xlsx` | 8 tabs | 43 web services, 116 tools, 56 APIs, 10 servers, 44 datasets, 50 DBs | ⚠️ counts differ from Toolkit_Truth (116 vs 115 tools) |
| `sota/PROTACXtend_SOTA_Audit_Pack.xlsx` | 27 tabs | 48 benchmark tasks READY; 115 toolkit tools; 108 functionalities | benchmark part audited in §1; toolkit/counts broadly consistent |
| `data/benchmark/PROTAC-DB_3.0_protacs.xlsx` | 1 tab | 15,502 PROTAC records × 89 cols | real data asset |
| `data/protac_repos/protac_repo_registry.xlsx` | 1 tab | 29 repos | infra registry |

**Key sheet finding:** there is **no single canonical sheet**. Tool counts drift
across four copies (`115` vs `116` vs `123` vs `124`), agent counts drift
(`23` vs `37` vs `41`), and the "Not Built" list is out of date. The only current
source of truth is `TOOLKIT_TRUTH.md` / `Toolkit_Truth.xlsx` (2026-09-16).

---

## 6. System readiness for any benchmark run

| System (as claimed by sheet) | Adapter state | Evidence |
|---|---|---|
| PROTACXtend | chat/agent adapter runs (acceptance ok) but not wired to runner | `benchmark_results/acceptance/*` |
| Biomni | installed & runs; official package; not wired to runner | `benchmark_results/reports/biomni_install_smoke.md` |
| AI-Co-Scientist-compatible | proxy only | acceptance matrix |
| Base-LLM-control | runs via provider; not wired | acceptance matrix |
| DeepSeek-Flash-control | provider config only | `benchmark_results/configs/` |
| Local-Ollama-control | config only | `benchmark_results/configs/` |
| Independent TPD comparator (system C) | **does not exist** | `tpdeval/adapters.py::status_table()` |
| Retrieval-only (E) / tool-only (F) / hybrids (G/H) | **do not exist** | tpdeval blueprint P0.3–P0.5 |

---

## 7. Where we are left — benchmark action list

### P0 — required before any comparison
1. **Bind case → ground truth in the runner** (`TaskInput` / `runner.py`) and
   populate `automatic_scoring_fields` / `expert_review_fields` in cases.
2. **Reconcile the manifest flag** `objective_ground_truth` with the actual GT
   type (19 mismatched rows).
3. **Attach or inline the two missing CSVs** (`blinded_candidates_features.csv`,
   `blinded_components_sample.csv`) and re-freeze.
4. **Publish the ground-truth audit** for the 29 rubric tasks (no objective
   anchor today) — target ≥80% objectively scorable.
5. **Wire real adapters** (PROTACXtend, Biomni, base-LLM, and the missing C/E/F/G/H).
6. **Author the 500 tpdeval tasks' ground truth** (0/500 scorable).
7. **Fix the `.xlsx` sheet drift** — declare `TOOLKIT_TRUTH.md` canonical, mark
   the other copies superseded, and add `scorable`/`executed`/`scored` columns to
   the benchmark sheet.

### P1 — before the full 48×N run
8. Run the **144-run (48 × 3)** only after (1)–(3); currently blocked by the
   CSV-attachment gap.
9. Split the test suite fast/slow and fix the recorded failures (gap G11).
10. Add a `claim → citation` grounding scorer before claiming "grounded".

### P2/P3 — before publication
11. Human adjudication + IRR for the 29 rubric tasks.
12. Rebuild `eval500` as authored (or retire it) and remove the misleading
    "SEALED" claim.
13. Implement the eval500 grader described in `SCORING.md`.

---

## 8. Pointer index

| What | Where |
|---|---|
| The benchmark sheet | `sota/PROTACXtend_SOTA_Audit_Pack.xlsx` → `Benchmark_Tasks`, `Benchmark_Axes` |
| Task cases | `benchmark/cases/*.json` (+ `_TASK_TEMPLATE.json`) |
| Ground truth | `benchmark/ground_truth/*.json` |
| Manifest CSV | `benchmark/benchmark_manifest.csv` |
| Freeze manifest | `benchmark/FREEZE_MANIFEST.json` |
| Protocol / blindness / rubric | `benchmark/BENCHMARK_PROTOCOL.md`, `benchmark/BLINDNESS_RULES.md`, `benchmark/SCORING_RUBRIC.md` |
| Authoring audit | `benchmark/SPRINT2_CASE_AUDIT.md`, `benchmark/SPRINT2A_ACCEPTANCE.md` |
| Runner audit | `benchmark/SPRINT2B_AUDIT.md` |
| Runner / scoring / rubric / freeze | `benchmark_runner/runner.py`, `scoring.py`, `rubric.py`, `freeze.py`, `fixtures.py` |
| Runner tests | `tests/test_benchmark_runner.py` (17) |
| Acceptance smoke + logs | `benchmark_results/reports/acceptance_matrix.md`, `benchmark_results/acceptance/execution_log.csv` |
| Missing-input root cause | `benchmark_results/reports/pilot_KNOW01_REASON03_verification.md` |
| Eval500 | `sota/eval/eval500/` (README, tasks_dev.jsonl, hidden/, SCORING.md) |
| Head-to-head design | `tpdeval/docs/00_AUDIT.md` … `03_VERDICT.md`, `tpdeval/config/allocation_500.json` |
| Readiness + gap tables | `audit_nextgen/csv/benchmark_readiness.csv`, `audit_nextgen/csv/gap_analysis.csv` |
| Toolkit source of truth | `TOOLKIT_TRUTH.md`, `analysis/inventory/PROTACXtend_Toolkit_Truth.xlsx` |
| Codebase state / project closeout | `CODEBASE_STATE.md`, `PROJECT_CLOSEOUT.md` |

---

### Standing rule (kept throughout this audit)

> *code present ≠ imports ≠ executes ≠ schema-valid ≠ scientifically meaningful ≠
> experimentally validated.* A benchmark task is "done" only when it is
> **authored + independently verified + bound to a scorer + executed + scored**.
> By that definition the 48-task benchmark is **≈ 37% done**, tpdeval is **≈ 5%**
> (instrument only), Eval500 is **≈ 10%** (template mock), and **no scored
> benchmark result exists** for any system.
