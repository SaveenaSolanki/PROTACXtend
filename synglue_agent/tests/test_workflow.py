"""Lightweight tests for the deterministic SynGlue workflow."""

from __future__ import annotations

import unittest

from synglue_agent.backend.main import run_workflow_from_request, summarize_state
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


class SynGlueWorkflowTests(unittest.TestCase):
    def test_parse_request(self) -> None:
        toolbox = ProtacDesignToolbox()
        objective = toolbox.parse_user_request("Design CRBN-based PROTACs for BRD4 with low hERG risk.")
        self.assertEqual(objective.target_name.upper(), "BRD4")
        self.assertEqual(objective.e3_ligase, "CRBN")
        self.assertTrue(objective.admet_constraints["avoid_hERG"])

    def test_demo_workflow_runs(self) -> None:
        state = run_workflow_from_request(
            "Design CRBN-based PROTACs for BRD4 with PEG, alkyl, piperazine, and triazole linkers. 20 candidates."
        )
        summary = summarize_state(state)
        self.assertEqual(state.design_plan["status"], "continue")
        self.assertIn("DesignPlannerAgent", [trace.agent for trace in state.workflow_log])
        self.assertGreater(summary["warheads_selected"], 0)
        self.assertGreater(summary["e3_ligands_selected"], 0)
        self.assertGreater(summary["linkers_generated"], 0)
        self.assertGreater(summary["valid_candidates"], 0)
        self.assertGreater(len(state.ranking_results), 0)
        self.assertIn("SynGlue-Agent PROTAC Design Report", state.report)

    def test_planner_stops_when_required_target_is_missing(self) -> None:
        state = run_workflow_from_request("")
        self.assertEqual(state.design_plan["status"], "needs_user_input")
        self.assertTrue(state.design_plan["missing_input_questions"])
        self.assertTrue(any("target protein/gene" in error for error in state.errors))
        self.assertIn("DesignPlannerAgent", [trace.agent for trace in state.workflow_log])


if __name__ == "__main__":
    unittest.main()
