"""RDKit validation, descriptor, and fingerprint wrappers."""

from __future__ import annotations

from typing import Any
from typing import Sequence

from protacxtend.backend.schemas import CandidateRecord
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def validate_smiles(smiles: str) -> str:
    return _TOOLBOX.validate_smiles(smiles)


def validate_candidate(candidate: CandidateRecord) -> CandidateRecord:
    candidate.validity_status = _TOOLBOX.validate_smiles(candidate.full_protac_smiles)
    return candidate


def sanitize_molecule(smiles: str) -> str:
    return _TOOLBOX.canonicalize_smiles(smiles)


def check_valence(smiles: str) -> bool:
    return not _TOOLBOX.validate_smiles(smiles).startswith("invalid")


def check_stereochemistry(smiles: str) -> bool:
    return "@" not in smiles or not _TOOLBOX.validate_smiles(smiles).startswith("invalid")


def canonicalize_candidate(candidate: CandidateRecord) -> CandidateRecord:
    candidate.full_protac_smiles = _TOOLBOX.canonicalize_smiles(candidate.full_protac_smiles)
    return candidate


def remove_duplicates(candidates: Sequence[CandidateRecord]) -> list[CandidateRecord]:
    return _TOOLBOX.remove_duplicate_candidates(candidates)


def compute_protac_properties(smiles: str) -> dict:
    return _TOOLBOX.compute_basic_properties(smiles)


def calculate_rdkit_descriptors(smiles: str) -> dict[str, Any]:
    """Return RDKit molecular descriptors without fake fallback values."""

    query = {"smiles": smiles}
    try:
        from rdkit import Chem
        from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
    except Exception as exc:
        return {
            "source": "RDKit",
            "query": query,
            "success": False,
            "error": f"RDKit is not available: {exc}",
            "descriptors": {},
        }
    if not smiles:
        return {"source": "RDKit", "query": query, "success": False, "error": "SMILES is required.", "descriptors": {}}
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"source": "RDKit", "query": query, "success": False, "error": "RDKit could not parse SMILES.", "descriptors": {}}
    try:
        Chem.SanitizeMol(mol)
        descriptors = {
            "canonical_smiles": Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True),
            "mw": round(float(Descriptors.MolWt(mol)), 4),
            "exact_mw": round(float(Descriptors.ExactMolWt(mol)), 4),
            "tpsa": round(float(rdMolDescriptors.CalcTPSA(mol)), 4),
            "logp": round(float(Crippen.MolLogP(mol)), 4),
            "hbd": int(Lipinski.NumHDonors(mol)),
            "hba": int(Lipinski.NumHAcceptors(mol)),
            "rotatable_bonds": int(Lipinski.NumRotatableBonds(mol)),
            "heavy_atom_count": int(mol.GetNumHeavyAtoms()),
            "ring_count": int(rdMolDescriptors.CalcNumRings(mol)),
        }
    except Exception as exc:
        return {"source": "RDKit", "query": query, "success": False, "error": str(exc), "descriptors": {}}
    return {"source": "RDKit", "query": query, "success": True, "error": None, "descriptors": descriptors}


def calculate_morgan_fingerprint(smiles: str, radius: int = 2, n_bits: int = 2048) -> dict[str, Any]:
    """Return an RDKit Morgan fingerprint bit vector summary."""

    query = {"smiles": smiles, "radius": radius, "n_bits": n_bits}
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except Exception as exc:
        return {
            "source": "RDKit Morgan fingerprint",
            "query": query,
            "success": False,
            "error": f"RDKit is not available: {exc}",
            "fingerprint": None,
        }
    if not smiles:
        return {
            "source": "RDKit Morgan fingerprint",
            "query": query,
            "success": False,
            "error": "SMILES is required.",
            "fingerprint": None,
        }
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {
            "source": "RDKit Morgan fingerprint",
            "query": query,
            "success": False,
            "error": "RDKit could not parse SMILES.",
            "fingerprint": None,
        }
    try:
        fingerprint = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
        on_bits = list(fingerprint.GetOnBits())
    except Exception as exc:
        return {"source": "RDKit Morgan fingerprint", "query": query, "success": False, "error": str(exc), "fingerprint": None}
    return {
        "source": "RDKit Morgan fingerprint",
        "query": query,
        "success": True,
        "error": None,
        "fingerprint": {
            "radius": radius,
            "n_bits": n_bits,
            "on_bit_count": len(on_bits),
            "on_bits": on_bits,
            "bit_string": fingerprint.ToBitString(),
        },
    }
