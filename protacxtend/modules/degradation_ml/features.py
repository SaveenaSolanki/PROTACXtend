"""RDKit features + entity encoding + scaffold groups (Module 4).

Molecular features are deterministic RDKit descriptors + Morgan (ECFP4)
fingerprints of the full PROTAC. Entity (target/E3) codes are fit on the
TRAINING fold only to avoid leakage. Scaffold groups (Murcko) back the
unseen-scaffold split.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Crippen, Descriptors, Lipinski, rdMolDescriptors
    from rdkit.Chem.Scaffolds import MurckoScaffold
    _RDKIT = True
except Exception:  # pragma: no cover - rdkit required for training
    _RDKIT = False

DESCRIPTOR_NAMES = ["mol_wt", "clogp", "tpsa", "rotb", "hbd", "hba", "aromatic_rings",
                    "fraction_csp3"]
MORGAN_RADIUS = 2
MORGAN_BITS = 1024
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "pdc50_model.joblib"


def _descriptors(mol) -> np.ndarray:
    return np.array([
        float(Descriptors.MolWt(mol)), float(Crippen.MolLogP(mol)),
        float(rdMolDescriptors.CalcTPSA(mol)), float(Lipinski.NumRotatableBonds(mol)),
        float(Lipinski.NumHDonors(mol)), float(Lipinski.NumHAcceptors(mol)),
        float(rdMolDescriptors.CalcNumAromaticRings(mol)),
        float(rdMolDescriptors.CalcFractionCSP3(mol)),
    ], dtype=float)


def featurize_molecule(smiles: str) -> tuple[np.ndarray, bool]:
    """Concatenated [8 descriptors | Morgan1024] vector; ok=False if invalid."""
    if not _RDKIT or not smiles:
        zero = np.zeros(8 + MORGAN_BITS, dtype=float)
        return zero, False
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        zero = np.zeros(8 + MORGAN_BITS, dtype=float)
        return zero, False
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, MORGAN_RADIUS, MORGAN_BITS)
    vec = np.concatenate([_descriptors(mol),
                          np.frombuffer(bytes(fp.ToBitString().encode()), dtype="u1") - 48])
    return vec.astype(float), True


def murcko_group(smiles: str) -> str:
    if not _RDKIT:
        return "na"
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return "na"
    try:
        scaf = MurckoScaffold.MurckoScaffoldSmiles(mol=mol)
        return scaf if scaf else "na"
    except Exception:
        return "na"


class EntityEncoder:
    """Ordinal encoder for categorical entities, FIT ON TRAIN ONLY."""

    def __init__(self) -> None:
        self.vocab: dict[str, int] = {}
        self.oov = 0

    def fit(self, values: list[str]) -> EntityEncoder:
        seen = []
        for v in values:
            key = (v or "unknown").strip().lower()
            if key and key not in seen:
                seen.append(key)
        self.vocab = {k: i for i, k in enumerate(seen)}
        self.oov = len(self.vocab)
        return self

    def transform(self, values: list[str]) -> np.ndarray:
        return np.array([self.vocab.get((v or "unknown").strip().lower(), self.oov)
                         for v in values], dtype=float)


def feature_matrix(smiles_list: list[str], targets: list[str] | None = None,
                   e3s: list[str] | None = None,
                   enc_target: EntityEncoder | None = None,
                   enc_e3: EntityEncoder | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Build [molecular | target_code | e3_code] rows.

    Returns (X, ok_mask). Encoders, when given, are applied; otherwise the two
    trailing categorical slots are zero (kept out when encoders are None).
    """
    n = len(smiles_list)
    if targets is None and enc_target is not None:
        targets = [""] * n
    if e3s is None and enc_e3 is not None:
        e3s = [""] * n
    if targets is not None and len(targets) != n:
        raise ValueError("targets must be parallel to smiles_list")
    if e3s is not None and len(e3s) != n:
        raise ValueError("e3s must be parallel to smiles_list")
    rows = []
    ok = []
    for i, s in enumerate(smiles_list):
        vec, good = featurize_molecule(s)
        parts = [vec]
        if enc_target is not None:
            parts.append(np.array([enc_target.transform([str(targets[i])])[0]]))
        if enc_e3 is not None:
            parts.append(np.array([enc_e3.transform([str(e3s[i])])[0]]))
        rows.append(np.concatenate(parts))
        ok.append(good)
    return np.vstack(rows), np.array(ok, dtype=bool)
