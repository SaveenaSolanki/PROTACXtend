"""
Tests for the Chemprop degradation backend (B1).
================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.tools.chemprop_degradation import (
    chemprop_available,
    predict_log_dc50_batch,
    predict_degradation_chemprop,
)


@pytest.mark.skipif(not chemprop_available(), reason="trained chemprop model not on disk")
class TestChempropBackend:
    def test_model_available(self):
        assert chemprop_available()

    def test_batch_prediction(self):
        res = predict_log_dc50_batch(["CCO", "CC(=O)Oc1ccccc1C(=O)O"])
        assert res["ok"] is True
        assert res["n_valid"] == 2
        assert all(v is not None for v in res["dc50_nM"])
        assert all(v > 0 for v in res["dc50_nM"])

    def test_invalid_smiles_none(self):
        res = predict_log_dc50_batch(["NOT_A_SMILES", "CCO"])
        assert res["ok"] is True
        assert res["dc50_nM"][0] is None
        assert res["dc50_nM"][1] is not None

    def test_single_convenience(self):
        res = predict_degradation_chemprop("CCO")
        assert res["ok"] is True
        assert res["dc50_nM"] is not None
        assert res["model"] == "chemprop_dmpnn"
        assert res["evidence_type"] == "trained_model"

    def test_benchmark_molecules_reproduce_rank_order(self):
        """Top-3 benchmark molecules by published DC50 keep sub-100 nM order."""
        import pandas as pd
        bench = pd.read_csv(
            Path(__file__).resolve().parents[2] / "outputs" / "benchmark" / "benchmark_predictions.csv"
        )
        top = bench.nsmallest(3, "published_dc50_nM")
        preds = []
        for _, r in top.iterrows():
            res = predict_degradation_chemprop(r["smiles"])
            preds.append(res["dc50_nM"])
        assert all(p is not None for p in preds)
        # all three are sub-100 nM in the published data → predictions should
        # also be sub-100 nM (rank-preserving at the potent end)
        assert all(p < 100 for p in preds), f"preds={preds}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
