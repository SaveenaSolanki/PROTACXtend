# B6 — Ablation: agentic vs non-agentic pipeline (capability 10)

_Generated 2026-08-03 · reproducible via `scripts/ablation_agentic_vs_pipeline.py`_

## [A] Degradation layer: heuristic vs trained (n=64 PROTAC-DB)

| Metric | Heuristic (pre-B1) | Trained Chemprop ensemble | Δ |
|---|---|---|---|
| Spearman ρ (log10 DC50) | 0.420 | **0.783** | +0.36 |
| Hit rate <1000 nM | 75% | **92%** | +17 pts |

## [B] Graph: repair loop on vs off (linker strain, failure-injected)

| | Agentic (repair loop) | Sequential pipeline |
|---|---|---|
| Generations | 2 (scan → repair → re-scan) | 1 |
| Strain check | routes to repair | absent |
| Ranking outcome | clean candidates ranked | strained set ranked as-is |

The repair loop rescues a candidate set that a fixed pipeline would either
discard or rank with known-bad geometry.

## [C] Uncertainty: AD flagging on vs off

| | With AD | Without AD |
|---|---|---|
| OOD molecules flagged (8 tested) | 8/8 | 0/8 |
| In-domain misflagged (8 tested) | 0/8 | — |
| OOD prediction ranking | escalated/repair | ranked as confident |

## Verdict

The agent architecture adds measurable value at every layer:
1. **Validated predictive layer** beats the heuristic (+0.36 ρ, +17 pt hit rate)
2. **Bounded repair loops** rescue candidates a pipeline would discard
3. **AD-flagging** prevents out-of-domain predictions from being ranked as
   high-confidence (a silent failure mode of the non-agentic pipeline)

This is the first measured, per-layer ablation. Baseline for future changes:
any modification must not regress A/B/C on the same sets.
