"""
Unblocked-agent tests: binder normalization, novelty patents, ADMET-AI,
fragment linkers, genetic evolution.
=======================================================================
Live network tests are marked @pytest.mark.network (skip with -m "not network").
ADMET-AI tests skip when the isolated venv is not bootstrapped.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.agents.binder_agent import TargetBinderRetrievalAgent  # noqa: E402


# ── Novelty: patent cross-reference ──────────────────────────────────
class TestNoveltyPatents:
    def test_pubchem_patents_mocked(self, monkeypatch):
        from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox
        t = ProtacDesignToolbox()

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'{"IdentifierList": {"CID": [2244]}}'

        class FakeView:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                import json
                return json.dumps({"Record": {"Section": [{
                    "TOCHeading": "Patents",
                    "Information": [
                        {"StringValue": "US5972916"},
                        {"StringValue": "US6015577"},
                        {"StringValue": "US6926907"},
                    ],
                }]}}).encode()

        real = __import__("urllib.request", fromlist=["urlopen"]).urlopen
        calls = {"n": 0}

        def fake_urlopen(req, timeout=30):
            calls["n"] += 1
            url = str(req.full_url) if hasattr(req, "full_url") else str(req)
            if "pug/compound/" in url:
                return FakeResp()
            return FakeView()

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        n, ids = t._pubchem_patents("CC(=O)Oc1ccccc1C(=O)O")
        assert n == 3
        assert "US5972916" in ids
        assert calls["n"] == 2

    @pytest.mark.network
    def test_pubchem_patents_live_aspirin(self):
        from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox
        n, ids = ProtacDesignToolbox()._pubchem_patents("CC(=O)Oc1ccccc1C(=O)O")
        assert n >= 1, "aspirin has patents in PubChem"
        assert ids


# ── ADMET-AI ML layer ────────────────────────────────────────────────
class TestAdmetAi:
    def test_runner_script_exists(self):
        from synglue_agent.tools.admet_integration import ADMET_AI_READY, ADMET_AI_RUNNER
        assert ADMET_AI_RUNNER.exists()

    @pytest.mark.skipif(
        not (Path(__file__).resolve().parents[2] / ".venvs/admet/bin/python").exists(),
        reason="ADMET-AI venv not bootstrapped (scripts/bootstrap_assets.sh --admet)",
    )
    def test_predict_aspirin(self):
        from synglue_agent.tools.admet_integration import predict_admet_properties
        r = predict_admet_properties("CC(=O)Oc1ccccc1C(=O)O")
        assert r["prediction_source"] == "admet_ai+rules"
        assert r["admet_ai"] is not None
        assert "hERG" in r["admet_ai"]
        assert 0.0 <= r["admet_ai"]["AMES"] <= 1.0

    def test_rules_fallback_without_venv(self, monkeypatch):
        from synglue_agent.tools import admet_integration as ai
        monkeypatch.setattr(ai, "ADMET_AI_READY", False)
        r = ai.predict_admet_properties("CCCOCCC")
        assert r["prediction_source"] == "rules"
        assert r["admet_ai"] is None
        assert "druglikeness" in r


# ── Linker: fragment-combination generation ──────────────────────────
class TestFragmentLinkers:
    def test_generation_bounded_and_unique(self):
        from synglue_agent.tools.linker_generator import generate_fragment_combination_linkers
        links = generate_fragment_combination_linkers(max_linkers=40)
        assert 0 < len(links) <= 40
        smiles = [l.smiles for l in links]
        assert len(set(smiles)) == len(smiles), "unique linkers"
        from rdkit import Chem
        for l in links:
            mol = Chem.MolFromSmiles(l.smiles.replace("[*:1]", "[*]").replace("[*:2]", "[*]"))
            assert mol is not None, f"invalid: {l.smiles}"

    def test_scanner_library_contains_fragments(self):
        from synglue_agent.tools.linker_scanner import load_linker_library
        lib = load_linker_library()
        assert any(l.get("source") == "fragment_combination" for l in lib)


# ── Evolution: genetic operators ─────────────────────────────────────
class TestGeneticOperators:
    def test_mutation_valid_and_distinct(self):
        from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox
        import random
        t = ProtacDesignToolbox()
        out = t._smiles_mutate("CC(=O)Oc1ccccc1C(=O)O", random.Random(42))
        assert out is not None
        assert out != "CC(=O)Oc1ccccc1C(=O)O"
        from rdkit import Chem
        assert Chem.MolFromSmiles(out) is not None

    def test_evolve_produces_offspring(self):
        from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox
        from synglue_agent.backend.schemas import CandidateRecord
        t = ProtacDesignToolbox()
        p = CandidateRecord(candidate_id="p1", full_protac_smiles="CC(=O)Oc1ccccc1C(=O)O")
        ev = t.evolve_candidates([p], [], [], None, max_new=2)
        assert 0 < len(ev) <= 2
        for e in ev:
            assert e.candidate_id != "p1"
            assert e.full_protac_smiles != p.full_protac_smiles


# ── Binder: live sources ─────────────────────────────────────────────
@pytest.mark.network
class TestBinderLiveChEMBL:
    def test_chembl_live_brd4(self):
        a = TargetBinderRetrievalAgent()
        binders, ok = a._search_chembl("BRD4", "O60885")
        assert ok
        assert len(binders) >= 5
        assert all(b.metadata.get("source_db") == "ChEMBL" for b in binders)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
