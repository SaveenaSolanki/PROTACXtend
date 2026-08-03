# Uncertainty calibration + applicability domain (capability 5)

_Generated 2026-08-03_

## What was measured (n=64 held-out PROTAC-DB 3.0 molecules)

| Signal | Result | Verdict |
|---|---|---|
| Chemprop ensemble mean (3 members, cal-set excluded) | Spearman ρ=0.783 (p<0.001), MAE=0.61 log10 | validated rank signal |
| Raw ensemble std vs \|error\| | ρ=0.086 (p=0.50) | **NOT calibrated alone** |
| AD similarity (Morgan nn-Tanimoto) tertiles | far RMSE 0.88, mid 0.45, near 0.50 log10 | calibrated trust signal |
| **Conformal intervals** (cal set n=200, conformal-regression) | **92.2% coverage (target 90%)**, widths ~±1.4 log10 | properly calibrated |

## Design

`tools/applicability_domain.py` — Morgan(2048, r=2) fingerprints of the 1,698
training molecules (cached), nearest-neighbor Tanimoto per candidate:
  - in_domain   ≥ 0.40
  - borderline  ≥ 0.30
  - out_of_domain < 0.30
(Fixed a real bug: numpy bool matmul `B @ a` does not AND-count — explicit
logical ops required.)

`tools/uncertainty_aware_prediction.py` — chemprop 3-member ensemble +
conformal-regression calibration + AD, composed into verdicts:
  - high_confidence  (in-domain, interval not extreme)
  - medium_confidence (borderline or wide interval)
  - low_confidence   (out-of-domain)

## Integration

`agents/degradation_node.py` — the real degradation node for the agentic
graph: runs the validated layer on candidate SMILES, stores per-candidate
(dc50, uncertainty, AD status, verdict, model_confidence), routes
low-confidence candidates into the bounded repair loop → human gate.

## Honest limits

- Conformal intervals are wide (±1.4 log10 ≈ 25×) — the model genuinely
  cannot pin absolute DC50 tightly; ranking (ρ=0.78) is the reliable output.
- Ensemble std alone is not calibrated (measured); conformal fixes this at
  the cost of width.
- n=64 benchmark; cal set n=200 — intervals will tighten with more data.
