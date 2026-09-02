"""Tests for honest pipeline status labels in reports."""

from __future__ import annotations

import unittest

from protacxtend.backend.main import run_workflow_from_request, summarize_state


class HonestReportLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.state = run_workflow_from_request(
            "Design CRBN-based PROTACs for BRD4 with PEG linkers. Generate 5 candidates with low hERG risk."
        )

    def test_report_includes_status_labels(self) -> None:
        self.assertIn("## Pipeline Status Labels", self.state.report)
        self.assertIn("step_name", self.state.report)
        self.assertIn("tool_status", self.state.report)
        self.assertTrue(self.state.pipeline_status)
        for row in self.state.pipeline_status:
            self.assertIn("selected_tool_or_method", row)
            self.assertIn("real_output_generated", row)
            self.assertIn("stub_or_heuristic", row)
            self.assertIn("next_integration_needed", row)

    def test_stub_modules_are_not_labeled_real(self) -> None:
        by_step = {row["step_name"]: row for row in self.state.pipeline_status}
        self.assertEqual(by_step["DC50/Dmax prediction"]["stub_or_heuristic"], "heuristic_stub")
        self.assertFalse(by_step["DC50/Dmax prediction"]["real_output_generated"])
        self.assertIn("ADME/Tox backend=", by_step["ADME/Tox prediction"]["tool_status"])
        self.assertIn(
            by_step["ADME/Tox prediction"]["stub_or_heuristic"],
            {"descriptor_rule_based", "local_model", "external_api", "heuristic_stub", "not_connected"},
        )

    def test_report_does_not_claim_docking_was_run(self) -> None:
        by_step = {row["step_name"]: row for row in self.state.pipeline_status}
        ternary = by_step["ternary feasibility"]
        self.assertIn("GNINA docking: registered but not executable", ternary["tool_status"])
        self.assertIn("docking_run=False", ternary["evidence"])
        self.assertNotIn("GNINA docking: executable", self.state.report)

    def test_summary_exposes_structured_pipeline_status(self) -> None:
        summary = summarize_state(self.state)
        self.assertIn("pipeline_status", summary)
        self.assertTrue(summary["pipeline_status"])
        self.assertTrue(any(row["step_name"] == "final report" for row in summary["pipeline_status"]))


if __name__ == "__main__":
    unittest.main()
