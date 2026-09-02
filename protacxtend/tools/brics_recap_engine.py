"""BRICS/RECAP-inspired local fragment tools."""

from __future__ import annotations

from protacxtend.tools.linker_generator import generate_brics_recap_linkers
from protacxtend.tools.molecular_constructor import construct_with_brics_recap


def generate_brics_fragments(smiles: str) -> list[str]:
    return [part for part in smiles.replace("[*:1]", ".").replace("[*:2]", ".").split(".") if part]


def recombine_brics_recap(warhead_smiles: str, linker_smiles: str, e3_smiles: str):
    return construct_with_brics_recap(warhead_smiles, linker_smiles, e3_smiles)
