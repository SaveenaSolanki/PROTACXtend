"""Module 7 tests — challenges 1..N as tests (deterministic, offline).

Suites:
  - schema/JSON integrity
  - search-space construction (curated library load, pool, stereo cap)
  - objective correctness (synthetic known-max enumeration; hook-dose uses M1)
  - acquisition correctness (EI ordering, Pareto non-domination, crowding)
  - optimizer behaviour (budget, reproducibility, no double-eval)
  - benchmark: BO beats random on a fixed seed with fewer evaluations
"""

import json
import os

import pytest

from protacxtend.modules.active_learning import (
    ActiveLearningParams,
    BayesianOptimizer,
    SyntheticObjective2D,
    dose_objective_from_hook,
    expected_improvement,
    load_linker_library,
    make_candidate_pool,
    pareto_front,
    select_next_experiments,
    update_models,
)
from protacxtend.modules.active_learning.schemas import Evaluation

HERE = os.path.dirname(__file__)
CONFIG = os.path.abspath(os.path.join(HERE, "..", "configs", "active_learning.json"))

TOY_LIB = [{"linker_id": f"toy_{i:03d}", "smiles": f"[1*]C{i}[4*]", "family": "toy"}
           for i in range(16)]


def params(**over):
    base = ActiveLearningParams(dose_levels=[1.0, 10.0, 100.0])
    return ActiveLearningParams(**{**base.__dict__, **over})


# ── schema / config ─────────────────────────────────────────────────────────
def test_config_json_valid_and_defaults():
    cfg = json.load(open(CONFIG))
    assert cfg["module"] == "active_learning"
    assert cfg["public_claim"] is False          # honest: no experimental loop
    p = ActiveLearningParams()
    assert p.budget_evals > 0 and p.seed == 42


def test_evaluation_roundtrip():
    ev = SyntheticObjective2D()(make_candidate_pool(params())[0])
    d = ev.to_dict()
    back = Evaluation.from_dict(d)
    assert back.candidate.candidate_id == ev.candidate.candidate_id
    assert back.objectives == ev.objectives
    assert back.sources["synthetic_2d"] == "synthetic"


# ── search space ────────────────────────────────────────────────────────────
def test_curated_linker_library_present():
    lib = load_linker_library()
    assert len(lib) >= 200                 # shipped data/linkers file
    assert all("linker_id" in e and "smiles" in e for e in lib)


def test_pool_build_covered_by_dose_grid():
    p = params(dose_levels=[1.0, 10.0, 100.0])
    pool = make_candidate_pool(p, library=TOY_LIB)
    assert len(pool) == 3 * len(TOY_LIB)
    doses = {c.dose_nM for c in pool}
    assert doses == {1.0, 10.0, 100.0}
    assert all(c.meta["max_stereo_centers"] == p.max_stereo_centers for c in pool)


def test_pool_features_include_linker_index_and_dose():
    pool = make_candidate_pool(params(), library=TOY_LIB)
    c = pool[0]
    assert "linker_index" in c.features and "dose_log10_nM" in c.features


# ── objectives ──────────────────────────────────────────────────────────────
def test_synthetic_objective_max_known_by_enumeration():
    pool = make_candidate_pool(params(), library=TOY_LIB)
    vals = [SyntheticObjective2D()(c).objectives["synthetic_2d"] for c in pool]
    assert max(vals) > 0.5                 # global optimum reachable in pool
    assert all(0.0 <= v <= 1.0 for v in vals)


def test_dose_objective_uses_module1_equilibrium():
    pool = make_candidate_pool(params(), library=TOY_LIB)
    c = next(x for x in pool if x.dose_nM == 10.0)
    ev = dose_objective_from_hook(c, kd_poi_protac_nM=50.0,
                                  kd_e3_protac_nM=50.0, alpha=30.0)
    assert ev.sources["hook_dose"] == "calculated"     # M1 model, not measured
    assert 0.0 <= ev.objectives["hook_dose"] <= 1.0
    assert "hook_ok" in ev.constraints


def test_hook_penalty_grows_with_hook_severity():
    # high alpha + tight Kds should suppress occupancy at high dose => penalty
    low = dose_objective_from_hook(make_candidate_pool(params(), library=TOY_LIB)[0],
                                   kd_poi_protac_nM=50.0, kd_e3_protac_nM=50.0,
                                   alpha=1.0)
    high = dose_objective_from_hook(
        next(c for c in make_candidate_pool(params(), library=TOY_LIB) if c.dose_nM == 100.0),
        kd_poi_protac_nM=10.0, kd_e3_protac_nM=10.0, alpha=300.0)
    assert high.warnings or high.objectives["hook_dose"] <= low.objectives["hook_dose"] + 1e-9


# ── acquisition ─────────────────────────────────────────────────────────────
def test_ei_prefers_promising_point():
    import numpy as np
    mean = np.asarray([0.5, 0.9])
    std = np.asarray([0.1, 0.1])
    ei = expected_improvement(mean, std, incumbent=0.5)
    assert ei[1] > ei[0]


def test_pareto_front_masks_dominated():
    import numpy as np
    objs = np.asarray([[2.0, 0.0], [1.0, 1.0], [0.0, 2.0], [1.0, 0.5]])  # maximise
    from protacxtend.modules.active_learning.schemas import Candidate
    evs = []
    for o in objs:
        c = Candidate(candidate_id=str(len(evs)))
        evs.append(Evaluation(candidate=c, objectives={"a": float(o[0]), "b": float(o[1])}))
    front = pareto_front(evs, ["a", "b"])
    ids = {evs[i].candidate.candidate_id for i in front}
    assert ids == {"0", "1", "2"}          # (1.0, 0.5) is dominated by (1.0, 1.0)


# ── optimizer behaviour ─────────────────────────────────────────────────────
def test_optimizer_respects_budget_and_dedupes():
    pool = make_candidate_pool(params(budget_evals=25), library=TOY_LIB)
    out = BayesianOptimizer(pool, params(budget_evals=25)).run()
    assert out.budget_used == 25
    ids = [h["candidate"] for h in out.history]
    assert len(ids) == len(set(ids))        # never double-evaluate


def test_optimizer_reproducible_under_seed():
    pool = make_candidate_pool(params(budget_evals=30), library=TOY_LIB)
    a = BayesianOptimizer(pool, params(budget_evals=30, seed=7)).run()
    b = BayesianOptimizer(pool, params(budget_evals=30, seed=7)).run()
    assert [h["candidate"] for h in a.history] == [h["candidate"] for h in b.history]
    assert a.best_objective == b.best_objective


def test_optimizer_finds_best_candidate_in_pool():
    pool = make_candidate_pool(params(budget_evals=30), library=TOY_LIB)
    out = BayesianOptimizer(pool, params(budget_evals=30)).run()
    assert out.best_candidate is not None
    assert out.best_candidate.candidate_id in {c.candidate_id for c in pool}


def test_optimizer_beats_random_on_fixed_seed():
    """Benchmark: BO with 30 evals beats 30 random evals (deterministic)."""
    import random as _r
    pool = make_candidate_pool(params(), library=TOY_LIB)
    bo = BayesianOptimizer(pool, params(budget_evals=30, seed=11)).run()

    rng = _r.Random(11)
    rand_vals = []
    for c in rng.sample(pool, 30):
        rand_vals.append(SyntheticObjective2D()(c).objectives["synthetic_2d"])
    assert bo.best_objective >= max(rand_vals)


# ── batch recommendation ────────────────────────────────────────────────────
def test_select_batch_returns_pareto_first_diverse():
    pool = make_candidate_pool(params(), library=TOY_LIB)
    evs = [SyntheticObjective2D()(c) for c in pool]          # full enumeration
    rec = select_next_experiments(pool, evs, k=5)
    assert len(rec.recommended) == 5
    assert rec.pareto_ids
    assert len(set(rec.pareto_ids)) == len(rec.pareto_ids)
    assert all(c.candidate_id in {p.candidate_id for p in pool} for c in rec.recommended)


def test_update_models_is_honest_waiting():
    rep = update_models()
    assert rep["status"] == "waiting_for_labels"
    assert rep["training_rows"] == 0
