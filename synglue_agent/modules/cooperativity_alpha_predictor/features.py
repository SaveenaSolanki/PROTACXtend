"""Structural + molecular features for cooperativity (Module 3).

Structural features reuse the Module 2 structural toolkit (PDB parser +
numeric Shrake-Rupley SASA) so ternary-complex infrastructure is not
duplicated. Molecular descriptors use RDKit (records without SMILES are
supported on the structural path only).
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from synglue_agent.modules.cooperativity_alpha_predictor.schemas import (
    InterfaceFeatures,
    MolecularFeatures,
)
from synglue_agent.modules.lysine_ubiquitination_feasibility.core import (
    Atom,
    LysineScorerError,
    read_pdb,
    shrake_rupley_sasa,
)

logger = logging.getLogger("protacxtend.cooperativity_features")

VDW = {"C": 1.7, "N": 1.55, "O": 1.52, "S": 1.8, "P": 1.8}
CONTACT_CUT = 4.5
HBOND_CUT = 3.5
SALT_CUT = 4.0
HYDROPHOBIC_CUT = 4.5


def _atom_pairs_by_chain(atoms: list[Atom], chain_a: str, chain_b: str
                         ) -> tuple[list[Atom], list[Atom], dict[tuple, Atom]]:
    a_list = [a for a in atoms if a.chain == chain_a]
    b_list = [a for a in atoms if a.chain == chain_b]
    keyed = {(a.chain, a.resname, a.resseq, a.name): a for a in atoms}
    return a_list, b_list, keyed


def _interface_analysis(atoms: list[Atom], chain_a: str, chain_b: str,
                        sasa_complex: dict[int, float],
                        sasa_a: dict[int, float], sasa_b: dict[int, float],
                        radii: dict[str, float]) -> dict[str, Any]:
    """Pair-wise interface analysis between two chains."""
    a_list = [a for a in atoms if a.chain == chain_a]
    b_list = [a for a in atoms if a.chain == chain_b]
    coords_b = np.array([a.coord for a in b_list])

    contacts = 0
    hbonds = 0
    salts = 0
    hydrophobic = 0
    clashes = 0
    res_a: set = set()
    res_b: set = set()

    def _is_salt(a: Atom, b: Atom) -> bool:
        pos = {"ARG": {"NH1", "NH2", "NE"}, "LYS": {"NZ"}, "HIS": {"ND1", "NE2"}}
        neg = {"ASP": {"OD1", "OD2"}, "GLU": {"OE1", "OE2"}}
        return ((a.resname in pos and a.name in pos[a.resname] and b.resname in neg and b.name in neg[b.resname])
                or (b.resname in pos and b.name in pos[b.resname] and a.resname in neg and a.name in neg[a.resname]))

    for atom in a_list:
        d = np.linalg.norm(coords_b - atom.coord, axis=1)
        for bj in np.where(d <= CONTACT_CUT)[0]:
            other = b_list[bj]
            dist = float(d[bj])
            contacts += 1
            res_a.add(atom.resseq)
            res_b.add(other.resseq)
            els = {atom.element, other.element}
            if "C" in els and len(els) == 1:
                hydrophobic += 1
            if dist <= HBOND_CUT and atom.element in ("N", "O") and other.element in ("N", "O"):
                hbonds += 1  # heavy-atom donor/acceptor proxy (documented approximation)
            if dist <= SALT_CUT and _is_salt(atom, other):
                salts += 1
            r_sum = radii.get(atom.element, 1.7) + radii.get(other.element, 1.7)
            if dist < 0.75 * r_sum:
                clashes += 1

    # buried surface area (classic BSA = (SASA_A + SASA_B - SASA_complex)/2)
    sasa_tot_a = sum(v for i, v in sasa_a.items())
    sasa_tot_b = sum(v for i, v in sasa_b.items())
    sasa_tot_c = sum(v for i, v in sasa_complex.items())
    bsa = max(0.0, (sasa_tot_a + sasa_tot_b - sasa_tot_c) / 2.0)
    return {"bsa": bsa, "contacts": contacts, "hbonds": hbonds, "salts": salts,
            "hydrophobic": hydrophobic, "clashes": clashes,
            "interface_residues": len(res_a | res_b),
            "residue_set_a": sorted(res_a), "residue_set_b": sorted(res_b)}


def interface_features(
    structure_paths: list[str],
    poi_chain: str,
    e3_chain: str,
    probe: float = 1.4,
    n_dots: int = 64,
    radii: dict[str, float] | None = None,
) -> tuple[InterfaceFeatures, list[dict[str, Any]]]:
    """Interface features over one or several ternary pose(s) (ensemble)."""
    radii = radii or dict(VDW)
    per_pose: list[dict[str, Any]] = []
    if not structure_paths:
        raise LysineScorerError("no structure provided for interface features")
    for path in structure_paths:
        atoms = read_pdb(path)
        complex_sasa = shrake_rupley_sasa(atoms, probe, n_dots, radii)
        atoms_a = [a for a in atoms if a.chain == poi_chain]
        atoms_b = [a for a in atoms if a.chain == e3_chain]
        if not atoms_a or not atoms_b:
            raise LysineScorerError(
                f"poi_chain={poi_chain!r} or e3_chain={e3_chain!r} missing in {path}")
        sasa_a_alone = shrake_rupley_sasa(atoms_a, probe, n_dots, radii)
        sasa_b_alone = shrake_rupley_sasa(atoms_b, probe, n_dots, radii)
        full_index = {id(a): i for i, a in enumerate(atoms)}
        full_a = {full_index[id(atoms_a[i])]: v for i, v in sasa_a_alone.items()}
        full_b = {full_index[id(atoms_b[i])]: v for i, v in sasa_b_alone.items()}
        analysis = _interface_analysis(atoms, poi_chain, e3_chain,
                                       complex_sasa, full_a, full_b, radii)
        analysis["n_atoms"] = len(atoms)
        per_pose.append(analysis)

    if not per_pose:
        raise LysineScorerError("no analyzable pose")
    bsas = [p["bsa"] for p in per_pose]
    # ensemble interface conservation = mean pairwise Jaccard of interface residues
    jaccards = []
    for i in range(len(per_pose)):
        set_i = set(per_pose[i]["residue_set_a"]) | set(per_pose[i]["residue_set_b"])
        for j in range(i + 1, len(per_pose)):
            set_j = set(per_pose[j]["residue_set_a"]) | set(per_pose[j]["residue_set_b"])
            union = set_i | set_j
            jaccards.append(len(set_i & set_j) / len(union) if union else 0.0)
    relstd = (float(np.std(bsas)) / max(float(np.mean(bsas)), 1e-9)) if len(bsas) > 1 else 0.0
    feat = InterfaceFeatures(
        buried_surface_area_angstrom2=round(float(np.mean(bsas)), 2),
        intermolecular_contacts=int(np.mean([p["contacts"] for p in per_pose])),
        putative_hbonds=int(np.mean([p["hbonds"] for p in per_pose])),
        salt_bridges=int(np.mean([p["salts"] for p in per_pose])),
        hydrophobic_contacts=int(np.mean([p["hydrophobic"] for p in per_pose])),
        steric_clashes=int(np.mean([p["clashes"] for p in per_pose])),
        interface_residue_count=int(np.mean([p["interface_residues"] for p in per_pose])),
        ensemble_bsa_relstd=round(relstd, 4),
        ensemble_interface_jaccard=round(float(np.mean(jaccards)), 4) if jaccards else 0.0,
        n_poses=len(per_pose),
    )
    return feat, per_pose


def molecular_features(smiles: str | None) -> MolecularFeatures:
    """RDKit 2D descriptors (deterministic). Empty when SMILES unavailable."""
    if not smiles:
        return MolecularFeatures(available=False)
    try:
        from rdkit import Chem
        from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return MolecularFeatures(available=False)
        rings = rdMolDescriptors.CalcNumAromaticRings(mol)
        return MolecularFeatures(
            available=True,
            mol_wt=round(float(Descriptors.MolWt(mol)), 2),
            clogp=round(float(Crippen.MolLogP(mol)), 3),
            tpsa=round(float(rdMolDescriptors.CalcTPSA(mol)), 2),
            rotatable_bonds=int(Lipinski.NumRotatableBonds(mol)),
            hbd=int(Lipinski.NumHDonors(mol)),
            hba=int(Lipinski.NumHAcceptors(mol)),
            aromatic_rings=int(rings),
        )
    except Exception:
        return MolecularFeatures(available=False)
