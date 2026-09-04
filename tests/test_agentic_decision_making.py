from protacxtend.agentic.decision_making import DecisionMakingAgent
from protacxtend.agentic.goal_setting import GoalSettingAgent
from protacxtend.agentic.perception import PerceptionAgent
from protacxtend.agentic.reasoning import ReasoningAgent
from protacxtend.schemas.tool_schema import ToolResult

import unittest


def _states(request: str):
    perception = PerceptionAgent().run(request)
    reasoning = ReasoningAgent().run(perception)
    goal = GoalSettingAgent().run(perception, reasoning)
    return perception, reasoning, goal


class AgenticDecisionMakingTests(unittest.TestCase):
    def test_missing_e3_ligase_is_handled_as_assumption(self):
        _, reasoning, goal = _states("Design PROTACs for BRD4. Generate 5 candidates.")
        self.assertTrue(reasoning.e3_assessment["assumption"])
        self.assertEqual(goal.e3_ligase, "CRBN/VHL")

    def test_construction_failure_triggers_fallback_decision(self):
        perception, reasoning, goal = _states("Design CRBN PROTACs for BRD4. Generate 5 candidates.")
        last = ToolResult(tool_name="construction", status="failed", error_message="No PROTAC candidates assembled during construction")
        action = DecisionMakingAgent().choose_next_action(perception, reasoning, goal, last_result=last)
        self.assertEqual(action.action_name, "revise_linker_panel")
        self.assertIn("exit", action.fallback_action)
