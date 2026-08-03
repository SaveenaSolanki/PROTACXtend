"""
Multi-objective Pareto ranking (B4 / capability 8).
====================================================

Replaces the single weighted composite score with true multi-objective
non-dominated sorting (NSGA-II-style).

Objectives (all minimized):
  o1 = log10(DC50)            — potency (lower better)
  o2 = 1 - Dmax%              — efficacy (lower better; Dmax missing → 0.5 penalty)
  o3 = ADMET penalty          — developability (lower better)
  o4 = synthesis difficulty   — 1 - synthetic feasibility (lower better)
  o5 = ternary distance       — e.g., 1 - ternary_feasibility (lower better)

Outputs:
  - pareto_front: the non-dominated candidate set
  - crowding_distance per candidate (NSGA-II diversity)
  - pareto_rank per candidate (0 = front, 1 = next, ...)
  - a single `pareto_score` for convenience (rank + crowding, still honest:
    dominated candidates never outrank front members)

No weights are used in the dominance comparison — that is the point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


@dataclass
class ParetoResult:
    candidate_id: str
    objectives: Dict[str, float]     # name → value (minimized)
    pareto_rank: int
    crowding_distance: float
    on_front: bool
    pareto_score: float              # lower = better (rank, then -crowding)


def _dominates(a: np.ndarray, b: np.ndarray) -> bool:
    """True if a dominates b (a <= b in all objectives, < in at least one)."""
    return bool(np.all(a <= b) and np.any(a < b))


def non_dominated_sort(objectives: np.ndarray) -> Tuple[List[List[int]], np.ndarray]:
    """NSGA-II fast non-dominated sort. Returns (fronts, ranks).

    objectives: (n, m) array, all objectives MINIMIZED.
    """
    n = objectives.shape[0]
    dominates_count = np.zeros(n, dtype=int)
    dominated_by: List[List[int]] = [[] for _ in range(n)]
    fronts: List[List[int]] = []

    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if _dominates(objectives[p], objectives[q]):
                dominated_by[p].append(q)
            elif _dominates(objectives[q], objectives[p]):
                dominates_count[p] += 1
        if dominates_count[p] == 0:
            if not fronts:
                fronts.append([])
            fronts[0].append(p)

    ranks = np.zeros(n, dtype=int)
    front_idx = 0
    while fronts[front_idx]:
        next_front: List[int] = []
        for p in fronts[front_idx]:
            ranks[p] = front_idx
            for q in dominated_by[p]:
                dominates_count[q] -= 1
                if dominates_count[q] == 0:
                    next_front.append(q)
        front_idx += 1
        fronts.append(next_front)
        if front_idx > n:  # safety
            break
    fronts = [f for f in fronts if f]
    return fronts, ranks


def crowding_distance(objectives: np.ndarray) -> np.ndarray:
    """NSGA-II crowding distance per solution (higher = more isolated)."""
    n, m = objectives.shape
    if n <= 2:
        return np.full(n, np.inf)
    cd = np.zeros(n)
    for j in range(m):
        order = np.argsort(objectives[:, j])
        cd[order[0]] = np.inf
        cd[order[-1]] = np.inf
        col = objectives[:, j]
        spread = col[order[-1]] - col[order[0]]
        if spread <= 1e-12:
            continue
        for k in range(1, n - 1):
            if np.isfinite(cd[order[k]]):
                cd[order[k]] += (col[order[k + 1]] - col[order[k - 1]]) / spread
    return cd


def pareto_rank_candidates(
    candidates: Sequence[Dict[str, Any]],
    objective_keys: Optional[List[str]] = None,
) -> List[ParetoResult]:
    """Rank candidates by NSGA-II non-dominated sorting.

    Each candidate dict must contain numeric objective values. Default keys:
      log_dc50, dmax_inverted, admet_penalty, synthesis_difficulty, ternary_penalty
    Missing objectives default to their max (worst) — the caller should
    provide them; a missing key is treated as 1.0 (worst on 0-1 scale).

    Returns ParetoResult list sorted by (rank, -crowding).
    """
    if objective_keys is None:
        objective_keys = [
            "log_dc50", "dmax_inverted", "admet_penalty",
            "synthesis_difficulty", "ternary_penalty",
        ]

    n = len(candidates)
    if n == 0:
        return []

    obj_matrix = np.zeros((n, len(objective_keys)))
    for i, c in enumerate(candidates):
        for j, k in enumerate(objective_keys):
            v = c.get(k)
            obj_matrix[i, j] = float(v) if v is not None else 1.0

    fronts, ranks = non_dominated_sort(obj_matrix)
    cd = crowding_distance(obj_matrix)

    results = []
    for i, c in enumerate(candidates):
        cd_i = float(cd[i])
        # inf crowding (extremes) → best possible diversity bonus
        diversity = (cd_i / (1.0 + abs(cd_i))) if np.isfinite(cd_i) else 1.0
        results.append(ParetoResult(
            candidate_id=str(c.get("candidate_id", f"c{i}")),
            objectives={k: round(float(obj_matrix[i, j]), 4)
                        for j, k in enumerate(objective_keys)},
            pareto_rank=int(ranks[i]),
            crowding_distance=cd_i,
            on_front=bool(ranks[i] == 0),
            pareto_score=float(ranks[i] - diversity),
        ))

    results.sort(key=lambda r: (r.pareto_rank, -r.crowding_distance))
    return results


def select_pareto_top(results: List[ParetoResult], k: int) -> List[ParetoResult]:
    """Select the top-k with diversity: front members first, then by crowding."""
    front = [r for r in results if r.on_front]
    if len(front) >= k:
        return sorted(front, key=lambda r: -r.crowding_distance)[:k]
    rest = [r for r in results if not r.on_front]
    return sorted(front, key=lambda r: -r.crowding_distance) + rest[: k - len(front)]


def objectives_from_candidate(c: Dict[str, Any]) -> Dict[str, float]:
    """Build the objective vector from a candidate dict (0-1 scale helpers).

    Expected keys (from pipeline stages):
      dc50_nM, dmax_pct, overall_admet_penalty, synthetic_feasibility_score,
      ternary_plausibility_score
    """
    dc50 = c.get("dc50_nM")
    log_dc50 = float(np.log10(dc50)) / 5.0 if dc50 and dc50 > 0 else 1.0  # normalize 1nM..100µM
    log_dc50 = max(0.0, min(1.0, log_dc50))

    dmax = c.get("dmax_pct")
    dmax_inv = (1.0 - float(dmax) / 100.0) if dmax is not None else 0.5

    admet = float(c.get("overall_admet_penalty", 0.0))
    synth = float(c.get("synthetic_feasibility_score", 0.5))
    synth_diff = 1.0 - min(1.0, max(0.0, synth))

    ternary = float(c.get("ternary_plausibility_score", 0.5))
    ternary_pen = 1.0 - min(1.0, max(0.0, ternary))

    return {
        "log_dc50": log_dc50,
        "dmax_inverted": dmax_inv,
        "admet_penalty": admet,
        "synthesis_difficulty": synth_diff,
        "ternary_penalty": ternary_pen,
    }


if __name__ == "__main__":
    # Self-test
    cands = [
        {"candidate_id": "A", "dc50_nM": 5, "dmax_pct": 90, "overall_admet_penalty": 0.1,
         "synthetic_feasibility_score": 0.8, "ternary_plausibility_score": 0.8},
        {"candidate_id": "B", "dc50_nM": 500, "dmax_pct": 80, "overall_admet_penalty": 0.1,
         "synthetic_feasibility_score": 0.8, "ternary_plausibility_score": 0.8},
        {"candidate_id": "C", "dc50_nM": 8, "dmax_pct": 85, "overall_admet_penalty": 0.05,
         "synthetic_feasibility_score": 0.6, "ternary_plausibility_score": 0.6},
    ]
    for c in cands:
        c.update(objectives_from_candidate(c))
    res = pareto_rank_candidates(cands)
    for r in res:
        print(f"{r.candidate_id}: rank={r.pareto_rank} front={r.on_front} cd={r.crowding_distance:.3f}")
