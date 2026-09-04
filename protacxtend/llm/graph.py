"""
LangGraph wiring for the LLM-gated layer (A6 / v0.3).
=====================================================

Graph:
  START → llm_evidence_gate ──conditional──→ collect_evidence / design_planner / human_gate / report
  design_planner → construction → llm_critic ──conditional──→ report / repair_controller
  repair_controller ──conditional──→ (stage) / human_gate / report

Every LLM node has a deterministic fallback; the graph never depends on
the model being reachable. Human review is enforced before expensive
tools and before final recommendation.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from protacxtend.llm.decision_layer import (
    llm_evidence_gate,
    llm_repair_controller,
    llm_critic,
    route_after_llm_evidence_gate,
)
from protacxtend.agents.state import WorkflowState, sum_counts
from typing import Annotated


# Graph state: reuse WorkflowState shape; retry_counts uses the sum reducer
# so bounded loops actually count (plain `dict` state replaces, not merges).
class LlmGraphState(WorkflowState):
    retry_counts: Annotated[dict, sum_counts]


# ── deterministic stubs for the non-LLM stages ────────────────────────

def _stub(name: str) -> Callable:
    def node(state: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", "last_node": name}
    return node


def collect_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "ok", "last_node": "collect_evidence"}


def human_gate(state: Dict[str, Any]) -> Command:
    """Deterministic human gate: pause and surface decision packet."""
    from langgraph.types import interrupt
    decision = interrupt({
        "reason": "llm_evidence_gate_required_human_review",
        "evidence_decision": state.get("evidence", {}).get("llm_evidence_decision"),
    })
    goto = "design_planner" if decision == "approve" else "report"
    return Command(goto=goto, update={"status": "human_decided"})


def route_after_critic(state: Dict[str, Any]) -> str:
    critique = state.get("evidence", {}).get("llm_critique", {})
    return "report" if critique.get("verdict") == "accept" else "repair_controller"


def route_after_repair(state: Dict[str, Any]) -> str:
    repair = state.get("evidence", {}).get("llm_repair_decision", {})
    action = repair.get("action", "human_review")
    stage_map = {
        "retry_relaxed_params": "ternary_feasibility",
        "escalate_ensemble": "ternary_ensemble",
        "alternate_linker": "linker_generation",
        "alternate_warhead": "warhead_selection",
        "alternate_exit_vector": "exit_vector_detection",
        "collect_more_evidence": "collect_evidence",
        "human_review": "human_gate",
        "abort": "report",
    }
    return stage_map.get(action, "human_gate")


def build_llm_graph(extra_nodes: Optional[Dict[str, Callable]] = None):
    """Compile the LLM-gated v0.3 graph.

    extra_nodes: supply real stage implementations; defaults to stubs so the
    graph runs without external tools.
    """
    nodes: Dict[str, Callable] = {
        "collect_evidence": collect_evidence,
        "design_planner": _stub("design_planner"),
        "construction": _stub("construction"),
        "ternary_feasibility": _stub("ternary_feasibility"),
        "ternary_ensemble": _stub("ternary_ensemble"),
        "linker_generation": _stub("linker_generation"),
        "warhead_selection": _stub("warhead_selection"),
        "exit_vector_detection": _stub("exit_vector_detection"),
        "report": _stub("report"),
    }
    if extra_nodes:
        nodes.update(extra_nodes)

    builder = StateGraph(LlmGraphState)

    builder.add_node("llm_evidence_gate", llm_evidence_gate)
    builder.add_node("llm_repair_controller", llm_repair_controller)
    builder.add_node("llm_critic", llm_critic)
    builder.add_node("human_gate", human_gate)
    for name, fn in nodes.items():
        builder.add_node(name, fn)

    builder.add_edge(START, "llm_evidence_gate")
    builder.add_conditional_edges(
        "llm_evidence_gate", route_after_llm_evidence_gate,
        {
            "collect_evidence": "collect_evidence",
            "design_planner": "design_planner",
            "human_gate": "human_gate",
            "report": "report",
        },
    )

    builder.add_edge("collect_evidence", "llm_evidence_gate")
    builder.add_edge("design_planner", "construction")
    builder.add_edge("construction", "llm_critic")

    builder.add_conditional_edges(
        "llm_critic", route_after_critic,
        {"report": "report", "repair_controller": "llm_repair_controller"},
    )

    builder.add_conditional_edges(
        "llm_repair_controller", route_after_repair,
        {
            "ternary_feasibility": "ternary_feasibility",
            "ternary_ensemble": "ternary_ensemble",
            "linker_generation": "linker_generation",
            "warhead_selection": "warhead_selection",
            "exit_vector_detection": "exit_vector_detection",
            "collect_evidence": "collect_evidence",
            "human_gate": "human_gate",
            "report": "report",
        },
    )

    builder.add_edge("human_gate", "report")
    builder.add_edge("report", END)
    builder.add_edge("ternary_feasibility", "report")
    builder.add_edge("ternary_ensemble", "report")
    builder.add_edge("linker_generation", "report")
    builder.add_edge("warhead_selection", "report")
    builder.add_edge("exit_vector_detection", "report")

    return builder.compile()
