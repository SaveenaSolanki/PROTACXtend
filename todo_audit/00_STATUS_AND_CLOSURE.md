# Audit of `todo/PROTACXtend_00_STATUS_AND_CLOSURE.md`

That file is a **report audit** (it correctly states it is not a repository
inspection). This document performs the inspection it deferred. Each row of its
"what the uploaded evidence establishes" table is now checked against the tree.

Date 2026-09-23 · HEAD `0abbe83` · see `FINDINGS.md` for full evidence.

## Claim-by-claim

| Item in `_00` | Report says | Live check | Verdict |
|---|---|---|---|
| Canonical output `TherapeuticStrategy.v1` | implemented as reported | `protacxtend/canonical/schemas.py` + `outputs/strategies/strategy_17aa7ab30f.strategy.json` contains all named fields | `verified` (presence) |
| Persisted `therapeutic_strategy.json` + manifest | yes | `strategy` CLI writes `*.strategy.json` and `*.manifest.json` | `verified` |
| Field presence ≠ decision validity | flagged as risk | realised: demo warheads + wrong UniProt in "scientific" run, `stopping_state=REVISE` | `confirmed` (F-03, F-04) |
| Scientific mode / DEMO/TEST/SCIENTIFIC gates | evidenced in report | `protacxtend/runtime/modes.py` exists; **agent path enforces**, canonical path does not | `partial` (F-03) |
| Removal of CRBN / concentration defaults | yes | `PROBE_FIXTURES` still present by design; scientific path still emits demo inputs | `partial` |
| BRD4–VHL trace, 6 recomputed ranks, 0 measured degradation | yes | `outputs/…` traces exist; `degradation` values are model predictions, correctly labelled as such by the critic | `verified` (arithmetic/lineage only) |
| 125-prompt parser accuracy 1.0000 | yes | `python scripts/evaluate_parser.py` → 125 prompts, 1.0000 ≥ 0.98 | `verified` |
| 48/48 offline smoke, mean 0.885 | yes | reproduced (mean 0.8854) but it is **circular self-grading**; Gate C drafted independent rubrics | `draft_pending_review` (F-05, `gateC/rubrics/`) |
| 92 tests reported | yes | 107 selected PASS + 48 selected PASS; full suite polluted (1357 collected/156 errors) | `partial` (F-16) |
| 29 gold checklists flagged | yes | `SCORABLE_MANIFEST.json` `n_requires_expert_review=29`; Gate C enumerated 29 decisions + `gold_review.tsv`, all `PENDING` | `pending` (F-06) |
| KNOW-01 real run 239 s, wrong engine | yes | artifact confirms 238.86 s and **score 0.0** | `verified`, worse than reported |
| Repository state / clean commits | reports disagree | memory rename committed (`82a0e4d`); Gate B source edits still unstaged; installed CLI fixed | `partial` (F-14 fixed, F-15 fixed) |
| Breadth×depth figure at (8.5, 9.5) | conceptual target | no rubric/source table/rater agreement in repo | `absent` |
| E1–E8 figure | study proposal | see `01_EXPERIMENTS.md` — all E2–E8 lack datasets/splits | `absent` |

## The five closure definitions in `_00` vs reality

1. *Freeze tracker; link path/hash/run-id/command; mark verified/report-only/failed/absent.*
   → **Partially done by this audit.** `evidence/git_state.txt` records HEAD;
   each finding links a command/artifact. Remaining: run-ids for every claim.
2. *Finish the matched-tool pilot on 48 reviewed tasks.*
   → **Not done.** Only 1 deterministic task + a 4-task acceptance run (F-01, F-09).
3. *Build E1–E8 with gold adjudication and held-out splits.*
   → **Not done.** No splits/gold files (F-06, F-10, `01_EXPERIMENTS.md`).
4. *Promote tools through the L0–L5 evidence ladder.*
   → **Only L0 exists.** Registry reports `available/executable = 0` (F-07).
5. *Rebuild the landscape plot only after rubric + comparator freeze.*
   → **Correctly deferred**; no frozen rubric/comparator exists.

## Evidence ladder: what the repo can currently support

| level | requirement | repo state |
|---|---|---|
| L0 registered | registry entry + declared inputs | **296 rows** (F-07) |
| L1 executable | real input completes under pinned env | **agent tools: 34; registry tools: 0 declared** |
| L2 chemically valid | IDs/units/outputs/provenance pass checks | only ad-hoc; no per-tool L2 report |
| L3 retrospective external | held-out beats matched baselines + CI | not run (no splits, no scored baseline) |
| L4 prospective | frozen model precedes outcome, blind | not run |
| L5 experimental | wet-lab | not run |

## Immediate decision (as instructed by `_00`)

`_00` says: "Start with a read-only repository reconciliation and 48-task
matched-tool pilot." — **This audit did the reconciliation (S1/S2/S3 findings).
The 48-task pilot remains blocked** on the questions in `QUESTIONS.md` §A–B.
The shortest honest next step is: F-15 (install) and F-14 (commit/restore) are
fixed; decide F-03 (which path is scientific), then run the 48 deterministic
tasks with the same runner that produced the KNOW-01 artifact only after Gate C
gold is independently approved.
