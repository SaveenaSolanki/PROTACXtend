"""Module 6 tests — deterministic; no invented values.

Covers the specification's challenge tests 1-7 plus integrity rules:
no structural/lysine claim without evidence; recruiters only counted from
DOI-cited rows; expression-only never yields SUPPORTED; unknown POI fails
gracefully; determinism.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from protacxtend.modules.e3_opportunity import context, e3_catalog, recruiters
from protacxtend.modules.e3_opportunity import dataset as ds
from protacxtend.modules.e3_opportunity import rank as rank_mod
from protacxtend.modules.e3_opportunity.predict import rank_e3_ligases


class TestCatalogAndRecruiters:
    def test_catalog_integrity(self):
        cat = e3_catalog.load_catalog()
        assert len(cat) >= 25
        assert cat["e3_gene"].is_unique
        assert set(cat["e3_family"])

    def test_db_labels_map_to_catalog(self):
        # every E3 label that appears in the degradation DB maps to catalog
        pairs = ds.load_benchmark_pairs()
        mapped = set()
        for lab in pairs["e3_label"].unique():
            gs = e3_catalog.alias_to_genes(lab)
            if gs:
                mapped.update(gs)
        assert mapped  # at least CRBN/VHL etc.
        assert {"CRBN", "VHL"} <= mapped

    def test_demo_recruiters_not_evidence(self):
        rec = recruiters.recruiters()
        demo = rec[rec["demo_only"]]
        assert len(demo) >= 0
        info = recruiters.recruiter_info("CRBN")
        assert info["available"] is True       # cited pomalidomide etc.
        assert info["n_cited_ligands"] >= 5
        assert info["n_demo_ligands"] == 0

    def test_absent_recruiter_explicitly_reported(self):
        # challenge 6: no library recruiters for HUWE1 -> None + limitation
        info = recruiters.recruiter_info("HUWE1")
        assert info["available"] is None
        assert info["n_cited_ligands"] == 0


class TestEvidenceRules:
    def test_expression_alone_never_supported(self):
        # unit rule: low/no-handle, expression-only -> not SUPPORTED/PROMISING
        v = rank_mod._verdict(raw=0.9, conf=0.9, coverage=0.5,
                              rec_avail=None, has_precedent=False,
                              low_expr=False, axes={}, family_precedent=0)
        assert v in ("EXPLORATORY", "INSUFFICIENT EVIDENCE")
        assert v != "SUPPORTED"

    def test_low_expression_caps_verdict(self):
        # challenge 3
        v = rank_mod._verdict(raw=0.9, conf=0.9, coverage=0.8,
                              rec_avail=True, has_precedent=True,
                              low_expr=True, axes={}, family_precedent=0)
        assert v == "EXPLORATORY"

    def test_supported_requires_direct_precedent(self):
        v = rank_mod._verdict(raw=0.7, conf=0.7, coverage=0.7,
                              rec_avail=True, has_precedent=False,
                              low_expr=False, axes={}, family_precedent=0)
        assert v == "PROMISING"
        v2 = rank_mod._verdict(raw=0.7, conf=0.7, coverage=0.7,
                               rec_avail=True, has_precedent=True,
                               low_expr=False, axes={}, family_precedent=0)
        assert v2 == "SUPPORTED"

    def test_structure_unknown_when_unsupported(self):
        # challenge 5: no mechanistic claim without structural evidence
        from protacxtend.modules.e3_opportunity.structure import structural_axis
        st = structural_axis("BRD4", "PRKN", None)
        assert st["ternary_feasibility"] is None
        assert not st["e3_complex_pdb_ids"]
        assert any("ternary" in x for x in st["limitations"])

    def test_lysine_unknown_without_structure(self):
        from protacxtend.modules.e3_opportunity import lysines
        res = lysines.surface_lysines("no/such/file.pdb")
        assert res["status"] == "UNKNOWN"
        assert res["lysine_opportunity"] is None

    def test_missing_context_is_uncertainty_not_fabrication(self):
        # challenge 4
        cs = context.context_scores("BRD4", None, "not-a-tissue-xyz", "CRBN")
        assert cs["score"] is None
        assert cs["confidence"] == 0.0
        assert "flags" in cs and len(cs["flags"]) > 0


class TestRanking:
    def test_known_pairs_supported_in_context(self):
        out = rank_e3_ligases("BRD4", cell_line="K562")
        cands = {c["e3_gene"]: c for c in out["candidates"]}
        # BRD4-VHL/CRBN have direct measured precedent -> SUPPORTED
        assert cands["VHL"]["verdict"] == "SUPPORTED"
        assert cands["CRBN"]["verdict"] == "SUPPORTED"
        # supported candidates are ranked above expression-only novel E3s
        tiers = [c["verdict"] for c in out["candidates"]]
        assert tiers.index("SUPPORTED") < tiers.index("EXPLORATORY")

    def test_same_poi_different_cells_differ(self):
        # challenge 1: same POI, two cell lines -> expression axis can differ
        a = context.context_scores("AR", "VCaP", None, "CRBN")
        b = context.context_scores("AR", "K562", None, "CRBN")
        assert a["score"] is not None and b["score"] is not None
        assert a["e3_expression_percentile"] != b["e3_expression_percentile"]

    def test_vhl_and_crbn_both_returned_for_poi(self):
        # challenge 2: both E3s present with real precedent values
        out = rank_e3_ligases("BRD4", cell_line="K562")
        names = {c["e3_gene"] for c in out["candidates"]}
        assert {"VHL", "CRBN"} <= names

    def test_low_expression_not_supported_end_to_end(self):
        # no candidate with very low context expression can be SUPPORTED
        out = rank_e3_ligases("BRD4", cell_line="K562")
        for c in out["candidates"]:
            cx = c["cell_context_score"]
            if cx is not None and cx < 0.2:
                assert c["verdict"] != "SUPPORTED"

    def test_unknown_poi_fails_gracefully(self):
        # challenge 7
        out = rank_e3_ligases("NotARealGeneZZZ")
        assert out["poi_gene"] is None
        assert out["candidates"] == []
        assert out["status"] == "INSUFFICIENT EVIDENCE"

    def test_deterministic(self):
        a = rank_e3_ligases("BTK", cell_line="K562", top_k=5)
        b = rank_e3_ligases("BTK", cell_line="K562", top_k=5)
        assert a == b

    def test_ranks_are_1_to_top_k(self):
        out = rank_e3_ligases("BRD4", cell_line="K562", top_k=10)
        ranks = [c["rank"] for c in out["candidates"]]
        assert ranks == list(range(1, len(ranks) + 1))
        # structural feasibility is always explicit UNKNOWN (None)
        for c in out["candidates"]:
            assert c["structural_feasibility"] is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
