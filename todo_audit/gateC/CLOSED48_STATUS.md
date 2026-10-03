# Closed 48-case benchmark — scope-lock status

Date: 2026-09-23 · F-14 commit `82a0e4d` · run `closed48_locked`

## Scope lock

* The existing **48-case** benchmark is the only study in scope.
* The two 500-question templates are **archived, uncurated and unscored**
  (`benchmark500/ARCHIVE_NOTICE.md`, `benchmark500/ARCHIVE_MANIFEST.json`).
* No E2–E8 expansion.

## Done in this scope

1. **`generate_linkers` scientific-input gap fixed.** Both conjugation
   partners (`warhead_smiles`, `e3_smiles`) are now required in SCIENTIFIC mode
   (`protacxtend/runtime/modes.py`). Regression:
   `tests/test_gate_c_input_contract.py` (4 tests). 77 focused tests pass.
2. **Closed 48-case run executed** over three arms with locked budgets
   (`scripts/run_closed_48.py`, run `closed48_locked`):
   `protacxtend` deterministic, `direct_tool` (one matched tool), and
   `fixed_workflow` (same fixed chain for every case).
3. **Gold-gated scoring installed** (`scripts/score_closed_48.py`). It refuses
   to score without `benchmark/gateC/reviewed_gold/consensus.json` approved by
   two reviewers + adjudicator, and grades with `use_overlay=False` (never the
   self-derived overlays).
4. **Figures + manuscript report** (`scripts/plot_closed_48.py`,
   `scripts/make_closed48_report.py`) at
   `benchmark_results/closed48/closed48_locked/`.
5. **Code/data/splits/scoring frozen** (`scripts/freeze_closed48.py`,
   `benchmark/gateC/CLOSED48_FREEZE.json`, 221 hashed entries).

## Headline gold-independent result (run `closed48_locked`)

| arm | completed | partial | abstained | refused | failed | timeout |
|---|---|---|---|---|---|---|
| `direct_tool` | 45 | 1 | 2 | 0 | 0 | 0 |
| `fixed_workflow` | 0 | 48 | 0 | 0 | 0 | 0 |
| `protacxtend` | 0 | 0 | 26 | 0 | 0 | 22 |

Median wall time: `direct_tool` 0.85 s · `fixed_workflow` 51.6 s ·
`protacxtend` 78.4 s (22 cases hit the 120 s cut-off).

**This is a completion/latency result, not a correctness result.** Correctness
is `PENDING_INDEPENDENT_GOLD`.

### Specific result the 48-case study produced

The canonical deterministic `PROTACXtend` path did not return a completed
strategy on any of the 48 cases within the 120 s per-case budget: it abstained
with `INSUFFICIENT EVIDENCE` on 26 and exceeded the budget on 22. The matched
single tool completed 45/48 and the fixed workflow returned partial traces
48/48. Therefore the binding limitation of the 48-case study is **throughput /
latency of the canonical engine**, not a demonstrated accuracy gap.

Per the scope lock, E2–E8 must not start on this basis alone: a latency budget
increase, an offline retrieval cache, or an LLM/agentic arm would answer the
remaining question *within* the 48-case design. Escalating to the 500-question
templates requires a specific question the 48-case design cannot answer (for
example, external validity across targets/E3s not present in the 48), which we
do not yet have.

## Blocked on humans (cannot be done by the agent)

* **Independent gold/rubric review for all 48 cases.** Requires two independent
  domain annotators plus an adjudicator. The agent is not independent of the
  system author; marking gold approved from this side would invalidate the
  benchmark.
* **Resolving the 29 pending decisions.** `REVIEWER_DECISIONS.tsv` enumerates
  the exact questions; all remain `PENDING`.

Until those are signed, `scripts/score_closed_48.py` writes
`pending_adjudication` and no accuracy, paired difference or uncertainty
estimate is produced.

## Evidence-complete and justified no-go cases

* `benchmark_results/closed48/closed48_locked/case_studies/evidence_complete_KNOW-01.md`
* `benchmark_results/closed48/closed48_locked/case_studies/no_go_REASON-02.md`

## Freeze

```
freeze_hash 4c5ff96a8dff94f9f32e6fe343bf71741fa3a662a75508267c135e4ab4e4d981
n_entries   221
gold_adjudicated false · benchmark_score_reported false
```
