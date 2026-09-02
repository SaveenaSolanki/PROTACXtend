"""Exit-vector detection functions."""

from __future__ import annotations

from typing import Any, Sequence

from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def detect_exit_vectors(molecules: Sequence[Any], role: str):
    return _TOOLBOX.detect_exit_vectors(molecules, role)


def apply_attachment_marker(smiles: str, marker: str = "[*:1]") -> str:
    return smiles if "[*" in smiles else smiles + marker


def use_curated_exit_vector(molecule: Any, role: str):
    vectors = _TOOLBOX.detect_exit_vectors([molecule], role)
    return vectors[0] if vectors else None


def score_exit_vector_confidence(smiles: str) -> float:
    return 0.9 if "[*" in smiles else 0.25


def explain_exit_vector_choice(smiles: str) -> str:
    return "Explicit attachment marker found." if "[*" in smiles else "No explicit attachment marker; confidence is low."
