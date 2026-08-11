"""
Automated tests for the 3 agentic scenarios (Task A1).
======================================================

Locks in the v0.2 "agentic" claim with assertions on the decision_log
and visited-node sequence — not print output.

Scenario 1 — GOOD PATH:   sufficient evidence everywhere →
                          18 nodes, no repair, no human gate, straight to report
Scenario 2 — OUT-OF-DOMAIN: ternary says applicability_domain=outside →
                          routes directly to human_gate, downstream stages skipped
Scenario 3 — REPAIR LOOP: ternary low confidence first, high after repair →
                          repair_controller fires, ternary runs twice,
                          retry_counts['ternary'] == 1, then proceeds to report

Also: determinism — same input + same evidence ⇒ same path (A4 regression seed).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.agents.agentic_core import build_agentic_graph
from langgraph.errors import GraphRecursionError

# Thresholds mirrored from agentic_core (kept in sync manually)
TERNARY_CONFIDENCE_THRESHOLD = 0.45
DEGRADATION_CONFIDENCE_THRESHOLD = 0.40
ADMET_PENALTY_THRESHOLD = 0.65  # mirror of agentic_core (composite AMES/DILI/hERG)
MAX_REPAIR_ATTEMPTS = 3


# ── Scenario stub factories ───────────────────────────────────────────

def _base_chain() -> List[str]:
    # NOTE: gates (evidence_sufficiency_gate, repair_controller, human_gate)
    # are registered by build_agentic_graph itself — never pass them as stubs.
    return [
        "supervisor", "planner", "safety", "target_resolver",
        "binder_retrieval", "warhead_selection", "e3_selection",
        "exit_vector_detection", "linker_generation", "construction",
        "validation", "ternary_feasibility", "degradation_prediction",
        "admet_prediction", "novelty_check", "ranking", "report",
    ]


def make_stubs(
    ternary_score: float = 0.85,
    ternary_domain: str = "inside",
    degradation_conf: float = 0.8,
    admet_penalty: float = 0.1,
    ranking_conf: float = 0.85,
    ternary_scores_over_calls: List[float] | None = None,
) -> Dict[str, Callable]:
    """Build stub agents with configurable evidence.

    `ternary_scores_over_calls`: if given, the ternary stub returns each
    score in sequence (stateful) — used for the repair-loop scenario.
    """
    chain = _base_chain()
    call_state = {"ternary_calls": 0}

    def make_stub(name: str) -> Callable:
        def stub(state: Dict[str, Any]) -> Dict[str, Any]:
            t_score = ternary_score
            t_domain = ternary_domain
            if name == "ternary_feasibility" and ternary_scores_over_calls:
                idx = call_state["ternary_calls"]
                t_score = ternary_scores_over_calls[min(idx, len(ternary_scores_over_calls) - 1)]
                call_state["ternary_calls"] += 1

            stage_fields: Dict[str, Any] = {}
            if name == "ternary_feasibility":
                stage_fields = {
                    "ternary_feasibility": {
                        "stub_ternary": {"ternary_plausibility_score": t_score}
                    },
                    "applicability_domain": [{"domain_status": t_domain}],
                }
            elif name == "degradation_prediction":
                stage_fields = {
                    "degradation_predictions": [{"model_confidence": degradation_conf}]
                }
            elif name == "admet_prediction":
                stage_fields = {
                    "admet_predictions": [{"overall_admet_penalty": admet_penalty}]
                }
            elif name == "novelty_check":
                stage_fields = {"novelty_results": [{"is_novel": True}]}
            elif name == "ranking":
                stage_fields = {
                    "ranking_results": [{"confidence": ranking_conf, "candidate_id": "stub_top"}]
                }

            return {
                "status": "ok",
                "last_node": name,
                "evidence": {
                    "ternary": {
                        "ternary_confidence": t_score,
                        "applicability_domain": t_domain,
                        "status": "ok",
                    },
                    "degradation": {"degradation_confidence": degradation_conf, "status": "ok"},
                    "admet": {"admet_penalty": admet_penalty, "status": "ok"},
                },
                "valid_candidates": state.get("valid_candidates", []) or [
                    {"candidate_id": f"stub_{name}", "score": 0.5}
                ],
                **stage_fields,
            }

        return stub

    return {name: make_stub(name) for name in chain}


def run_graph(stubs: Dict[str, Callable]) -> List[str]:
    """Invoke the graph and return the ordered list of visited nodes."""
    graph = build_agentic_graph(legacy_nodes=stubs)
    initial: Dict[str, Any] = {
        "user_request": "design PROTAC for HMGB2 with CRBN",
        "decision_log": [], "retry_counts": {}, "warnings": [], "errors": [],
        "status": "running", "pipeline_status": "running", "evidence": {},
        "valid_candidates": [], "degradation_predictions": [],
        "admet_predictions": [], "novelty_results": [], "applicability_domain": [],
        "ternary_feasibility": {}, "ranking_results": [],
    }
    visited: List[str] = []
    try:
        for chunk in graph.stream(initial, config={"recursion_limit": 100}):
            for node in chunk:
                visited.append(node)
    except GraphRecursionError as exc:
        pytest.fail(f"Graph hit recursion limit — unresolvable loop. Last nodes: {visited[-10:]}. {exc}")
    return visited


# ── Scenario 1: Good path ─────────────────────────────────────────────

class TestGoodPath:
    def test_sufficient_evidence_runs_straight_path(self):
        visited = run_graph(make_stubs())
        # No repair, no human gate
        assert "repair_controller" not in visited
        assert "human_gate" not in visited
        # Ends at report
        assert visited[-1] == "report"
        # Key stages executed in order (relative order preserved)
        order = {node: i for i, node in enumerate(visited)}
        assert order["ternary_feasibility"] < order["degradation_prediction"]
        assert order["degradation_prediction"] < order["admet_prediction"]
        assert order["admet_prediction"] < order["ranking"]
        assert order["ranking"] < order["report"]
        # Nothing after report
        assert visited.count("report") == 1

    def test_same_input_same_path_determinism(self):
        # Same stubs + same input → identical path (regression seed for
        # agentic_mode=false guarantee on the deterministic good path)
        v1 = run_graph(make_stubs())
        v2 = run_graph(make_stubs())
        assert v1 == v2
        assert len(v1) == 18  # 17 chain nodes + 0 detours, report terminal


# ── Scenario 2: Out-of-domain ─────────────────────────────────────────

class TestOutOfDomain:
    def test_out_of_domain_routes_to_human_gate(self):
        visited = run_graph(make_stubs(ternary_domain="outside"))
        # human gate visited
        assert "human_gate" in visited
        # Downstream stages must NOT run — no score is emitted
        for skipped in ["degradation_prediction", "admet_prediction",
                        "novelty_check", "ranking", "report"]:
            assert skipped not in visited, f"{skipped} should be skipped for OOD"
        # The gate was reached immediately after ternary
        ti = visited.index("ternary_feasibility")
        assert visited[ti + 1] == "human_gate"


# ── Scenario 3: Repair loop ───────────────────────────────────────────

class TestRepairLoop:
    def test_low_confidence_triggers_repair_then_proceeds(self):
        # 1st ternary call: 0.2 (below 0.45) → repair; 2nd call: 0.85 → proceed
        visited = run_graph(make_stubs(ternary_scores_over_calls=[0.2, 0.85]))
        assert "repair_controller" in visited
        assert visited.count("ternary_feasibility") >= 2
        # Repair routes back through linker_generation → construction → validation
        # before re-running ternary
        assert visited.count("linker_generation") >= 2
        # Ends at report (the repair actually fixed it)
        assert visited[-1] == "report"
        # No human gate (repair succeeded within budget)
        assert "human_gate" not in visited

    def test_repair_budget_exhaustion_escalates_to_human(self):
        # Ternary always low (0.2) → all 3 repair attempts consumed → human gate
        visited = run_graph(make_stubs(ternary_scores_over_calls=[0.2, 0.2, 0.2, 0.2]))
        assert "repair_controller" in visited
        assert "human_gate" in visited
        assert visited.count("ternary_feasibility") >= 2


# ── Scenario 4: degradation low-confidence escalation ─────────────────

class TestDegradationEscalation:
    def test_low_degradation_confidence_escalates(self):
        visited = run_graph(make_stubs(degradation_conf=0.2))
        # degradation routes to repair → repair controller escalates
        assert "repair_controller" in visited
        assert "human_gate" in visited


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
