# VALIDATION

Run: `python -m pytest protacxtend/modules/active_learning/tests/` → **16 passed** (2026-09-03).

| Area | Check | Result |
|---|---|---|
| Schema | JSON config valid; Evaluation round-trip; honest flags (public_claim false) | ✅ |
| Search space | curated library ≥200; pool = linkers × dose grid; features present | ✅ |
| Objectives | synthetic global max reachable in pool; dose objective integrates M1; hook penalty grows with severity | ✅ |
| Acquisition | EI prefers promising point; Pareto front masks dominated rows | ✅ |
| Optimizer | budget respected; no double evaluation; seed-reproducible; best ∈ pool | ✅ |
| Benchmark | BO(30 evals) ≥ random(30 evals), fixed seed (synthetic) | ✅ |
| Batch | Pareto-first + diversity; ids unique & in pool | ✅ |
| Retraining | `update_models()` honest: waiting_for_labels, 0 rows | ✅ |

Benchmark run (quickstart, 2026-09-03): best synthetic 0.7958 in 40 evals vs
random baseline 0.6022 on the same 40 — search machinery, **not** a real-DC50
claim. Real-objective benchmarking requires registered M4/M5 adapters and is
deferred until the Module-6 audit gate closes the experimental-loop design.
