"""Tests for Phase 10 DC50/Dmax model loading infrastructure."""

from __future__ import annotations

import os
import pickle
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from protacxtend.backend.schemas import CandidateRecord
from protacxtend.models.degradation_model import (
    STATUS_HEURISTIC_STUB,
    STATUS_MODEL_LOADED,
    STATUS_MODEL_MISSING,
    discover_degradation_models,
    load_dc50_model,
    load_dmax_model,
    predict_dc50_dmax,
)


class TinyRegressor:
    def __init__(self, offset: float = 0.0) -> None:
        self.offset = offset

    def predict(self, x):
        return [float(sum(x[0])) / len(x[0]) + self.offset]


@contextmanager
def pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class DegradationModelTests(unittest.TestCase):
    def _candidate(self) -> CandidateRecord:
        return CandidateRecord(
            candidate_id="C1",
            full_protac_smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
            warhead_smiles="CC(=O)O[*:1]",
            linker_smiles="[*:1]CCO[*:2]",
            e3_ligand_smiles="[*:2]c1ccccc1",
            e3_ligase="CRBN",
        )

    def test_missing_model_gives_model_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with pushd(Path(directory)):
                discovered = discover_degradation_models("models/")
                self.assertEqual(discovered["status"], STATUS_MODEL_MISSING)

    def test_heuristic_predictor_is_labeled_heuristic_stub(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with pushd(Path(directory)):
                result = predict_dc50_dmax(self._candidate(), backend="heuristic_stub")
                self.assertEqual(result["status"], STATUS_HEURISTIC_STUB)
                self.assertFalse(result["real_output_generated"])

    def test_tiny_pickle_models_load_and_predict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / "models"
            model_dir.mkdir(parents=True, exist_ok=True)
            schema = ["MW", "TPSA", "LogP", "HBD", "HBA", "rotatable_bonds", "ring_count", "aromatic_ring_count", "heavy_atom_count", "fraction_Csp3"]
            dc50_bundle = {
                "model": TinyRegressor(offset=10.0),
                "metadata": {
                    "model_name": "tiny_dc50.pkl",
                    "version": "0.0-test",
                    "training_data": "unit_test_fixture",
                    "endpoint": "dc50_nM",
                    "feature_schema": schema,
                    "date": "2026-05-27",
                },
            }
            dmax_bundle = {
                "model": TinyRegressor(offset=40.0),
                "metadata": {
                    "model_name": "tiny_dmax.pkl",
                    "version": "0.0-test",
                    "training_data": "unit_test_fixture",
                    "endpoint": "dmax_percent",
                    "feature_schema": schema,
                    "date": "2026-05-27",
                },
            }
            with (model_dir / "tiny_dc50.pkl").open("wb") as handle:
                pickle.dump(dc50_bundle, handle)
            with (model_dir / "tiny_dmax.pkl").open("wb") as handle:
                pickle.dump(dmax_bundle, handle)

            with pushd(root):
                discovered = discover_degradation_models("models/")
                self.assertTrue(discovered["dc50_candidates"])
                self.assertTrue(discovered["dmax_candidates"])
                loaded_dc50 = load_dc50_model(discovered["dc50_candidates"][0])
                loaded_dmax = load_dmax_model(discovered["dmax_candidates"][0])
                self.assertTrue(loaded_dc50["success"], loaded_dc50.get("error"))
                self.assertTrue(loaded_dmax["success"], loaded_dmax.get("error"))
                result = predict_dc50_dmax(self._candidate(), backend="auto")
                self.assertEqual(result["status"], STATUS_MODEL_LOADED)
                self.assertTrue(result["real_output_generated"])
                self.assertIsNotNone(result["predicted_dc50_nM"])
                self.assertIsNotNone(result["predicted_dmax_percent"])


if __name__ == "__main__":
    unittest.main()
