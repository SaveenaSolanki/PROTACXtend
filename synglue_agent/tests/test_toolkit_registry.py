"""Tests for the Phase 1 Excel-backed toolkit registry."""

from __future__ import annotations

import unittest

from synglue_agent.toolkit.registry import (
    get_agent_module,
    get_agent_modules,
    get_databases,
    get_modalities,
    get_packages,
    get_skills,
    get_tools,
    load_toolkit_registry,
    search_databases,
    search_registry,
    search_skills,
    search_tools,
    summarize_registry,
)


class ToolkitRegistryTests(unittest.TestCase):
    def test_excel_loads_successfully(self) -> None:
        registry = load_toolkit_registry()
        self.assertIn("source_path", registry)
        self.assertTrue(registry["source_path"].endswith("Agent_Toolkit.xlsx"))

    def test_all_six_key_sheets_are_parsed(self) -> None:
        registry = load_toolkit_registry()
        for section in ["modalities", "tools", "databases", "packages", "skills", "agent_modules"]:
            self.assertIn(section, registry)
            self.assertTrue(registry[section], section)
            first = registry[section][0]
            self.assertIn("source_sheet", first)
            self.assertIn("source_row", first)
            self.assertIsInstance(first["fields"], dict)

    def test_expected_sections_have_many_entries(self) -> None:
        self.assertGreater(len(get_modalities()), 10)
        self.assertGreater(len(get_tools()), 100)
        self.assertGreater(len(get_databases()), 40)
        self.assertGreater(len(get_packages()), 30)
        self.assertGreater(len(get_skills()), 10)
        self.assertGreater(len(get_agent_modules()), 10)

    def test_search_returns_structured_results(self) -> None:
        results = search_registry("docking", top_k=5)
        self.assertTrue(results)
        self.assertTrue(all(isinstance(item, dict) for item in results))
        self.assertTrue(all("name" in item and "fields" in item for item in results))
        self.assertTrue(search_tools("docking", top_k=3))
        self.assertTrue(search_databases("PROTAC", top_k=3))
        self.assertTrue(search_skills("ADME", top_k=3))

    def test_agent_module_lookup(self) -> None:
        module = get_agent_module("Target Agent")
        self.assertIsNotNone(module)
        self.assertEqual(module["name"], "Target Agent")

    def test_summary_counts_sections(self) -> None:
        summary = summarize_registry()
        self.assertGreater(summary["total_rows"], 200)
        self.assertEqual(summary["sections"]["tools"]["source_sheet"], "Tools_Expanded")

    def test_missing_excel_path_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "Toolkit Excel registry not found"):
            load_toolkit_registry("data/toolkit/does_not_exist.xlsx")


if __name__ == "__main__":
    unittest.main()
