"""Tests for Phase 2 toolkit status annotations."""

from __future__ import annotations

import unittest

from protacxtend.toolkit.registry import load_toolkit_registry
from protacxtend.toolkit.status import (
    classify_existing_implementation,
    detect_cli_availability,
    detect_package_availability,
    get_all_tool_statuses,
    get_tool_status,
    summarize_toolkit_status,
)


class ToolkitStatusTests(unittest.TestCase):
    def test_every_registry_entry_receives_status(self) -> None:
        registry = load_toolkit_registry()
        expected = sum(len(registry[section]) for section in registry["sections"])
        statuses = get_all_tool_statuses()
        self.assertEqual(len(statuses), expected)
        for status in statuses:
            self.assertIn("registered", status)
            self.assertIn("available", status)
            self.assertIn("executable", status)
            self.assertIn("execution_mode", status)
            self.assertIn("evidence", status)
            self.assertIn("failure_reason", status)
            self.assertIn("source_sheet", status)
            self.assertIn("source_row", status)
            self.assertIn("source_link", status)

    def test_registered_entries_are_true(self) -> None:
        self.assertTrue(all(status["registered"] for status in get_all_tool_statuses()))

    def test_missing_implementation_is_not_executable(self) -> None:
        status = get_tool_status("Definitely Missing Tool")
        self.assertFalse(status["registered"])
        self.assertFalse(status["executable"])
        self.assertEqual(status["execution_mode"], "not_connected")

    def test_stub_tools_are_labeled_stub_not_real(self) -> None:
        status = get_tool_status("DC50/Dmax prediction")
        self.assertTrue(status["registered"])
        self.assertFalse(status["executable"])
        self.assertEqual(status["classification"], "stub")
        self.assertEqual(status["execution_mode"], "stub")
        self.assertIn("heuristic", status["failure_reason"])

    def test_summary_counts_status_categories(self) -> None:
        summary = summarize_toolkit_status()
        self.assertGreater(summary["registered"], 200)
        self.assertIn("available", summary)
        self.assertIn("executable", summary)
        self.assertIn("stub", summary)
        self.assertIn("not_connected", summary)
        self.assertGreater(summary["stub"], 0)
        self.assertGreater(summary["not_connected"], 0)

    def test_detection_helpers_are_structured(self) -> None:
        package = detect_package_availability("rdkit")
        self.assertIn("available", package)
        self.assertIn("evidence", package)
        cli = detect_cli_availability("definitely-not-a-command")
        self.assertFalse(cli["available"])
        self.assertIn("evidence", cli)
        implementation = classify_existing_implementation("DC50/Dmax prediction")
        self.assertEqual(implementation["classification"], "stub")


if __name__ == "__main__":
    unittest.main()
