"""Integration tests for ProtacCandidate evaluation pipeline."""
import pytest
import sys
sys.path.insert(0, ".")

from protacxtend.schemas.protac_candidate import ProtacCandidate
from protacxtend.evaluator import evaluate_protac_candidate, evaluate_batch


class MockCandidate:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_evaluate_brd4_vhl():
    c = MockCandidate(
        candidate_id="BRD4-VHL-001",
        canonical_smiles="CC(=O)Oc1ccccc1C(=O)NCCOCCOCC(=O)N[C@@H](C(C)(C)C)C(=O)N1C[C@@H](C[C@H]1C(=O)N[C@H](c1ccc(cc1)c1scnc1C)C)O",
        e3_ligase="VHL",
        ternary_plausibility_score=0.72,
        predicted_dc50_nM=15.0,
        predicted_dmax_percent=85.0,
        hook_effect_EC50=1000.0,
        rdkit_valid=True,
    )
    result = evaluate_protac_candidate(c)
    assert result["structurally_valid"] is True
    assert result["ternary_score"] == 0.72
    assert result["scores"]["degradation"] > 0.8
    assert result["overall_score"] > 0.5
    assert result["developability"] in ("moderate", "good")

def test_evaluate_brd4_crbn():
    c = MockCandidate(
        candidate_id="BRD4-CRBN-001",
        canonical_smiles="c1cc2c(cc1)cc(n2Cc1ccccn1)C(=O)NCCOCCOCC(=O)N1C[C@@H](C[C@H]1C(=O)N[C@H](c1ccc(cc1)c1scnc1C)C)O",
        e3_ligase="CRBN",
        ternary_plausibility_score=0.68,
        predicted_dc50_nM=45.0,
        predicted_dmax_percent=78.0,
        rdkit_valid=True,
    )
    result = evaluate_protac_candidate(c)
    assert result["ternary_score"] == 0.68
    assert result["degradation"]["dmax_percent"] == 78.0
    assert "neosubstrate_flagged" in result["flags"]
    assert result["developability"] in ("moderate", "poor", "good")

def test_evaluate_with_hook_effect():
    c = MockCandidate(
        candidate_id="BRD4-VHL-002",
        e3_ligase="VHL",
        ternary_plausibility_score=0.8,
        predicted_dc50_nM=12.0,
        hook_effect_EC50=500.0,
        rdkit_valid=True,
    )
    result = evaluate_protac_candidate(c)
    assert result["hook_effect"]["EC50"] == 500.0
    assert result["overall_score"] > 0.5

def test_evaluate_batch():
    candidates = [MockCandidate(
        candidate_id=f"test-{i}",
        e3_ligase="VHL" if i % 2 == 0 else "CRBN",
        ternary_plausibility_score=0.5 + i * 0.05,
        predicted_dc50_nM=100 - i * 10,
        rdkit_valid=True,
    ) for i in range(5)]
    results = evaluate_batch(candidates)
    assert len(results) == 5
    assert results[0]["rank"] == 1
    assert results[0]["overall_score"] >= results[1]["overall_score"]
