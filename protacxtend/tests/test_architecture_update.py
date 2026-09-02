"""AGENT_ARCHITECTURE_UPDATE implementation tests (nodes 5/19/20 observability)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from protacxtend.tools.protac_toolbox import chem_identity  # noqa: E402


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
        import protacxtend.agents.binder_agent as ba
        from protacxtend.agents.binder_agent import TargetBinderRetrievalAgent
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
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
        from protacxtend.backend.schemas import CandidateRecord
        t = ProtacDesignToolbox()
        c1 = CandidateRecord(candidate_id="g1", full_protac_smiles="CC(=O)Oc1ccccc1C(=O)O")
        res = t.evolve_with_generations([c1], [], [], max_generations=3)
        assert len(res["records"]) >= 1
        assert res["stop_reason"] != ""

    def test_offspring_carry_lineage(self):
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
        from protacxtend.backend.schemas import CandidateRecord
        t = ProtacDesignToolbox()
        c1 = CandidateRecord(candidate_id="g1", full_protac_smiles="CC(=O)Oc1ccccc1C(=O)O")
        res = t.evolve_with_generations([c1], [], [], max_generations=2)
        for c in res["evolved"]:
            assert getattr(c, "operator_applied", None) is not None
            assert getattr(c, "parent_ids", None) is not None


class TestPlddtGate:
    def test_gate_flag_and_pass(self):
        from protacxtend.agents.ternary_stage import plddt_gate
        assert plddt_gate({"plddt_min": None})["reason"] == "plddt_unknown"
        assert plddt_gate({"plddt_min": 0.55})["mode"] == "flag"
        assert plddt_gate({"plddt_min": 0.85})["mode"] == "pass"


class TestCoverageCells:
    def test_record_and_summary(self, tmp_path):
        import protacxtend.tools.coverage_matrix as cm
        from protacxtend.backend.schemas import CoverageCell
        # run against a temp coverage file
        tmp = tmp_path / "coverage_cells.jsonl"
        old = cm.COVERAGE_FILE
        cm.COVERAGE_FILE = tmp
        try:
            c1 = CoverageCell(warhead_inchikey="A", e3="CRBN", linker_inchikey="L", n_evaluated=1)
            entries = [c1]
            with tmp.open("w") as fh:
                for c in entries:
                    fh.write(c.model_dump_json() + "\n")
            snap = cm.summarize_coverage()
            assert snap["distinct_cells_evaluated"] == 1
            assert snap["measured_cells"] == 0  # pass-rate NULL discipline
        finally:
            cm.COVERAGE_FILE = old

    def test_no_pass_rate_backfill(self):
        from protacxtend.backend.schemas import CoverageCell
        c = CoverageCell(warhead_inchikey="A", e3="CRBN", linker_inchikey="L",
                         best_proxy_score=0.9)
        assert c.best_pass_rate is None
        assert c.measured is False
