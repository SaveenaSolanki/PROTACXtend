"""E3 ligand selection functions."""

from __future__ import annotations

from typing import Optional, Sequence

from protacxtend.backend.schemas import E3LigandRecord
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def load_curated_e3_ligands() -> list[dict[str, str]]:
    return _TOOLBOX.load_curated_e3_ligands()


def select_e3_ligands(
    e3_ligase: Optional[str] = None,
    e3_ligand_smiles: Optional[str] = None,
    max_ligands_per_e3: int = 3,
) -> list[E3LigandRecord]:
    return _TOOLBOX.select_e3_ligands(e3_ligase, e3_ligand_smiles, max_ligands_per_e3)


def validate_e3_ligand(smiles: str) -> str:
    return _TOOLBOX.validate_smiles(smiles)


def assign_e3_exit_vector(ligand: E3LigandRecord):
    vectors = _TOOLBOX.detect_exit_vectors([ligand], "e3_ligand")
    return vectors[0] if vectors else None


def rank_e3_ligands(ligands: Sequence[E3LigandRecord]) -> list[E3LigandRecord]:
    return sorted(ligands, key=lambda item: item.exit_vector_confidence + item.source_confidence + item.diversity_score, reverse=True)
