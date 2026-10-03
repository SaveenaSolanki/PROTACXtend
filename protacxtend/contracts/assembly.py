"""Chemistry + identity checks for the contract layer.

Assembly uses RDKit's atom-map aware ``molzip`` — not naive string
concatenation — so attachment points and stereochemistry survive. The
controlled BRD4–VHL example reproduces MZ1 and is checked by InChIKey against
the curated source structure.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from .records import (
    Binder,
    E3Ligand,
    Linker,
    ProtacCandidate,
    ScientificRecord,
    Warhead,
)

_DATA = Path(__file__).resolve().parents[1] / "data" / "verified_components.json"


# ── RDKit helpers ────────────────────────────────────────────────────

def rdkit_available() -> bool:
    try:
        import rdkit  # noqa: F401
        return True
    except Exception:
        return False


def canonicalize(smiles: str) -> tuple[bool, str, Optional[str]]:
    """Return (ok, canonical_smiles, reason). Empty/invalid never 'ok'."""
    text = (smiles or "").strip()
    if not text:
        return False, "", "empty_smiles"
    try:
        from rdkit import Chem
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")
        mol = Chem.MolFromSmiles(text)
        if mol is None:
            return False, "", "rdkit_parse_failed"
        return True, Chem.MolToSmiles(mol), None
    except Exception as exc:  # pragma: no cover - defensive
        return False, "", f"rdkit_error:{exc}"


def attachment_maps(smiles: str) -> list[int]:
    """Atom-map numbers of dummy atoms (attachment vectors) in *smiles*."""
    try:
        from rdkit import Chem
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return []
        return sorted(a.GetAtomMapNum() for a in mol.GetAtoms() if a.GetAtomicNum() == 0)
    except Exception:  # pragma: no cover
        return []


def _renumber_single_dummy_to(mol: Any, target_map: int) -> bool:
    from rdkit import Chem
    dummies = [a for a in mol.GetAtoms() if a.GetAtomicNum() == 0]
    if len(dummies) != 1:
        return False
    dummies[0].SetAtomMapNum(target_map)
    return True


def assemble_product(warhead_smiles: str, linker_smiles: str, e3_smiles: str) -> tuple[bool, str, str, Optional[str]]:
    """Assemble warhead + linker + E3 ligand via RDKit molzip.

    Returns (ok, canonical_product_smiles, inchikey, reason). Attachment maps
    follow ``verified_components.json``: warhead ``[*:1]``; linker
    ``[*:1]->warhead`` and ``[*:2]->E3``; E3 ligand ``[*:1]``.
    """
    if not rdkit_available():
        return False, "", "", "rdkit_unavailable"
    try:
        from rdkit import Chem
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")

        wh, lk, e3 = (Chem.MolFromSmiles(warhead_smiles),
                      Chem.MolFromSmiles(linker_smiles),
                      Chem.MolFromSmiles(e3_smiles))
        if wh is None or lk is None or e3 is None:
            return False, "", "", "component_parse_failed"
        if 1 not in attachment_maps(warhead_smiles):
            return False, "", "", "warhead_missing_attachment_map_1"
        if not ({1, 2} <= set(attachment_maps(linker_smiles))):
            return False, "", "", "linker_missing_attachment_maps_1_2"
        if 1 not in attachment_maps(e3_smiles):
            return False, "", "", "e3_missing_attachment_map_1"

        try:
            step1 = Chem.molzip(wh, lk)
        except Exception as exc:
            return False, "", "", f"molzip_warhead_linker_failed:{exc}"
        if step1 is None:
            return False, "", "", "molzip_warhead_linker_returned_none"
        if not _renumber_single_dummy_to(step1, 1):
            return False, "", "", "linker_residual_attachment_not_single"

        try:
            product = Chem.molzip(step1, e3)
        except Exception as exc:
            return False, "", "", f"molzip_product_failed:{exc}"
        if product is None:
            return False, "", "", "molzip_product_returned_none"
        if any(a.GetAtomicNum() == 0 for a in product.GetAtoms()):
            return False, "", "", "unreacted_attachment_vector_in_product"
        Chem.SanitizeMol(product)
        canonical = Chem.MolToSmiles(product)
        return True, canonical, Chem.MolToInchiKey(product), None
    except Exception as exc:  # pragma: no cover - defensive
        return False, "", "", f"assembly_error:{exc}"


def molecular_formula_and_mw(canonical_smiles: str) -> tuple[str, Optional[float]]:
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")
        mol = Chem.MolFromSmiles(canonical_smiles)
        if mol is None:
            return "", None
        return rdMolDescriptors.CalcMolFormula(mol), round(Descriptors.MolWt(mol), 3)
    except Exception:  # pragma: no cover
        return "", None


# ── Verified components ──────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_verified_components() -> dict[str, Any]:
    if not _DATA.exists():
        return {"components": []}
    return json.loads(_DATA.read_text())


def verified_by_role(role: str) -> list[dict[str, Any]]:
    return [c for c in load_verified_components().get("components", [])
            if c.get("role") == role and c.get("verified")]


def build_warhead(component: dict[str, Any]) -> Warhead:
    ok, canon, reason = canonicalize(component.get("smiles", ""))
    maps = attachment_maps(component.get("smiles", ""))
    return Warhead(
        name=component.get("name", ""),
        target_gene=component.get("target", ""),
        smiles=component.get("smiles", ""),
        canonical_smiles=canon or component.get("smiles", ""),
        attachment_atom_map=component.get("attachment_atom_map"),
        attachment_smarts=f"[*:{component.get('attachment_atom_map')}]" if maps else "",
        evidence_status="verified" if ok and maps else "invalid",
        source_uri=component.get("source", ""),
        source_record_id=component.get("component_id", ""),
        validation_state="valid" if ok and maps else "invalid",
        provenance={"applicability": component.get("applicability", [])},
    )


def build_e3_ligand(component: dict[str, Any]) -> E3Ligand:
    ok, canon, reason = canonicalize(component.get("smiles", ""))
    maps = attachment_maps(component.get("smiles", ""))
    return E3Ligand(
        name=component.get("name", ""),
        e3_gene=component.get("e3_ligase", ""),
        smiles=component.get("smiles", ""),
        canonical_smiles=canon or component.get("smiles", ""),
        attachment_atom_map=component.get("attachment_atom_map"),
        attachment_smarts=f"[*:{component.get('attachment_atom_map')}]" if maps else "",
        evidence_status="verified" if ok and maps else "invalid",
        source_uri=component.get("source", ""),
        source_record_id=component.get("component_id", ""),
        validation_state="valid" if ok and maps else "invalid",
        provenance={"applicability": component.get("applicability", [])},
    )


def build_linker(component: dict[str, Any]) -> Linker:
    ok, canon, _ = canonicalize(component.get("smiles", ""))
    maps = attachment_maps(component.get("smiles", ""))
    return Linker(
        name=component.get("name", ""),
        smiles=component.get("smiles", ""),
        canonical_smiles=canon or component.get("smiles", ""),
        source_uri=component.get("source", ""),
        source_record_id=component.get("component_id", ""),
        validation_state="valid" if ok and {1, 2} <= set(maps) else "invalid",
        provenance={"attachment_maps": maps},
    )


# ── Binder usability ─────────────────────────────────────────────────

def assess_binder(binder: Binder, target_gene: str) -> Binder:
    """Decide whether a binder is usable; never promote an empty record."""
    name = (binder.name or "").strip()
    smiles = (binder.smiles or "").strip()
    if not smiles:
        binder.structure_valid = False
        binder.rejection_reason = "missing_structure"
        binder.evidence_status = "rejected_missing_structure"
        binder.validation_state = "rejected"
        return binder
    ok, canon, reason = canonicalize(smiles)
    if not ok:
        binder.structure_valid = False
        binder.rejection_reason = reason or "invalid_structure"
        binder.evidence_status = "rejected_invalid_structure"
        binder.validation_state = "rejected"
        return binder
    if not name:
        binder.structure_valid = True
        binder.canonical_smiles = canon
        binder.rejection_reason = "missing_identity"
        binder.evidence_status = "rejected_missing_identity"
        binder.validation_state = "rejected"
        return binder
    if target_gene and binder.target_gene and binder.target_gene.upper() != target_gene.upper():
        binder.structure_valid = True
        binder.canonical_smiles = canon
        binder.rejection_reason = "target_mismatch"
        binder.evidence_status = "rejected_target_mismatch"
        binder.validation_state = "rejected"
        return binder
    binder.structure_valid = True
    binder.canonical_smiles = canon
    binder.evidence_status = "usable"
    binder.validation_state = "valid"
    return binder


# ── Identity consistency ─────────────────────────────────────────────

def assert_identity_consistency(record: Any) -> list[str]:
    """Return violations where target/E3 identities disagree across the run.

    Regression guard for run_e4e21ccd: a candidate labelled RLBP1 must never
    carry a BRD4-associated warhead.
    """
    violations: list[str] = []
    target = record.target.gene_symbol.upper() if record.target else ""
    e3 = record.e3_ligase.gene_symbol.upper() if record.e3_ligase else ""

    for wh in record.warheads:
        if target and wh.target_gene and wh.target_gene.upper() != target:
            violations.append(
                f"warhead {wh.name!r} targets {wh.target_gene} but run target is {target}")
    for lig in record.e3_ligands:
        if e3 and lig.e3_gene and lig.e3_gene.upper() != e3:
            violations.append(
                f"E3 ligand {lig.name!r} recruits {lig.e3_gene} but run E3 is {e3}")
    for cand in record.candidates:
        if target and cand.target_gene and cand.target_gene.upper() != target:
            violations.append(
                f"candidate {cand.candidate_id} labelled {cand.target_gene} != target {target}")
        if e3 and cand.e3_gene and cand.e3_gene.upper() != e3:
            violations.append(
                f"candidate {cand.candidate_id} uses E3 {cand.e3_gene} != {e3}")
    return violations
