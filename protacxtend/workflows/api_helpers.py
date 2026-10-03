"""Helpers for workflow API (lightweight; no heavy imports at module load)."""

from __future__ import annotations

import glob, json, os
from typing import Any, Optional

from protacxtend.evidence.graph import EvidenceGraph, make_claim


def compare_molecules(smiles_list: list[str], *, graph: Optional[EvidenceGraph] = None) -> list[dict[str, Any]]:
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors

    rows = []
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        rows.append({
            "smiles": smi,
            "valid": mol is not None,
            "MW": round(Descriptors.MolWt(mol), 1) if mol else None,
            "TPSA": round(rdMolDescriptors.CalcTPSA(mol), 1) if mol else None,
            "logP": round(Crippen.MolLogP(mol), 2) if mol else None,
            "rot_bonds": rdMolDescriptors.CalcNumRotatableBonds(mol) if mol else None,
            "verdict": "descriptor comparison only (computed); activity requires measured data",
        })
    if graph is not None:
        graph.add(make_claim(command="compare", dimension="exposure", kind="computed",
                             statement="descriptor comparison across molecules",
                             tool="rdkit.descriptors", params={"n": len(rows)}))
    return rows


def load_latest_graphs(limit: int = 200) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for p in sorted(glob.glob("outputs/workflows/**/*_evidence.json", recursive=True))[-10:]:
        try:
            with open(p) as f:
                data = json.load(f)
            claims.extend(data.get("claims", []))
        except Exception:  # noqa: BLE001
            continue
    return claims[:limit]