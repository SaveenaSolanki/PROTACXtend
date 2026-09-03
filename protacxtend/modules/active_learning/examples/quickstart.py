"""Module 7 quickstart — run the optimizer + batch recommendation.

Default run is the deterministic synthetic benchmark (no I/O): it shows the
search machinery finding the best region of a 2-D multimodal objective with
fewer evaluations than random. Then, if kinetics are known, it demonstrates the
calculated Module-1 hook-dose objective on the recommended dose.

Run:  python -m protacxtend.modules.active_learning.examples.quickstart
"""

from __future__ import annotations

import json

from protacxtend.modules.active_learning import (
    ActiveLearningParams,
    BayesianOptimizer,
    dose_objective_from_hook,
    load_linker_library,
    make_candidate_pool,
    select_next_experiments,
)

if __name__ == "__main__":
    library = load_linker_library()
    print(f"curated linker library: {len(library)} entries")

    params = ActiveLearningParams(budget_evals=40, seed=42)
    pool = make_candidate_pool(params, library=library)
    print(f"candidate pool: {len(pool)} (linkers x dose grid)")

    opt = BayesianOptimizer(pool, params, objective_name="synthetic_2d")
    outcome = opt.run()
    print(f"\noptimizer: {outcome.budget_used} evals | best synthetic = "
          f"{outcome.best_objective:.4f}")
    print(f"best candidate : {outcome.best_candidate.candidate_id}")

    # random baseline for context
    import random
    rng = random.Random(params.seed)
    from protacxtend.modules.active_learning.objectives import SyntheticObjective2D
    rand_best = max(SyntheticObjective2D()(c).objectives["synthetic_2d"]
                    for c in rng.sample(pool, params.budget_evals))
    print(f"random baseline: best synthetic = {rand_best:.4f} (same budget)")

    rec = select_next_experiments([e.candidate for e in opt.evaluations],
                                  opt.evaluations,
                                  k=params.diversity_top_k, seed=params.seed)
    print(f"\nrecommended batch (k={len(rec.recommended)}): "
          f"{[c.candidate_id for c in rec.recommended]}")
    print(f"pareto ids: {rec.pareto_ids}")

    # dose planning demo — calculated (Module 1), when kinetics are known
    print("\ndose objective demo (Module-1 equilibrium, label=calculated):")
    for c in rec.recommended[:3]:
        ev = dose_objective_from_hook(c, kd_poi_protac_nM=50.0,
                                      kd_e3_protac_nM=50.0, alpha=30.0)
        print(f"  {c.candidate_id:24s} hook_dose={ev.objectives['hook_dose']:.4f}"
              f"  warnings={ev.warnings or 'none'}")

    report = {"best": outcome.to_dict()["best_candidate"],
              "best_synthetic": outcome.best_objective,
              "random_baseline": rand_best,
              "budget_used": outcome.budget_used,
              "recommended_batch": rec.to_dict()}
    print("\nreport (json):")
    print(json.dumps(report, indent=2, default=str)[:2000])
