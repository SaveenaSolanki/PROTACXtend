# 02 — Benchmark Audit (all assets on disk)

**Artifact:** Phase 0 benchmark audit. Read-only. No file modified.
**Audit date (UTC):** 2026-09-29T08:03:46Z
**Audit rule:** *listed ≠ authored ≠ frozen ≠ scorable ≠ executed ≠ scored ≠ scientifically validated.* Every number below was computed from files on disk.

> **Expected vs actual (the question asked).** You expected ~500 task-level
> questions and ~48 deep/end-to-end cases. The repository contains **multiple,
> partly-overlapping** assets. The truthful inventory is:
>
> | Asset | Nominal count | Curated gold | Ready for correctness scoring |
> |---|---|---|---|
> | `benchmark/` governed cases | **48** | frozen GT text present; **0/48 independently adjudicated** | **No** (29 need expert review; all reviewer decisions PENDING) |
> | `benchmark500/general_500` | **500** | **0/500** (`Not curated`) | **No** |
> | `benchmark500/temporal_500` | **500** | **0/500** (`TO CURATE`) | **No** |
> | `tpdeval` design manifest | **500** (design only) | **0** (`REQUIRES_AUTHORING`) | **No** |
> | `sota/eval/eval500` | **504 + 120 adversarial = 624** | ~50 exact (subset) | **Partially** |
>
> So the honest statement is: **48 authored cases exist; 1000+ uncurated question
> banks exist; and the primary endpoint currently has denominator 0 for the 48
> and 0 for the 1000.** The study cannot report a correctness number until gold is
> adjudicated. This is the single most important Phase 0 finding.

---

## 1. `benchmark/` — the 48-case governed benchmark (Sprint 2A/2B)

### 1.1 Inventory

| Item | Measured |
|---|---|
| Case files | `benchmark/cases/*.json` → 50 files (48 cases + `_TASK_TEMPLATE.json` + 1 non-case) |
| Real cases | **48** |
| Ground-truth files | `benchmark/ground_truth/*.json` → **48** |
| Freeze manifest | `benchmark/FREEZE_MANIFEST.json`, freeze v2A.1, **100 entries** (48 cases + 48 GT + 4 support) |
| SHA-256 drift | 0 (per repository audit) |
| `prescriptions`/assets | `benchmark/gateC/`, `benchmark/scoring/`, `benchmark/frozen_cache/` |

### 1.2 Case distribution by capability

| Capability | n | Meaning (workflow stage) |
|---|---|---|
| KNOW | 12 | retrieval / factual |
| REASON | 12 | mechanistic reasoning |
| DESIGN | 12 | multi-stage design |
| DISCOVER | 12 | end-to-end discovery / ranking |
| **Total** | **48** | |

### 1.3 Ground-truth types (measured)

| GT type | n | Objectively scorable? |
|---|---|---|
| `exact` | 5 | ✅ deterministic (exact/normalised match) |
| `categorical` | 10 | ✅ deterministic (set/synonym match) |
| `ranked` | 4 | ✅ deterministic (ranking metrics) |
| `mechanistic_rubric` | 9 | ⚠ expert rubric |
| `design_rubric` | 20 | ⚠ expert rubric + deterministic chemistry checks |
| **Objective total** | **19 / 48 (39.6 %)** | |
| **Rubric total** | **29 / 48 (60.4 %)** | |

### 1.4 Difficulty (from GT)

| Difficulty | n |
|---|---|
| easy | 5 |
| medium | 19 |
| hard | 24 |

### 1.5 Evidence grounding in GT

Each GT carries `expected_answer`, `mandatory_answer_elements`,
`acceptable_alternatives`, `evidence_sources`, `numerical_context`,
`data_cutoff_date`, `immutable`, `frozen_at`. `evidence_sources` count distribution:
1 source = 35, 2 = 11, 3 = 2. **All 48 have ≥1 evidence source.**

### 1.6 Adjudication status — **BLOCKING**

| Item | State |
|---|---|
| Gold adjudicated | **0 / 48** |
| Reviewer decisions enumerated | 29 (`REVIEWER_DECISIONS.tsv`) |
| Reviewer decision status | **all `PENDING`** |
| `gold_review.tsv` rows | 48, all `PENDING_ADJUDICATION` |
| `gold_answers_v1.jsonl` | 48 rows; 0 with `acceptable_answer`; 6 with `mandatory_facts` |
| `benchmark/SCORABLE_REPORT.md` | claims 48 auto-scorable, **but** 29 require expert review → the "auto" label counts a rubric checklist, not objective correctness |
| Splits | development 16 / validation 3 / **blind 29** (group-disjoint by leakage group) |

**Interpretation:** the 19 objective cases (5 exact + 10 categorical + 4 ranked)
can be scored the moment a normalisation/synonym table is frozen. The 29 rubric
cases require blinded expert adjudication and are the long pole.

### 1.7 Execution status

- Adapters wired: `benchmark_runner/live.py` (PROTACXtend, Base-LLM-control,
  AI-Co-Scientist-compatible) + `benchmark_runner/baselines.py`
  (RetrievalOnly, ToolOnly, LLM, ProtacxtendOffline).
- Actually executed: **4 acceptance tasks × 3 systems** (`benchmark_results/raw/`:
  `KNOW-01`, `REASON-03` per system).
- Scored aggregates: **none** (`benchmark_results/scored/` empty).
- Baseline comparison reports exist (2026-09-23, 2026-09-26) but are smoke runs.

---

## 2. `benchmark500/` — the 1000-task banks

### 2.1 Inventory

| Suite | File | n | IDs |
|---|---|---|---|
| general | `cases/general_500.jsonl` | **500** | TD-001…TD-500 |
| temporal | `cases/temporal_500.jsonl` | **500** | BTC-001…BTC-500 |
| **Total** | | **1000** | |

Manifests: `manifests/general_500.manifest.json`, `manifests/temporal_500.manifest.json`.
Splits: `splits/general_500.splits.json`, `splits/temporal_500.splits.json`.
Archive: `ARCHIVE_MANIFEST.json`.

### 2.2 Distribution (from `INTEGRITY_REPORT.md`)

**Domains (16) — identical in both suites:**

| Domain | n |
|---|---|
| Target biology & disease mechanism | 50 |
| Target validation | 40 |
| TPD tractability | 40 |
| E3 ligase selection | 35 |
| Warhead discovery | 35 |
| Linker/PROTAC design | 50 |
| Binary structural modeling | 30 |
| Ternary-complex reasoning | 50 |
| Degradation prediction | 30 |
| ADME/PK/developability | 30 |
| Polypharmacology/safety | 25 |
| Resistance/escape mechanisms | 20 |
| Biomarker/patient stratification | 20 |
| Combination/synergy | 15 |
| Translational/experimental design | 15 |
| Failure analysis | 15 |
| **Total** | **500** |

**Difficulty L1–L7:** general `{1:38, 2:40, 3:78, 4:112, 5:116, 6:78, 7:38}`;
temporal `{1:37, 2:41, 3:79, 4:118, 5:112, 6:75, 7:38}`.

**Temporal suite cutoffs:** 12 distinct dates (2019-06-30 … 2024-09-30), ~65 tasks
per annual cutoff. **50 targets, 10 E3 contexts.**

### 2.3 Gold / scorable status — **BLOCKING**

- `gold uncurated rows: 500/500` for BOTH suites.
- `gold_answer = null`, `gold_status ∈ {Not curated, TO CURATE}`.
- `evidence_package = null`, `expected_source_types` = placeholder text.
- `permitted_tools` = "Specify per task" (not bound).

### 2.4 Execution status

- Last recorded run `b500_probe_20260923` (offline probe mode):
  **1000 tasks → 476 executed with traceable evidence, 524 typed abstentions, 0 failed.**
- `--mode capability --online` and `--mode llm` runs exist as reports
  (`REPORT_b500_capability_online_20260923.md`) but **scientific correctness was
  never scored** (gold denominator 0).
- `ADJUDICATION_QUEUE.xlsx` is blank (pre-filled questions only).

**Verdict:** `benchmark500` is a **validated, versioned, integrity-checked question
bank**, not a scoreable benchmark. It is an excellent source of *task-level
questions* once a stratified subset is curated to gold (design doc Part III/§11).

---

## 3. `tpdeval/` — the head-to-head instrument (design, not data)

| Item | State |
|---|---|
| Benchmark id | `TPD-HEADTOHEAD/1.0.0` |
| Partition design | A controlled 300 + B end-to-end 150 + C temporal 50 = 500 |
| Allocation manifest | `tpdeval/config/allocation_500.json` (design only) |
| Task ground truth | **`REQUIRES_AUTHORING` for all** (`ground_truth.status`) |
| Systems defined | 8 (A PROTACXtend … H planner-vs-generic-tools) |
| Systems executable | **A only**; B Biomni partial; **C/E/F/G/H not wired** |
| Measurement modules | taxonomy, toolenv, evidence, mechanism, trajectory, calibration, temporal, failure, reproducibility, ablation, stats, provenance |
| Unit tests | 20/20 passing (per `docs/03_VERDICT.md` — pre-existing claim, to be re-verified in pilot) |

`tpdeval/docs/03_VERDICT.md` states every performance cell is `NOT YET MEASURED`.
This is consistent with the on-disk evidence: no scored aggregate exists.

**This is the correct skeleton for the study.** The experimental design reuses its
system slots, statistics and provenance guard rather than inventing a parallel one.

---

## 4. `sota/eval/` — template task sets

| File | n | Note |
|---|---|---|
| `sota/eval/tasks.jsonl` | 504 | generated task set |
| `sota/eval/tasks_adversarial.jsonl` | 120 | adversarial |
| `sota/eval/eval500/tasks_dev.jsonl` | 303 | dev split |
| `sota/eval/eval500/tasks_adversarial_dev.jsonl` | 57 | dev adversarial |
| `sota/eval/eval500/hidden/tasks_hidden.jsonl` | 197 | hidden |
| `sota/eval/eval500/hidden/tasks_adversarial_hidden.jsonl` | 43 | hidden adversarial |
| **Total (eval500 dev+hidden)** | **600** | |

Per the repository's own audit, these are **template stubs with ~50 exact
answers** — not authored science. Use only as a *negative control / smoke set*,
never as a primary endpoint.

---

## 5. Existing execution runs already on disk (not part of the study)

| Location | Content |
|---|---|
| `outputs/runs/run_*` | ~50+ captured PROTACXtend run dirs (run.json, trace, evidence, candidates, report) |
| `outputs/runs/e2e_*` | manual e2e probes (KRAS evidence-limited, HMGB2 nanobinder, impossible input) |
| `validation_runs/1a46_pl/` | one full structural validation (docking, ternary, MD, energy) |
| `benchmark_results/raw/` | 4 acceptance tasks × 3 systems |
| `benchmark_results/closed48*` | closed-loop 48 attempts |
| `results/`, `results/figures*`, `results/statistics/` | prior figure/table production |

**Audit rule:** these pre-date the frozen study and were produced under
undocumented conditions (unknown dirty tree, unknown memory state). They may be
used for **pipeline debugging only** and must never enter the study result tables.

---

## 6. Measurement-instrument readiness (what can be measured today vs not)

| Endpoint | Instrument exists? | Bound to gold? | Ready for Phase 2? |
|---|---|---|---|
| Scientific success (binary) | `benchmark_runner/scoring.py`, `grader.py`, `rubric.py` | No (gold unadjudicated) | **No** |
| Partial rubric score | `tpdeval/scoring.py`, `rubric.py` | No | **No** |
| Evidence-grounded success | `benchmark_runner/grader.py` (citation checks) | Partial | After claim-extractor validation |
| Evidence quality (claim-level) | `tpdeval/evidence.py` | No | After pilot validation |
| Abstention quality | `tpdeval/taskmodel.py`, `failure.py` | No | After abstention cases authored |
| Tool performance | `tpdeval/toolenv.py` (8-step) | n/a (not gold) | **Yes** (log-derived) |
| E2E stage outcome | `tpdeval/trajectory.py` (9-step), `runtime/e2e.py` | Partial | After stage rubric frozen |
| Failure classification | `runtime/fault_injection.py` + `tpdeval/failure.py` | n/a | **Yes** |
| Reproducibility | `tpdeval/reproducibility.py` | n/a | **Yes** |
| Ablation Δ | `tpdeval/ablation.py` | No | After primary runs |
| Calibration (ECE/Brier) | `tpdeval/calibration.py` | Needs confidence labels | Only if confidence emitted |
| Statistics | `tpdeval/stats.py` (Wilcoxon, McNemar, bootstrap, mixed effects, Holm) | n/a | **Yes** |

---

## 7. Data-leakage audit (first pass)

| Check | Result |
|---|---|
| Case questions inside `memory/literature_store` | 0 substring hits |
| `expected_answer` in agent prompts (`agents/prompts.py`) | not found |
| Gold in retrieval corpus | not found in first pass |
| `benchmark/gateC/rubrics/` visibility to system | offline asset, not in retrieval path (to be confirmed) |
| `ground_truth/` importable by runner | `TaskInput.from_case()` does NOT load GT — separation holds |
| Benchmark-generation code | `scripts/build_gold_v1.py`, `sota/eval/generate_tpd_benchmark.py` exist on disk (could leak if exposed) |

**Status: first pass clean, not exhaustive.** Full leakage audit per Part XXIII is
a Phase 0/1 gate (design doc §11, §10). Each case must be tagged
`clean | possible_leakage | confirmed_leakage`; primary results on the clean subset.

---

## 8. Benchmark audit conclusions

1. **48 authored, frozen, evidence-linked cases** exist and are the only asset
   with real ground truth. Only **19/48** are objectively scorable; the other
   **29** block the primary endpoint until blinded adjudication completes.
2. **1000 question-bank tasks** (`benchmark500`) and **500 design slots**
   (`tpdeval`) exist but have **zero curated gold**.
3. **624 template tasks** (`sota/eval`) are smoke material, not science.
4. **No scored aggregate, for any system, on any benchmark, exists.**
5. Therefore the study's **Phase 0 exit gate is gold curation + system freeze**,
   not code changes. Without it, `H1–H3`, `H5`, `H6` cannot be evaluated for
   correctness — only tool/reproducibility/failure endpoints (§6) can.
6. The measurement machinery in `tpdeval/` and `benchmark_runner/` is sufficient
   to start **Phase 1 pilot** immediately (scoring plumbing, logs, cost, failure
   capture), which is exactly what the pilot is for.
