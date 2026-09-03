# USAGE

```bash
# tests
python -m pytest protacxtend/modules/active_learning/tests -q

# demo (synthetic benchmark + dose planning)
python -m protacxtend.modules.active_learning.examples.quickstart
```

```python
from protacxtend.modules.active_learning import (
    ActiveLearningParams, BayesianOptimizer, load_linker_library,
    make_candidate_pool, select_next_experiments)

params = ActiveLearningParams(budget_evals=40, seed=42)
pool = make_candidate_pool(params, library=load_linker_library())
out = BayesianOptimizer(pool, params, objective_name="synthetic_2d").run()
rec = select_next_experiments([e.candidate for e in out.pareto],
                              out.pareto, k=10, seed=42)
print(out.best_candidate.candidate_id, out.best_objective)
```

Register a real objective (e.g. an M4/M5 adapter) before production use:

```python
from protacxtend.modules.active_learning import register_objective

def my_objective(candidate):
    ...  # must return Evaluation or None
    return None

register_objective("m4_pdc50_adapter", my_objective)
```

Agent tool call (JSON): `{"tool": "run_active_learning",
"payload": {"budget_evals": 40, "acq": "ei", "batch_k": 10}}`
