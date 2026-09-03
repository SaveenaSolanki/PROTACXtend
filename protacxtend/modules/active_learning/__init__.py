"""Module 7 — Active Learning / Experiment Selection (multiobjective search).

Multiobjective Bayesian/evolutionary experiment selection over PROTAC design
decisions (linker choice, stereochemistry budget, operating dose). Built v1.0.0
on 2026-09-03: BO surrogate + acquisition (EI/UCB), (mu+lambda) evolution
refinement, Pareto archive + diversity batch selection, and a dose objective
computed from the validated Module-1 hook-effect equilibrium.

Honest boundary (see docs/LIMITATIONS.md): without an experimental feedback
loop the optimizer is validated on deterministic synthetic objectives and on
unit-level component checks — it does NOT claim real-world DC50 improvement.
public_claim stays false in config/scientific_status.yaml until assay feedback
exists.
"""

__version__ = "0.1.0"
MODEL_VERSION = __version__

from protacxtend.modules.active_learning.acquisition import (
    expected_improvement,
    pareto_front,
    surrogate_predict,
)
from protacxtend.modules.active_learning.objectives import (
    SyntheticObjective2D,
    dose_objective_from_hook,
    register_objective,
)
from protacxtend.modules.active_learning.optimizer import (
    BayesianOptimizer,
    select_next_experiments,
    update_models,
)
from protacxtend.modules.active_learning.schemas import (
    ActiveLearningParams,
    BatchRecommendation,
    Candidate,
    Evaluation,
    SearchOutcome,
)
from protacxtend.modules.active_learning.search_space import (
    load_linker_library,
    make_candidate_pool,
)

__all__ = [
    "ActiveLearningParams",
    "BatchRecommendation",
    "BayesianOptimizer",
    "Candidate",
    "Evaluation",
    "MODEL_VERSION",
    "SearchOutcome",
    "SyntheticObjective2D",
    "dose_objective_from_hook",
    "expected_improvement",
    "load_linker_library",
    "make_candidate_pool",
    "pareto_front",
    "register_objective",
    "select_next_experiments",
    "surrogate_predict",
    "update_models",
]
