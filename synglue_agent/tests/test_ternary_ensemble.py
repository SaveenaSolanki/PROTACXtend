"""
Task 3 — real ternary ensemble tests.
=====================================
- schema validation
- escalation policy (budget-controlled: reject <0.30, p4ward <0.60, top→p4ward+se3)
- consensus math (normalization, agreement, uncertainty)
- disagreement → human gate
- tool failure does not crash; provenance retained
- real geometric proxy produces a score
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.tools.ternary_ensemble import (
    TernaryConsensusResult,
    escalation_plan,
    run_ensemble,
    route_after_ternary_consensus,
    geometric_proxy_score,
    GEOMETRIC_REJECT,
    GEOMETRIC_P4WARD,
)


class TestSchema:
    def test_result_model_defaults(self):
        r = TernaryConsensusResult(candidate_id="x")
        assert r.status == "ambiguous"
        assert r.agreement == 0.0


class TestEscalationPolicy:
    def _cand(self, **kw):
        c = {
            "candidate_id": "c1",
            "warhead_smiles": "CC1(C2=CCN3C(=O)N(C(=O)N3C2C4=C(C=CC(=C4O)C1)O)C5=CC=C(C=C5)C(=O)O)",
            "e3_ligand_smiles": "Nc1cccc2c1C(=O)N(C1CCC(=O)NC1=O)C2=O",
            "linker_smiles": "CCCCCCCCOCCOCCOCCOCC",
            "target_sequence": "MGDKKKKKKKKKKKK",
            "ligase_sequence": "MAAAAAAA",
        }
        c.update(kw)
        return c

    def test_low_geometric_rejects_no_expensive(self, monkeypatch):
        monkeypatch.setattr(
            "synglue_agent.tools.ternary_ensemble.geometric_proxy_score",
            lambda c: {"score": 0.1, "ok": True, "tool": "geometric_proxy"},
        )
        plan = escalation_plan(self._cand())
        assert plan == ["geometric_proxy"]  # reject — no expensive compute

    def test_mid_geometric_runs_p4ward(self, monkeypatch):
        monkeypatch.setattr(
            "synglue_agent.tools.ternary_ensemble.geometric_proxy_score",
            lambda c: {"score": 0.45, "ok": True, "tool": "geometric_proxy"},
        )
        plan = escalation_plan(self._cand())
        assert "p4ward" in plan
        assert "se3_protacs" not in plan

    def test_top_ranked_runs_p4ward_and_se3(self, monkeypatch):
        monkeypatch.setattr(
            "synglue_agent.tools.ternary_ensemble.geometric_proxy_score",
            lambda c: {"score": 0.8, "ok": True, "tool": "geometric_proxy"},
        )
        plan = escalation_plan(self._cand(), top_ranked=True)
        assert "p4ward" in plan and "se3_protacs" in plan

    def test_budget_respected(self, monkeypatch):
        monkeypatch.setattr(
            "synglue_agent.tools.ternary_ensemble.geometric_proxy_score",
            lambda c: {"score": 0.45, "ok": True, "tool": "geometric_proxy"},
        )
        plan = escalation_plan(self._cand(), budget={"p4ward": False, "se3": True})
        assert "p4ward" not in plan


class TestConsensus:
    def test_agreement_supported(self):
        r = TernaryConsensusResult(
            candidate_id="x", methods_run=["a", "b"],
            normalized_scores={"a": 0.8, "b": 0.9}, agreement=1.0,
            consensus_score=0.85, status="supported", uncertainty=0.1,
        )
        assert route_after_ternary_consensus(r) == "degradation_prediction"

    def test_disagreement_routes_human(self):
        r = TernaryConsensusResult(
            candidate_id="x", methods_run=["a", "b"],
            normalized_scores={"a": 0.9, "b": 0.2}, agreement=0.5,
            consensus_score=0.55, status="ambiguous", uncertainty=0.7,
        )
        assert route_after_ternary_consensus(r) == "human_gate"

    def test_unsupported_routes_repair(self):
        r = TernaryConsensusResult(candidate_id="x", status="unsupported")
        assert route_after_ternary_consensus(r) == "repair_controller"


class TestEnsembleExecution:
    def test_real_geometric_proxy_scores(self):
        cand = {"candidate_id": "c1", "warhead_smiles": "CCO", "e3_ligand_smiles": "CCO",
                "linker_smiles": "CCOCC"}
        res = geometric_proxy_score(cand)
        assert res["ok"] is True
        assert 0.0 <= res["score"] <= 1.0

    def test_ensemble_no_crash_all_methods_fail(self, monkeypatch):
        monkeypatch.setattr(
            "synglue_agent.tools.ternary_ensemble.geometric_proxy_score",
            lambda c: {"score": None, "ok": False, "tool": "geometric_proxy", "error": "x"},
        )
        monkeypatch.setattr(
            "synglue_agent.tools.ternary_ensemble.p4ward_score",
            lambda c, **kw: {"score": None, "ok": False, "tool": "p4ward", "error": "no_run_dir"},
        )
        monkeypatch.setattr(
            "synglue_agent.tools.ternary_ensemble.se3_protacs_score",
            lambda c, **kw: {"score": None, "ok": False, "tool": "se3_protacs", "error": "weights_missing"},
        )
        cand = {"candidate_id": "c1"}
        r = run_ensemble(cand, methods=["geometric_proxy", "p4ward", "se3_protacs"])
        assert r.status == "out_of_domain"
        assert all(v.startswith("failed") for v in r.provenance.values())

    def test_ensemble_consensus_with_two_methods(self, monkeypatch):
        def fake_geom(c):
            return {"score": 0.8, "ok": True, "tool": "geometric_proxy"}
        def fake_se3(c, model_dir=None):
            return {"score": 0.9, "ok": True, "tool": "se3_protacs"}
        monkeypatch.setattr("synglue_agent.tools.ternary_ensemble.geometric_proxy_score", fake_geom)
        monkeypatch.setattr("synglue_agent.tools.ternary_ensemble.se3_protacs_score", fake_se3)
        cand = {"candidate_id": "c1"}
        r = run_ensemble(cand, methods=["geometric_proxy", "se3_protacs"])
        assert r.status == "supported"
        assert r.consensus_score > 0.5
        assert r.agreement == 1.0
        assert set(r.methods_run) >= {"geometric_proxy", "se3_protacs"}


class TestSe3Availability:
    def test_se3_unavailable_graceful(self):
        """Without sequences/weights → failed provenance, no crash."""
        import os
        if os.path.exists("data/protac_repos/repos/SE3-protacs/model/SE3-PROTACs.pt"):
            pytest.skip("weights present — slow load test")
        from synglue_agent.tools.ternary_ensemble import se3_protacs_score
        res = se3_protacs_score({"candidate_id": "c1"})
        assert res["ok"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
