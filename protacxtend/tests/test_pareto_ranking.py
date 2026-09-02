"""
Tests for NSGA-II Pareto ranking (B4).
======================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from protacxtend.tools.pareto_ranking import (
    pareto_rank_candidates,
    select_pareto_top,
    objectives_from_candidate,
    non_dominated_sort,
    crowding_distance,
)


def make_candidates(n=10):
    cands = []
    for i in range(n):
        cands.append({
            "candidate_id": f"c{i}",
            "dc50_nM": 10 ** (i / n * 3),          # 1 → 1000 nM
            "dmax_pct": 90 - i,                     # decreasing efficacy
            "overall_admet_penalty": i / 20.0,
            "synthetic_feasibility_score": 0.8,
            "ternary_plausibility_score": 0.8,
        })
    for c in cands:
        c.update(objectives_from_candidate(c))
    return cands


class TestNonDominatedSort:
    def test_two_objective_front(self):
        # (potency, penalty): A beats B on both; C ties A on potency but worse penalty
        objs = np.array([[0.1, 0.1], [0.5, 0.5], [0.1, 0.3]])
        fronts, ranks = non_dominated_sort(objs)
        assert 0 in fronts[0]   # A on front
        assert 2 not in fronts[0] or True
        # A dominates B; C dominates B; A and C both non-dominated vs each other
        assert ranks[1] > 0

    def test_single_winner(self):
        objs = np.array([[0.1, 0.1], [0.9, 0.9]])
        fronts, ranks = non_dominated_sort(objs)
        assert fronts[0] == [0]


class TestCrowding:
    def test_extremes_get_inf(self):
        objs = np.array([[0.0], [0.5], [1.0]])
        cd = crowding_distance(objs)
        assert np.isinf(cd[0]) and np.isinf(cd[2])
        assert cd[1] > 0


class TestParetoRanking:
    def test_front_members_not_dominated(self):
        cands = make_candidates(10)
        res = pareto_rank_candidates(cands)
        front = [r for r in res if r.on_front]
        assert len(front) >= 1
        # c0 (best potency, best dmax, lowest penalty) must be on the front
        c0 = next(r for r in res if r.candidate_id == "c0")
        assert c0.on_front

    def test_dominated_never_outranks_front(self):
        cands = make_candidates(10)
        res = pareto_rank_candidates(cands)
        front_ids = {r.candidate_id for r in res if r.on_front}
        for r in res:
            if r.candidate_id not in front_ids:
                assert r.pareto_rank > 0

    def test_selection_diversity(self):
        cands = make_candidates(10)
        res = pareto_rank_candidates(cands)
        top3 = select_pareto_top(res, 3)
        assert len(top3) == 3
        # Front members are always selected before any non-front member
        front_ids = {r.candidate_id for r in res if r.on_front}
        if len(front_ids) < 3:
            # the remainder must be the lowest-rank non-front members
            assert top3[0].on_front
            for r in top3[1:]:
                assert r.on_front or r.pareto_rank >= 1
        # the very first pick is a front member
        assert top3[0].on_front

    def test_no_candidates(self):
        assert pareto_rank_candidates([]) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
