from synglue_agent.agentic.goal_setting import GoalSettingAgent
from synglue_agent.agentic.perception import PerceptionAgent
from synglue_agent.agentic.reasoning import ReasoningAgent

import unittest


class AgenticGoalSettingTests(unittest.TestCase):
    def test_brd4_crbn_request_produces_design_goal(self):
        perception = PerceptionAgent().run("Design CRBN-based PROTACs for BRD4. Generate 20 candidates with low hERG risk.")
        reasoning = ReasoningAgent().run(perception)
        goal = GoalSettingAgent().run(perception, reasoning)
        self.assertEqual(goal.target.upper(), "BRD4")
        self.assertEqual(goal.e3_ligase, "CRBN")
        self.assertEqual(goal.candidate_count, 20)
        self.assertIn("reduce hERG risk", goal.optimization_objectives)
