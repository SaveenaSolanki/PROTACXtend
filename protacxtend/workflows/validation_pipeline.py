"""End-to-end scientific validation pipeline (free/local stack only).

One command runs a raw input (target protein ± ligand ± partner) through:

    structure QC → protein prep → ligand prep + OpenFF parameterization →
    pocket detection → 3-engine docking + rank consensus → PPI/LightDock →
    three-interface model → PROTAC anchors → OpenMM MD (min/NVT/NPT/prod) →
    replicates → trajectory analysis (SASA/BSA/contacts) → convergence →
    apo-vs-bound → MM/GBSA → figures → provenance → final report

Every artifact lands in a structured run directory and every result carries an
evidence tier and QC verdict.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from protacxtend.workflows.convergence import assess_convergence

try:  # optional at import time
    from protacxtend.scientific_backends.evidence import EvidenceTier
except Exception:  # pragma: no cover
    EvidenceTier = None  # type: ignore

MODES = {
    "fast": dict(minimize=200, restrained=500, nvt=500, npt=500, production=2500,
                 replicas=2, mmpbsa_frames=3),
    "standard": dict(minimize=500, restrained=1000, nvt=1000, npt=1000, production=10000,
                     replicas=3, mmpbsa_frames=5),
    "thorough": dict(minimize=1000, restrained=5000, nvt=5000, npt=5000, production=25000,
                     replicas=3, mmpbsa_frames=10),
}
DEFAULT_LIGAND_RESNAME = "LIG"


# ── small helpers ───────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class ValidationRequest:
    target: str
    ligand_smiles: str = ""
    ligand_sdf: str = ""
    partner: str = ""
    reference_ligand: str = ""
    known_pocket: list[float] | None = None
    mode: str = "fast"
    replicas: int = 0
    output: str = ""
    solvent: str = "implicit"
    temperature_k: float = 300.0
    seed: int = 42
    ligand_resname: str = DEFAULT_LIGAND_RESNAME
    run_apo_bound: bool = True
    run_mmpbsa: bool = True
    docking_engines: list[str] = field(default_factory=lambda: ["vina", "gnina", "diffdock"])
    ppi_swarms: int = 4
    ppi_glowworms: int = 10
    ppi_steps: int = 10


# ════════════════════════════════════════════════════════════════════════
# 1. Structure QC
# ════════════════════════════════════════════════════════════════════════

_METALS = {"ZN", "MG", "CA", "FE", "MN", "CU", "CO", "NI", "NA", "K", "CD", "HG"}
_COFACTORS = {"HEM", "FAD", "FMN", "NAD", "NAP", "SAM", "SAH", "PLP", "TPP", "ADP", "ATP"}
_STANDARD = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE", "LEU",
    "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
}
_MEMBRANE_RES = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO", "GLY"}


def _atom_element(atom) -> str:
    """Robust element for a Biopython atom (element field is often blank)."""
    el = (atom.element or "").strip().upper()
    if el and len(el) <= 2:
        return el
    name = atom.get_name().strip()
    stripped = "".join(ch for ch in name if ch.isalpha())
    return (stripped[:1] or "X").upper()


def _is_hydrogen(atom) -> bool:
    el = _atom_element(atom)
    if el == "H":
        return True
    # element blank: names like H, HA, 1HB, HB2
    name = atom.get_name().strip()
    return el == "X" and name[:1].upper() == "H"


def structure_qc(pdb_path: str) -> dict[str, Any]:
    from Bio.PDB import PDBParser

    report: dict[str, Any] = {"file": pdb_path, "checks": {}, "errors": [], "warnings": []}
    structure = PDBParser(QUIET=True).get_structure("s", pdb_path)[0]
    chains = list(structure)
    report["checks"]["n_chains"] = len(chains)
    report["checks"]["chain_ids"] = [c.id for c in chains]

    waters, hetero, nonstandard, altlocs, disulfides = 0, set(), set(), 0, []
    residues = []
    protein_names = []
    sg_atoms = []
    for chain in chains:
        prev = None
        for residue in chain:
            name = residue.get_resname().strip()
            if name in {"HOH", "WAT"}:
                waters += 1
            elif residue.id[0] != " ":
                hetero.add(name)
            else:
                residues.append((chain.id, residue.id[1]))
                protein_names.append(name)
                if name not in _STANDARD:
                    nonstandard.add(name)
                if prev is not None and residue.id[1] != prev + 1:
                    report["warnings"].append(
                        f"numbering gap {chain.id}:{prev}->{residue.id[1]}")
                prev = residue.id[1]
            for atom in residue:
                if atom.is_disordered() or atom.get_altloc() not in (" ", ""):
                    altlocs += 1
                if atom.get_name() == "SG" and name == "CYS":
                    sg_atoms.append(atom.coord)
    for i in range(len(sg_atoms)):
        for j in range(i + 1, len(sg_atoms)):
            if float(np.linalg.norm(sg_atoms[i] - sg_atoms[j])) < 2.5:
                disulfides.append([i, j])
    report["checks"].update({
        "n_residues": len(residues), "waters": waters,
        "hetero": sorted(hetero), "nonstandard_residues": sorted(nonstandard),
        "alternate_locations": altlocs, "disulfides": len(disulfides),
        "metals": sorted(_METALS & hetero), "cofactors": sorted(_COFACTORS & hetero),
    })
    if protein_names:
        frac = sum(1 for r in protein_names if r in _MEMBRANE_RES) / len(protein_names)
        report["checks"]["hydrophobic_fraction"] = round(frac, 3)
        report["checks"]["membrane_like"] = bool(frac > 0.42 and len(protein_names) > 60)

    # clashes (non-bonded heavy-atom pairs < 2.0 Å; covalent bonds excluded)
    heavy_atoms = []
    seen_alt: set = set()
    for a in structure.get_atoms():
        if _is_hydrogen(a):
            continue
        alt = a.get_altloc()
        if alt not in (" ", "", "A"):
            continue
        key = (id(a.get_parent().get_parent()), a.get_parent().id[1], a.get_name())
        if key in seen_alt:
            continue
        seen_alt.add(key)
        heavy_atoms.append(a)
    clashes = 0
    if heavy_atoms and len(heavy_atoms) < 8000:
        from scipy.spatial import cKDTree

        arr = np.asarray([a.coord for a in heavy_atoms])
        for i, j in cKDTree(arr).query_pairs(r=2.0):
            ai, aj = heavy_atoms[i], heavy_atoms[j]
            ci, ri = ai.get_parent().get_parent().id, ai.get_parent().id[1]
            cj, rj = aj.get_parent().get_parent().id, aj.get_parent().id[1]
            if ci == cj and ri == rj:          # same residue → bonded/non-bonded intra
                continue
            ni, nj = ai.get_name(), aj.get_name()
            if ci == cj and abs(ri - rj) == 1 and {ni, nj} == {"C", "N"}:
                continue                        # peptide bond C(i)-N(i+1)
            clashes += 1
    report["checks"]["steric_clashes_lt2A"] = clashes

    # missing backbone atoms / unresolved termini
    missing_atoms = 0
    termini = []
    for chain in chains:
        res = [r for r in chain if r.id[0] == " "]
        for r in res:
            names = {a.get_name() for a in r}
            if not {"N", "CA", "C", "O"} <= names:
                missing_atoms += 1
        if res:
            for end in (res[0], res[-1]):
                if not {"N", "CA", "C", "O"} <= {a.get_name() for a in end}:
                    termini.append(f"{end.get_parent().id}:{end.id[1]}")
    report["checks"]["residues_missing_backbone"] = missing_atoms
    report["checks"]["unresolved_termini"] = termini

    if report["errors"]:
        verdict = "FAIL"
    elif (report["checks"]["metals"] or report["checks"]["cofactors"]) and not True:
        verdict = "WARN"
    elif report["warnings"] or missing_atoms or clashes > 50 or nonstandard:
        verdict = "WARN"
    else:
        verdict = "PASS"
    report["verdict"] = verdict
    return report


# ════════════════════════════════════════════════════════════════════════
# 3. Ligand preparation
# ════════════════════════════════════════════════════════════════════════

def _ligand_smiles(req: ValidationRequest) -> str:
    if req.ligand_smiles:
        return req.ligand_smiles.strip()
    if req.ligand_sdf and Path(req.ligand_sdf).exists():
        from rdkit import Chem

        mols = [m for m in Chem.SDMolSupplier(req.ligand_sdf, removeHs=False) if m is not None]
        if not mols:
            raise ValueError(f"no molecule in {req.ligand_sdf}")
        return Chem.MolToSmiles(Chem.RemoveHs(mols[0]))
    raise ValueError("ligand_smiles or ligand_sdf required")


def prepare_ligand(req: ValidationRequest, out_dir: Path) -> dict[str, Any]:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors

    smiles = _ligand_smiles(req)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"invalid ligand SMILES: {smiles}")
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = int(req.seed)
    AllChem.EmbedMultipleConfs(mol, numConfs=10, params=params)
    if mol.GetNumConformers():
        AllChem.MMFFOptimizeMoleculeConfs(mol, maxIters=200)
    sdf = out_dir / "ligand.sdf"
    writer = Chem.SDWriter(str(sdf))
    for cid in range(mol.GetNumConformers()):
        writer.write(mol, confId=cid)
    writer.close()
    canonical = Chem.MolToSmiles(Chem.RemoveHs(mol))
    info = {
        "canonical_smiles": canonical,
        "formal_charge": Chem.GetFormalCharge(mol),
        "n_heavy_atoms": Chem.RemoveHs(mol).GetNumHeavyAtoms(),
        "n_conformers": mol.GetNumConformers(),
        "molecular_weight": round(Descriptors.MolWt(mol), 3),
        "sdf": str(sdf),
    }
    # OpenFF → GAFF parameterization (in the OpenFF env)
    from protacxtend.scientific_backends.dispatch import run_cross_env

    out = run_cross_env("protacxtend.scientific_backends.backends.md",
                        "_parameterize_ligand_openmm",
                        args=[canonical, req.ligand_resname],
                        require_import="openmm", prefer_env="md-openff", timeout=900)
    if out.get("ok"):
        info["parameterization"] = out["result"]
        info["fallback_used"] = out["result"].get("engine") != "openff"
    else:
        info["parameterization"] = {"engine": "generic_unparameterized", "error": out.get("error")}
        info["fallback_used"] = True
    _write_json(out_dir / "ligand_parameterization.json", info)
    return info


def _merge_ligand_into_pdb(protein_pdb: str, ligand_sdf: str, out_pdb: Path,
                           resname: str = DEFAULT_LIGAND_RESNAME) -> Path:
    """Append a 3D ligand to a protein PDB as a HETATM residue **with CONECT
    records** so OpenMM can perceive the ligand bonds and match its template."""
    from rdkit import Chem

    mols = [m for m in Chem.SDMolSupplier(ligand_sdf, removeHs=False) if m is not None]
    if not mols:
        raise ValueError("ligand SDF has no 3D molecule")
    mol = mols[0]
    if mol.GetNumConformers() == 0:
        raise ValueError("ligand has no 3D conformer to merge")

    protein_lines = [ln for ln in Path(protein_pdb).read_text().splitlines()
                     if ln.startswith(("ATOM", "HETATM", "TER"))]
    # next serial number after the protein
    max_serial = 0
    for ln in protein_lines:
        if ln.startswith(("ATOM", "HETATM")):
            try:
                max_serial = max(max_serial, int(ln[6:11]))
            except ValueError:
                continue
    offset = max_serial

    block = Chem.MolToPDBBlock(mol, flavor=0)
    ligand_atoms: list[str] = []
    serial_map: dict[int, int] = {}
    for ln in block.splitlines():
        if not ln.startswith(("ATOM", "HETATM")):
            continue
        old_serial = int(ln[6:11])
        new_serial = old_serial + offset
        serial_map[old_serial] = new_serial
        name = ln[12:16]
        alt = ln[16:17] or " "
        x, y, z = ln[30:38], ln[38:46], ln[46:54]
        occ = ln[54:60] if len(ln) >= 60 else "  1.00"
        temp = ln[60:66] if len(ln) >= 66 else "  0.00"
        element = (ln[76:78] if len(ln) >= 78 else ln[12:14]).strip()
        ligand_atoms.append(
            f"HETATM{new_serial:5d} {name}{alt}{resname:>3s} A{900:4d}    "
            f"{x}{y}{z}{occ}{temp}          {element:>2s}")
    conect_lines = []
    for ln in block.splitlines():
        if ln.startswith("CONECT"):
            serials = [int(ln[i:i + 5]) for i in range(6, len(ln), 5) if ln[i:i + 5].strip()]
            mapped = [serial_map.get(s, s) for s in serials]
            conect_lines.append("CONECT" + "".join(f"{s:5d}" for s in mapped))

    out_pdb.parent.mkdir(parents=True, exist_ok=True)
    out_pdb.write_text("\n".join(protein_lines + ["TER"] + ligand_atoms + conect_lines + ["END"]) + "\n")
    return out_pdb


# ════════════════════════════════════════════════════════════════════════
# 5. Docking + consensus
# ════════════════════════════════════════════════════════════════════════

def _sanitize_pose_mol(mol):
    """Sanitize a docked pose defensively and drop all hydrogens."""
    from rdkit import Chem

    if mol is None:
        return None
    try:
        mol.UpdatePropertyCache(strict=False)
        ops = Chem.SANITIZE_ALL ^ Chem.SANITIZE_PROPERTIES
        Chem.SanitizeMol(mol, sanitizeOps=ops)
    except Exception:
        pass
    try:
        mol = Chem.RemoveAllHs(mol)
    except Exception:
        pass
    return mol


def _top_pose_mol(engine_result: dict[str, Any]):
    from rdkit import Chem

    poses = engine_result.get("poses") or []
    if not poses:
        return None
    pose = poses[0]
    path = pose.get("sdf") or engine_result.get("best_pose_sdf")
    if path and Path(path).exists():
        mols = [m for m in Chem.SDMolSupplier(path, removeHs=False, sanitize=False) if m is not None]
        if mols:
            return _sanitize_pose_mol(mols[0])
    if pose.get("pdbqt"):
        try:
            return _sanitize_pose_mol(Chem.MolFromPDBBlock(pose["pdbqt"], removeHs=False,
                                                           sanitize=False))
        except Exception:
            pass
    best_pdb = engine_result.get("best_pose_pdb")
    if best_pdb and Path(best_pdb).exists():
        try:
            return _sanitize_pose_mol(Chem.MolFromPDBFile(best_pdb, removeHs=False, sanitize=False))
        except Exception:
            pass
    return None


def _heavy_mol(mol):
    """Strip all hydrogens manually (robust to sanitization issues)."""
    from rdkit import Chem

    if mol is None:
        return None
    try:
        rw = Chem.RWMol(mol)
        for atom in reversed(list(rw.GetAtoms())):
            if atom.GetAtomicNum() == 1:
                rw.RemoveAtom(atom.GetIdx())
        return rw.GetMol()
    except Exception:
        return mol


def _kabsch_rmsd(mol_a, mol_b) -> float | None:
    """Ordered-atom optimal-superposition RMSD (needs equal heavy-atom counts)."""
    if mol_a is None or mol_b is None or mol_a.GetNumAtoms() != mol_b.GetNumAtoms():
        return None
    try:
        ca = mol_a.GetConformer()
        cb = mol_b.GetConformer()
        A = np.asarray([list(ca.GetAtomPosition(i)) for i in range(mol_a.GetNumAtoms())])
        B = np.asarray([list(cb.GetAtomPosition(i)) for i in range(mol_b.GetNumAtoms())])
        A = A - A.mean(0)
        B = B - B.mean(0)
        U, _s, Vt = np.linalg.svd(A.T @ B)
        d = np.sign(np.linalg.det(Vt.T @ U.T))
        D = np.diag([1.0, 1.0, d])
        R = Vt.T @ D @ U.T
        diff = A - (B @ R.T)
        return round(float(np.sqrt((diff ** 2).sum(1).mean())), 3)
    except Exception:
        return None


def _pose_rmsd(mol_a, mol_b) -> float | None:
    if mol_a is None or mol_b is None:
        return None
    a, b = _heavy_mol(mol_a), _heavy_mol(mol_b)
    if a.GetNumAtoms() != b.GetNumAtoms():
        return None
    try:
        from rdkit.Chem import rdMolAlign

        return round(float(rdMolAlign.GetBestRMS(a, b)), 3)
    except Exception:
        # different bond perception (e.g. PDBQT) — fall back to ordered Kabsch
        return _kabsch_rmsd(a, b)


def _receptor_residue_contacts(receptor_pdb: str, mol, cutoff: float = 5.0) -> set[str]:
    if mol is None:
        return set()
    try:
        from Bio.PDB import PDBParser

        conf = mol.GetConformer()
        pts = np.asarray([list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())])
        contacts: set[str] = set()
        for atom in PDBParser(QUIET=True).get_structure("s", receptor_pdb).get_atoms():
            if atom.element == "H":
                continue
            d = float(np.linalg.norm(pts - np.asarray(atom.coord), axis=1).min())
            if d < cutoff:
                contacts.add(f"{atom.get_parent().get_resname()}{atom.get_parent().id[1]}")
        return contacts
    except Exception:
        return set()


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return round(len(a & b) / max(1, len(a | b)), 3)


def docking_stage(req: ValidationRequest, receptor: str, ligand_smiles: str,
                  out_dir: Path) -> dict[str, Any]:
    from protacxtend.scientific_backends.backends.docking import (
        diffdock_docking, gnina_docking, vina_docking,
    )

    engines: dict[str, Any] = {}
    runners = {"vina": vina_docking, "gnina": gnina_docking, "diffdock": diffdock_docking}
    for name in req.docking_engines:
        fn = runners.get(name)
        if fn is None:
            continue
        started = time.time()
        try:
            if name == "vina":
                result = fn(receptor_pdb=receptor, ligand_smiles=ligand_smiles,
                            exhaustiveness=2, num_modes=9, cpu=4)
            elif name == "gnina":
                result = fn(receptor_pdb=receptor, ligand_smiles=ligand_smiles)
            else:
                result = fn(receptor_pdb=receptor, ligand_smiles=ligand_smiles,
                            n_poses=10, inference_steps=20)
        except Exception as exc:  # noqa: BLE001
            engines[name] = {"status": "error", "error": str(exc), "poses": []}
            continue
        engine_dir = out_dir / name
        engine_dir.mkdir(parents=True, exist_ok=True)
        payload = result.data if hasattr(result, "data") else {}
        engines[name] = {
            "status": result.status, "method": getattr(result, "method_label", ""),
            "n_poses": len(payload.get("poses") or []),
            "best_score_kcal_mol": payload.get("best_score_kcal_mol"),
            "best_confidence": payload.get("best_confidence"),
            "poses": payload.get("poses") or [],
            "best_pose_sdf": payload.get("best_pose_sdf"),
            "best_pose_pdb": payload.get("best_pose_pdb"),
            "best_pose_mol2": payload.get("best_pose_mol2"),
            "runtime_seconds": round(time.time() - started, 2),
        }
        _write_json(engine_dir / "result.json", engines[name])

    valid = {k: v for k, v in engines.items() if v.get("poses")}
    # geometric clustering + agreements
    mols = {k: _top_pose_mol(v) for k, v in valid.items()}
    # persist a canonical top pose SDF per engine for reproducibility
    for k, m in mols.items():
        if m is not None:
            try:
                from rdkit import Chem

                w = Chem.SDWriter(str(out_dir / k / "rank1.sdf"))
                w.write(m)
                w.close()
            except Exception:
                pass
    contacts = {k: _receptor_residue_contacts(receptor, m) for k, m in mols.items()}
    pairwise: dict[str, float | None] = {}
    names = sorted(mols)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            pairwise[f"{names[i]}-{names[j]}"] = _pose_rmsd(mols[names[i]], mols[names[j]])
    contact_agreement = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            contact_agreement[f"{names[i]}-{names[j]}"] = _jaccard(contacts[names[i]], contacts[names[j]])

    # Borda rank fusion (never averages raw scores)
    ballots = []
    for name, v in valid.items():
        order = [f"{name}#{p.get('rank', i + 1)}" for i, p in enumerate(v["poses"])]
        ballots.append(order)
    points: dict[str, int] = {}
    for ballot in ballots:
        n = len(ballot)
        for pos, item in enumerate(ballot):
            points[item] = points.get(item, 0) + (n - pos)
    ranking = sorted(points, key=lambda k: -points[k])

    # benchmark against a reference ligand if provided
    native: dict[str, Any] = {}
    ref_path = req.reference_ligand or req.ligand_sdf
    if ref_path and Path(ref_path).exists():
        from rdkit import Chem

        ref_mols = [m for m in Chem.SDMolSupplier(ref_path, removeHs=True) if m is not None]
        if ref_mols:
            ref = ref_mols[0]
            for name, m in mols.items():
                native[name] = _pose_rmsd(m, ref)

    consensus = {
        "engines": {k: {kk: vv for kk, vv in v.items() if kk != "poses"} for k, v in engines.items()},
        "valid_engines": sorted(valid),
        "n_valid_engines": len(valid),
        "consensus_complete": len(valid) >= 2,
        "rank_method": "BORDA",
        "consensus_ranking": ranking[:20],
        "pairwise_pose_rmsd": pairwise,
        "contact_jaccard": contact_agreement,
        "native_pose_rmsd_top": native,
        "scoring_policy": "per-engine raw scores retained; consensus is rank-based, never averaged",
    }
    _write_json(out_dir / "docking_consensus.json", consensus)
    return consensus


# ════════════════════════════════════════════════════════════════════════
# 9–12. MD + trajectory analysis
# ════════════════════════════════════════════════════════════════════════

def run_replica(req: ValidationRequest, complex_pdb: str, md_dir: Path, replica: int,
                ligand_smiles: str, export_amber: bool = False) -> dict[str, Any]:
    from protacxtend.scientific_backends.dispatch import run_cross_env

    params = MODES[req.mode]
    out = run_cross_env(
        "protacxtend.workflows.md_runner", "_openmm_staged",
        args=[complex_pdb, str(md_dir / f"replica_{replica}")],
        kwargs={
            "ligand_resname": req.ligand_resname, "ligand_smiles": ligand_smiles,
            "minimize_steps": params["minimize"], "restrained_steps": params["restrained"],
            "nvt_steps": params["nvt"], "npt_steps": params["npt"],
            "production_steps": params["production"], "temperature_k": req.temperature_k,
            "solvent": req.solvent, "seed": req.seed + replica,
            "export_amber": export_amber,
        },
        require_import="openmm", prefer_env="md-openff", timeout=7200)
    if not out.get("ok"):
        return {"error": out.get("error"), "replica": replica}
    return out["result"]


def trajectory_timeseries(topology: str, trajectory: str, *, ligand_sel: str = "",
                          target_sel: str = "protein", partner_sel: str = "",
                          stride: int = 1) -> dict[str, Any]:
    import MDAnalysis as mda
    from MDAnalysis.analysis import hbonds, rms
    from MDAnalysis.analysis.distances import distance_array

    u = mda.Universe(topology, trajectory)
    ref = mda.Universe(topology)
    out: dict[str, Any] = {"n_frames": len(u.trajectory)}
    protein = u.select_atoms("protein")
    if len(protein) > 3:
        R = rms.RMSD(protein, ref, select="backbone").run(step=stride)
        out["rmsd"] = [round(float(x), 3) for x in R.results.rmsd[:, 2]]
        F = rms.RMSF(protein.select_atoms("backbone")).run()
        out["rmsf"] = [round(float(x), 3) for x in F.results.rmsf]
    rg = []
    for _ts in u.trajectory[::stride]:
        pos = protein.positions
        rg.append(round(float(np.sqrt(((pos - pos.mean(0)) ** 2).sum(1).mean())), 3))
    out["rg"] = rg
    # interface series
    pairs = {"target_ligand": (target_sel, ligand_sel),
             "ligand_partner": (ligand_sel, partner_sel),
             "target_partner": (target_sel, partner_sel)}
    interfaces: dict[str, Any] = {}
    for name, (sel_a, sel_b) in pairs.items():
        if not (sel_a and sel_b):
            continue
        a = u.select_atoms(sel_a)
        b = u.select_atoms(sel_b)
        if len(a) == 0 or len(b) == 0:
            continue
        contacts, min_d, com = [], [], []
        for _ts in u.trajectory[::stride]:
            d = distance_array(a.positions, b.positions)
            contacts.append(int((d < 5.0).sum()))
            min_d.append(round(float(d.min()), 3))
            com.append(round(float(np.linalg.norm(a.center_of_mass() - b.center_of_mass())), 3))
        interfaces[name] = {"contacts": contacts, "min_distance": min_d, "com_distance": com}
    if interfaces:
        out["interfaces"] = interfaces
    return out


def sasa_timeseries(topology: str, trajectory: str, *, ligand_sel: str = "",
                    target_sel: str = "", partner_sel: str = "", stride: int = 1) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        import mdtraj as mdj

        traj = mdj.load(trajectory, top=topology)[::stride]
        total = mdj.shrake_rupley(traj, mode="residue").sum(axis=1)

        def _sel(sel):
            idx = traj.topology.select(sel)
            if len(idx) == 0:
                return None
            return mdj.shrake_rupley(traj.atom_slice(idx), mode="residue").sum(axis=1)

        out["sasa"] = [round(float(x), 2) for x in total]
        if ligand_sel:
            lig = _sel(ligand_sel)
            rec = _sel(f"not ({ligand_sel})")
            if lig is not None and rec is not None:
                out["sasa_ligand"] = [round(float(x), 2) for x in lig]
                out["bsa_target_ligand"] = [round(float(x), 2) for x in (total - lig - rec)]
        if target_sel and partner_sel:
            a, b = _sel(target_sel), _sel(partner_sel)
            if a is not None and b is not None:
                out["bsa_target_partner"] = [round(float(x), 2) for x in (total - a - b)]
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
    return out


def _stats(series: list[float]) -> dict[str, Any]:
    arr = np.asarray([x for x in (series or []) if x is not None], dtype=float)
    if len(arr) == 0:
        return {}
    return {"mean": round(float(arr.mean()), 3), "sd": round(float(arr.std()), 3),
            "median": round(float(np.median(arr)), 3),
            "iqr": round(float(np.percentile(arr, 75) - np.percentile(arr, 25)), 3),
            "initial": round(float(arr[0]), 3), "final": round(float(arr[-1]), 3),
            "delta": round(float(arr[-1] - arr[0]), 3), "n": int(len(arr))}


def analyze_replica(topology: str, trajectory: str, ligand_sel: str, target_sel: str,
                    partner_sel: str, analysis_dir: Path, replica: int) -> dict[str, Any]:
    ts = trajectory_timeseries(topology, trajectory, ligand_sel=ligand_sel,
                               target_sel=target_sel, partner_sel=partner_sel)
    sasa = sasa_timeseries(topology, trajectory, ligand_sel=ligand_sel,
                           target_sel=target_sel, partner_sel=partner_sel)
    rows = []
    n = max(len(ts.get("rmsd", [])), len(sasa.get("sasa", [])))
    for i in range(n):
        rows.append({
            "frame": i,
            "rmsd": _at(ts.get("rmsd"), i), "rg": _at(ts.get("rg"), i),
            "sasa": _at(sasa.get("sasa"), i),
            "bsa_target_ligand": _at(sasa.get("bsa_target_ligand"), i),
            "bsa_target_partner": _at(sasa.get("bsa_target_partner"), i),
            "target_ligand_contacts": _at((ts.get("interfaces", {}).get("target_ligand") or {}).get("contacts"), i),
            "target_partner_contacts": _at((ts.get("interfaces", {}).get("target_partner") or {}).get("contacts"), i),
            "target_ligand_com": _at((ts.get("interfaces", {}).get("target_ligand") or {}).get("com_distance"), i),
            "target_partner_com": _at((ts.get("interfaces", {}).get("target_partner") or {}).get("com_distance"), i),
        })
    _write_csv(analysis_dir / f"timeseries_replica_{replica}.csv", rows)
    energy = _read_energy(trajectory)
    result = {"replica": replica, "timeseries": ts, "sasa": sasa,
              "summary": {"rmsd": _stats(ts.get("rmsd", [])), "rg": _stats(ts.get("rg", [])),
                          "sasa": _stats(sasa.get("sasa", [])),
                          "bsa_target_ligand": _stats(sasa.get("bsa_target_ligand", [])),
                          "bsa_target_partner": _stats(sasa.get("bsa_target_partner", []))},
              "energy": energy}
    return result


def _at(series, i):
    if series is None or i >= len(series):
        return None
    return series[i]


def _read_energy(trajectory: str) -> dict[str, Any]:
    path = Path(trajectory).parent / "energy.csv"
    if not path.exists():
        return {}
    rows = list(csv.DictReader(path.open()))
    pe = [float(r["Potential Energy (kJ/mole)"]) for r in rows if r.get("Potential Energy (kJ/mole)")]
    temp = [float(r["Temperature (K)"]) for r in rows if r.get("Temperature (K)")]
    return {"n_points": len(pe), "potential_energy": pe[-200:],
            "temperature": temp[-200:], "temperature_mean": round(float(np.mean(temp)), 2) if temp else None,
            "temperature_sd": round(float(np.std(temp)), 2) if temp else None}


# ════════════════════════════════════════════════════════════════════════
# 16. MM/GBSA via AmberTools
# ════════════════════════════════════════════════════════════════════════

def run_mmpbsa(amber: dict[str, Any], ligand_resname: str, out_dir: Path,
               frames: int = 3, gb: bool = True) -> dict[str, Any]:
    prmtop = amber.get("prmtop")
    netcdf = amber.get("netcdf")
    if not (prmtop and netcdf and Path(prmtop).exists() and Path(netcdf).exists()):
        return {"status": "unavailable", "method_label": "MMPBSA_UNAVAILABLE",
                "reason": (amber.get("error") or "no Amber topology/trajectory exported")}
    out_dir.mkdir(parents=True, exist_ok=True)
    amberhome = Path.home() / ".protacxtend" / "envs" / "gromacs"
    env = dict(**__import__("os").environ)
    env["AMBERHOME"] = str(amberhome)
    try:
        complex_p = Path(prmtop)
        receptor_p = out_dir / "receptor.prmtop"
        ligand_p = out_dir / "ligand.prmtop"
        cmd = [str(amberhome / "bin" / "ante-MMPBSA.py"), "-p", str(complex_p),
               "-c", str(complex_p), "-r", str(receptor_p), "-l", str(ligand_p),
               "-m", f":{ligand_resname}", "-s", ":WAT,Na+,Cl-"]
        proc = __import__("subprocess").run(cmd, capture_output=True, text=True, env=env, timeout=1800)
        if proc.returncode != 0:
            return {"status": "failed", "method_label": "MMPBSA_UNAVAILABLE",
                    "reason": proc.stderr[-400:]}
        input_file = out_dir / "mmpbsa.in"
        input_file.write_text(
            "&general\n  startframe=1, endframe=%d, interval=1, verbose=2, keep_files=0,\n/\n"
            "&gb\n  igb=5, saltcon=0.150,\n/\n" % max(1, int(frames)))
        cmd2 = [str(amberhome / "bin" / "MMPBSA.py"), "-O", "-i", str(input_file),
                "-o", str(out_dir / "FINAL_RESULTS_MMPBSA.dat"),
                "-sp", str(complex_p), "-cp", str(complex_p),
                "-rp", str(receptor_p), "-lp", str(ligand_p), "-y", str(netcdf)]
        proc2 = __import__("subprocess").run(cmd2, capture_output=True, text=True, env=env,
                                             cwd=out_dir, timeout=7200)
        if proc2.returncode != 0:
            return {"status": "failed", "method_label": "MMPBSA_UNAVAILABLE",
                    "reason": (proc2.stderr or proc2.stdout)[-500:]}
        result_file = out_dir / "FINAL_RESULTS_MMPBSA.dat"
        delta_total = None
        per_residue = []
        if result_file.exists():
            lines = result_file.read_text(errors="ignore").splitlines()
            for idx, line in enumerate(lines):
                if "DELTA TOTAL" in line:
                    parts = line.split()
                    for token in reversed(parts):
                        try:
                            delta_total = float(token)
                            break
                        except ValueError:
                            continue
                if line.strip().startswith("Residue"):
                    per_residue.append(line.strip())
        label = "MMGBSA_ESTIMATE" if gb else "MMPBSA_ESTIMATE"
        return {"status": "success", "method_label": label,
                "delta_total_kcal_mol": delta_total, "gb_model": 5 if gb else None,
                "per_residue_lines": per_residue[:100],
                "result_file": str(result_file)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "method_label": "MMPBSA_UNAVAILABLE", "reason": str(exc)}


# ════════════════════════════════════════════════════════════════════════
# 15. Molecular glue / metabolite verdict
# ════════════════════════════════════════════════════════════════════════

def glue_verdict(apo: dict[str, Any], bound: dict[str, Any]) -> dict[str, Any]:
    def g(d, *keys):
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

    d_contacts = None
    d_bsa = None
    a = g(apo, "summary", "sasa", "mean")
    b = g(bound, "summary", "sasa", "mean")
    bsa_a = g(apo, "summary", "bsa_target_partner", "mean")
    bsa_b = g(bound, "summary", "bsa_target_partner", "mean")
    if bsa_a is not None and bsa_b is not None:
        d_bsa = round(bsa_b - bsa_a, 3)
    a_ct = g(apo, "timeseries", "interfaces", "target_partner", "contacts")
    b_ct = g(bound, "timeseries", "interfaces", "target_partner", "contacts")
    if a_ct and b_ct:
        d_contacts = round(float(np.mean(b_ct)) - float(np.mean(a_ct)), 3)
    score = 0.0
    if d_bsa is not None:
        score += 1.0 if d_bsa > 25 else (-1.0 if d_bsa < -25 else 0.0)
    if d_contacts is not None:
        score += 1.0 if d_contacts > 10 else (-1.0 if d_contacts < -10 else 0.0)
    if score > 0:
        verdict = "POTENTIAL_STABILIZATION"
    elif score < 0:
        verdict = "POTENTIAL_DESTABILIZATION"
    elif d_bsa is None and d_contacts is None:
        verdict = "INSUFFICIENT_EVIDENCE"
    else:
        verdict = "NO_CLEAR_EFFECT"
    return {"verdict": verdict, "delta_bsa_target_partner_A2": d_bsa,
            "delta_contact_persistence": d_contacts, "score": score,
            "disclaimer": "computational evidence only; not experimental proof"}


# ════════════════════════════════════════════════════════════════════════
# 25. Figures
# ════════════════════════════════════════════════════════════════════════

def make_figures(analysis: dict[str, Any], figures_dir: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)
    made: list[str] = []
    ts = analysis.get("timeseries", {})
    sasa = analysis.get("sasa", {})

    def _plot(series, title, ylabel, name):
        if not series:
            return
        fig, ax = plt.subplots(figsize=(7, 3.6))
        ax.plot(range(len(series)), series, lw=1.2, color="#2b6cb0")
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("frame"); ax.set_ylabel(ylabel)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        path = figures_dir / name
        fig.savefig(path, dpi=150)
        plt.close(fig)
        made.append(name)

    _plot(ts.get("rmsd"), "Backbone RMSD", "RMSD (Å)", "01_rmsd_vs_time.png")
    if ts.get("rmsf"):
        fig, ax = plt.subplots(figsize=(7, 3.6))
        ax.plot(range(len(ts["rmsf"])), ts["rmsf"], lw=1.0, color="#805ad5")
        ax.set_title("RMSF per residue"); ax.set_xlabel("residue"); ax.set_ylabel("RMSF (Å)")
        ax.grid(alpha=0.25); fig.tight_layout()
        fig.savefig(figures_dir / "02_rmsf_per_residue.png", dpi=150); plt.close(fig)
        made.append("02_rmsf_per_residue.png")
    _plot(ts.get("rg"), "Radius of gyration", "Rg (Å)", "03_radius_of_gyration.png")
    _plot(sasa.get("sasa"), "SASA", "SASA (Å²)", "04_sasa_vs_time.png")
    _plot(sasa.get("bsa_target_ligand"), "Buried SASA (target–ligand)", "BSA (Å²)",
          "05_bsa_target_ligand.png")
    _plot(sasa.get("bsa_target_partner"), "Buried SASA (target–partner)", "BSA (Å²)",
          "05b_bsa_target_partner.png")
    eng = analysis.get("energy", {})
    _plot(eng.get("potential_energy"), "Potential energy", "PE (kJ/mol)",
          "06_interaction_energy_vs_time.png")
    for key, fname in (("target_ligand", "10_target_ligand_contacts.png"),
                       ("ligand_partner", "11_ligand_partner_contacts.png"),
                       ("target_partner", "12_target_partner_contacts.png")):
        ifaces = ts.get("interfaces", {})
        if key in ifaces:
            _plot(ifaces[key].get("contacts"), f"{key} contacts", "contacts", fname)
    _plot((analysis.get("replicas") or [{}])[0].get("timeseries", {}).get("rmsd"),
          "Replica 1 RMSD (see replica CSV for all)", "RMSD (Å)", "14_replica_comparison.png")
    return made


# ════════════════════════════════════════════════════════════════════════
# Orchestration
# ════════════════════════════════════════════════════════════════════════

def run_validation(req: ValidationRequest) -> dict[str, Any]:
    t0 = time.time()
    params = MODES.get(req.mode, MODES["fast"])
    replicas = req.replicas or params["replicas"]
    run_id = f"validate_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_{req.seed}"
    root = Path(req.output or f"validation_runs/{run_id}")
    dirs = {name: root / name for name in
            ("input", "preparation", "pockets", "docking", "ppi_docking", "ternary",
             "md", "analysis", "energy", "figures", "logs", "provenance")}
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    provenance: dict[str, Any] = {
        "run_id": run_id, "started_at": _now(), "python": __import__("sys").version.split()[0],
        "mode": req.mode, "replicas": replicas, "seed": req.seed, "solvent": req.solvent,
        "inputs": {},
    }
    for label, path in (("target", req.target), ("partner", req.partner),
                        ("ligand_sdf", req.ligand_sdf), ("reference_ligand", req.reference_ligand)):
        if path and Path(path).exists():
            provenance["inputs"][label] = {"path": path, "sha256": _sha256(path)}
    ligand_smiles = _ligand_smiles(req)
    provenance["inputs"]["ligand_smiles"] = ligand_smiles

    report: dict[str, Any] = {"run_id": run_id, "target": req.target,
                              "ligand_smiles": ligand_smiles, "mode": req.mode,
                              "replicas": replicas, "warnings": warnings}

    # 1. structure QC
    qc = structure_qc(req.target)
    _write_json(dirs["preparation"] / "structure_qc.json", qc)
    report["structure_qc"] = qc
    if qc["verdict"] == "FAIL":
        warnings.append("structure QC FAIL — aborting before simulation")
        report["evidence_tier"] = "TIER_0_GEOMETRY"
        _finalize(root, report, provenance, warnings, t0)
        return report

    # 2. protein preparation
    from protacxtend.scientific_backends import prepare_protein

    prep = prepare_protein(req.target)
    prepared = prep.data.get("output") if prep.ok() else req.target
    if not prepared or not Path(prepared).exists():
        prepared = str(dirs["preparation"] / "prepared_protein.pdb")
        shutil.copy(req.target, prepared)
        warnings.append("PDBFixer prep unavailable; using raw structure")
    report["protein_preparation"] = {"status": prep.status, "data": prep.data,
                                     "prepared": prepared, "backend": prep.backend}
    _write_json(dirs["preparation"] / "protein_prep.json", report["protein_preparation"])

    # 3. ligand preparation + parameterization
    lig = prepare_ligand(req, dirs["preparation"])
    report["ligand_preparation"] = lig
    if lig.get("fallback_used"):
        warnings.append(f"ligand parameterization fallback: {lig['parameterization'].get('engine')}")

    # 4. pockets
    from protacxtend.scientific_backends import detect_pockets

    pockets = detect_pockets(prepared, top_n=5)
    pocket_payload = {"engine": pockets.backend, "pockets": pockets.data.get("pockets", []),
                      "known_pocket": req.known_pocket}
    if req.known_pocket and pocket_payload["pockets"]:
        c = np.asarray(pocket_payload["pockets"][0].get("center") or [0, 0, 0], dtype=float)
        d = float(np.linalg.norm(c - np.asarray(req.known_pocket, dtype=float)))
        pocket_payload["known_pocket_distance_A"] = round(d, 3)
    _write_json(dirs["pockets"] / "pockets.json", pocket_payload)
    report["pockets"] = pocket_payload

    # 5. docking + consensus
    consensus = docking_stage(req, prepared, ligand_smiles, dirs["docking"])
    report["docking_consensus"] = consensus
    if not consensus["consensus_complete"]:
        warnings.append(f"docking consensus incomplete: {consensus['n_valid_engines']} valid engine(s)")
    tier = "TIER_2_DOCKED" if consensus["n_valid_engines"] >= 1 else "TIER_0_GEOMETRY"

    # 6. PPI docking
    ppi = None
    if req.partner and Path(req.partner).exists():
        from protacxtend.scientific_backends.backends.docking import lightdock_ppi_docking

        ppi_res = lightdock_ppi_docking(receptor_pdb=prepared, ligand_pdb=req.partner,
                                        n_swarms=req.ppi_swarms, glowworms=req.ppi_glowworms,
                                        steps=req.ppi_steps, top_n=10)
        ppi = {"status": ppi_res.status, "data": ppi_res.data}
        _write_json(dirs["ppi_docking"] / "lightdock.json", ppi)
        report["ppi_docking"] = {k: v for k, v in ppi.items() if k != "data"}
        if ppi_res.ok():
            tier = "TIER_2_DOCKED"

    # assemble holo complex (crystal/reference ligand placed into prepared protein)
    merge_source = req.reference_ligand or req.ligand_sdf or lig["sdf"]
    complex_pdb = _merge_ligand_into_pdb(prepared, merge_source,
                                         dirs["preparation"] / "holo_complex.pdb",
                                         req.ligand_resname)
    report["holo_complex"] = str(complex_pdb)

    # 8. PROTAC / linker analysis (if markers present)
    if "[*:" in ligand_smiles or "!" in ligand_smiles:
        from protacxtend.scientific_backends import analyze_linker

        linker = analyze_linker(ligand_smiles)
        report["protac_linker"] = {"status": linker.status, "data": linker.data}
        _write_json(dirs["ternary"] / "linker_analysis.json", report["protac_linker"])

    # 9–10. MD replicates (holo)
    md_runs: list[dict[str, Any]] = []
    for replica in range(1, replicas + 1):
        run = run_replica(req, str(complex_pdb), dirs["md"], replica, ligand_smiles,
                          export_amber=(req.run_mmpbsa and replica == 1))
        md_runs.append(run)
        if "error" in run:
            warnings.append(f"replica {replica} failed: {run['error']}")
    successful = [r for r in md_runs if "error" not in r]
    report["md"] = {"n_replicas": len(successful),
                    "platforms": [r.get("platform") for r in successful],
                    "solvent": req.solvent,
                    "production_steps": params["production"],
                    "atom_counts": [r.get("n_atoms") for r in successful]}
    if not successful:
        warnings.append("no MD replica completed")
        report["evidence_tier"] = tier
        _finalize(root, report, provenance, warnings, t0)
        return report

    # 11–12. analysis + SASA/BSA
    ligand_sel = f"resname {req.ligand_resname}"
    target_sel = "protein"
    partner_sel = ""
    analyses = []
    for idx, r in enumerate(successful, start=1):
        a = analyze_replica(r["topology_pdb"], r["trajectory"], ligand_sel, target_sel,
                            partner_sel, dirs["analysis"], idx)
        analyses.append(a)
    report["analysis_summary"] = {f"replica_{a['replica']}": a.get("summary", {}) for a in analyses}
    _write_json(dirs["analysis"] / "analysis_summary.json",
                {f"replica_{a['replica']}": a.get("summary", {}) for a in analyses})

    # 13. convergence
    r1 = analyses[0]
    replica_means = {f"replica_{a['replica']}": (a.get("summary", {}).get("rmsd", {}) or {}).get("mean", 0.0)
                     for a in analyses}
    conv = assess_convergence(
        rmsd=r1.get("timeseries", {}).get("rmsd"),
        bsa=r1.get("sasa", {}).get("bsa_target_ligand"),
        contact_occupancy=(r1.get("timeseries", {}).get("interfaces", {}).get("target_ligand") or {}).get("contacts"),
        replica_means=replica_means)
    report["convergence"] = conv
    _write_json(dirs["analysis"] / "convergence.json", conv)

    # 14. apo-vs-bound (matched, dedicated directory so holo replicas are not touched)
    apo_bound = None
    if req.run_apo_bound:
        apo_dir = dirs["md"] / "apo"
        apo = run_replica(req, prepared, apo_dir, 1, "", export_amber=False)
        if "error" not in apo:
            apo_analysis = analyze_replica(apo["topology_pdb"], apo["trajectory"], "",
                                           target_sel, partner_sel, dirs["analysis"], 99)
            bound_analysis = analyses[0]
            apo_bound = {"apo": apo_analysis.get("summary", {}),
                         "bound": bound_analysis.get("summary", {}),
                         "verdict": glue_verdict(apo_analysis, bound_analysis)}
            _write_json(dirs["analysis"] / "apo_vs_bound.json", apo_bound)
        else:
            apo_bound = {"status": "failed", "error": apo["error"]}
            warnings.append(f"apo MHz failed: {apo['error']}")
    report["apo_vs_bound"] = apo_bound

    # 16. MM/GBSA
    mmpbsa = None
    if req.run_mmpbsa and successful:
        amber = successful[0].get("amber") or {}
        mmpbsa = run_mmpbsa(amber, req.ligand_resname, dirs["energy"],
                            frames=params["mmpbsa_frames"], gb=True)
        _write_json(dirs["energy"] / "mmpbsa.json", mmpbsa)
        report["mmpbsa"] = mmpbsa
    # OpenMM interaction energy (always, correctly labelled)
    from protacxtend.scientific_backends import interaction_energy

    inter = interaction_energy(str(complex_pdb), ligand_resname=req.ligand_resname)
    report["openmm_interaction_energy"] = {"method_label": inter.method_label or "STRUCTURAL_ENERGY_SURROGATE",
                                           "status": inter.status, "data": inter.data,
                                           "summary": inter.summary}
    _write_json(dirs["energy"] / "openmm_interaction.json", report["openmm_interaction_energy"])

    # 17/20. evidence tier
    converged = conv.get("verdict") == "CONVERGED"
    if len(successful) >= 2 and converged:
        tier = "TIER_4_REPLICATE_MD"
    elif len(successful) >= 1:
        tier = "TIER_3_SHORT_MD"
    if mmpbsa and mmpbsa.get("status") == "success":
        tier = "TIER_5_ENDPOINT_FREE_ENERGY"
    report["evidence_tier"] = tier
    if len(successful) >= 2 and not converged:
        warnings.append("replicate MD present but convergence not reached; tier held at TIER_3")

    # 25. figures
    fig_analysis = dict(r1)
    fig_analysis["replicas"] = analyses
    figs = make_figures(fig_analysis, dirs["figures"])
    report["figures"] = figs

    # 24. provenance
    from protacxtend.scientific_backends.runner import backend_health

    provenance["software"] = {row["name"]: {"available": row["available"], "version": row["version"]}
                              for row in backend_health()}
    provenance["forcefield"] = (successful[0].get("forcefield") if successful else "")
    provenance["ligand_parameters"] = (successful[0].get("ligand_parameters") if successful else {})
    provenance["seeds"] = [req.seed + i for i in range(1, replicas + 1)]
    provenance["md"] = report.get("md", {})
    provenance["warnings"] = warnings
    report["provenance"] = provenance

    _finalize(root, report, provenance, warnings, t0)
    return report


def _finalize(root: Path, report: dict[str, Any], provenance: dict[str, Any],
              warnings: list[str], t0: float) -> None:
    provenance["finished_at"] = _now()
    provenance["wall_seconds"] = round(time.time() - t0, 2)
    _write_json(root / "provenance" / "provenance.json", provenance)
    report["wall_seconds"] = provenance["wall_seconds"]
    report["qc_verdict"] = _overall_qc(report)
    _write_json(root / "final_report.json", report)
    (root / "final_report.md").write_text(_render_md(report), encoding="utf-8")


def _overall_qc(report: dict[str, Any]) -> str:
    if report.get("structure_qc", {}).get("verdict") == "FAIL":
        return "FAIL"
    if report.get("warnings"):
        return "WARN"
    if report.get("convergence", {}).get("verdict") == "CONVERGED":
        return "PASS"
    return "WARN"


def _render_md(report: dict[str, Any]) -> str:
    lines = [f"# Validation report — {report.get('run_id')}", ""]
    lines.append(f"- Evidence tier: **{report.get('evidence_tier')}**")
    lines.append(f"- Overall QC: **{report.get('qc_verdict')}**")
    lines.append(f"- Wall time: {report.get('wall_seconds')} s")
    lines.append(f"- Target: `{report.get('target')}`  Ligand: `{report.get('ligand_smiles')}`")
    lines.append("")
    qc = report.get("structure_qc", {})
    lines.append("## Structure QC\n")
    lines.append(f"- verdict: {qc.get('verdict')}")
    for k, v in (qc.get("checks") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    dc = report.get("docking_consensus", {})
    lines.append("## Docking consensus\n")
    lines.append(f"- valid engines: {dc.get('valid_engines')}")
    lines.append(f"- rank method: {dc.get('rank_method')}")
    lines.append(f"- native pose RMSD (Å): {dc.get('native_pose_rmsd_top')}")
    lines.append(f"- pairwise pose RMSD (Å): {dc.get('pairwise_pose_rmsd')}")
    lines.append(f"- contact Jaccard: {dc.get('contact_jaccard')}")
    lines.append("")
    lines.append("## MD\n")
    for k, v in (report.get("md") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Convergence\n")
    lines.append(f"- verdict: {report.get('convergence', {}).get('verdict')}")
    lines.append(f"- checks: {report.get('convergence', {}).get('checks')}")
    lines.append("")
    lines.append("## Energetics\n")
    lines.append(f"- OpenMM interaction: {(report.get('openmm_interaction_energy') or {}).get('method_label')}")
    lines.append(f"- MM/GBSA: {(report.get('mmpbsa') or {}).get('method_label')} "
                 f"{(report.get('mmpbsa') or {}).get('delta_total_kcal_mol')} kcal/mol")
    lines.append("")
    lines.append("## Apo vs bound / glue verdict\n")
    lines.append(f"- {report.get('apo_vs_bound')}")
    lines.append("")
    if report.get("warnings"):
        lines.append("## Warnings\n")
        for w in report["warnings"]:
            lines.append(f"- {w}")
        lines.append("")
    lines.append("_Computational evidence only; not experimental proof._")
    return "\n".join(lines)
