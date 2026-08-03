"""Tests for agent-callable wrappers around cloned PROTAC repos."""

from __future__ import annotations

import unittest

from synglue_agent.tools.protac_repo_tool_wrappers import (
    execute_protac_repo_tool,
    get_protac_repo_wrapper_status,
    list_bellerophon_assets,
    list_protac_repo_wrappers,
    list_ternify_example_complexes,
    load_degradomap_tables,
    load_env_spec_summary,
    manual_only_tool_response,
    protac_degradation_predictor_status,
    smoke_test_protac_repo_import,
    split_protac_with_safe_wrapper,
)


class ProtacRepoToolWrapperTests(unittest.TestCase):
    def test_list_wrappers_exposes_agent_callable_records(self) -> None:
        result = list_protac_repo_wrappers()
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["count"], 10)
        names = {row["name"] for row in result["records"]}
        self.assertIn("PROTAC-Splitter", names)
        self.assertIn("TERNIFY", names)
        self.assertIn("degradomap", names)

    def test_env_spec_summary_reads_specs(self) -> None:
        result = load_env_spec_summary("PROTAC-Splitter")
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["count"], 1)
        self.assertTrue(result["records"][0]["preview"])

    def test_degradomap_local_tables_are_workable(self) -> None:
        result = load_degradomap_tables("e3_ligases_verified", max_rows=3)
        self.assertTrue(result["success"], result.get("error"))
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["records"][0]["row_count"], 0)
        self.assertLessEqual(len(result["records"][0]["preview_rows"]), 3)
        self.assertIn("no model fitting", result["limitations"])

    def test_ternify_example_catalog_is_workable_without_modeling(self) -> None:
        result = list_ternify_example_complexes()
        self.assertTrue(result["success"], result.get("error"))
        self.assertGreaterEqual(len(result["records"]), 1)
        self.assertIn("complete", result["records"][0])
        self.assertIn("not run", result["limitations"])

    def test_bellerophon_asset_catalog_is_workable_without_pipeline(self) -> None:
        result = list_bellerophon_assets()
        self.assertTrue(result["success"], result.get("error"))
        suffixes = {row["suffix"] for row in result["records"]}
        self.assertTrue({".sdf", ".py"} & suffixes)
        self.assertIn("manual-only", result["limitations"])

    def test_splitter_safe_wrapper_never_claims_model_when_unavailable(self) -> None:
        result = split_protac_with_safe_wrapper("CCOCC")
        self.assertTrue(result["success"], result.get("error"))
        self.assertTrue(result["valid_smiles"])
        self.assertIn(result["status"], {"ok", "validated_only"})
        if result["status"] == "validated_only":
            self.assertIsNone(result["split"])

    def test_degradation_predictor_is_manual_until_model_wrapper_exists(self) -> None:
        result = protac_degradation_predictor_status()
        self.assertFalse(result["success"])
        self.assertFalse(result["prediction_available"])
        self.assertEqual(result["status"], "manual_only")
        self.assertIn("Do not claim", result["claim_allowed"])

    def test_dispatch_routes_safe_tasks(self) -> None:
        degradomap = execute_protac_repo_tool("degradomap", "load e3 table", {"table_name": "e3_ligases_verified", "max_rows": 1})
        ternify = execute_protac_repo_tool("TERNIFY", "list example data", {})
        bellerophon = execute_protac_repo_tool("Bellerophon", "list assets", {})
        self.assertTrue(degradomap["success"])
        self.assertTrue(ternify["success"])
        self.assertTrue(bellerophon["success"])

    def test_manual_only_dispatch_for_heavy_tool(self) -> None:
        result = manual_only_tool_response("PROTACFold", "run folding")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "unsafe_heavy_manual_only")
        self.assertIn("no scientific result", result["claim_allowed"])

    def test_status_and_smoke_test_are_structured(self) -> None:
        status = get_protac_repo_wrapper_status("PROTAC-Splitter")
        smoke = smoke_test_protac_repo_import("PROTAC-Splitter")
        self.assertTrue(status["registered"])
        self.assertIn("safe_capabilities", status)
        self.assertIn(smoke["status"], {"success", "failed", "not_tested", "skipped_manual_review"})
        if not smoke["success"]:
            self.assertTrue(smoke["error"])


if __name__ == "__main__":
    unittest.main()
