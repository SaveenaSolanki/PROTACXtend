"""Decision-making layer for action selection and fallbacks."""

from __future__ import annotations

from typing import Any

from synglue_agent.schemas.agentic_schema import DesignGoal, PerceptionState, ReasoningState
from synglue_agent.schemas.tool_schema import NextAction, ToolResult


class DecisionMakingAgent:
    """Choose the next action from evidence, risk, and current state."""

    name = "DecisionMakingAgent"

    def choose_next_action(
        self,
        perception: PerceptionState,
        reasoning: ReasoningState,
        goal: DesignGoal,
        last_result: ToolResult | None = None,
    ) -> NextAction:
        if "target_name" in perception.missing_information:
            return NextAction(
                action_name="ask_user_for_clarification",
                selected_tool="user_input",
                input_payload={"missing": ["target_name"]},
                expected_output="target protein or gene symbol",
                reason_for_action="Scientific constraints conflict with missing required target.",
                fallback_action="stop",
                safety_checks=["do_not_guess_target"],
                confidence=0.99,
            )
        if last_result and last_result.status == "failed":
            msg = (last_result.error_message or "").lower()
            if "construct" in msg or "candidate" in msg:
                return NextAction(
                    action_name="revise_linker_panel",
                    selected_tool="linker_generation",
                    input_payload={"strategy": "broaden_linkers_or_recheck_exit_vectors"},
                    expected_output="new linker panel",
                    reason_for_action="Construction failed, so revise linker panel or exit-vector assumptions.",
                    fallback_action="ask_user_for_warhead_or_exit_vector",
                    safety_checks=["do_not_invent_exit_vector"],
                    confidence=0.82,
                )
        if perception.available_models.get("degradation", {}).get("status") != "model_loaded":
            reason = "Trained model files are absent; use deterministic workflow with heuristic fallback warnings."
        else:
            reason = "All required initial context is available; run deterministic workflow with model provenance."
        return NextAction(
            action_name="run_deterministic_design_workflow",
            selected_tool="synglue_agent.backend.main.run_workflow_from_request",
            input_payload={"request": perception.raw_request},
            expected_output="WorkflowState with candidates, rankings, report, and warnings",
            reason_for_action=reason,
            fallback_action="return_structured_failure",
            safety_checks=["label_heuristic_outputs", "validate_candidates", "record_provenance"],
            confidence=0.86,
        )

