"""LangGraph-ready agent tool — Module 7 run_active_learning."""

from __future__ import annotations

from typing import Any, Dict

from protacxtend.modules.active_learning import (
    MODEL_VERSION,
    ActiveLearningParams,
    BayesianOptimizer,
    select_next_experiments,
    update_models,
)
from protacxtend.modules.active_learning.search_space import make_candidate_pool

TOOL_NAME = "run_active_learning"
EXPENSIVE = False


def tool_spec() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": ("Recommend the next PROTAC design/experiment batch with "
                        "budget-bounded multiobjective Bayesian/evolutionary "
                        "search over (linker x dose). Default objective is the "
                        "deterministic synthetic benchmark; register real "
                        "objectives via register_objective() before use. Honest "
                        "labels: sources predicted/calculated/synthetic — never "
                        "measured."),
        "expensive": EXPENSIVE,
        "model_version": MODEL_VERSION,
        "input_schema": {"type": "object",
                         "properties": {"budget_evals": {"type": "integer"},
                                        "acq": {"type": "string",
                                                "enum": ["ei", "ucb"]},
                                        "objective": {"type": "string",
                                                      "default": "synthetic_2d"},
                                        "batch_k": {"type": "integer"},
                                        "seed": {"type": "integer"}},
                         "required": []},
    }


def run_active_learning(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        action = payload.get("action", "optimize")
        if action == "retraining_readiness":
            return {"success": True, "result": update_models(), "error": ""}
        params = ActiveLearningParams.from_dict({
            k: v for k, v in payload.items()
            if k in {"budget_evals", "n_initial_random", "acq", "ucb_beta",
                     "seed", "batch_k", "dose_levels"}})
        if "batch_k" in payload:
            batch_k = int(payload["batch_k"])
        else:
            batch_k = params.diversity_top_k
        objective = payload.get("objective", "synthetic_2d")
        pool = make_candidate_pool(params)
        if not pool:
            raise ValueError("empty candidate pool (linker library missing)")
        opt = BayesianOptimizer(pool, params, objective_name=objective)
        outcome = opt.run()
        rec = select_next_experiments(
            [e.candidate for e in outcome.pareto] or pool,
            outcome.pareto, k=batch_k, seed=params.seed)
        return {"success": True,
                "result": {"outcome": outcome.to_dict(),
                           "recommendation": rec.to_dict()},
                "error": ""}
    except (ValueError, KeyError) as exc:
        return {"success": False, "result": None,
                "error": f"active_learning: {exc}"}
    except Exception as exc:  # graph safety
        return {"success": False, "result": None,
                "error": f"active_learning: unexpected failure ({exc})"}
