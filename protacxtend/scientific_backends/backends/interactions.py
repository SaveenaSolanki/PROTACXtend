"""Local structural interaction fingerprint + linker analysis (pure geometry)."""

from __future__ import annotations

import itertools
import math
from pathlib import Path
from typing import Any

import numpy as np

from protacxtend.scientific_backends.dispatch import (
    Availability,
    module_available,
    module_version,
    safe_call,
)
from protacxtend.scientific_backends.evidence import (
    CapabilityStatus,
    EvidenceTier,
    ScientificResult,
)
from protacxtend.scientific_backends.licenses import OPEN_SOURCE_PERMISSIVE
from protacxtend.scientific_backends.registry import Capability, BackendSpec, register

_METALS = {"ZN", "MG", "CA", "FE", "MN", "CU", "CO", "NI"}
_ANIONIC = {"ASP", "GLU"}
_CATIONIC = {"LYS", "ARG", "HIS"}
_AROMATIC = {"PHE", "TYR", "TRP", "HIS"}
_HYDROPHOBIC = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO", "CYS"}


def _atom_records(pdb_path: str, ligand_resname: str = "") -> list[dict[str, Any]]:
    from Bio.PDB import PDBParser

    structure = PDBParser(QUIET=True).get_structure("s", pdb_path)[0]
    records = []
    for chain in structure:
        for residue in chain:
            resname = residue.get_resname().strip()
            is_lig = bool(ligand_resname) and resname == ligand_resname
            for atom in residue:
                element = (atom.element or atom.get_name()[0]).strip().upper()
                if element == "H":
                    continue
                records.append({
                    "coord": atom.coord, "element": element, "resname": resname,
                    "resid": residue.id[1], "chain": chain.id, "name": atom.get_name(),
                    "is_ligand": is_lig,
                    "is_hetero": residue.id[0] != " ",
                })
    return records


def interaction_fingerprint(complex_pdb: str = "", ligand_resname: str = "LIG",
                            hbond_cutoff: float = 3.6, salt_cutoff: float = 4.5,
                            hydrophobic_cutoff: float = 4.5, clash_cutoff: float = 2.0,
                            **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.INTERACTION_FINGERPRINT.value, backend="geometry_fingerprint",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value, approximation=True,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["geometry-based interaction profiling"])
    try:
        if not complex_pdb or not Path(complex_pdb).exists():
            raise FileNotFoundError(f"complex PDB not found: {complex_pdb!r}")
        atoms = _atom_records(complex_pdb, ligand_resname)
        ligand = [a for a in atoms if a["is_ligand"]]
        if not ligand:
            raise ValueError(f"ligand residue '{ligand_resname}' not found")
        protein = [a for a in atoms if not a["is_ligand"] and not a["is_hetero"]]
        waters = [a for a in atoms if a["resname"] in {"HOH", "WAT"} and a["element"] == "O"]

        lig_xyz = np.asarray([a["coord"] for a in ligand])
        prot_xyz = np.asarray([a["coord"] for a in protein]) if protein else np.zeros((0, 3))
        hbonds, salts, hydrophobic, clashes = [], [], [], []
        if len(prot_xyz):
            d = np.linalg.norm(prot_xyz[:, None, :] - lig_xyz[None, :, :], axis=2)
            for pi, li in itertools.product(range(len(protein)), range(len(ligand))):
                pa, la = protein[pi], ligand[li]
                dist = float(d[pi, li])
                if dist < clash_cutoff:
                    clashes.append(_pair(pa, la, dist))
                if la["element"] in {"N", "O"} and pa["element"] in {"N", "O"} and dist <= hbond_cutoff:
                    hbonds.append(_pair(pa, la, dist))
                if dist <= salt_cutoff:
                    if (pa["resname"] in _ANIONIC and la["element"] in {"N"}) or \
                       (pa["resname"] in _CATIONIC and la["element"] in {"O"}):
                        salts.append(_pair(pa, la, dist))
                if pa["element"] == "C" and la["element"] == "C" and dist <= hydrophobic_cutoff \
                        and pa["resname"] in _HYDROPHOBIC:
                    hydrophobic.append(_pair(pa, la, dist))

        metal = []
        for atom in atoms:
            if atom["element"] in _METALS:
                for other in atoms:
                    if other is atom or other["element"] not in {"N", "O", "S"}:
                        continue
                    if float(np.linalg.norm(np.asarray(atom["coord"]) - np.asarray(other["coord"]))) < 2.8:
                        metal.append({"metal": atom["resname"], "resid": atom["resid"],
                                      "partner": f"{other['resname']}{other['resid']}:{other['name']}"})

        water_bridges = []
        for w in waters:
            near_prot = [a for a in protein
                         if float(np.linalg.norm(np.asarray(w["coord"]) - np.asarray(a["coord"]))) < 3.5]
            near_lig = [a for a in ligand
                        if float(np.linalg.norm(np.asarray(w["coord"]) - np.asarray(a["coord"]))) < 3.5]
            if near_prot and near_lig:
                water_bridges.append({"water_chain": w["chain"], "resid": w["resid"],
                                      "protein": f"{near_prot[0]['resname']}{near_prot[0]['resid']}",
                                      "ligand_atom": near_lig[0]["name"]})

        residue_contacts: dict[str, float] = {}
        if len(prot_xyz):
            d = np.linalg.norm(prot_xyz[:, None, :] - lig_xyz[None, :, :], axis=2)
            for pi, pa in enumerate(protein):
                key = f"{pa['resname']}{pa['resid']}"
                best = float(d[pi].min())
                residue_contacts[key] = min(residue_contacts.get(key, 99.0), best)
        contacts = sorted(({"residue": k, "min_distance_A": round(v, 3)}
                           for k, v in residue_contacts.items() if v < 5.0),
                          key=lambda x: x["min_distance_A"])

        result.data = {
            "n_hydrogen_bonds": len(hbonds), "hydrogen_bonds": hbonds[:40],
            "n_salt_bridges": len(salts), "salt_bridges": salts[:40],
            "n_hydrophobic_contacts": len(hydrophobic), "hydrophobic_contacts": hydrophobic[:60],
            "n_metal_coordination": len(metal), "metal_coordination": metal[:20],
            "n_steric_clashes": len(clashes), "steric_clashes": clashes[:20],
            "n_water_bridges": len(water_bridges), "water_bridges": water_bridges[:20],
            "residue_contacts": contacts[:60],
            "pi_pi_interactions": _pi_pi(ligand, protein)[:20],
            "cation_pi_interactions": _cation_pi(ligand, protein)[:20],
        }
        result.summary = (f"fingerprint: {len(hbonds)} H-bond, {len(salts)} salt, "
                          f"{len(hydrophobic)} hydrophobic, {len(clashes)} clash")
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"interaction fingerprint failed: {exc}"
    return result.finish()


def _pair(pa: dict[str, Any], la: dict[str, Any], dist: float) -> dict[str, Any]:
    return {"protein": f"{pa['resname']}{pa['resid']}:{pa['name']}",
            "ligand": la["name"], "distance_A": round(float(dist), 3),
            "chain": pa["chain"]}


def _ring_centroids(records: list[dict[str, Any]], names: set[str]) -> list[np.ndarray]:
    rings = []
    for res, atoms in _group_by_residue(records).items():
        ring_atoms = [a for a in atoms if a["name"] in names and a["element"] == "C"]
        if len(ring_atoms) >= 5:
            rings.append(np.asarray([a["coord"] for a in ring_atoms]).mean(axis=0))
    return rings


def _group_by_residue(records):
    grouped: dict[tuple, list] = {}
    for a in records:
        grouped.setdefault((a["chain"], a["resid"], a["resname"]), []).append(a)
    return grouped


def _ligand_aromatic_centroids(smiles: str) -> list[np.ndarray]:
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return []
        conf = mol.GetConformer() if mol.GetNumConformers() else None
        rings = []
        for ring in mol.GetRingInfo().AtomRings():
            if all(mol.GetAtomWithIdx(i).GetIsAromatic() for i in ring):
                if conf is not None:
                    rings.append(np.asarray([list(conf.GetAtomPosition(i)) for i in ring]).mean(axis=0))
                else:
                    rings.append(np.zeros(3))
        return rings
    except Exception:
        return []


def _pi_pi(ligand, protein) -> list[dict[str, Any]]:
    names = {"CG", "CD1", "CD2", "CE1", "CE2", "CZ", "CH2", "ND1", "NE1", "OH"}
    prot_rings = _ring_centroids([a for a in protein if a["resname"] in _AROMATIC], names)
    out = []
    lig_center = np.asarray([a["coord"] for a in ligand]).mean(axis=0)
    for pc in prot_rings:
        dist = float(np.linalg.norm(pc - lig_center))
        if dist < 6.5:
            out.append({"protein_ring": pc.round(3).tolist(), "distance_A": round(dist, 3)})
    return out


def _cation_pi(ligand, protein) -> list[dict[str, Any]]:
    cat_atoms = [a for a in protein if a["resname"] in _CATIONIC and a["element"] == "N"]
    lig_center = np.asarray([a["coord"] for a in ligand]).mean(axis=0)
    out = []
    for a in cat_atoms:
        dist = float(np.linalg.norm(np.asarray(a["coord"]) - lig_center))
        if dist < 6.5:
            out.append({"protein": f"{a['resname']}{a['resid']}:{a['name']}",
                        "distance_A": round(dist, 3)})
    return out


# ── linker analysis ─────────────────────────────────────────────────────

def linker_analysis(linker_smiles: str = "", warhead_smiles: str = "", e3_smiles: str = "",
                    n_conformers: int = 20, **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.LINKER_ANALYSIS.value, backend="rdkit_linker",
        evidence_tier=EvidenceTier.TIER_1_MINIMIZED.value, approximation=True,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["RDKit conformer analysis of linker geometry"])
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem

        smi = linker_smiles or ""
        if not smi:
            raise ValueError("linker_smiles required (use [*:1]/[*:2] attachment markers)")
        base_mol = Chem.MolFromSmiles(smi)
        if base_mol is None:
            raise ValueError(f"invalid linker SMILES: {smi!r}")
        attach = [a.GetIdx() for a in base_mol.GetAtoms() if a.GetAtomicNum() == 0]
        # replace attachment dummies with methyl carbons so ETKDG can embed them
        rw = Chem.RWMol(base_mol)
        for idx in attach:
            rw.GetAtomWithIdx(idx).SetAtomicNum(6)
            rw.GetAtomWithIdx(idx).SetNoImplicit(False)
        mol = rw.GetMol()
        Chem.SanitizeMol(mol)
        mol = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()
        params.randomSeed = 3
        AllChem.EmbedMultipleConfs(mol, numConfs=max(1, int(n_conformers)), params=params)
        props = AllChem.MMFFGetMoleculeProperties(mol)
        e2e, energies, dihedrals = [], [], []
        # contour length along the attachment-to-attachment path
        contour = 0.0
        if len(attach) >= 2:
            path = Chem.GetShortestPath(mol, attach[0], attach[-1])
            conf0 = mol.GetConformer(0)
            contour = sum(_bond_length(conf0, path[i], path[i + 1]) for i in range(len(path) - 1))
        for cid in range(mol.GetNumConformers()):
            conf = mol.GetConformer(cid)
            if len(attach) >= 2:
                a = np.asarray(conf.GetAtomPosition(attach[0]))
                b = np.asarray(conf.GetAtomPosition(attach[-1]))
                e2e.append(float(np.linalg.norm(a - b)))
            if props is not None:
                ff = AllChem.MMFFGetMoleculeForceField(mol, props, confId=cid)
                if ff is not None:
                    energies.append(float(ff.CalcEnergy()))
            dihedrals.append(round(float(Chem.rdMolTransforms.GetDihedralDeg(
                conf, *[a.GetIdx() for a in list(mol.GetAtoms())[:4]])), 2)
                if mol.GetNumAtoms() >= 4 else 0.0)
        contour = sum(_bond_length(mol.GetConformer(0), b.GetBeginAtomIdx(), b.GetEndAtomIdx())
                      for b in mol.GetBonds()) if mol.GetNumConformers() else 0.0
        strain = (max(energies) - min(energies)) if len(energies) > 1 else 0.0
        result.data = {
            "n_atoms": base_mol.GetNumHeavyAtoms(),
            "n_conformers": mol.GetNumConformers(),
            "contour_length_A": round(contour, 3),
            "end_to_end_distance_A": {"min": round(min(e2e), 3) if e2e else None,
                                      "max": round(max(e2e), 3) if e2e else None,
                                      "mean": round(float(np.mean(e2e)), 3) if e2e else None},
            "linker_strain_kcal_mol": round(strain, 3),
            "dihedral_sample_deg": dihedrals[:20],
        }
        result.summary = (f"linker: contour {round(contour, 1)} Å, "
                          f"strain {round(strain, 1)} kcal/mol")
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"linker analysis failed: {exc}"
    return result.finish()


def _bond_length(conf, i: int, j: int) -> float:
    return float(np.linalg.norm(np.asarray(conf.GetAtomPosition(i)) - np.asarray(conf.GetAtomPosition(j))))


INTERACTION_BACKEND = register(BackendSpec(
    name="geometry_fingerprint",
    capabilities=(Capability.INTERACTION_FINGERPRINT,),
    license=OPEN_SOURCE_PERMISSIVE, priority=80,
    description="Geometry-based protein–ligand interaction fingerprint (H-bond, salt, π, clash, metal).",
    citation="geometry-based interaction profiling",
    health_check=lambda: Availability(available=module_available("Bio"), detail="biopython/numpy"),
    handlers={Capability.INTERACTION_FINGERPRINT: interaction_fingerprint},
))

LINKER_BACKEND = register(BackendSpec(
    name="rdkit_linker",
    capabilities=(Capability.LINKER_ANALYSIS,),
    license=OPEN_SOURCE_PERMISSIVE, priority=80,
    description="Linker geometry: contour length, end-to-end distance, strain, dihedrals.",
    citation="RDKit conformers",
    health_check=lambda: Availability(available=module_available("rdkit"), version=module_version("rdkit"),
                                      detail="rdkit"),
    handlers={Capability.LINKER_ANALYSIS: linker_analysis},
))
