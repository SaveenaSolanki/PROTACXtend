"""Experimental pose-backed structural scoring for PROTAC ternary complexes.

This module is deliberately dependency-light. If a ternary PDB pose exists, it
computes real geometric metrics from atom coordinates. If no pose exists, callers
should keep using the existing proxy path and label it as such.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass
class AtomRecord:
    atom_name: str
    residue_name: str
    chain_id: str
    residue_id: int
    element: str
    x: float
    y: float
    z: float


@dataclass
class StructuralScore:
    candidate_id: str
    pose_file: str
    backend: str = "local_pose_geometry_experimental_v0.1"
    target_chain: str = ""
    e3_chain: str = ""
    interface_contact_count: int = 0
    polar_contact_count: int = 0
    clash_count: int = 0
    buried_sasa_proxy: float = 0.0
    interface_quality_score: float = 0.0
    nearest_lysine: str | None = None
    nearest_lysine_distance_A: float | None = None
    accessible_lysine_count: int = 0
    productive_lysine_count: int = 0
    lysine_geometry_score: float = 0.0
    linker_conformer_count: int = 0
    linker_energy_spread: float | None = None
    linker_strain_score: float = 0.0
    real_structural_score: float = 0.0
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _distance(a: AtomRecord, b: AtomRecord) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def _heavy_atoms(atoms: Iterable[AtomRecord]) -> list[AtomRecord]:
    return [atom for atom in atoms if atom.element.upper() != "H"]


def _is_polar(atom: AtomRecord) -> bool:
    return atom.element.upper() in {"N", "O", "S"}


def parse_pdb_atoms(path: str | Path) -> list[AtomRecord]:
    """Parse ATOM/HETATM coordinate rows from a PDB file."""
    atoms: list[AtomRecord] = []
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        try:
            atom_name = line[12:16].strip()
            residue_name = line[17:20].strip()
            chain_id = line[21].strip() or "_"
            residue_id = int(line[22:26])
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            element = line[76:78].strip() or "".join(ch for ch in atom_name if ch.isalpha())[:1]
        except Exception:
            continue
        atoms.append(
            AtomRecord(
                atom_name=atom_name,
                residue_name=residue_name,
                chain_id=chain_id,
                residue_id=residue_id,
                element=element.upper(),
                x=x,
                y=y,
                z=z,
            )
        )
    return atoms


def infer_target_e3_chains(atoms: list[AtomRecord], target_chain: str = "", e3_chain: str = "") -> tuple[str, str]:
    chains = []
    for atom in atoms:
        if atom.chain_id not in chains:
            chains.append(atom.chain_id)
    if target_chain and e3_chain:
        return target_chain, e3_chain
    if len(chains) >= 2:
        return target_chain or chains[0], e3_chain or chains[1]
    chain = chains[0] if chains else ""
    return target_chain or chain, e3_chain or chain


def score_interface(atoms: list[AtomRecord], target_chain: str, e3_chain: str) -> dict[str, Any]:
    target_atoms = _heavy_atoms(atom for atom in atoms if atom.chain_id == target_chain)
    e3_atoms = _heavy_atoms(atom for atom in atoms if atom.chain_id == e3_chain)
    contacts = 0
    polar_contacts = 0
    clashes = 0
    for target_atom in target_atoms:
        for e3_atom in e3_atoms:
            dist = _distance(target_atom, e3_atom)
            if dist <= 5.0:
                contacts += 1
                if _is_polar(target_atom) and _is_polar(e3_atom) and dist <= 3.8:
                    polar_contacts += 1
            if dist < 2.0:
                clashes += 1
    buried_proxy = _clamp(contacts / 180.0)
    contact_score = _clamp(contacts / 120.0)
    polar_score = _clamp(polar_contacts / 18.0)
    clash_penalty = _clamp(clashes / 12.0)
    quality = _clamp(0.58 * contact_score + 0.22 * polar_score + 0.20 * buried_proxy - 0.45 * clash_penalty)
    return {
        "interface_contact_count": contacts,
        "polar_contact_count": polar_contacts,
        "clash_count": clashes,
        "buried_sasa_proxy": round(buried_proxy, 3),
        "interface_quality_score": round(quality, 3),
    }


def score_lysine_geometry(atoms: list[AtomRecord], target_chain: str, e3_chain: str) -> dict[str, Any]:
    target_atoms = _heavy_atoms(atom for atom in atoms if atom.chain_id == target_chain)
    e3_atoms = _heavy_atoms(atom for atom in atoms if atom.chain_id == e3_chain)
    lys_nz = [atom for atom in target_atoms if atom.residue_name == "LYS" and atom.atom_name == "NZ"]
    if not lys_nz or not e3_atoms:
        return {
            "nearest_lysine": None,
            "nearest_lysine_distance_A": None,
            "accessible_lysine_count": 0,
            "productive_lysine_count": 0,
            "lysine_geometry_score": 0.0,
            "warning": "No target-chain lysine NZ atoms or E3 atoms found in pose.",
        }
    nearest = None
    nearest_distance = None
    accessible_count = 0
    productive_count = 0
    scores: list[float] = []
    for lys in lys_nz:
        dist = min(_distance(lys, atom) for atom in e3_atoms)
        local_contacts = sum(1 for atom in target_atoms if atom.residue_id != lys.residue_id and _distance(lys, atom) <= 6.0)
        accessible = local_contacts <= 18
        if accessible:
            accessible_count += 1
        if nearest_distance is None or dist < nearest_distance:
            nearest = lys
            nearest_distance = dist
        if 10.0 <= dist <= 60.0 and accessible:
            productive_count += 1
        if dist < 10.0:
            distance_score = _clamp(dist / 10.0)
        elif dist <= 35.0:
            distance_score = 1.0
        elif dist <= 60.0:
            distance_score = _clamp(1.0 - (dist - 35.0) / 25.0)
        else:
            distance_score = 0.0
        accessibility_score = 1.0 if accessible else 0.35
        scores.append(_clamp(0.70 * distance_score + 0.30 * accessibility_score))
    best_score = max(scores) if scores else 0.0
    nearest_label = f"LYS{nearest.residue_id}:{nearest.chain_id}" if nearest else None
    return {
        "nearest_lysine": nearest_label,
        "nearest_lysine_distance_A": round(nearest_distance, 2) if nearest_distance is not None else None,
        "accessible_lysine_count": accessible_count,
        "productive_lysine_count": productive_count,
        "lysine_geometry_score": round(best_score, 3),
        "warning": None if productive_count else "No accessible target lysine falls in the current productive distance window.",
    }


def score_linker_strain(smiles: str, max_conformers: int = 16) -> dict[str, Any]:
    """Estimate linker/PROTAC conformer strain with RDKit UFF energy spread."""
    if not smiles:
        return {
            "linker_conformer_count": 0,
            "linker_energy_spread": None,
            "linker_strain_score": 0.4,
            "warning": "No SMILES supplied for linker strain scoring.",
        }
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem, rdMolDescriptors
    except Exception as exc:
        return {
            "linker_conformer_count": 0,
            "linker_energy_spread": None,
            "linker_strain_score": 0.45,
            "warning": f"RDKit unavailable for linker strain scoring: {exc}",
        }
    mol = Chem.MolFromSmiles(smiles.replace("[*:1]", "").replace("[*:2]", "").replace("[*]", ""))
    if mol is None:
        return {
            "linker_conformer_count": 0,
            "linker_energy_spread": None,
            "linker_strain_score": 0.35,
            "warning": "SMILES could not be parsed for linker strain scoring.",
        }
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = 61453
    conf_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=max_conformers, params=params))
    energies: list[float] = []
    for conf_id in conf_ids:
        try:
            AllChem.UFFOptimizeMolecule(mol, confId=conf_id, maxIters=200)
            ff = AllChem.UFFGetMoleculeForceField(mol, confId=conf_id)
            energies.append(float(ff.CalcEnergy()))
        except Exception:
            continue
    if not energies:
        return {
            "linker_conformer_count": len(conf_ids),
            "linker_energy_spread": None,
            "linker_strain_score": 0.4,
            "warning": "RDKit generated no usable UFF energies.",
        }
    spread = max(energies) - min(energies)
    rotors = rdMolDescriptors.CalcNumRotatableBonds(mol)
    strain_score = _clamp(1.0 - spread / 80.0 - max(rotors - 22, 0) / 30.0)
    return {
        "linker_conformer_count": len(energies),
        "linker_energy_spread": round(spread, 3),
        "linker_strain_score": round(strain_score, 3),
        "warning": None,
    }


def score_ternary_pose_for_candidate(
    candidate_id: str,
    pose_pdb: str | Path,
    smiles: str = "",
    target_chain: str = "",
    e3_chain: str = "",
) -> StructuralScore:
    pose_path = Path(pose_pdb)
    warnings: list[str] = []
    if not pose_path.exists():
        return StructuralScore(
            candidate_id=candidate_id,
            pose_file=str(pose_path),
            warnings=[f"Pose PDB does not exist: {pose_path}"],
        )
    atoms = parse_pdb_atoms(pose_path)
    if not atoms:
        return StructuralScore(
            candidate_id=candidate_id,
            pose_file=str(pose_path),
            warnings=["No ATOM/HETATM records found in pose PDB."],
        )
    target_chain, e3_chain = infer_target_e3_chains(atoms, target_chain, e3_chain)
    if target_chain == e3_chain:
        warnings.append("Only one chain found or target/E3 chains overlap; interface score is low-confidence.")
    interface = score_interface(atoms, target_chain, e3_chain)
    lysine = score_lysine_geometry(atoms, target_chain, e3_chain)
    linker = score_linker_strain(smiles)
    for item in [lysine.get("warning"), linker.get("warning")]:
        if item:
            warnings.append(item)
    real_score = _clamp(
        0.34 * interface["interface_quality_score"]
        + 0.31 * lysine["lysine_geometry_score"]
        + 0.20 * linker["linker_strain_score"]
        + 0.15 * (1.0 if interface["interface_contact_count"] else 0.25)
    )
    confidence = _clamp(
        0.35
        + 0.20 * bool(interface["interface_contact_count"])
        + 0.20 * bool(lysine["productive_lysine_count"])
        + 0.15 * bool(linker["linker_conformer_count"])
        + 0.10 * (target_chain != e3_chain)
    )
    return StructuralScore(
        candidate_id=candidate_id,
        pose_file=str(pose_path),
        target_chain=target_chain,
        e3_chain=e3_chain,
        interface_contact_count=interface["interface_contact_count"],
        polar_contact_count=interface["polar_contact_count"],
        clash_count=interface["clash_count"],
        buried_sasa_proxy=interface["buried_sasa_proxy"],
        interface_quality_score=interface["interface_quality_score"],
        nearest_lysine=lysine["nearest_lysine"],
        nearest_lysine_distance_A=lysine["nearest_lysine_distance_A"],
        accessible_lysine_count=lysine["accessible_lysine_count"],
        productive_lysine_count=lysine["productive_lysine_count"],
        lysine_geometry_score=lysine["lysine_geometry_score"],
        linker_conformer_count=linker["linker_conformer_count"],
        linker_energy_spread=linker["linker_energy_spread"],
        linker_strain_score=linker["linker_strain_score"],
        real_structural_score=round(real_score, 3),
        confidence=round(confidence, 3),
        warnings=warnings,
    )
