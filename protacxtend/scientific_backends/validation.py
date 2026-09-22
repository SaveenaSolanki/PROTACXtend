"""Input / output validation and scientific sanity gates for backends.

The audit rule is simple and non-negotiable:

    a backend may only return ``SUCCESS`` when it has run on a *validated*
    input and produced an artefact that passes structural + physical sanity.

This module provides the cheap, deterministic checks used by the backends and
by the benchmark harness so that invalid SMILES, empty structures, NaN
coordinates, wrong atom counts, and non-finite energies are surfaced as
``REJECTED_INPUT`` / ``OUTPUT_INVALID`` / ``SCIENTIFIC_SANITY_FAILED`` instead of
silently becoming a "successful" row.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


# ── chemistry inputs ────────────────────────────────────────────────────

def validate_smiles(smiles: Any, *, min_heavy_atoms: int = 1) -> tuple[bool, str, Any]:
    """Return ``(ok, reason, mol)`` for a SMILES string.

    ``None``, NaN, ``""``, non-strings and RDKit-unparseable strings are all
    rejected.  A molecule with fewer than *min_heavy_atoms* heavy atoms is
    rejected too (guards against the classic "empty mol" trap, where
    ``Chem.MolFromSmiles("")`` returns a valid-but-empty molecule).
    """
    if smiles is None:
        return False, "empty ligand identifier (None)", None
    if isinstance(smiles, float) and np.isnan(smiles):
        return False, "empty ligand identifier (NaN)", None
    if not isinstance(smiles, str):
        return False, f"ligand identifier is not a string ({type(smiles).__name__})", None
    text = smiles.strip()
    if not text:
        return False, "empty ligand identifier", None
    if text.lower() in {"nan", "none", "null", "n/a"}:
        return False, f"placeholder ligand identifier '{text}'", None
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(text)
    except Exception as exc:  # noqa: BLE001
        return False, f"SMILES parser error: {exc}", None
    if mol is None:
        return False, f"invalid SMILES: {text[:80]}", None
    n_heavy = mol.GetNumHeavyAtoms()
    if n_heavy < min_heavy_atoms:
        return False, f"ligand has {n_heavy} heavy atoms (<{min_heavy_atoms})", None
    return True, "", mol


def validate_structure_pdb(path: Any, *, min_residues: int = 1) -> tuple[bool, str]:
    if not path:
        return False, "empty structure path"
    p = Path(str(path))
    if not p.exists() or p.stat().st_size == 0:
        return False, f"structure file missing/empty: {p}"
    try:
        from Bio.PDB import PDBParser

        structure = PDBParser(QUIET=True).get_structure("s", str(p))
        n_res = sum(1 for _ in structure.get_residues())
    except Exception as exc:  # noqa: BLE001
        return False, f"structure unreadable: {exc}"
    if n_res < min_residues:
        return False, f"structure has {n_res} residues (<{min_residues})"
    return True, ""


# ── pose / coordinate sanity ────────────────────────────────────────────

def coords_finite(coords: Any) -> bool:
    arr = np.asarray(coords, dtype=float)
    return bool(arr.size and np.isfinite(arr).all())


def validate_pose_coordinates(coords: Any, *, max_extent: float = 500.0) -> tuple[bool, str]:
    """Reject NaN/Inf coordinates or an absurd bounding-box extent."""
    arr = np.asarray(coords, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 3 or arr.shape[0] == 0:
        return False, f"pose coordinates have shape {arr.shape}"
    if not np.isfinite(arr).all():
        return False, "pose coordinates contain NaN/Inf"
    extent = float(np.linalg.norm(arr.max(axis=0) - arr.min(axis=0)))
    if extent > max_extent:
        return False, f"pose extent {extent:.1f} Å exceeds {max_extent:.0f} Å"
    return True, ""


def sanity_check_docking_poses(poses: list[dict[str, Any]]) -> tuple[bool, str]:
    """A docking run is only usable when it produced at least one scored pose."""
    if not poses:
        return False, "no poses produced"
    scored = [p for p in poses if _finite(p.get("score_kcal_mol")) or _finite(p.get("confidence"))]
    if not scored:
        return False, "no pose carried a finite score/confidence"
    return True, ""


def _finite(value: Any) -> bool:
    try:
        return value is not None and np.isfinite(float(value))
    except Exception:
        return False


# ── generic ScientificResult output gate ────────────────────────────────

def validate_result_output(result: Any) -> tuple[bool, str]:
    """Reject a ``ScientificResult`` whose data payload is empty/NaN-only.

    This is deliberately conservative: a result that claims success but carries
    no data, or only NaN numbers, is downgraded by the caller.
    """
    data = getattr(result, "data", None)
    if not data:
        return False, "result carried no data payload"
    if not isinstance(data, dict):
        return True, ""
    meaningful = False
    for key, value in data.items():
        if key in {"stdout_tail", "setup_tail", "run_tail", "warnings", "note",
                   "score_policy", "confidence_is_heuristic", "out_dir", "method"}:
            continue
        if value is None or value == "" or value == [] or value == {}:
            continue
        if isinstance(value, float) and not np.isfinite(value):
            continue
        meaningful = True
        break
    if not meaningful:
        return False, "result data payload contained no finite/meaningful values"
    return True, ""


def apply_output_gate(result: Any) -> Any:
    """Downgrade a ``SUCCESS`` result that fails the output gate."""
    from protacxtend.scientific_backends.evidence import CapabilityStatus

    if getattr(result, "status", "") != CapabilityStatus.SUCCESS.value:
        return result
    ok, reason = validate_result_output(result)
    if not ok:
        result.status = CapabilityStatus.OUTPUT_INVALID.value
        result.method_label = "OUTPUT_INVALID"
        result.warnings.append(reason)
    return result


__all__ = [
    "validate_smiles", "validate_structure_pdb", "coords_finite",
    "validate_pose_coordinates", "sanity_check_docking_poses",
    "validate_result_output", "apply_output_gate",
]
