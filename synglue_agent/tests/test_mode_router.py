"""Tests for mode router input/output structure and status labels."""

from __future__ import annotations

import unittest

from synglue_agent.backend.mode_router import run_mode


class ModeRouterTests(unittest.TestCase):
    def test_ask_mode_returns_structured_sections(self) -> None:
        output = run_mode({"mode": "ask", "query": "BRD4 UniProt", "top_k": 3})
        self.assertEqual(output["mode"], "ask")
        self.assertIn("results", output)
        self.assertIn("tools", output["results"])
        self.assertIn("databases", output["results"])
        self.assertIn("skills", output["results"])
        self.assertIn("status_labels", output)

    def test_validate_mode_includes_status_labels(self) -> None:
        output = run_mode({"mode": "validate", "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"})
        self.assertEqual(output["mode"], "validate")
        self.assertIn("validation", output)
        self.assertIn("chemistry", output)
        self.assertIn("admet", output)
        self.assertIn("degradation", output)
        self.assertTrue(output["status_labels"])
        for row in output["status_labels"]:
            self.assertIn("selected_tool_or_method", row)
            self.assertIn("tool_status", row)
            self.assertIn("real_output_generated", row)

    def test_ternary_mode_never_fakes_docking_score(self) -> None:
        output = run_mode(
            {
                "mode": "ternary",
                "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "backend": "vina",
            }
        )
        self.assertEqual(output["mode"], "ternary")
        ternary = output["ternary"]
        self.assertIn("success", ternary)
        if ternary.get("success") is False:
            self.assertIsNone(ternary.get("docking_score"))


if __name__ == "__main__":
    unittest.main()
