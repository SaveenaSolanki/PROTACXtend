# Gold review — human handoff package

This package is ready for **independent human reviewers**. It contains no
pre-filled judgments and no synthetic gold. Agreement is computed *before*
adjudication. Nothing here may be filled by an LLM or by the system author.

## Files

| file | purpose |
|---|---|
| `benchmark/gateC/reviewed_gold/reviewer_1.csv` | blinded reviewer 1 sheet (48 rows, empty verdicts) |
| `benchmark/gateC/reviewed_gold/reviewer_2.csv` | blinded reviewer 2 sheet (identical schema, independent) |
| `benchmark/gateC/reviewed_gold/adjudicator.csv` | adjudicator sheet (only disagreements) |
| `benchmark/gateC/REVIEWER_DECISIONS.tsv` | 29 blocked-endpoint decisions (RD-01…RD-29) |
| `benchmark/gateC/ADJUDICATION_PROTOCOL.md` | protocol |
| `RUBRIC.md` (this dir) | scoring rubric |
| `scripts/gold_adjudication.py` | status / validate / kappa / merge tooling |

## Workflow

```bash
# 1. Validate a filled workbook (schema + allowed verdicts)
python scripts/gold_adjudication.py validate benchmark/gateC/reviewed_gold/reviewer_1.csv

# 2. Inter-rater agreement BEFORE adjudication (must be reported, not tuned)
python scripts/gold_adjudication.py kappa \
  benchmark/gateC/reviewed_gold/reviewer_1.csv \
  benchmark/gateC/reviewed_gold/reviewer_2.csv

# 3. Only after both reviews are locked, resolve disagreements in adjudicator.csv,
#    then merge. Merge refuses to approve without 2 distinct reviewers + 1 adjudicator.
python scripts/gold_adjudication.py merge --dir benchmark/gateC/reviewed_gold
```

## Rules (enforced by tooling)

- Two distinct reviewer names + one adjudicator are required for `approved:true`.
- `approve / revise / unanswerable / unscorable` are the only verdicts; kappa is
  Cohen's κ on the categorical `verdict` column.
- Empty sheets → `n_filled_both=0`, `cohens_kappa=null`, `approved=false`,
  `gold={}`. Synthetic rows cannot satisfy the approval gate.
- Gold is never visible to evaluated systems or their retrieval channels.

## 48 cases vs 29 reviewer-decision rows

- The benchmark has **48 cases** (`benchmark/gateC/CASE_INVENTORY.json`).
- **29 of the 48** are flagged `requires_expert_review` and have a matching
  `REVIEWER_DECISIONS.tsv` row (RD-01…RD-29) whose `blocked_endpoint` names the
  claim each decision unlocks (e.g. "task-valid evidence-supported success for
  DESIGN-01").
- The other **19** are objective cases gradeable by the deterministic scorer once
  gold exists.
- **Which decisions block the pilot:** all 29 `REVIEWER_DECISIONS` rows are
  `PENDING` and all 48 `gold_review.tsv` rows are `PENDING_ADJUDICATION`. The
  adjudicated-accuracy endpoint stays blocked until ≥ the 30-task pilot subset is
  reviewed; the objective execution endpoint is available now.

## Status (measured)

```
gold_review_pending: 48/48
reviewer_decisions_pending: 29/29
consensus_approved: false
consensus_cases_resolved: 0
scoring_possible: false
```
