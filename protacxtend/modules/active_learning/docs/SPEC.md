# SPEC — active learning module

## Scope
Recommend the next PROTAC design/experiment batch within an evaluation budget,
treating design as multiobjective search over: linker identity (curated +
rule + generative space), operating dose, and stereochemistry budget.

## Non-goals (v1)
- No experimental-labelled training loop (Module-7 full loop needs assay
  feedback rows; see LIMITATIONS).
- No mutation of M4/M5 artifacts (retraining is `update_models()`-gated).
- No claim of real-world DC50 improvement.

## Interfaces
- `make_candidate_pool(params, library, warhead, e3) -> list[Candidate]`
- `BayesianOptimizer(pool, params, objective_name).run() -> SearchOutcome`
- `select_next_experiments(candidates, evaluations, k) -> BatchRecommendation`
- `dose_objective_from_hook(candidate, kd_*, alpha, ...) -> Evaluation`
- `register_objective(name, fn)`, `evaluate_candidate(...)`
- tool `run_active_learning(payload)` mirrors the Python API

## Honesty contract
Every `Evaluation` carries per-objective `sources` (synthetic/calculated/
predicted). Constraints are boolean; warnings list hook-effect flags. Nothing
is ever labelled measured without an assay row.
