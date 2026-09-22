"""Structure curation for the frozen benchmarks (RCSB download + selection)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from protacxtend.validation.datasets import CACHE

RCSB = "https://files.rcsb.org/download"
RCSB_LIGAND = "https://files.rcsb.org/ligands/download"

_BLOCK = {
    "HOH", "WAT", "DOD", "NA", "K", "CL", "BR", "IOD", "MG", "CA", "ZN", "MN",
    "FE", "CU", "CO", "NI", "CD", "HG", "SO4", "PO4", "GOL", "EDO", "PEG", "PG4",
    "DMS", "ACT", "FMT", "MPD", "TRS", "NHE", "MES", "EPE", "IMD", "BME", "DTT",
    "NAG", "MAN", "BMA", "FUC", "GAL", "GLC", "NDG", "BGC", "SIA", "FUL", "XYP",
    "HEM", "FAD", "FMN", "NAD", "NAP", "SAM", "SAH", "PLP", "TPP", "ADP", "ATP",
    "GDP", "GTP", "AMP", "GMP", "CMP", "UMP", "ANP", "AGS", "ACP", "TRP", "CIT",
    "TAR", "MLI", "MSE", "SEP", "TPO", "PTR", "CSO", "CME", "KCX", "LLP", "PCA",
}


def download(url: str, dest: Path, *, timeout: int = 60) -> bool:
    import requests

    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except Exception:
        return False


def fetch_structure(pdb_id: str) -> Path:
    dest = CACHE / f"{pdb_id.lower()}.pdb"
    if not download(f"{RCSB}/{pdb_id.upper()}.pdb", dest):
        raise RuntimeError(f"download failed for {pdb_id}")
    return dest


def fetch_ideal_ligand(het: str) -> Path:
    dest = CACHE / f"{het}_ideal.sdf"
    if not download(f"{RCSB_LIGAND}/{het}_ideal.sdf", dest):
        raise RuntimeError(f"no ideal SDF for {het}")
    return dest


# ── protein–ligand complex ──────────────────────────────────────────────

def curate_ligand_complex(pdb_id: str) -> dict[str, Any]:
    """Return receptor PDB, crystal-ligand SDF, docking SMILES and metadata."""
    from Bio.PDB import PDBIO, PDBParser, Select
    from rdkit import Chem

    pdb_id = pdb_id.lower()
    pdb_file = fetch_structure(pdb_id)
    structure = PDBParser(QUIET=True).get_structure(pdb_id, str(pdb_file))[0]

    candidates = []
    for chain in structure:
        for res in chain:
            het = res.get_resname().strip()
            if res.id[0] == " " or het in _BLOCK:
                continue
            n_heavy = sum(1 for a in res if (a.element or "").strip() != "H")
            if n_heavy >= 8:
                candidates.append((n_heavy, chain.id, res))
    if not candidates:
        raise RuntimeError("no drug-like ligand found")
    candidates.sort(key=lambda x: -x[0])
    _n_heavy, lig_chain, lig_res = candidates[0]
    het = lig_res.get_resname().strip()
    ideal_sdf = fetch_ideal_ligand(het)

    # crystal ligand mol; try the RCSB ideal bond orders, then RDKit perception
    lig_pdb = CACHE / f"{pdb_id}_{het}_crystal.pdb"
    lines = []
    for atom in lig_res:
        lines.append(
            f"HETATM{atom.get_serial_number():5d} {atom.get_name():<4s} {het:>3s} A{900:4d}    "
            f"{atom.coord[0]:8.3f}{atom.coord[1]:8.3f}{atom.coord[2]:8.3f}  1.00  0.00          "
            f"{(atom.element or atom.get_name()[0]).strip():>2s}")
    lig_pdb.write_text("\n".join(lines) + "\nEND\n")
    mol = None
    try:
        ideal_mols = [m for m in Chem.SDMolSupplier(str(ideal_sdf), removeHs=False, sanitize=False) if m]
        if ideal_mols:
            mol = _assign_crystal_bonds(lig_pdb, ideal_mols[0])
    except Exception:
        mol = None
    if mol is None:
        mol = _perceive_crystal_bonds(lig_pdb)
    if mol is None or mol.GetNumAtoms() < 8:
        raise RuntimeError("could not build the crystal ligand mol")
    mol = Chem.RemoveHs(mol)

    out_lig = CACHE / f"{pdb_id}_crystal.sdf"
    writer = Chem.SDWriter(str(out_lig))
    writer.write(mol)
    writer.close()

    # docking SMILES from the RCSB ideal template (correct chemistry)
    dock_smiles = ""
    try:
        ideal_mols = [m for m in Chem.SDMolSupplier(str(ideal_sdf), removeHs=False, sanitize=False) if m]
        dock_smiles = Chem.MolToSmiles(Chem.RemoveHs(ideal_mols[0]))
    except Exception:
        dock_smiles = Chem.MolToSmiles(mol)

    class _Prot(Select):
        def accept_residue(self, residue):
            return residue.id[0] == " " and residue.get_resname().strip() != "HOH"

    out_rec = CACHE / f"{pdb_id}_receptor.pdb"
    io = PDBIO()
    io.set_structure(structure)
    io.save(str(out_rec), _Prot())

    conf = mol.GetConformer()
    coords = [list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())]
    centroid = [sum(c[i] for c in coords) / len(coords) for i in range(3)]
    return {
        "pdb_id": pdb_id, "het": het, "lig_chain": lig_chain,
        "receptor": str(out_rec), "ligand_sdf": str(out_lig),
        "smiles": dock_smiles, "n_lig_atoms": mol.GetNumAtoms(),
        "lig_centroid": [round(float(x), 3) for x in centroid],
        "n_candidates": len(candidates),
        "source_file": str(pdb_file),
    }


def _assign_crystal_bonds(lig_pdb: Path, template) -> Any:
    from rdkit import Chem
    from rdkit.Chem import rdDetermineBonds

    raw = Chem.MolFromPDBFile(str(lig_pdb), removeHs=False, sanitize=False)
    if raw is None:
        return None
    raw.UpdatePropertyCache(strict=False)
    charge = int(sum(a.GetFormalCharge() for a in template.GetAtoms()))
    for candidate_charge in (charge, 0, 1, -1):
        trial = Chem.RWMol(raw)
        try:
            rdDetermineBonds.DetermineBonds(trial, charge=candidate_charge)
            return trial.GetMol()
        except Exception:
            continue
    return None


def _perceive_crystal_bonds(lig_pdb: Path) -> Any:
    from rdkit import Chem
    from rdkit.Chem import rdDetermineBonds

    raw = Chem.MolFromPDBFile(str(lig_pdb), removeHs=False, sanitize=False)
    if raw is None:
        return None
    raw.UpdatePropertyCache(strict=False)
    trial = Chem.RWMol(raw)
    try:
        rdDetermineBonds.DetermineConnectivity(trial)
        return trial.GetMol()
    except Exception:
        return None


# ── binary protein–protein complex ──────────────────────────────────────

def curate_binary_complex(pdb_id: str, *, min_residues: int = 15) -> dict[str, Any]:
    """Select the two largest protein chains and write native/receptor/ligand."""
    from Bio.PDB import PDBIO, PDBParser, Select

    pdb_id = pdb_id.lower()
    pdb_file = fetch_structure(pdb_id)
    structure = PDBParser(QUIET=True).get_structure(pdb_id, str(pdb_file))[0]

    chain_sizes = []
    for chain in structure:
        n_res = sum(1 for r in chain if r.id[0] == " ")
        if n_res >= min_residues:
            chain_sizes.append((n_res, chain.id))
    if len(chain_sizes) < 2:
        raise RuntimeError(f"fewer than two protein chains ({len(chain_sizes)})")
    chain_sizes.sort(reverse=True)
    rec_chain, lig_chain = chain_sizes[0][1], chain_sizes[1][1]

    out_dir = CACHE / f"{pdb_id}_ppi"
    out_dir.mkdir(parents=True, exist_ok=True)

    def _save(chain_id: str, dest: Path) -> None:
        class _Ch(Select):
            def accept_chain(self, c):
                return c.id == chain_id

            def accept_residue(self, r):
                return r.id[0] == " "

        io = PDBIO()
        io.set_structure(structure)
        io.save(str(dest), _Ch())

    rec_pdb = out_dir / "receptor.pdb"
    lig_pdb = out_dir / "ligand.pdb"
    _save(rec_chain, rec_pdb)
    _save(lig_chain, lig_pdb)
    return {
        "pdb_id": pdb_id, "receptor_chain": rec_chain, "ligand_chain": lig_chain,
        "receptor_pdb": str(rec_pdb), "ligand_pdb": str(lig_pdb),
        "native_pdb": str(pdb_file),
        "n_chains": len(chain_sizes),
        "receptor_residues": chain_sizes[0][0], "ligand_residues": chain_sizes[1][0],
    }


def protein_chain_ids(pdb_id: str) -> list[str]:
    from Bio.PDB import PDBParser

    structure = PDBParser(QUIET=True).get_structure(pdb_id, str(fetch_structure(pdb_id)))[0]
    return [c.id for c in structure if any(r.id[0] == " " for r in c)]


__all__ = [
    "download", "fetch_structure", "fetch_ideal_ligand", "curate_ligand_complex",
    "curate_binary_complex", "protein_chain_ids",
]
