"""Bayesian/evolutionary optimizer for Module 7.

Search loop (budget-bounded, deterministic under a seed):
  1. random seed points from the candidate pool
  2. fit RF surrogate over evaluated (features -> objectives)
  3. build proposals: random draws + (mu+lambda) mutations of current elite
  4. acquire with EI/UCB over the surrogate; evaluate the argmax
  5. repeat until budget; return Pareto + best + history

All labels are honest: the default objective is the deterministic synthetic
benchmark ("synthetic"), and any real objective must be registered explicitly
by the caller (never auto-invented).
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence

from protacxtend.modules.active_learning.acquisition import (
    crowding_distance,
    expected_improvement,
    fit_surrogate,
    pareto_front,
    surrogate_predict,
    upper_confidence_bound,
)
from protacxtend.modules.active_learning.objectives import evaluate_candidate
from protacxtend.modules.active_learning.schemas import (
    ActiveLearningParams,
    BatchRecommendation,
    Candidate,
    Evaluation,
    SearchOutcome,
)
from protacxtend.modules.active_learning.search_space import make_candidate_pool

FEATURES = ["linker_index", "dose_log10_nM"]


class BayesianOptimizer:
    """Budget-bounded multiobjective Bayesian/evolutionary experiment selector."""

    def __init__(self,
                 pool: Sequence[Candidate],
                 params: Optional[ActiveLearningParams] = None,
                 objective_name: str = "synthetic_2d"):
        self.pool = list(pool)
        self.params = params or ActiveLearningParams()
        self.objective_name = objective_name
        self.rng = random.Random(self.params.seed)
        self._evals: List[Evaluation] = []

    # -- evaluation ---------------------------------------------------------
    @property
    def evaluations(self) -> List[Evaluation]:
        """All evaluations performed so far (chronological)."""
        return list(self._evals)

    def _evaluate(self, candidate: Candidate) -> Evaluation:
        ev = evaluate_candidate(candidate, objective_name=self.objective_name)
        self._evals.append(ev)
        return ev

    # -- proposals ----------------------------------------------------------
    def _elite_ids(self, top: int = 6) -> List[str]:
        scored = [(e.score(self.params.weights), e) for e in self._evals]
        scored.sort(key=lambda t: t[0], reverse=True)
        return [e.candidate.candidate_id for _, e in scored[:top]]

    def _mutate(self, base: Candidate, count: int) -> List[Candidate]:
        """(mu+lambda)-style local perturbations over the pool neighbourhood."""
        out: List[Candidate] = []
        base_linker = base.linker_id
        for _ in range(count):
            choice = self.rng.random()
            if choice < 0.5:
                # dose perturbation only
                dose = self.rng.choice(list(set(c.dose_nM for c in self.pool)))
                nxt = Candidate(candidate_id=f"{base_linker}@d{dose:g}",
                                linker_id=base_linker,
                                linker_smiles=base.linker_smiles,
                                linker_family=base.linker_family,
                                warhead=base.warhead, e3=base.e3,
                                dose_nM=float(dose), features=dict(base.features))
                nxt.features["dose_log10_nM"] = _log10(dose)
            else:
                # random neighbour linker at same dose
                nxt = self.rng.choice(self.pool)
            if nxt.candidate_id not in {e.candidate.candidate_id for e in self._evals}:
                out.append(nxt)
        return out[:count]

    # -- main loop ----------------------------------------------------------
    def run(self, initial_ids: Optional[Sequence[str]] = None) -> SearchOutcome:
        if not self.pool:
            return SearchOutcome(warnings=["empty candidate pool"])
        budget = self.params.budget_evals
        n_init = min(self.params.n_initial_random, len(self.pool), budget)

        # phase 1: deterministic random seeding
        if initial_ids:
            chosen = [c for c in self.pool if c.candidate_id in set(initial_ids)]
        else:
            chosen = self.rng.sample(self.pool, n_init)
        for c in chosen:
            if len(self._evals) < budget:
                self._evaluate(c)

        # phase 2: surrogate-guided rounds
        rounds = 0
        max_rounds = max(1, budget - n_init)
        while len(self._evals) < budget and rounds < max_rounds * 2:
            rounds += 1
            pts = [e.candidate.features for e in self._evals]
            vals = [e.score(self.params.weights) for e in self._evals]
            model = fit_surrogate(pts, vals, FEATURES, seed=self.params.seed)
            mean, std = surrogate_predict(model, _pool_features(self.pool), FEATURES)

            elite = self._elite_ids(top=self.params.mu)
            proposals = list(self.pool)
            # evolution proposals near current elite
            for eid in elite:
                base = next(c for c in self.pool if c.candidate_id == eid)
                proposals += self._mutate(base, self.params.lam)
            # dedupe unevaluated proposals
            evaluated = {e.candidate.candidate_id for e in self._evals}
            uneval = [c for c in proposals if c.candidate_id not in evaluated]
            if not uneval:
                break

            if mean is None:
                # no surrogate yet -> explore randomly among unevaluated
                nxt = self.rng.choice(uneval)
            else:
                idx_map = {c.candidate_id: i for i, c in enumerate(self.pool)}
                candidates_scores: List[float] = []
                for c in uneval:
                    i = idx_map[c.candidate_id]
                    if self.params.acq == "ucb":
                        acq = upper_confidence_bound(
                            np_array(mean[i]), np_array(std[i]), self.params.ucb_beta)
                    else:
                        incumbent = max(vals) if vals else 0.0
                        acq = expected_improvement(
                            np_array(mean[i]), np_array(std[i]), incumbent)
                    candidates_scores.append(float(acq[0]))
                best_acq = max(range(len(uneval)), key=lambda k: candidates_scores[k])
                nxt = uneval[best_acq]

            if len(self._evals) < budget:
                self._evaluate(nxt)
            else:
                break

        return self._outcome(budget_used=len(self._evals))

    def _outcome(self, budget_used: int) -> SearchOutcome:
        if not self._evals:
            return SearchOutcome(budget_used=budget_used,
                                 warnings=["no evaluations completed"])
        weights = self.params.weights
        best = max(self._evals, key=lambda e: e.score(weights))
        obj_names = sorted({n for e in self._evals for n in e.objectives})
        front_idx = pareto_front(self._evals, obj_names)
        history = [{"candidate": e.candidate.candidate_id,
                    "score": e.score(weights),
                    "objectives": dict(e.objectives),
                    "sources": dict(e.sources)} for e in self._evals]
        return SearchOutcome(
            best_objective=best.score(weights),
            best_candidate=best.candidate,
            pareto=[self._evals[i] for i in front_idx],
            history=history,
            budget_used=budget_used,
            objective_name=self.objective_name,
            warnings=[])


def _pool_features(pool: Sequence[Candidate]) -> List[Dict[str, float]]:
    return [c.features for c in pool]


def np_array(x: float) -> Any:
    import numpy as _np
    return _np.asarray([x])


def _log10(x: float) -> float:
    import math
    return math.log10(x) if x > 0 else 0.0


def _diverse_batch(evaluations: List[Evaluation], k: int,
                   seed: int) -> List[Evaluation]:
    """Greedy max-min batch over normalised objective space (diversity)."""
    import numpy as np
    if not evaluations or k <= 0:
        return []
    names = sorted({n for e in evaluations for n in e.objectives})
    if not names:
        return evaluations[:k]
    mat = np.asarray([[e.objectives.get(n, 0.0) for n in names]
                      for e in evaluations], dtype=float)
    lo, hi = mat.min(axis=0), mat.max(axis=0)
    span = hi - lo
    span[span == 0] = 1.0
    norm = (mat - lo) / span
    rng = random.Random(seed)
    # seed with the best-scoring member
    best = max(range(len(evaluations)),
               key=lambda i: evaluations[i].score({}))
    chosen = [best]
    while len(chosen) < min(k, len(evaluations)):
        dists = []
        for i in range(len(evaluations)):
            if i in chosen:
                dists.append(-1.0)
                continue
            d = min(np.linalg.norm(norm[i] - norm[j]) for j in chosen)
            dists.append(d)
        nxt = int(max(range(len(evaluations)), key=lambda i: dists[i]))
        chosen.append(nxt)
    return [evaluations[i] for i in chosen]


def select_next_experiments(candidates: Sequence[Candidate],
                            evaluations: Sequence[Evaluation],
                            k: int = 10,
                            seed: int = 42) -> BatchRecommendation:
    """Recommend the next design/experiment batch from evaluated candidates.

    Selection = Pareto front first (diversity-aware via max-min), then fill
    from the top-ranked remainder. Every returned candidate carries its
    objective sources so callers can see predicted vs calculated vs synthetic.
    """
    evals = list(evaluations)
    if not evals:
        return BatchRecommendation(rationale="no evaluations available")
    names = sorted({n for e in evals for n in e.objectives})
    front_idx = pareto_front(evals, names)
    front = [evals[i] for i in front_idx]
    rest = [evals[i] for i in range(len(evals)) if i not in set(front_idx)]
    rest.sort(key=lambda e: e.score({}), reverse=True)

    batch = _diverse_batch(front, k, seed)
    if len(batch) < k:
        remaining_ids = {b.candidate.candidate_id for b in batch}
        for e in rest:
            if len(batch) >= k:
                break
            if e.candidate.candidate_id not in remaining_ids:
                batch.append(e)
    return BatchRecommendation(
        recommended=[e.candidate for e in batch],
        pareto_ids=[e.candidate.candidate_id for e in front],
        rationale=(f"Pareto front first (n={len(front)}), diversity-max batch, "
                   f"then ranked remainder; objectives={names}"),
        n_evaluated=len(evals),
        budget_used=len(evals),
        meta={"objective_names": names,
              "sources": {n: sorted({e.sources.get(n, "?") for e in evals})
                          for n in names}})


def update_models() -> Dict[str, Any]:
    """Retraining-readiness report (honest: no experimental labels yet)."""
    return {
        "status": "waiting_for_labels",
        "training_rows": 0,
        "retraining_recommendation": (
            "no experimental assay feedback recorded; M4/M5 artifacts frozen "
            "until curated labelled rows from Module-7-selected experiments "
            "are available"),
        "module": "active_learning",
        "model_version": "0.1.0",
    }


def optimize_and_recommend(pool: Sequence[Candidate],
                           params: Optional[ActiveLearningParams] = None,
                           objective_name: str = "synthetic_2d",
                           batch_k: int = 10) -> Dict[str, Any]:
    """One-call convenience: run the optimizer then recommend a batch."""
    params = params or ActiveLearningParams()
    opt = BayesianOptimizer(pool, params, objective_name=objective_name)
    outcome = opt.run()
    rec = select_next_experiments(
        [e.candidate for e in outcome.pareto] or pool,
        outcome.pareto, k=batch_k, seed=params.seed)
    return {"outcome": outcome.to_dict(),
            "recommendation": rec.to_dict(),
            "params": params.to_dict()}
