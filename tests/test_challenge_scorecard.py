"""Unit tests for protacxtend.tools.challenge_scorecard + feynman_summary.

Offline-safe: uses a minimal in-test workflow fixture (no ADMET-AI subprocess,
no network). Covers: dimension coverage counting, evidence levels, aggregate,
markdown rendering, and the Feynman-style candidate brief.
"""
from __future__ import annotations

import unittest

from protacxtend.tools.challenge_scorecard import (
    aggregate,
    scorecard_from_workflow,
    scorecard_markdown,
    scorecard_report_json,
)
from protacxtend.tools.feynman_summary import summarize_candidate


def _mini_workflow() -> dict:
    """Minimal workflow state exercising every evidence level."""
    cid = "TEST-1"
    return {
        "assembled_candidates": [{
            "candidate_id": cid, "full_protac_smiles": "CCOC(=O)c1ccc2ccccc2c1",
            "target": "BRD4", "e3_ligase": "CRBN", "mw": 785.0, "logp": 3.68,
            "tpsa": 194.0, "hbd": 3, "hba": 11, "rotatable_bonds": 12,
            "warhead_name": "MZ1 JQ1 warhead", "reaction_class": "amide_coupling",
            "synthetic_feasibility_score": 0.8, "validity_status": "valid",
        }],
        "admet_predictions": [{
            "candidate_id": cid, "hERG_risk": "medium", "AMES_risk": "low",
            "DILI_risk": "medium", "CYP_risk": "low", "Pgp_risk": "medium",
            "solubility_risk": "high", "overall_admet_penalty": 0.472,
            "qed": 0.142, "sa_score_proxy": 0.2,
        }],
        "ternary_feasibility_results": [{
            "candidate_id": cid, "ternary_plausibility_score": 0.852,
            "fast_geometry_feasibility_score": 0.833, "linker_reachability_score": 0.924,
            "structural_backend": "geometry_proxy_stub",
            "docking_status": "not_run_stub_available", "proceed_to_expensive_modeling": True,
        }],
        "e3_context_predictions": [{
            "candidate_id": cid, "e3_ligase": "CRBN", "confidence": 0.62,
            "expression_score": 0.6, "colocalization_score": 1.0,
            "ligand_availability_score": 1.0, "structural_support_score": 0.9,
            "resistance_risk": 0.7, "total_context_score": 0.79,
        }],
        "degradation_predictions": [{
            "candidate_id": cid, "predicted_dc50_nM": 181.7,
            "predicted_dmax_percent": 91.4, "model_confidence": 0.85,
            "result_source": "tack-style-v1", "chemprop_dc50_nM": 200.1,
        }],
        "novelty_results": [{"candidate_id": cid, "top_similarity": 0.12}],
        "applicability_domain_results": [{"candidate_id": cid, "applicability_domain_score": 1.0}],
    }


class ChallengeScorecardTest(unittest.TestCase):
    def test_ten_dimensions_and_levels(self):
        wf = _mini_workflow()
        rows = scorecard_from_workflow(wf, "TEST-1")
        self.assertEqual(len(rows), 10)
        levels = {r.dimension: r.evidence_level for r in rows}
        self.assertEqual(levels["cell_permeability"], "rule_descriptor")
        self.assertEqual(levels["ternary_complex"], "geometry_stub")
        self.assertEqual(levels["in_vivo_efficacy"], "ml_model")
        self.assertEqual(levels["safety"], "rule_descriptor")

    def test_aggregate_coverage(self):
        wf = _mini_workflow()
        rows = scorecard_from_workflow(wf, "TEST-1")
        agg = aggregate(rows)
        self.assertEqual(agg["n_dimensions"], 10)
        self.assertEqual(agg["covered"], 10)  # every dimension has some evidence
        self.assertEqual(agg["gaps"], [])
        self.assertIn("ml_model", agg["level_counts"])
        # requires_experiment flags survive even when evidence exists
        self.assertIn("In vivo efficacy (PK/PD translation)", agg["requires_experiment"])

    def test_markdown_and_json(self):
        wf = _mini_workflow()
        rows = scorecard_from_workflow(wf, "TEST-1")
        md = scorecard_markdown(rows, "TEST-1", meta={"campaign": "unit"})
        self.assertIn("Challenge scorecard", md)
        self.assertIn("10/10 dimensions", md)
        rep = scorecard_report_json(rows, "TEST-1", meta={"campaign": "unit"})
        self.assertEqual(len(rep["dimensions"]), 10)
        self.assertEqual(rep["aggregate"]["covered"], 10)

    def test_feynman_brief(self):
        wf = _mini_workflow()
        rows = scorecard_from_workflow(wf, "TEST-1")
        md = summarize_candidate(rows, "TEST-1", meta={"campaign": "unit", "target": "BRD4"})
        for fragment in ("TL;DR", "Candidate brief", "Strongest evidence", "Suggested next steps",
                         "Uncertainty & honesty contract"):
            self.assertIn(fragment, md)
        self.assertIn("DC50", md)
        # no invented numbers: brief must only quote values from the fixture
        self.assertIn("181.7", md)


if __name__ == "__main__":
    unittest.main()