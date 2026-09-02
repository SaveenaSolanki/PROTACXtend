"""Reaction SMARTS-inspired assembly functions.

The local implementation uses explicit dummy-atom joins. Production deployments
can replace each function with validated RDKit reaction SMARTS.
"""

from __future__ import annotations

from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def amide_coupling(left_smiles: str, linker_smiles: str, right_smiles: str):
    return _TOOLBOX.assemble_components(left_smiles, linker_smiles, right_smiles)


def ether_formation(left_smiles: str, linker_smiles: str, right_smiles: str):
    return _TOOLBOX.assemble_components(left_smiles, linker_smiles, right_smiles)


def alkylation(left_smiles: str, linker_smiles: str, right_smiles: str):
    return _TOOLBOX.assemble_components(left_smiles, linker_smiles, right_smiles)


def carbamate_formation(left_smiles: str, linker_smiles: str, right_smiles: str):
    return _TOOLBOX.assemble_components(left_smiles, linker_smiles, right_smiles)


def urea_formation(left_smiles: str, linker_smiles: str, right_smiles: str):
    return _TOOLBOX.assemble_components(left_smiles, linker_smiles, right_smiles)


def sulfonamide_formation(left_smiles: str, linker_smiles: str, right_smiles: str):
    return _TOOLBOX.assemble_components(left_smiles, linker_smiles, right_smiles)


def triazole_click_formation(left_smiles: str, linker_smiles: str, right_smiles: str):
    return _TOOLBOX.assemble_components(left_smiles, linker_smiles, right_smiles)
