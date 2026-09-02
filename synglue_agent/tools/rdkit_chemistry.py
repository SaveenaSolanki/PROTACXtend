"""Real RDKit chemistry utilities for Phase 4.

Every function returns a structured dictionary and never falls back to regex or
hardcoded chemistry. If RDKit or an optional RDKit feature is unavailable, the
result is marked unsuccessful or unavailable with an explicit reason.
"""

from __future__ import annotations

from typing import Any


SOURCE = "RDKit chemistry"


def _base(query: dict[str, Any]) -> dict[str, Any]:
    return {"source": SOURCE, "query": query, "success": False, "error": None}


def _rdkit() -> tuple[Any, Any, Any, Any, Any, Any, Any, Any, Any, Any, str | None]:
    try:
        from rdkit import Chem, DataStructs
        from rdkit.Chem import BRICS, Crippen, Descriptors, Lipinski, QED, Recap, rdMolDescriptors

        try:
            from rdkit.Chem.MolStandardize import rdMolStandardize
        except Exception:
            rdMolStandardize = None
        return (
            Chem,
            DataStructs,
            BRICS,
            Crippen,
            Descriptors,
            Lipinski,
            QED,
            Recap,
            rdMolDescriptors,
            rdMolStandardize,
            None,
        )
    except Exception as exc:
        return (None, None, None, None, None, None, None, None, None, None, f"RDKit is not available: {exc}")


def _mol_from_smiles(smiles: str) -> tuple[Any, Any, str | None]:
    Chem, *_rest, error = _rdkit()
    if error:
        return None, Chem, error
    if not smiles or not str(smiles).strip():
        return None, Chem, "SMILES is required."
    mol = Chem.MolFromSmiles(str(smiles).strip())
    if mol is None:
        return None, Chem, "RDKit could not parse SMILES."
    try:
        Chem.SanitizeMol(mol)
    except Exception as exc:
        return None, Chem, f"RDKit sanitization failed: {exc}"
    return mol, Chem, None


def validate_smiles(smiles: str) -> dict[str, Any]:
    query = {"smiles": smiles}
    result = _base(query)
    mol, Chem, error = _mol_from_smiles(smiles)
    if error:
        result.update({"error": error, "valid": False, "canonical_smiles": None})
        return result
    result.update(
        {
            "success": True,
            "valid": True,
            "canonical_smiles": Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True),
        }
    )
    return result


def canonicalize_smiles(smiles: str, isomeric: bool = True) -> dict[str, Any]:
    query = {"smiles": smiles, "isomeric": isomeric}
    result = _base(query)
    mol, Chem, error = _mol_from_smiles(smiles)
    if error:
        result.update({"error": error, "canonical_smiles": None})
        return result
    result.update(
        {
            "success": True,
            "canonical_smiles": Chem.MolToSmiles(mol, canonical=True, isomericSmiles=isomeric),
        }
    )
    return result


def standardize_smiles(smiles: str) -> dict[str, Any]:
    query = {"smiles": smiles}
    result = _base(query)
    (
        Chem,
        _DataStructs,
        _BRICS,
        _Crippen,
        _Descriptors,
        _Lipinski,
        _QED,
        _Recap,
        _rdMolDescriptors,
        rdMolStandardize,
        error,
    ) = _rdkit()
    if error:
        result.update({"error": error, "standardized_smiles": None})
        return result
    mol, _Chem, parse_error = _mol_from_smiles(smiles)
    if parse_error:
        result.update({"error": parse_error, "standardized_smiles": None})
        return result
    try:
        if rdMolStandardize is not None:
            mol = rdMolStandardize.Cleanup(mol)
            mol = rdMolStandardize.FragmentParent(mol)
            mol = rdMolStandardize.Uncharger().uncharge(mol)
        result.update(
            {
                "success": True,
                "standardized_smiles": Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True),
                "standardization": "rdMolStandardize" if rdMolStandardize is not None else "sanitize_and_canonicalize",
            }
        )
    except Exception as exc:
        result.update({"error": f"RDKit standardization failed: {exc}", "standardized_smiles": None})
    return result


def calculate_descriptors(smiles: str) -> dict[str, Any]:
    query = {"smiles": smiles}
    result = _base(query)
    (
        Chem,
        _DataStructs,
        _BRICS,
        Crippen,
        Descriptors,
        Lipinski,
        QED,
        _Recap,
        rdMolDescriptors,
        _rdMolStandardize,
        error,
    ) = _rdkit()
    if error:
        result.update({"error": error, "descriptors": {}})
        return result
    mol, _Chem, parse_error = _mol_from_smiles(smiles)
    if parse_error:
        result.update({"error": parse_error, "descriptors": {}})
        return result
    try:
        descriptors = {
            "canonical_smiles": Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True),
            "MW": float(Descriptors.MolWt(mol)),
            "LogP": float(Crippen.MolLogP(mol)),
            "TPSA": float(rdMolDescriptors.CalcTPSA(mol)),
            "HBD": int(Lipinski.NumHDonors(mol)),
            "HBA": int(Lipinski.NumHAcceptors(mol)),
            "rotatable_bonds": int(Lipinski.NumRotatableBonds(mol)),
            "ring_count": int(rdMolDescriptors.CalcNumRings(mol)),
            "aromatic_ring_count": int(rdMolDescriptors.CalcNumAromaticRings(mol)),
            "heavy_atom_count": int(mol.GetNumHeavyAtoms()),
            "formal_charge": int(sum(atom.GetFormalCharge() for atom in mol.GetAtoms())),
            "fraction_Csp3": float(rdMolDescriptors.CalcFractionCSP3(mol)),
            "QED": float(QED.qed(mol)) if QED is not None else None,
            "SA_score": None,
            "SA_score_status": "unavailable",
            "SA_score_evidence": "RDKit does not ship a stable public SA score API; no local scorer is wired in Phase 4.",
        }
    except Exception as exc:
        result.update({"error": f"RDKit descriptor calculation failed: {exc}", "descriptors": {}})
        return result
    result.update({"success": True, "descriptors": descriptors})
    return result


def calculate_morgan_fingerprint(smiles: str, radius: int = 2, n_bits: int = 2048) -> dict[str, Any]:
    query = {"smiles": smiles, "radius": radius, "n_bits": n_bits}
    result = _base(query)
    _Chem, _DataStructs, *_rest, error = _rdkit()
    if error:
        result.update({"error": error, "fingerprint": None})
        return result
    mol, _Chem, parse_error = _mol_from_smiles(smiles)
    if parse_error:
        result.update({"error": parse_error, "fingerprint": None})
        return result
    if radius < 0 or n_bits <= 0:
        result.update({"error": "radius must be non-negative and n_bits must be positive.", "fingerprint": None})
        return result
    try:
        from rdkit.Chem import AllChem

        fingerprint = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
        on_bits = list(fingerprint.GetOnBits())
    except Exception as exc:
        result.update({"error": f"RDKit Morgan fingerprint failed: {exc}", "fingerprint": None})
        return result
    result.update(
        {
            "success": True,
            "fingerprint": {
                "radius": radius,
                "n_bits": n_bits,
                "on_bit_count": len(on_bits),
                "on_bits": on_bits,
                "bit_string": fingerprint.ToBitString(),
            },
        }
    )
    return result


def calculate_similarity(smiles_a: str, smiles_b: str) -> dict[str, Any]:
    query = {"smiles_a": smiles_a, "smiles_b": smiles_b, "metric": "tanimoto_morgan_radius2_2048"}
    result = _base(query)
    _Chem, DataStructs, *_rest, error = _rdkit()
    if error:
        result.update({"error": error, "similarity": None})
        return result
    mol_a, _Chem, error_a = _mol_from_smiles(smiles_a)
    mol_b, _Chem, error_b = _mol_from_smiles(smiles_b)
    if error_a or error_b:
        result.update({"error": error_a or error_b, "similarity": None})
        return result
    try:
        from rdkit.Chem import AllChem

        fp_a = AllChem.GetMorganFingerprintAsBitVect(mol_a, 2, nBits=2048)
        fp_b = AllChem.GetMorganFingerprintAsBitVect(mol_b, 2, nBits=2048)
        similarity = float(DataStructs.TanimotoSimilarity(fp_a, fp_b))
    except Exception as exc:
        result.update({"error": f"RDKit similarity calculation failed: {exc}", "similarity": None})
        return result
    result.update({"success": True, "similarity": similarity})
    return result


def calculate_basic_protac_properties(smiles: str) -> dict[str, Any]:
    result = calculate_descriptors(smiles)
    if not result["success"]:
        result["protac_properties"] = {}
        return result
    descriptors = result["descriptors"]
    result["protac_properties"] = {
        "MW": descriptors["MW"],
        "LogP": descriptors["LogP"],
        "TPSA": descriptors["TPSA"],
        "HBD": descriptors["HBD"],
        "HBA": descriptors["HBA"],
        "rotatable_bonds": descriptors["rotatable_bonds"],
        "heavy_atom_count": descriptors["heavy_atom_count"],
        "ring_count": descriptors["ring_count"],
        "aromatic_ring_count": descriptors["aromatic_ring_count"],
        "fraction_Csp3": descriptors["fraction_Csp3"],
        "protac_like_size_flag": descriptors["MW"] >= 600 or descriptors["rotatable_bonds"] >= 10,
    }
    return result


def detect_dummy_atoms(smiles: str) -> dict[str, Any]:
    query = {"smiles": smiles}
    result = _base(query)
    mol, _Chem, error = _mol_from_smiles(smiles)
    if error:
        result.update({"error": error, "dummy_atoms": []})
        return result
    dummy_atoms = []
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 0:
            dummy_atoms.append(
                {
                    "atom_index": atom.GetIdx(),
                    "isotope": atom.GetIsotope(),
                    "atom_map_number": atom.GetAtomMapNum(),
                    "degree": atom.GetDegree(),
                    "neighbor_indices": [neighbor.GetIdx() for neighbor in atom.GetNeighbors()],
                }
            )
    result.update({"success": True, "dummy_atoms": dummy_atoms, "dummy_atom_count": len(dummy_atoms)})
    return result


def detect_exit_vector_atoms(smiles: str) -> dict[str, Any]:
    query = {"smiles": smiles}
    result = _base(query)
    dummy_result = detect_dummy_atoms(smiles)
    if not dummy_result["success"]:
        result.update({"error": dummy_result["error"], "exit_vector_atoms": []})
        return result
    mol, _Chem, error = _mol_from_smiles(smiles)
    if error:
        result.update({"error": error, "exit_vector_atoms": []})
        return result
    exit_atoms = []
    seen = set()
    for dummy in dummy_result["dummy_atoms"]:
        for atom_index in dummy["neighbor_indices"]:
            if atom_index in seen:
                continue
            seen.add(atom_index)
            atom = mol.GetAtomWithIdx(atom_index)
            exit_atoms.append(
                {
                    "atom_index": atom.GetIdx(),
                    "symbol": atom.GetSymbol(),
                    "formal_charge": atom.GetFormalCharge(),
                    "degree": atom.GetDegree(),
                    "attached_dummy_atom_index": dummy["atom_index"],
                    "attached_dummy_atom_map_number": dummy["atom_map_number"],
                }
            )
    result.update({"success": True, "exit_vector_atoms": exit_atoms, "exit_vector_atom_count": len(exit_atoms)})
    return result


def run_brics_fragmentation(smiles: str) -> dict[str, Any]:
    query = {"smiles": smiles}
    result = _base(query)
    Chem, _DataStructs, BRICS, *_rest, error = _rdkit()
    if error:
        result.update({"error": error, "fragments": []})
        return result
    mol, _Chem, parse_error = _mol_from_smiles(smiles)
    if parse_error:
        result.update({"error": parse_error, "fragments": []})
        return result
    try:
        fragments = sorted(BRICS.BRICSDecompose(mol))
    except Exception as exc:
        result.update({"error": f"RDKit BRICS fragmentation failed: {exc}", "fragments": []})
        return result
    result.update({"success": True, "fragments": fragments, "fragment_count": len(fragments)})
    return result


def run_recap_fragmentation(smiles: str) -> dict[str, Any]:
    query = {"smiles": smiles}
    result = _base(query)
    _Chem, _DataStructs, _BRICS, _Crippen, _Descriptors, _Lipinski, _QED, Recap, *_rest, error = _rdkit()
    if error:
        result.update({"error": error, "fragments": []})
        return result
    mol, _Chem, parse_error = _mol_from_smiles(smiles)
    if parse_error:
        result.update({"error": parse_error, "fragments": []})
        return result
    if Recap is None:
        result.update({"error": "RDKit RECAP module is unavailable.", "fragments": [], "unavailable": True})
        return result
    try:
        hierarchy = Recap.RecapDecompose(mol)
        fragments = sorted(hierarchy.GetLeaves().keys()) if hierarchy is not None else []
    except Exception as exc:
        result.update({"error": f"RDKit RECAP fragmentation failed: {exc}", "fragments": []})
        return result
    result.update({"success": True, "fragments": fragments, "fragment_count": len(fragments)})
    return result


__all__ = [
    "standardize_smiles",
    "canonicalize_smiles",
    "validate_smiles",
    "calculate_descriptors",
    "calculate_morgan_fingerprint",
    "calculate_similarity",
    "calculate_basic_protac_properties",
    "detect_dummy_atoms",
    "detect_exit_vector_atoms",
    "run_brics_fragmentation",
    "run_recap_fragmentation",
]
