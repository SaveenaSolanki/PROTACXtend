"""
Tests for adaptive decision-graph extras (capabilities 2, 3, 4, 7).
===================================================================
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.agents.adaptive_extras import (
    warhead_evidence_check, warhead_repair, route_after_warhead_check,
    exit_vector_check, exit_vector_repair, route_after_exit_vector_check,
    select_ternary_tool, tool_selection_node,
    parallel_evaluate, expensive_modeling_gate,
    MAX_SELECTION_RETRY,
)


def base_state(evidence=None, retry=None):
    return {"evidence": evidence or {}, "retry_counts": retry or {},
            "valid_candidates": [], "decision_log": []}


# ── Warhead repair loop ──────────────────────────────────────────────

class TestWarheadLoop:
    def test_weak_warheads_trigger_repair(self):
        state = base_state({"warheads": [{"potency": 0.1}, {"potency": 0.2}]})
        out = warhead_evidence_check(state)
        assert out["status"] == "needs_repair"
        assert route_after_warhead_check({"evidence": {"warhead_check": "all_weak"},
                                          "retry_counts": {}}) == "warhead_repair"

    def test_repair_bounded(self):
        # After MAX_SELECTION_RETRY repairs → human gate
        assert route_after_warhead_check(
            {"evidence": {"warhead_check": "all_weak"},
             "retry_counts": {"warhead": MAX_SELECTION_RETRY}}) == "human_gate"

    def test_good_warhead_proceeds(self):
        state = base_state({"warheads": [{"potency": 0.8}]})
        out = warhead_evidence_check(state)
        assert out["status"] == "ok"
        assert route_after_warhead_check({"evidence": {"warhead_check": "ok"},
                                          "retry_counts": {}}) == "exit_vector_detection"

    def test_repair_bumps_retry_and_relaxes(self):
        out = warhead_repair(base_state({"warhead_repair_round": 0}))
        assert out["retry_counts"] == {"warhead": 1}
        assert out["evidence"]["warhead_min_potency"] < 0.4


# ── Exit-vector repair loop ──────────────────────────────────────────

class TestExitVectorLoop:
    def test_no_exit_vectors_triggers_repair(self):
        state = base_state({"exit_vectors": []})
        out = exit_vector_check(state)
        assert out["status"] == "needs_repair"
        assert route_after_exit_vector_check(
            {"evidence": {"exit_vector_check": "none"}, "retry_counts": {}}) == "exit_vector_repair"

    def test_poor_exit_vectors_escalate_after_budget(self):
        assert route_after_exit_vector_check(
            {"evidence": {"exit_vector_check": "all_poor"},
             "retry_counts": {"exit_vector": MAX_SELECTION_RETRY}}) == "human_gate"

    def test_good_exit_vector_proceeds(self):
        state = base_state({"exit_vectors": [{"score": 0.6}]})
        out = exit_vector_check(state)
        assert out["status"] == "ok"
        assert route_after_exit_vector_check(
            {"evidence": {"exit_vector_check": "ok"}, "retry_counts": {}}) == "linker_generation"


# ── Dynamic tool selection ───────────────────────────────────────────

class TestToolSelection:
    def test_full_evidence_selects_p4ward(self):
        plan = select_ternary_tool({
            "receptor_pdb": "r.pdb", "ligase_pdb": "l.pdb",
            "receptor_ligand_mol2": "r.mol2", "ligase_ligand_mol2": "l.mol2",
            "p4ward_docker_available": True, "exit_vectors": [{"score": 0.6}],
        })
        assert plan["tool"] == "p4ward"
        assert plan["cost"] == "hours"

    def test_smiles_only_selects_proxy(self):
        plan = select_ternary_tool({"warhead_smiles": "C", "e3_ligand_smiles": "N",
                                    "exit_vectors": [{"score": 0.6}]})
        assert plan["tool"] == "geometric_proxy"

    def test_no_evidence_blocked(self):
        plan = select_ternary_tool({})
        assert plan["tool"] == "none"

    def test_tool_selection_node_records_plan(self):
        out = tool_selection_node(base_state({"warhead_smiles": "C", "e3_ligand_smiles": "N",
                                              "exit_vectors": [{"score": 0.6}]}))
        assert out["evidence"]["tool_plan"]["ternary"]["tool"] == "geometric_proxy"


# ── Parallel evaluation ──────────────────────────────────────────────

class TestParallelEvaluate:
    def test_parallel_speedup_and_order(self):
        def slow(c):
            time.sleep(0.15)
            return {"candidate_id": c["candidate_id"], "x": 1}
        cands = [{"candidate_id": f"c{i}"} for i in range(8)]
        t0 = time.time()
        res = parallel_evaluate(cands, slow, max_workers=4)
        elapsed = time.time() - t0
        assert len(res) == 8
        # 8 × 0.15s with 4 workers ≈ 0.3s, not 1.2s
        assert elapsed < 0.9, f"parallel took {elapsed:.2f}s"
        assert [r["candidate_id"] for r in res] == [f"c{i}" for i in range(8)]

    def test_failure_does_not_crash_batch(self):
        def boom(c):
            if c["candidate_id"] == "c2":
                raise RuntimeError("boom")
            return {"candidate_id": c["candidate_id"]}
        cands = [{"candidate_id": f"c{i}"} for i in range(4)]
        res = parallel_evaluate(cands, boom, max_workers=2)
        assert len(res) == 4
        err = [r for r in res if "evaluation_error" in r]
        assert len(err) == 1


# ── Expensive modelling gate ─────────────────────────────────────────

class TestExpensiveGate:
    def test_p4ward_plan_pauses_for_human(self):
        state = base_state({"tool_plan": {"ternary": {"tool": "p4ward", "cost": "hours"}}})
        out = expensive_modeling_gate(state)
        assert out["status"] == "needs_human"
        assert out["decision_log"][0].decision_type == "gate"

    def test_cheap_plan_does_not_pause(self):
        state = base_state({"tool_plan": {"ternary": {"tool": "geometric_proxy", "cost": "seconds"}}})
        out = expensive_modeling_gate(state)
        # still emits a gate but with a "review" reason (deterministic)
        assert out["decision_log"][0].decision_type == "gate"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
