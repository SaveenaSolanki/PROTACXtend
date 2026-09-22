"""BRD/BET intelligence tests — determinism + honesty gates."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from protacxtend.modules import brd_bet_intelligence as bbi


def test_evidence_table_loaded_and_provenanced():
    ev = bbi.load_evidence()
    assert len(ev) > 100
    assert set(ev["evidence_level"].unique()) <= {"measured", "inferred", "proxy"}
    assert {"BRD2", "BRD3", "BRD4", "BRDT"} <= set(ev["target_gene"].unique())
    prov = bbi.provenance()
    assert prov.get("n_rows") == len(ev)
    # every measured row carries a source; domain ordering flagged explicitly
    assert (ev["source_file"].astype(str).str.len() > 0).all()
    assert "inferred_pair_order" in set(ev["domain_assignment"])


def test_bd1_bd2_pairs_are_measured_values():
    pairs = bbi.load_pairs()
    assert len(pairs) >= 20
    assert (pairs["BD1"] > 0).all() and (pairs["BD2"] > 0).all()


def test_domain_class_semantics():
    # fold = BD1/BD2; >1 means BD2 is more potent
    assert bbi.classify_domain_selectivity(175.0) == "BD2-selective"
    assert bbi.classify_domain_selectivity(0.1) == "BD1-selective"
    assert bbi.classify_domain_selectivity(1.0) == "pan-BD1/BD2"
    assert bbi.classify_domain_selectivity(None) is None


def test_measured_ligand_gets_measured_evidence():
    s = bbi.score_brd_bet("BRD4", warhead_name="ABBV-744")
    assert s["evidence_level"] == "measured"
    assert s["status"] == "MEASURED"
    assert s["domain_selectivity"]["domain_class"] == "BD2-selective"
    assert s["score"] is not None


def test_unknown_ligand_is_proxy_not_measurement():
    s = bbi.score_brd_bet("BRD4", warhead_name="NOT_A_REAL_LIGAND_XYZ")
    assert s["evidence_level"] == "proxy"
    assert s["status"] == "PRIOR_ONLY"
    assert any("PROXY" in lim for lim in s["limitations"])
    # population-level components must not masquerade as query-specific
    if s.get("domain_selectivity"):
        assert s["domain_selectivity"]["source"] == "target_population"
    if s.get("bet_family"):
        assert s["bet_family"]["source"] == "target_population"


def test_non_bet_target_returns_not_bet():
    s = bbi.score_brd_bet("EGFR", warhead_name="gefitinib")
    assert s["status"] == "NOT_BET"
    assert s["score"] is None


def test_ligand_profile_reports_sources():
    prof = bbi.ligand_selectivity_profile(name="JQ1", target="BRD4")
    assert prof["status"] == "FOUND"
    assert prof["evidence_level"] == "measured"
    assert prof["sources"]["dois"]
    assert prof["bd1_bd2_pairs"]


def test_determinism():
    a = bbi.score_brd_bet("BRD2", warhead_name="HJB97")
    b = bbi.score_brd_bet("BRD2", warhead_name="HJB97")
    assert a == b


def test_landscape_coverage():
    land = bbi.domain_landscape()
    assert land["available"] is True
    assert land["n_ligands"] > 50
    assert "inferred_pair_order" in land["domain_assignment_counts"]
