"""Optional aromaticity-core adapter with RDKit fallback.

The adapter never claims aromaticity-core was used unless the package imports
and a callable path succeeds. RDKit fallback remains explicit.
"""

from __future__ import annotations

import importlib
from typing import Any

from protacxtend.tools.chemistry_core import RDKIT_AVAILABLE, safe_mol_from_smiles


def _import_aromaticity_core() -> tuple[Any | None, str | None]:
    for module_name in ("aromaticity_core", "aromaticity"):
        try:
            return importlib.import_module(module_name), None
        except Exception as exc:
            last_error = f"{module_name}: {exc}"
    return None, f"aromaticity-core is not importable ({last_error})."


def detect_aromaticity_backend() -> dict[str, Any]:
    module, error = _import_aromaticity_core()
    aromaticity_core_available = module is not None
    if aromaticity_core_available:
        selected = "aromaticity_core"
        status = "available"
    elif RDKIT_AVAILABLE:
        selected = "rdkit"
        status = "fallback_rdkit"
    else:
        selected = "none"
        status = "not_available"
    return {
        "aromaticity_core_available": aromaticity_core_available,
        "rdkit_available": RDKIT_AVAILABLE,
        "selected_backend": selected,
        "status": status,
        "error": None if aromaticity_core_available else error,
    }


def rdkit_aromaticity_summary(smiles: str) -> dict[str, Any]:
    mol, error = safe_mol_from_smiles(smiles, sanitize=True)
    if error or mol is None:
        return {
            "canonical_smiles": None,
            "aromatic_atom_count": 0,
            "aromatic_bond_count": 0,
            "aromatic_ring_count": 0,
            "aromatic_atom_indices": [],
            "backend": "rdkit",
            "status": "failed",
            "error": error,
        }
    try:
        from rdkit import Chem
        from rdkit.Chem import rdMolDescriptors

        aromatic_atom_indices = [atom.GetIdx() for atom in mol.GetAtoms() if atom.GetIsAromatic()]
        aromatic_bond_count = sum(1 for bond in mol.GetBonds() if bond.GetIsAromatic())
        return {
            "canonical_smiles": Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True),
            "aromatic_atom_count": len(aromatic_atom_indices),
            "aromatic_bond_count": int(aromatic_bond_count),
            "aromatic_ring_count": int(rdMolDescriptors.CalcNumAromaticRings(mol)),
            "aromatic_atom_indices": aromatic_atom_indices,
            "backend": "rdkit",
            "status": "success",
            "error": None,
        }
    except Exception as exc:
        return {
            "canonical_smiles": None,
            "aromatic_atom_count": 0,
            "aromatic_bond_count": 0,
            "aromatic_ring_count": 0,
            "aromatic_atom_indices": [],
            "backend": "rdkit",
            "status": "failed",
            "error": f"RDKit aromaticity summary failed: {exc}",
        }


def aromaticity_core_summary(smiles: str) -> dict[str, Any]:
    module, import_error = _import_aromaticity_core()
    if module is None:
        return {
            "canonical_smiles": None,
            "aromatic_atom_count": 0,
            "aromatic_bond_count": 0,
            "aromatic_ring_count": 0,
            "aromatic_atom_indices": [],
            "backend": "aromaticity_core",
            "backend_status": "not_available",
            "status": "not_available",
            "error": import_error,
            "available_callables": [],
        }

    callable_names = [name for name in dir(module) if not name.startswith("_") and callable(getattr(module, name, None))]
    preferred = [
        "aromaticity_summary",
        "summarize_aromaticity",
        "detect_aromaticity",
        "analyze_aromaticity",
    ]
    for name in preferred:
        func = getattr(module, name, None)
        if not callable(func):
            continue
        try:
            raw = func(smiles)
        except Exception as exc:
            return {
                "canonical_smiles": None,
                "aromatic_atom_count": 0,
                "aromatic_bond_count": 0,
                "aromatic_ring_count": 0,
                "aromatic_atom_indices": [],
                "backend": "aromaticity_core",
                "backend_status": "available_call_failed",
                "status": "failed",
                "error": f"aromaticity-core callable {name} failed: {exc}",
                "available_callables": callable_names,
            }
        if isinstance(raw, dict):
            return {
                "canonical_smiles": raw.get("canonical_smiles") or raw.get("smiles"),
                "aromatic_atom_count": int(raw.get("aromatic_atom_count", raw.get("num_aromatic_atoms", 0)) or 0),
                "aromatic_bond_count": int(raw.get("aromatic_bond_count", raw.get("num_aromatic_bonds", 0)) or 0),
                "aromatic_ring_count": int(raw.get("aromatic_ring_count", raw.get("num_aromatic_rings", 0)) or 0),
                "aromatic_atom_indices": list(raw.get("aromatic_atom_indices", [])),
                "backend": "aromaticity_core",
                "backend_status": "available",
                "status": "success",
                "error": None,
                "available_callables": callable_names,
            }
        return {
            "canonical_smiles": None,
            "aromatic_atom_count": 0,
            "aromatic_bond_count": 0,
            "aromatic_ring_count": 0,
            "aromatic_atom_indices": [],
            "backend": "aromaticity_core",
            "backend_status": "available_unrecognized_output",
            "status": "not_connected",
            "error": f"aromaticity-core callable {name} returned unsupported type {type(raw).__name__}.",
            "available_callables": callable_names,
        }

    return {
        "canonical_smiles": None,
        "aromatic_atom_count": 0,
        "aromatic_bond_count": 0,
        "aromatic_ring_count": 0,
        "aromatic_atom_indices": [],
        "backend": "aromaticity_core",
        "backend_status": "not_connected",
        "status": "not_connected",
        "error": "aromaticity-core imported, but no known summary callable was found.",
        "available_callables": callable_names,
    }


def aromaticity_summary(smiles: str, prefer: str = "auto") -> dict[str, Any]:
    prefer = (prefer or "auto").strip().lower()
    if prefer in {"auto", "aromaticity_core"}:
        core = aromaticity_core_summary(smiles)
        if core.get("status") == "success":
            core["limitation"] = "aromaticity-core summary succeeded."
            return core
        if prefer == "aromaticity_core":
            core["limitation"] = "aromaticity-core was requested but did not produce a usable result."
            return core

    rdkit = rdkit_aromaticity_summary(smiles)
    rdkit["backend"] = "rdkit_fallback"
    rdkit["backend_status"] = "fallback" if rdkit.get("status") == "success" else "failed"
    rdkit["limitation"] = "aromaticity-core was not used; RDKit aromatic atom/bond/ring detection was used as fallback."
    return rdkit

