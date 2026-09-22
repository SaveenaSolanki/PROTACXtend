# tpdeval — TPD Head-to-Head Evaluation Framework

`TPD-HEADTOHEAD/1.0.0` — a publication-grade benchmark architecture for
comparing **PROTACXtend** against **Biomni**, an independent **TPD-specific
agent**, a **general LLM**, a **retrieval-only** baseline, a **tool-only**
baseline, and two hybrids.

## Read in this order

1. [`docs/00_AUDIT.md`](docs/00_AUDIT.md) — evidence-based audit of every existing
   benchmark, agent integration, Biomni status, TPD comparator and baseline.
2. [`docs/01_DESIGN.md`](docs/01_DESIGN.md) — 500-task architecture, two
   conditions, matched-tool design, temporal challenge, failure recovery,
   reproducibility, human adjudication, statistics, ablation, figures, tables.
3. [`docs/02_BLUEPRINT.md`](docs/02_BLUEPRINT.md) — file-by-file blueprint and
   P0–P3 roadmap with acceptance gates.
4. [`docs/03_VERDICT.md`](docs/03_VERDICT.md) — the verdict table. **Every
   performance cell is `NOT YET MEASURED` by design.**

## Quick start

```bash
python -m tpdeval.allocation          # writes config/allocation_500.json
python -c "from tpdeval import validate_taxonomy; print(validate_taxonomy())"
python -m pytest tests/test_tpdeval.py -q
```

## Modules

| Module | Purpose |
|---|---|
| `taxonomy.py` | 16 domains, L1–L7, 300/150/50 partitions, 100 stress tags |
| `taskmodel.py` | strict task/run/score records; anti-fabrication ground-truth status |
| `allocation.py` | 500-task **design** manifest (no invented ground truth) |
| `toolenv.py` | tool-selection precision/recall, call hygiene, 8-step execution |
| `evidence.py` | citation precision/coverage, context match, contradiction |
| `mechanism.py` | causal-graph ground truth + node/edge matching |
| `trajectory.py` | 9-step decision trajectory scoring |
| `calibration.py` | ECE / Brier / reliability |
| `temporal.py` | T0/T1 challenge, leakage flags, outcome classification |
| `failure.py` | 10 injected faults + recovery metrics |
| `reproducibility.py` | repeat agreement, variance, replay, efficiency ledger |
| `stats.py` | paired Wilcoxon / permutation / McNemar / bootstrap / mixed model |
| `ablation.py` | component ablations + planner isolation |
| `systems.py` | systems A–H, conditions, fairness manifest, decomposition |
| `adapters.py` | fail-closed adapters + honest integration status |
| `provenance.py` | run manifests, admissibility, leakage |
| `scoring.py` | separate-metric scoring, secondary composite, claim boundary |
| `dimensions.py` | **deterministic 11-dimension scoring** (9 general + 2 temporal, 0–5), machine + expert components kept separate, no headline composite |
| `reporting.py` | 9 figures + 14 tables, render guard |

## Invariants

- No fabricated ground truth: every task starts `REQUIRES_AUTHORING`.
- No fabricated results: metrics run on recorded data only; figures refuse
  non-measured data.
- Unwired systems are reported `MISSING`/`BLOCKED`, never silently skipped.
- Metrics stay separate; a composite is secondary and labelled.
- **Every task is scored on 11 independent 0–5 dimensions** (9 general + 2
  temporal) by a machine component and an expert component that are stored
  separately and never averaged into one value.
- A dimension the harness cannot compute deterministically is `None`
  (reported as *missing*) — never imputed or defaulted.
- Aggregation reports per-dimension statistics only; the composite is opt-in,
  coverage-labelled and must never be the headline.
- Claim boundaries are attached to every aggregate.
