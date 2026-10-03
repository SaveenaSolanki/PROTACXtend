# Audit of `todo/PROTACXtend_05_BENCHMARK_AUDIT_AND_NEXT_STEPS.md`

`_05` is a benchmark audit + execution plan written from a *summary* of this
`todo_audit/` folder. This file checks the plan against the live tree and records
which gates have now been executed.

Date: 2026-09-23 · HEAD `0abbe83` (working tree: see `gateA/archive/git_state.txt`).

## Section 2 — table of "what exists / fails / unverified"

`_05` asks for confirmation of each row. All rows were independently reproduced
in `FINDINGS.md`; the rows it flagged as critical are now repaired.

| component | `_05` interpretation | audit result |
|---|---|---|
| Parser 125 / 1.0000 | retain as limited result | `verified` (`evidence/parser_eval.txt`) |
| Typed contracts + 34 agent tools | good infra, inspect traces | `verified` (`evidence/mode_probe.txt`) |
| Grader + `unscorable_missing_fields` | scorer exists; 0.885 not headline | `confirmed` (F-05) |
| Scientific mode ignored on canonical path | critical integrity failure | **fixed** (Gate B, F-03) |
| Entity resolution `M0QZD9` | critical identity error | **fixed** (Gate B, F-04) |
| Registry 296, executable 0 | count ≠ coverage | `confirmed` (F-07) — not in Gate B scope |
| One critic / no leakage code | treat as unimplemented | `confirmed` (F-11/F-12) |
| Dirty tree / stale script / pytest | pin clean revision, reinstall | **script + pytest fixed**; rename still open (F-14) |
| 107 + 48 focused tests | identify names/commit | `verified`; now 328 root tests + 11 Gate B tests |

## Section 3 — gate status

| gate | items | status |
|---|---|---|
| **A preserve & reproduce** | archive HEAD/status/env; rename inspection; verify.sh; project-only tests; reinstall; cross-route matrix | **✅ executed** → `gateA/README.md`, `gateA/cross_route_matrix.{csv,md}` |
| **B repair integrity** | mode propagation; shared reviewed target resolution; BRD4 regression tests; real-or-abstain BRD4–VHL rerun | **✅ executed** → `gateB/README.md`, before/after traces |
| **C independent gold** | freeze inventory; replace derived overlays; 2 annotators; `gold_review.tsv`, `splits.json`, `pre_registration.md`, `tool_registry_snapshot.json`; preregister endpoint | **❌ pending** (needs domain annotators) |
| **D matched pilot → full cohort** | 4-task pilot, then 48; per-case manifests/tool_runs/predictions/failures/scores; grouped bootstrap CIs | **❌ pending** (blocked on C; must not reuse self-grade) |
| **E scale E2–E8** | E1 in parallel; E2→500 only if adjudicated | **❌ pending** |

## Section 4 — dataset / result schema

`_05` specifies one JSONL case and one prediction record. Current state:

| required field group | present? |
|---|---|
| case: `case_id`, `task_type`, `question`, eligible tools, inputs, accession/species, E3, source DOI/PMID, cutoff, split | partial — `benchmark/cases/*.json` (TASK_SCHEMA 2.0.0) has most, **no `split`, no DOI per case, no adjudicators** |
| prediction: `case_id`, `arm`, `run_id`, status, `ToolRun` IDs, cited evidence IDs, measured/predicted/surrogate tag, error/abstention, time/cost, hashes | partial — canonical strategy carries most; **no `splits.json`, no scored prediction writer** |

## Section 5 — figures

No figure was generated: they depend on Gate D scored output, which does not
exist. The breadth × depth plot remains a conceptual illustration.

## Section 6 — what to ask the repository agent now (delivered)

| requested deliverable | delivered |
|---|---|
| complete `FINDINGS.md`, `FINDINGS.json`, `QUESTIONS.md`, `evidence/`, `csv/`, `verify.sh`, git status | present |
| preserve current user changes | preserved; nothing deleted |
| reproduce every severity-1 finding | F-01…F-06 reproduced (F-03/F-04 since fixed) |
| repair scientific-mode propagation on the canonical path | **done** (`gateB/`) |
| repair BRD4 protein identity | **done** (`O60885`, regression test) |
| cross-route end-to-end regression tests with real input or explicit abstention | **done** (`tests/test_gate_b_scientific_integrity.py`, `gateA/cross_route_matrix.py`) |
| return changed paths, before/after traces, passing focused tests, unresolved failures, exact commands | **done** (`gateB/README.md` §1, §3, §6, §7) |
| do not score the full 48 or present 0.885 as therapeutic performance | **honoured** |

## Verdict

Gates A and B are complete and evidenced. Gates C–E require resources the agent
cannot supply (independent annotators, datasets, wet-lab) and remain the honest
boundary of this work.
