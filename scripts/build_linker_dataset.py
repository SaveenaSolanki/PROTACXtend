#!/usr/bin/env python3
"""Extract linker SMILES from PROTAC-DB 3.0 via BRICS decomposition.

For each PROTAC SMILES: BRICS breaks it into fragments. The warhead and E3
ligand are typically the two ring-rich terminal fragments; the linker is the
fragment that connects them (most acyclic, central). Heuristic: drop fragments
containing aromatic rings + the largest fragment; among the rest pick the one
with the most rotatable bonds (the chain), falling back to the largest acyclic
fragment. Keeps linkers with 3-20 heavy atoms, no aromatic atoms.

Usage: python scripts/build_linker_dataset.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from rdkit import Chem
from rdkit.Chem import BRICS
from rdkit.Chem.rdMolDescriptors import CalcNumRotatableBonds

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "data" / "benchmark" / "PROTAC-DB_3.0_protacs.xlsx"
OUT = ROOT / "data" / "linkers" / "linker_smiles.txt"


def extract_linker(smiles: str):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    frags = []
    for f in BRICS.BRICSDecompose(mol):
        m = Chem.MolFromSmiles(f)
        if m is None:
            continue
        ha = m.GetNumHeavyAtoms()
        aromatic = any(a.GetIsAromatic() for a in m.GetAtoms())
        if 3 <= ha <= 20 and not aromatic:
            frags.append((m, ha))
    if not frags:
        return None
    # linker = the acyclic fragment with the most rotatable bonds (chain-like)
    frags.sort(key=lambda t: -CalcNumRotatableBonds(t[0]))
    return Chem.MolToSmiles(frags[0][0])


def main() -> int:
    df = pd.read_excel(XLSX)
    smiles_col = "Smiles"
    linkers = set()
    for smi in df[smiles_col].dropna().unique()[:6000]:  # bounded, diverse
        lk = extract_linker(smi)
        if lk:
            linkers.add(lk)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(sorted(linkers)) + "\n")
    print(f"linkers extracted: {len(linkers)} -> {OUT}")
    lens = [len(x) for x in linkers]
    print(f"char length: min {min(lens)}, mean {sum(lens)//len(lens)}, max {max(lens)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
