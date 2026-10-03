# Audit + execution of the two 500-task benchmark workbooks

Sources:
- `todo/Blinded_Temporal_Challenge_500_Tasks.xlsx` (temporal suite, BTC-001…500)
- `todo/PROTACxtend_500_Task_Benchmark (1).xlsx` (general suite, TD-001…500)

Date 2026-09-23 · HEAD `0abbe83` · deliverable: `benchmark500/`.

---

## 1. What the two workbooks contain (checked)

| | temporal | general |
|---|---|---|
| tasks | 500 (BTC-001…500) | 500 (TD-001…500) |
| sheets | README, Challenge_Plan, Question_Bank_500, Temporal_Splits, Evidence_Protocol, Scoring_Rubric, Workflow, Dashboard | README, Tasks_500, Domain_Summary, Difficulty_Guide, Lists |
| domains | 16 | 16 (identical taxonomy) |
| difficulty | L1–L7 = 37/41/79/118/112/75/38 | L1–L7 = 38/40/78/112/116/78/38 |
| targets | 50 | 50 |
| E3 contexts | 10 | 10 |
| cutoffs | 12 dates, 2019-06-30 → 2024-09-30 | none |
| future horizons | 6/12/18/24 months | none |
| **gold** | `Ground_Truth_Status = TO CURATE` × 500 | `Curation_Status = Not curated` × 500 |
| answers / evidence / scores populated | **0 / 18 output columns** | **0 / 14 output columns** |

Both are **specification/question banks**, not a benchmark dataset. The rubric,
protocol, splits and evidence-control sheets are present and internally
consistent. No duplicate IDs, no missing required fields, no domain/task-number
collisions, no blank questions (verified in `benchmark500/INTEGRITY_REPORT.md`).

**Defect / gap summary**

| id | finding | severity |
|---|---|---|
| G-01 | 1000/1000 gold answers uncurated — no expected answer, alternatives, evidence package or reference provenance | blocking |
| G-02 | no frozen pre-cutoff corpus (temporal suite); 12 cutoffs unenforced | blocking for temporal |
| G-03 | no table/tool versions pinned to cutoff; `Permitted_Tools` is prose | blocking for reproducibility claim |
| G-04 | `Evididence_Package`/`Structures`/`Molecules` columns are "To attach" — tool-execution tasks have no inputs | blocking for L3 |
| G-05 | 80 (temporal) / 236 (general) rows use non-ASCII targets (`ERα`, `PI3Kα`) — harmless but must be normalized before entity joins | low |
| G-06 | general suite has no cutoffs, so it is an E2-style bank, not temporal | informational |
| G-07 | workbooks disagree on target composition (temporal targets uneven, general 10×50) and difficulty counts | informational |

## 2. What was executed

Pipeline built under `scripts/` and run over **all 1000 tasks**:

```bash
python scripts/benchmark500_ingest.py                 # normalize + validate + split
python scripts/benchmark500_run.py --suite both --mode probe --run-id b500_probe_20260923
python scripts/benchmark500_score.py --run-id b500_probe_20260923
python scripts/benchmark500_report.py --run-id b500_probe_20260923
```

| result (`b500_probe_20260923`) | value |
|---|---|
| tasks | 1000 |
| executed with traceable evidence | **476** |
| typed abstention | **524** (500 `MISSING_SCIENTIFIC_INPUT`, 24 `NO_LOCAL_EVIDENCE`) |
| failed | 0 |
| valid output | 476 |
| gold curated | 0 |
| expert-adjudicated | 0 |

Per-domain execution: retrieval/evidence domains 94–96 % (target biology,
target validation, tractability, E3, warhead, binary structure, resistance);
design/reasoning domains 0 % abstained because the workbook attaches no
scientific inputs and no LLM is configured.

## 3. What is genuinely "done"

- [x] both workbooks ingested, hashed, validated (`INTEGRITY_REPORT.md`)
- [x] canonical 1000-case JSONL + manifests + target-grouped splits
- [x] pre-registration + data dictionary frozen
- [x] runner for all 1000 tasks with typed outcomes, provenance and manifests
- [x] objective scoring (tool execution, reproducibility, evidence availability)
- [x] results workbook + per-domain/difficulty/split tables + figures
- [x] adjudication queue prepared with question + system evidence per task

## 4. What is **not** done (and must not be faked)

- [ ] scientific/mechanistic/quantitative correctness, uncertainty calibration,
      final decision quality, future-outcome match, tool-selection correctness:
      **blank, `pending_adjudication`** — no gold exists.
- [ ] temporal compliance: **unverifiable** — no frozen as-of corpus.
- [ ] LLM reasoning for L4–L6: **not run** — no provider authenticated.
- [ ] baselines (general LLM, retrieval-only, tool-only, fixed pipeline):
      require the same gold + an LLM.

## 5. How to finish (exact next steps)

1. Curate gold + evidence for the 1000 cases (two adjudicators); fill
   `benchmark500/ADJUDICATION_QUEUE.xlsx` and mirror into the case JSONL
   (`gold_answer`, `accepted_alternatives`, `evidence_package`,
   `gold_status="curated"`).
2. Freeze pre-cutoff corpora per cutoff and pin tool/model versions ≤ cutoff.
3. `protacxtend setup` (authenticate an LLM), then
   `python scripts/benchmark500_run.py --mode llm` for L4–L6.
4. `python scripts/benchmark500_score.py` + `benchmark500_report.py` with gold
   present; the adjudicated dimensions then populate.

## 6. Relation to the earlier 48-task benchmark

`benchmark/` (48 authored cases, 29 flagged) remains the *pilot*; it also has no
adjudicated gold and its `0.885` offline mean is self-grading. `benchmark500/`
supersedes it in scale and adds the temporal suite, but inherits the same
blocking dependency: **independent gold curation**. Neither is a therapeutic
performance result until Gate C is complete.
