"""Acquisition & Pareto machinery for Module 7.

- ``surrogate_predict``: RandomForest regressor per objective over the design
  features (linker index, dose) -> mean + std (epistemic uncertainty).
- ``expected_improvement`` / ``upper_confidence_bound``: acquisition functions
  over the surrogate (maximise convention).
- ``pareto_front`` / ``crowding``: local non-dominated sort + crowding distance
  (module-local, numpy-only) so multiobjective batches are diversity-aware.

sklearn is required for the surrogate; when absent the module degrades to
random+elite (evolution-only) search — never silently fake acquisition.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


def _feature_matrix(points: Sequence[Dict[str, float]],
                    feature_names: Sequence[str]) -> np.ndarray:
    rows = []
    for p in points:
        rows.append([p.get(f, 0.0) for f in feature_names])
    return np.asarray(rows, dtype=float)


def fit_surrogate(points: Sequence[Dict[str, float]],
                  values: Sequence[float],
                  feature_names: Sequence[str],
                  seed: int = 42):
    """RandomForest surrogate. Returns None when sklearn is unavailable."""
    try:
        from sklearn.ensemble import RandomForestRegressor
    except Exception:  # noqa: BLE001 - optional dependency
        return None
    X = _feature_matrix(points, feature_names)
    y = np.asarray(list(values), dtype=float)
    if len(X) < 3 or np.all(y == y[0]):
        return None
    model = RandomForestRegressor(
        n_estimators=24, max_depth=6, min_samples_leaf=2,
        random_state=seed, n_jobs=1)
    model.fit(X, y)
    return model


def surrogate_predict(model, points: Sequence[Dict[str, float]],
                      feature_names: Sequence[str],
                      ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """(mean, std) over proposals; (None, None) when no surrogate."""
    if model is None:
        return None, None
    X = _feature_matrix(points, feature_names)
    preds = np.asarray([m.predict(X) for m in model.estimators_])
    mean = preds.mean(axis=0)
    std = preds.std(axis=0)
    return mean, std


def _erf_vectorized(z: np.ndarray) -> np.ndarray:
    from math import erf
    return np.frompyfunc(erf, 1, 1)(z).astype(float)


def expected_improvement(mean: np.ndarray, std: np.ndarray,
                         incumbent: float) -> np.ndarray:
    """EI over maximisation (closed form, normal)."""
    import math
    std = np.maximum(std, 1e-9)
    z = (mean - incumbent) / std
    phi = np.exp(-0.5 * z ** 2) / math.sqrt(2.0 * math.pi)
    Phi = 0.5 * (1.0 + _erf_vectorized(z / math.sqrt(2.0)))
    return (mean - incumbent) * Phi + std * phi


def upper_confidence_bound(mean: np.ndarray, std: np.ndarray,
                           beta: float = 1.6) -> np.ndarray:
    return mean + beta * std


def non_dominated(objectives: np.ndarray) -> np.ndarray:
    """Boolean mask of Pareto-nondominated rows (maximise each objective)."""
    n = objectives.shape[0]
    if n == 0:
        return np.zeros(0, dtype=bool)
    dominated = np.zeros(n, dtype=bool)
    for i in range(n):
        if dominated[i]:
            continue
        for j in range(n):
            if i == j or dominated[j]:
                continue
            # j dominates i if j >= i on all and > i on at least one
            ge = objectives[j] >= objectives[i]
            if ge.all() and (objectives[j] > objectives[i]).any():
                dominated[i] = True
                break
    return ~dominated


def crowding_distance(front_obj: np.ndarray) -> np.ndarray:
    """Crowding distance per row (sorted descending objective convention)."""
    n, m = front_obj.shape
    dist = np.zeros(n)
    if n <= 2:
        return dist
    for k in range(m):
        order = np.argsort(front_obj[:, k])
        dist[order[0]] = np.inf
        dist[order[-1]] = np.inf
        col = front_obj[order, k]
        span = col[-1] - col[0]
        if span <= 0:
            continue
        for idx in range(1, n - 1):
            dist[order[idx]] += (col[idx + 1] - col[idx - 1]) / span
    return dist


def pareto_front(evaluations: Sequence["objectives.Evaluation"],  # noqa: F821 - runtime
                 objective_names: Sequence[str],
                 ) -> List[int]:
    """Indices of evaluations lying on the Pareto front."""
    if not evaluations:
        return []
    mat = np.asarray([[e.objectives.get(n, float("-inf")) for n in objective_names]
                      for e in evaluations], dtype=float)
    mask = non_dominated(mat)
    return [i for i, m in enumerate(mask) if m]
