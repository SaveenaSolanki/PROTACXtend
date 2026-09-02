"""
TACK-model integration — degradation prediction from the TACK benchmark models.
===============================================================================
TACK (TArgeting Chimeras Knowledge, Ribes/Dunlop/Mercado 2026) merges TPDdb +
PROTAC-DB + PROTACpedia into 3,514 PROTACs / 6,561 degradation endpoints.

We trained TACK-STYLE models on the public TACK dataset with our stack
(scripts/build_tack_model.py, scaffold split):
    tack_dc50_model  HistGradientBoostingRegressor on log10(DC50 nM)  rho=0.80
    tack_dmax_model  HistGradientBoostingRegressor on Dmax (%)        rho=0.74
    tack_bin_model   HistGradientBoostingClassifier (DC50<100 nM)     AUC 0.92

The official TACK pretrained weights are on Hugging Face but GATED (auth
required); the dataset is public, so the reproducible path is training our own
TACK-style models — same feature philosophy (Morgan FP + descriptors + E3 /
cell-line / POI one-hot).

Inference: predict_from_smiles(smiles, e3, cell, poi) -> {dc50_nM, dmax_pct,
active, provenance}. Falls back gracefully to None when the models are absent.
"""
from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

# Thread-bounding: sklearn HistGradientBoosting opens libgomp parallel regions
# per predict call; on a shared/loaded machine the OpenMP barrier spin makes a
# single-row predict take ~10-30s (measured: ~11s/model under load 40+). These
# env defaults + the threadpool_limits context in TackModel.predict keep the
# TACK path fast and load-immune. Set early, before joblib/numpy/sklearn load.
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import joblib
import numpy as np

from protacxtend.tools.linker_scoring import _clean

logger = logging.getLogger("protacpilot.tack")

ROOT = Path(__file__).resolve().parents[2]
TACK_DIR = ROOT / "data" / "tack"


class TackModel:
    def __init__(self, model_dir: Path = TACK_DIR):
        self._dc50 = self._dmax = self._bin = None
        self._meta: Dict[str, Any] = {}
        self.compatibility_warnings: list[str] = []
        try:
            self._dc50 = self._load_joblib_with_warning_capture(model_dir / "tack_dc50_model.joblib")
            self._dmax = self._load_joblib_with_warning_capture(model_dir / "tack_dmax_model.joblib")
            self._bin = self._load_joblib_with_warning_capture(model_dir / "tack_bin_model.joblib")
            self._meta = self._load_joblib_with_warning_capture(model_dir / "tack_meta.joblib")
        except Exception as exc:  # noqa: BLE001
            logger.warning("TACK models unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._dc50 is not None and self._meta.get("metrics")

    def _load_joblib_with_warning_capture(self, path: Path) -> Any:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            payload = joblib.load(path)
        for warning in caught:
            message = str(warning.message)
            if "Trying to unpickle estimator" in message or "InconsistentVersionWarning" in message:
                summary = f"{path.name} was trained with a different sklearn version than the current runtime."
                if summary not in self.compatibility_warnings:
                    self.compatibility_warnings.append(summary)
                    logger.warning("TACK model compatibility warning: %s", summary)
            else:
                warnings.warn(warning.message, warning.category, stacklevel=2)
        return payload

    def _features(self, smiles: str, e3: str = "", cell: str = "", poi: str = "") -> np.ndarray:
        from rdkit import Chem
        from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
        top_ligases = self._meta.get("top_ligases", [])
        top_cells = self._meta.get("top_cells", [])
        top_pois = self._meta.get("top_pois", [])
        mol = Chem.MolFromSmiles(_clean(smiles))
        fp = np.zeros(1024)
        descs = np.zeros(6)
        if mol is not None:
            fp = np.array(AllChem.GetMorganFingerprintAsBitVect(mol, 2, 1024), dtype=float)
            descs = np.array([Descriptors.MolWt(mol), rdMolDescriptors.CalcTPSA(mol),
                              rdMolDescriptors.CalcNumHBD(mol), rdMolDescriptors.CalcNumHBA(mol),
                              rdMolDescriptors.CalcNumRotatableBonds(mol), Descriptors.MolLogP(mol)])
        oh = np.zeros(len(top_ligases) + len(top_cells) + len(top_pois))
        if e3 in top_ligases:
            oh[top_ligases.index(e3)] = 1.0
        if cell in top_cells:
            oh[len(top_ligases) + top_cells.index(cell)] = 1.0
        if poi in top_pois:
            oh[len(top_ligases) + len(top_cells) + top_pois.index(poi)] = 1.0
        return np.concatenate([fp, descs, oh])

    def predict(self, smiles: str, e3: str = "", cell: str = "", poi: str = "") -> Optional[Dict[str, Any]]:
        if not self.available:
            return None
        x = self._features(smiles, e3, cell, poi).reshape(1, -1)
        # Bound OpenMP/BLAS threads: single-row HGB inference needs no
        # parallelism; default thread pools spin hard on shared boxes
        # (measurement: ~11s per model under load 40+ vs <1ms at 1 thread).
        from threadpoolctl import threadpool_limits

        with threadpool_limits(limits=1, user_api="openmp"):
            log_dc50 = float(self._dc50.predict(x)[0])
            dmax = float(self._dmax.predict(x)[0])
            bin_prob = float(self._bin.predict_proba(x)[0, 1])
        metrics = self._meta.get("metrics", {})
        compatibility_note = None
        if self.compatibility_warnings:
            compatibility_note = (
                "TACK model artifact loaded with sklearn version mismatch; "
                "treat this as an uncalibrated second-opinion signal until models are rebuilt in the runtime environment."
            )
        return {
            "dc50_nM": round(float(10 ** log_dc50), 2),
            "log_dc50": round(log_dc50, 3),
            "dmax_pct": round(float(np.clip(dmax, 0.0, 100.0)), 1),
            "active_prob": round(bin_prob, 3),
            "active": bool(bin_prob >= 0.5),
            "provenance": {
                "model": "tack-style-v1",
                "training_data": f"TACK dataset (n_dc50={metrics.get('n_dc50')}, "
                                 f"n_dmax={metrics.get('n_dmax')})",
                "val_metrics": metrics,
                "compatibility_warning": compatibility_note,
            },
        }


_TACK: Optional[TackModel] = None


def predict_tack_degradation(smiles: str, e3: str = "", cell: str = "",
                             poi: str = "") -> Optional[Dict[str, Any]]:
    global _TACK
    if _TACK is None:
        _TACK = TackModel()
    return _TACK.predict(smiles, e3, cell, poi)


def predict_tack_batch(entries: List[Dict[str, str]]) -> List[Optional[Dict[str, Any]]]:
    """entries: [{'smiles','e3','cell','poi'}, ...]"""
    global _TACK
    if _TACK is None:
        _TACK = TackModel()
    if not _TACK.available:
        return [None] * len(entries)
    return [_TACK.predict(e.get("smiles", ""), e.get("e3", ""), e.get("cell", ""), e.get("poi", ""))
            for e in entries]


if __name__ == "__main__":
    r = predict_tack_degradation("CC(=O)Oc1ccccc1C(=O)O", e3="CRBN", cell="HEK293T", poi="BRD4")
    print("TACK prediction:", r)
