# Module 7 — Active Learning / Experiment Selection

Multiobjective **Bayesian/evolutionary experiment selection** over PROTAC design
decisions (linker × operating dose, with an orthogonal-design stereochemistry
cap). v1.0.0 · 2026-09-03 · status **PARTIAL** (validated on synthetic
objectives + component tests only; experimental feedback loop not yet
available) · `public_claim: false`.

Entry points:
- `BayesianOptimizer(pool, params).run()` — budget-bounded search
- `select_next_experiments(candidates, evaluations, k)` — Pareto-first, diversity-aware batch
- `dose_objective_from_hook(...)` — calculated dose objective from the Module-1 equilibrium
- `update_models()` — honest retraining-readiness report (no experimental labels yet)
- agent tool: `run_active_learning` (`protacxtend/tools/active_learning_tool.py`)

Objectives are **explicitly labelled**: `synthetic` (deterministic benchmark),
`calculated` (Module-1 model), or caller-registered (`register_objective`) —
never `measured` unless an assay supplies the label.
