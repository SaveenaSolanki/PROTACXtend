"""Module 4 tests — degradation dataset, features, training & predict API."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from synglue_agent.modules.degradation_ml import (
    DegradationModelError,
    dataset_report,
    evaluate_splits,
    featurize_molecule,
    load_curated,
    murcko_group,
    predict_degradation,
    train_pdc50,
)


class TestDataset:
    def test_curated_real_labels_present(self):
        df = load_curated()
        rep = dataset_report(df)
        assert rep["records"] >= 50
        assert rep["pdc50_range"][0] > 0
        assert rep["labels_measured"] is True
        assert rep["degradation_probability_labels"] == 0  # never fabricated

    def test_splits_no_leakage_definitions(self):
        from synglue_agent.modules.degradation_ml.dataset import curate_split_sets
        df = load_curated()
        splits = curate_split_sets(df)
        assert {"random", "scaffold", "unseen_target", "unseen_e3"} <= set(splits)
        assert len(splits["scaffold"]) == len(df)


class TestFeatures:
    def test_featurize_deterministic_and_valid(self):
        v1, ok1 = featurize_molecule("CC(=O)Oc1ccccc1C(=O)O")
        v2, ok2 = featurize_molecule("CC(=O)Oc1ccccc1C(=O)O")
        assert ok1 is True and ok2 is True
        assert np.array_equal(v1, v2)
        assert v1.shape[0] == 8 + 1024
        bad, ok = featurize_molecule("not-a-real-molecule!!")
        assert ok is False
        assert float(np.abs(bad).sum()) == 0.0

    def test_scaffold_grouping(self):
        a = murcko_group("CC(=O)Oc1ccccc1C(=O)O")
        assert isinstance(a, str) and a != "na"


class TestModelPipeline:
    def test_evaluate_splits_on_curated_data_returns_metrics(self):
        df = load_curated()
        out = evaluate_splits(df, models=["mean", "ridge"])
        assert "splits" in out
        for _split_name, per in out["splits"].items():
            assert "mean" in per or "unavailable" in per

    def test_train_and_predict_roundtrip(self, tmp_path):
        df = load_curated()
        out_path = tmp_path / "m.joblib"
        info = train_pdc50(df, out_path=out_path, model_name="ridge")
        assert info["model_path"].endswith("m.joblib")
        row = df.iloc[0]
        r = predict_degradation(row["smiles"], target=row["target"], e3=row["e3"],
                                model_path=out_path)
        assert r.pdc50 is not None and r.dc50_nM > 0
        assert r.degradation_probability is None          # no fabricated prob
        assert r.tasks["degradation_probability"].startswith("disabled")
        assert r.pdc50_lower_nM <= r.dc50_nM <= r.pdc50_upper_nM
        assert r.ood_score is not None

    def test_predict_without_artifact_fails_explicitly(self, tmp_path):
        with pytest.raises(DegradationModelError, match="no trained degradation model"):
            predict_degradation("CC(=O)Oc1ccccc1C(=O)O",
                                model_path=str(tmp_path / "missing.joblib"))

    def test_schema_version(self):
        df = load_curated()
        art = Path(__file__).resolve().parents[3] / "modules" / "degradation_ml" / "models" / "pdc50_model.joblib"
        assert art.exists()
        r = predict_degradation(df.iloc[0]["smiles"], model_path=art)
        assert r.model.startswith("protac_degradation_ml-v")

    def test_predict_forwards_target_and_e3_context(self, monkeypatch, tmp_path):
        # Regression: predict_degradation accepts target/e3 — they must reach
        # feature_matrix so a seen entity is coded with its training code
        # (absent/unknown -> OOV), not silently dropped.
        from synglue_agent.modules.degradation_ml import predict as predict_mod
        df = load_curated()
        out_path = tmp_path / "m.joblib"
        train_pdc50(df, out_path=out_path, model_name="ridge")
        captured: dict = {}
        real = predict_mod.feature_matrix

        def spy(smiles_list, targets=None, e3s=None, **kw):
            captured["targets"] = targets
            captured["e3s"] = e3s
            return real(smiles_list, targets=targets, e3s=e3s, **kw)

        monkeypatch.setattr(predict_mod, "feature_matrix", spy)
        row = df.iloc[0]
        predict_degradation(row["smiles"], target=row["target"], e3=row["e3"],
                            model_path=out_path)
        assert captured["targets"] == [row["target"]]
        assert captured["e3s"] == [row["e3"]]
        # absent context stays None -> feature_matrix maps to the OOV sentinel
        predict_degradation(row["smiles"], model_path=out_path)
        assert captured["targets"] is None and captured["e3s"] is None
