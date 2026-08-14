"""
Task 4 — degradation endpoint tests (DC50 + Dmax + class + context).
====================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.tools.degradation_endpoint import (
    DegradationEndpointResult,
    CellContext,
    build_cell_context,
    apply_context_gate,
    predict_degradation_endpoint,
    predict_endpoint_batch,
    ACTIVE_DC50_NM,
    ACTIVE_DMAX_PCT,
)


class TestSchema:
    def test_defaults(self):
        r = DegradationEndpointResult(candidate_id="x")
        assert r.activity_class == "unknown"
        assert r.verdict == "low_confidence"


class TestCellContext:
    def test_mm1s_crbn_high(self):
        ctx = build_cell_context("MM1.S", "BRD4", "CRBN")
        assert ctx.e3_expression == "high"
        assert ctx.evidence_refs  # provenance present

    def test_subcellular_match_rule(self):
        # nuclear target + CRBN → compatible
        ctx = build_cell_context("default", "BRD4", "CRBN", "nuclear")
        assert ctx.subcellular_match is True

    def test_context_gate_low_expression(self):
        ctx = CellContext(cell_line="x", e3_ligase="VHL", e3_expression="low",
                          subcellular_match=True)
        gate = apply_context_gate(ctx)
        assert gate["gated"] is True
        assert "LOW" in gate["notes"][0]

    def test_context_gate_passes_high_expression(self):
        ctx = CellContext(cell_line="x", e3_ligase="CRBN", e3_expression="high",
                          subcellular_match=True)
        assert apply_context_gate(ctx)["gated"] is False


class TestClassification:
    def test_active_thresholds(self):
        r = DegradationEndpointResult(candidate_id="x", dc50_nM=50.0, dmax_pct=90.0)
        # classification is applied in the orchestrator; verify thresholds
        assert 50.0 <= ACTIVE_DC50_NM and 90.0 >= ACTIVE_DMAX_PCT

    def test_inactive_high_dc50(self):
        r = DegradationEndpointResult(candidate_id="x", dc50_nM=2000.0, dmax_pct=30.0)
        assert r.dc50_nM > ACTIVE_DC50_NM  # would classify inactive


class TestEndpointLive:
    def test_full_endpoint_no_crash(self):
        r = predict_degradation_endpoint(
            "COc1ccc(CC(=O)Nc2ccccc2)cc1", candidate_id="c1",
            cell_line="MM1.S", target="BRD4", e3_ligase="CRBN",
        )
        assert isinstance(r, DegradationEndpointResult)
        assert r.dc50_nM is not None
        assert r.dmax_pct is not None
        assert r.activity_class in ("active", "inactive")
        assert r.context.cell_line == "MM1.S"
        assert r.provenance  # provenance required

    def test_context_gate_downgrades_verdict(self):
        # VHL low in MM1.S → chemistry score vetoed
        r = predict_degradation_endpoint(
            "COc1ccc(CC(=O)Nc2ccccc2)cc1", candidate_id="c2",
            cell_line="MM1.S", target="BRD4", e3_ligase="VHL",
        )
        assert r.context.e3_expression == "low"
        assert r.context_gated is True
        assert r.verdict == "low_confidence"
        assert r.note  # explains the veto

    def test_batch_never_crashes(self):
        results = predict_endpoint_batch(
            ["CCO", "CC(=O)Oc1ccccc1C(=O)O", "not-a-smiles"],
            cell_line="HCT116", target="X", e3_ligase="CRBN",
        )
        assert len(results) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


class TestAgentUsesTrainedModel:
    """The DegradationPredictionAgent path must use the trained Chemprop
    ensemble (model_version chemprop-...), with the heuristic only as a
    labelled fallback."""

    def test_predict_degradation_uses_chemprop(self):
        from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox
        from synglue_agent.backend.schemas import CandidateRecord
        t = ProtacDesignToolbox()
        c = CandidateRecord(candidate_id="c1", full_protac_smiles="CC(=O)Oc1ccccc1C(=O)O", e3_ligase="CRBN")
        p = t.predict_degradation([c], None)[0]
        assert p.model_version.startswith("chemprop"), p.model_version
        assert p.predicted_dc50_nM is not None

    def test_heuristic_fallback_labelled(self, monkeypatch):
        from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox
        from synglue_agent.backend.schemas import CandidateRecord
        import synglue_agent.tools.degradation_endpoint as dep
        monkeypatch.setattr(dep, "predict_degradation_batch", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("model down")))
        t = ProtacDesignToolbox()
        c = CandidateRecord(candidate_id="c2", full_protac_smiles="CCCOCCC", e3_ligase="CRBN")
        p = t.predict_degradation([c], None)[0]
        assert p.model_version.startswith("heuristic_proxy"), p.model_version
        assert "chemprop unavailable" in (p.warning or "")
