"""Tests for Phase 9 executable ADME/Tox layer."""

from __future__ import annotations

import unittest

from synglue_agent.tools.admet_predictors import (
    calculate_protac_admet_descriptors,
    predict_admet,
    predict_with_local_admet_model,
    run_rule_based_admet_flags,
)


class ADMETPredictorTests(unittest.TestCase):
    def test_rdkit_descriptors_feed_into_adme_layer(self) -> None:
        descriptor_result = calculate_protac_admet_descriptors("CCO")
        self.assertTrue(descriptor_result["success"], descriptor_result.get("error"))
        rule_result = run_rule_based_admet_flags("CCO")
        self.assertTrue(rule_result["success"], rule_result.get("error"))
        self.assertEqual(rule_result["backend_used"], "descriptor_rule_based")
        self.assertTrue(rule_result["real_output_generated"])
        for key in ["MW", "TPSA", "LogP", "rotatable_bonds"]:
            self.assertIn(key, rule_result)

    def test_missing_local_model_returns_unavailable(self) -> None:
        result = predict_with_local_admet_model("CCO", model_name="definitely_missing_model")
        self.assertFalse(result["success"])
        self.assertEqual(result["backend_used"], "local_model")
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("unavailable", result["error"].lower())

    def test_heuristic_fallback_is_explicitly_labeled(self) -> None:
        result = predict_admet("CCO", backend="heuristic_stub")
        self.assertTrue(result["success"])
        self.assertEqual(result["backend_used"], "heuristic_stub")
        self.assertEqual(result["status"], "heuristic_stub")
        self.assertFalse(result["real_output_generated"])


if __name__ == "__main__":
    unittest.main()
