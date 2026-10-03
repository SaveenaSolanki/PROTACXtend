# Reviewer-approved gold (unlocks correctness scoring)

This directory is the **only** permitted source of correctness gold for the
closed 48-case benchmark. Scoring is impossible until `consensus.json` exists
with `"approved": true` and two named reviewers plus an adjudicator.

## Workflow

1. Start from `consensus.template.json`.
2. Reviewers fill, per task, `expected_answer` (or `expected_value/set/ranking`),
   `mandatory_answer_elements`, `acceptable_alternatives`, `evidence_spans` and
   `answerability`.
3. For the 29 flagged tasks, the matching `RD-xx` decision in
   `../REVIEWER_DECISIONS.tsv` must be resolved and recorded.
4. Set `approved: true`, `approved_by`, `adjudicator`, `approved_at`.
5. Run:

```bash
python scripts/score_closed_48.py --run-dir benchmark_results/closed48/<run_id>
```

The scorer grades with `use_overlay=False`, i.e. **without** reading the
self-derived `benchmark/scoring/*.json` overlays. `design_rubric` and
`mechanistic_rubric` tasks remain `requires_expert_review` even then: they need
the reviewer dimension scores, not a checklist.

## Forbidden

* Do not copy `benchmark/ground_truth/*.json` answers in as "independent" gold.
* Do not mark `approved: true` without a second reviewer and an adjudicator.
