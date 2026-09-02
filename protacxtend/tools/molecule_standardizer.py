"""Molecule standardization helpers."""

from __future__ import annotations

from typing import Any, Dict

from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def standardize_smiles(smiles: str) -> str:
    return canonicalize_smiles(remove_salts(smiles))


def remove_salts(smiles: str) -> str:
    if "." not in smiles:
        return smiles
    parts = sorted(smiles.split("."), key=len, reverse=True)
    return parts[0]


def canonicalize_smiles(smiles: str) -> str:
    return _TOOLBOX.canonicalize_smiles(smiles)


def neutralize_molecule(smiles: str) -> str:
    return smiles.replace("[O-]", "O").replace("[N+]", "N")


def preserve_stereochemistry(smiles: str) -> str:
    return smiles


def compute_basic_properties(smiles: str) -> Dict[str, Any]:
    return _TOOLBOX.compute_basic_properties(smiles)
