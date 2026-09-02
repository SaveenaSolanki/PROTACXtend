"""
Binder agent: normalization + live-source tests.
=================================================
- test_normalization_mock: unit normalization with mocked ChEMBL payloads.
- test_chembl_live: live ChEMBL fetch (skipped when the network is blocked).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from protacxtend.agents.binder_agent import TargetBinderRetrievalAgent, _cached_request  # noqa: E402


class TestNormalization:
    def test_micromolar_units_converted(self, monkeypatch):
        """standard_value in uM must convert to nM (×1000)."""
        a = TargetBinderRetrievalAgent()
        payload = {"activities": [
            {"canonical_smiles": "CCO", "molecule_chembl_id": "CHEMBL1",
             "standard_value": "10", "standard_units": "uM",
             "standard_type": "IC50", "assay_chembl_id": "CHEMBL_ASS1",
             "pchembl_value": None},
        ]}
        monkeypatch.setattr("protacxtend.agents.binder_agent._cached_request", lambda *a_, **k: payload)
        monkeypatch.setattr(a, "_resolve_chembl_target", lambda *a_, **k: "CHEMBL_TGT1")
        binders, ok = a._search_chembl("BRD4", "O60885")
        assert ok and len(binders) == 1
        b = binders[0]
        assert b.activity_nM == pytest.approx(10_000.0), "10 uM -> 10,000 nM"
        assert b.p_activity == pytest.approx(5.0, abs=0.01)

    def test_pchembl_used_when_present(self, monkeypatch):
        a = TargetBinderRetrievalAgent()
        payload = {"activities": [
            {"canonical_smiles": "c1ccccc1", "molecule_chembl_id": "CHEMBL2",
             "standard_value": "999", "standard_units": "nM",
             "standard_type": "Ki", "assay_chembl_id": "CHEMBL_ASS2",
             "pchembl_value": "8.2"},
        ]}
        monkeypatch.setattr("protacxtend.agents.binder_agent._cached_request", lambda *a_, **k: payload)
        monkeypatch.setattr(a, "_resolve_chembl_target", lambda *a_, **k: "CHEMBL_TGT1")
        binders, ok = a._search_chembl("BRD4", "O60885")
        assert ok
        b = binders[0]
        assert b.p_activity == pytest.approx(8.2)
        assert b.activity_nM == pytest.approx(10 ** (9 - 8.2))

    def test_dedupe_keeps_strongest(self, monkeypatch):
        a = TargetBinderRetrievalAgent()
        payload = {"activities": [
            {"canonical_smiles": "CCO", "molecule_chembl_id": "CHEMBL1",
             "standard_value": "100", "standard_units": "nM", "standard_type": "IC50",
             "assay_chembl_id": "A", "pchembl_value": "7.0"},
            {"canonical_smiles": "CCO", "molecule_chembl_id": "CHEMBL1",
             "standard_value": "1", "standard_units": "nM", "standard_type": "IC50",
             "assay_chembl_id": "B", "pchembl_value": "9.0"},
            {"canonical_smiles": "CCN", "molecule_chembl_id": "CHEMBL3",
             "standard_value": "5", "standard_units": "nM", "standard_type": "IC50",
             "assay_chembl_id": "C", "pchembl_value": "8.3"},
        ]}
        monkeypatch.setattr("protacxtend.agents.binder_agent._cached_request", lambda *a_, **k: payload)
        monkeypatch.setattr(a, "_resolve_chembl_target", lambda *a_, **k: "CHEMBL_TGT1")
        binders, ok = a._search_chembl("BRD4", "O60885")
        assert ok and len(binders) == 2, "dedupe by SMILES"
        by_smiles = {b.smiles: b for b in binders}
        assert by_smiles["CCO"].p_activity == pytest.approx(9.0), "keeps strongest"


@pytest.mark.network
class TestLiveSources:
    def test_chembl_live_brd4(self):
        a = TargetBinderRetrievalAgent()
        binders, ok = a._search_chembl("BRD4", "O60885")
        assert ok, "live ChEMBL should respond"
        assert len(binders) >= 5
        assert all(b.activity_nM is None or b.activity_nM > 0 for b in binders)
        assert all(b.metadata.get("source_db") == "ChEMBL" for b in binders)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
