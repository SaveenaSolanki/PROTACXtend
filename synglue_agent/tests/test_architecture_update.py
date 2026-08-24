"""AGENT_ARCHITECTURE_UPDATE implementation tests (nodes 5/19/20 observability)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.tools.protac_toolbox import chem_identity  # noqa: E402


class TestChemIdentity:
    def test_full_inchikey_stable(self):
        a = chem_identity("CC(=O)Oc1ccccc1C(=O)O")
        b = chem_identity("CC(=O)Oc1ccccc1C(=O)O")
        assert a == b
        assert a is not None and len(a) >= 25

    def test_invalid_smiles_none(self):
        assert chem_identity("not_a_smiles!!") is None


class TestBinderCensus:
    def test_census_fields_present(self, monkeypatch):
        import synglue_agent.agents.binder_agent as ba
        from synglue_agent.agents.binder_agent import TargetBinderRetrievalAgent
        a = TargetBinderRetrievalAgent()
        payload = {"meta": {"total_count": 4120}, "activities": [
            {"canonical_smiles": "CCO", "molecule_chembl_id": "CHEMBL1",
             "pchembl_value": "7.0", "standard_units": "nM", "standard_type": "IC50",
             "assay_chembl_id": "A"}]}
        monkeypatch.setattr(ba, "_cached_request", lambda *a_, **k: payload)
        monkeypatch.setattr(a, "_resolve_chembl_target", lambda *a_, **k: "CHEMBL_TGT1")
        binders, ok = a._search_chembl("BRD4", "")
        census = a._last_census
        assert census and census["n_reported_total"] == 4120
        assert census["n_after_dedup"] == census["n_returned"] == 1


class TestEvolutionMemory:
    def test_generation_records_and_novelty_stop(self):
        from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox
        from synglue_agent.backend.schemas import CandidateRecord
        t = ProtacDesignToolbox()
        c1 = CandidateRecord(candidate_id="g1", full_protac_smiles="CC(=O)Oc1ccccc1C(=O)O")
        res = t.evolve_with_generations([c1], [], [], max_generations=3)
        assert len(res["records"]) >= 1
        assert res["stop_reason"] != ""

    def test_offspring_carry_lineage(self):
        from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox
        from synglue_agent.backend.schemas import CandidateRecord
        t = ProtacDesignToolbox()
        c1 = CandidateRecord(candidate_id="g1", full_protac_smiles="CC(=O)Oc1ccccc1C(=O)O")
        res = t.evolve_with_generations([c1], [], [], max_generations=2)
        for c in res["evolved"]:
            assert getattr(c, "operator_applied", None) is not None
            assert getattr(c, "parent_ids", None) is not None
