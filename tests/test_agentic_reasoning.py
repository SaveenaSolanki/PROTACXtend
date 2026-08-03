from synglue_agent.agentic.perception import PerceptionAgent
from synglue_agent.agentic.reasoning import ReasoningAgent

import unittest


class AgenticReasoningTests(unittest.TestCase):
    def test_reasoning_labels_missing_model_as_heuristic(self):
        perception = PerceptionAgent().run("Design CRBN PROTACs for BRD4. Generate 3 candidates.")
        reasoning = ReasoningAgent().run(perception)
        self.assertTrue(reasoning.target_assessment["suitable_for_protac_design"])
        self.assertIn(reasoning.scoring_strategy["degradation_backend"], {"heuristic_fallback", "trained_model"})
        if reasoning.scoring_strategy["degradation_backend"] == "heuristic_fallback":
            self.assertFalse(reasoning.scoring_strategy["claim_validated_prediction"])
