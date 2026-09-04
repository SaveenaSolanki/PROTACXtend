"""
Applicability-domain detection for degradation predictions (capability 5).
==========================================================================

A prediction is only as good as the model's familiarity with the molecule.
This module flags candidates whose chemistry is far from the training set
(ProtacPilot's Chemprop training data, 1,698 PROTAC-DB molecules) using
Tanimoto similarity on Morgan fingerprints.

Design:
  - Training fingerprints are computed once and cached to disk (npy).
  - For a candidate SMILES: nearest-neighbor Tanimoto to training set.
  - in-domain if nn_tanimoto >= AD_THRESHOLD (default 0.30).
  - Returns a structured ApplicabilityDomain verdict: in/out/borderline +
    nearest-neighbor similarity + closest training molecule index.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("protacpilot.appdomain")

# Paths
ROOT = Path(__file__).resolve().parents[2]
TRAIN_CSV = ROOT / "data" / "benchmark" / "chemprop_train.csv"
CACHE_DIR = ROOT / "data" / "benchmark" / "_ad_cache"
FPS_PATH = CACHE_DIR / "train_fps.npy"
SMILES_PATH = CACHE_DIR / "train_smiles.txt"

AD_THRESHOLD = 0.30          # below this → out-of-domain
AD_BORDERLINE = 0.40         # below this → borderline
RADIUS = 2
NBITS = 2048


def _morgan_fp(smiles: str) -> Optional[np.ndarray]:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=RADIUS, nBits=NBITS)
    return np.array(fp, dtype=np.uint8)


def _load_or_build_train_fps() -> tuple[np.ndarray, List[str]]:
    """Load cached training fingerprints or compute them."""
    if FPS_PATH.exists() and SMILES_PATH.exists():
        fps = np.load(FPS_PATH)
        smiles = SMILES_PATH.read_text().splitlines()
        if len(fps) == len(smiles):
            return fps, smiles

    if not TRAIN_CSV.exists():
        logger.warning("No training set at %s — AD detection unavailable.", TRAIN_CSV)
        return np.zeros((0, NBITS), dtype=np.uint8), []

    import pandas as pd
    df = pd.read_csv(TRAIN_CSV)
    smiles = df["smiles"].dropna().tolist()
    fps = []
    kept_smiles = []
    for s in smiles:
        fp = _morgan_fp(s)
        if fp is not None:
            fps.append(fp)
            kept_smiles.append(s)
    fps = np.array(fps, dtype=np.uint8)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(FPS_PATH, fps)
    SMILES_PATH.write_text("\n".join(kept_smiles))
    logger.info("Built AD training fingerprints: %d molecules", len(fps))
    return fps, kept_smiles


def _tanimoto(a: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Tanimoto between one binary vector and a matrix.

    Explicit logical ops — numpy matmul on bool dtypes does NOT behave like
    an AND-count (returns garbage for large sparse vectors).
    """
    a_b = a.astype(bool)
    B_b = B.astype(bool)
    inter = np.count_nonzero(np.logical_and(B_b, a_b), axis=1).astype(float)
    union = np.count_nonzero(B_b, axis=1) + np.count_nonzero(a_b) - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(union > 0, inter / np.maximum(union, 1), 0.0)
    return t


def assess_applicability_domain(
    smiles: str,
    threshold: float = AD_THRESHOLD,
    borderline: float = AD_BORDERLINE,
) -> Dict[str, Any]:
    """Assess whether a candidate is inside the model's applicability domain.

    Returns:
      {
        'in_domain': bool,
        'status': 'in_domain' | 'borderline' | 'out_of_domain' | 'unavailable',
        'nn_tanimoto': float,          # nearest-neighbor similarity
        'nn_train_index': int | None,
        'nn_train_smiles': str | None,
        'n_train_molecules': int,
      }
    """
    fps, train_smiles = _load_or_build_train_fps()
    if len(fps) == 0:
        return {
            "in_domain": None, "status": "unavailable",
            "nn_tanimoto": None, "nn_train_index": None,
            "nn_train_smiles": None, "n_train_molecules": 0,
        }

    fp = _morgan_fp(smiles)
    if fp is None:
        return {
            "in_domain": None, "status": "unavailable",
            "nn_tanimoto": None, "nn_train_index": None,
            "nn_train_smiles": None, "n_train_molecules": len(fps),
        }

    t = _tanimoto(fp, fps)
    best = int(np.argmax(t))
    nn_t = float(t[best])

    if nn_t >= borderline:
        status = "in_domain"
    elif nn_t >= threshold:
        status = "borderline"
    else:
        status = "out_of_domain"

    return {
        "in_domain": status == "in_domain",
        "status": status,
        "nn_tanimoto": round(nn_t, 4),
        "nn_train_index": best,
        "nn_train_smiles": train_smiles[best] if train_smiles else None,
        "n_train_molecules": len(fps),
    }


def assess_batch_applicability_domain(
    smiles_list: List[str],
) -> List[Dict[str, Any]]:
    return [assess_applicability_domain(s) for s in smiles_list]


if __name__ == "__main__":
    # Self-test: known in-domain (PROTAC-DB) vs a random drug
    test = {
        "protacdb_like": "COC1=CC(C2=CN(C)C(=O)C3=CN=CC=C23)=CC(OC)=C1CN1CCN(CCOCCOCCOC2=CC(C3=C(C)N=CS3)=CC=C2CNC(=O)[C@@H]2C[C@@H](O)CN2C(=O)[C@@H](NC(=O)C2(F)CC2)C(C)(C)C)CC1",
        "aspirin": "CC(=O)Oc1ccccc1C(=O)O",
    }
    for name, smi in test.items():
        res = assess_applicability_domain(smi)
        print(f"{name}: {res['status']} (nn_tanimoto={res['nn_tanimoto']})")
