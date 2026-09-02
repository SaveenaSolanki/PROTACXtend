from synglue_agent.agentic.orchestration import run_agentic_design

import unittest


class AgenticOrchestrationTests(unittest.TestCase):
    def test_agentic_orchestration_works_without_requiring_langgraph(self):
        result = run_agentic_design(
            "Design CRBN-based PROTACs for BRD4. Generate 3 candidates using PEG and alkyl linkers with low hERG risk.",
            config={"stem": "pytest_agentic_orchestration", "validation_depth": "medium"},
        )
        self.assertTrue(result.run_id)
        self.assertIn(result.final_status, {"completed", "completed_with_warnings"})
        self.assertEqual(result.design_goal["target"], "BRD4")
        self.assertTrue(result.candidate_csv_path)
        self.assertTrue(result.candidate_json_path)
        self.assertTrue("heuristic" in "\n".join(result.warnings).lower() or "heuristic" in result.markdown_report.lower())

    def test_orchestration_reports_langgraph_availability_key(self):
        result = run_agentic_design("", config={"stem": "pytest_agentic_missing_input"})
        self.assertEqual(result.final_status, "needs_user_input")
        self.assertIn("langgraph", result.perception["available_tools"])
