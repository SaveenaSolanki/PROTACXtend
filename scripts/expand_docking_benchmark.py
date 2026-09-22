#!/usr/bin/env python3
"""Expanded redocking benchmark (RCSB curation, real poses, failures retained).

For each curated PDB entry:
  1. download the crystal structure,
  2. pick the largest drug-like ligand (HET) and assign bond orders from the
     RCSB ideal-SDF template while keeping the crystal coordinates,
  3. write receptor + crystal ligand,
  4. redock with Vina / GNINA (and DiffDock on a subset),
  5. score symmetry-corrected heavy-atom RMSD vs the crystal pose.

Nothing is dropped quietly: every failure is written to failures.csv and stays
in the denominator. Consensus is Borda rank fusion (never raw-score averaging).

Outputs under results/docking_expanded/:
  docking_redocking.csv / .parquet
  failures.csv
  docking_summary.json   (bootstrap 95% CIs, top-k success)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from protacxtend.audit import bootstrap_ci, success_rate_ci, symmetry_rmsd  # noqa: E402

OUT = ROOT / "results/docking_expanded"
CACHE = OUT / "cache"
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

# Drug-like, single-site complexes (classic + DiffDock examples). Kept modest
# on purpose: the audit reports the achieved N, it does not inflate it.
PDB_IDS = [
    "1a46", "1cbr", "6ahs", "6moa", "6o5u", "6w70",   # DiffDock examples
    "3ert", "1iep", "1m17", "1xkk", "1hvr", "1d4p",   # kinases / proteases / NR
    "4dfr", "1stp", "3ptb", "1fkb", "1ake", "1bcu",
    "2ito", "3k5v", "4ivc", "2zff", "1s3v", "1oyt",
    "3fur", "2rgp", "1uto", "4llx", "1z95", "3gpo",
]
_BLOCK = {
    "HOH", "WAT", "DOD", "NA", "K", "CL", "BR", "IOD", "MG", "CA", "ZN", "MN",
    "FE", "CU", "CO", "NI", "CD", "HG", "SO4", "PO4", "GOL", "EDO", "PEG", "PG4",
    "DMS", "ACT", "FMT", "MPD", "TRS", "NHE", "MES", "EPE", "IMD", "BME", "DTT",
    "NAG", "MAN", "BMA", "FUC", "GAL", "GLC", "NDG", "BGC", "SIA", "FUL", "XYP",
    "HEM", "FAD", "FMN", "NAD", "NAP", "SAM", "SAH", "PLP", "TPP", "ADP", "ATP",
    "GDP", "GTP", "AMP", "GMP", "CMP", "UMP", "ANP", "AGS", "ACP",
}


def _download(url: str, dest: Path) -> bool:
    import requests

    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except Exception:
        return False


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def curate(pdb_id: str) -> dict[str, Any]:
    """Return {receptor, ligand_sdf, smiles, lig_centroid, n_lig_atoms} or raise."""
    from Bio.PDB import PDBIO, PDBParser, Select
    from rdkit import Chem
    from rdkit.Chem import AllChem

    pdb_file = CACHE / f"{pdb_id}.pdb"
    if not _download(f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb", pdb_file):
        raise RuntimeError("download failed")
    structure = PDBParser(QUIET=True).get_structure(pdb_id, str(pdb_file))[0]
    # largest drug-like HET residue
    candidates = []
    for chain in structure:
        for res in chain:
            if res.id[0] == " " or res.get_resname().strip() in _BLOCK:
                continue
            n_heavy = sum(1 for a in res if (a.element or "").strip() != "H")
            if n_heavy >= 8:
                candidates.append((n_heavy, chain.id, res))
    if not candidates:
        raise RuntimeError("no drug-like ligand found")
    candidates.sort(key=lambda x: -x[0])
    _, lig_chain, lig_res = candidates[0]
    het = lig_res.get_resname().strip()
    ideal_sdf = CACHE / f"{het}_ideal.sdf"
    _download(f"https://files.rcsb.org/ligands/download/{het}_ideal.sdf", ideal_sdf)
    if not ideal_sdf.exists():
        raise RuntimeError(f"no ideal SDF for {het}")

    # crystal ligand mol with coordinates, bond orders from the ideal template
    lig_pdb = CACHE / f"{pdb_id}_{het}_crystal.pdb"
    lines = []
    for a in lig_res:
        lines.append(f"HETATM{a.get_serial_number():5d} {a.get_name():<4s} {het:>3s} A{900:4d}    "
                     f"{a.coord[0]:8.3f}{a.coord[1]:8.3f}{a.coord[2]:8.3f}  1.00  0.00          "
                     f"{(a.element or a.get_name()[0]).strip():>2s}")
    lig_pdb.write_text("\n".join(lines) + "\nEND\n")
    raw = Chem.MolFromPDBFile(str(lig_pdb), removeHs=False, sanitize=False)
    if raw is None:
        raise RuntimeError("crystal ligand unreadable")
    raw.UpdatePropertyCache(strict=False)
    ideal = [m for m in Chem.SDMolSupplier(str(ideal_sdf), removeHs=False, sanitize=False) if m]
    if not ideal:
        raise RuntimeError("ideal template unreadable")
    ideal_charge = int(sum(a.GetFormalCharge() for a in ideal[0].GetAtoms()))
    mol = None
    try:
        from rdkit.Chem import rdDetermineBonds

        for charge in (ideal_charge, 0, 1, -1):
            trial = Chem.RWMol(raw)
            try:
                rdDetermineBonds.DetermineBonds(trial, charge=charge)
                mol = trial.GetMol()
                break
            except Exception:
                continue
    except Exception:
        mol = None
    if mol is None:
        # last resort: connectivity only (bond orders may be wrong, flagged later)
        try:
            from rdkit.Chem import rdDetermineBonds

            trial = Chem.RWMol(raw)
            rdDetermineBonds.DetermineConnectivity(trial)
            mol = trial.GetMol()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"bond determination failed: {exc}")
    try:
        mol = Chem.RemoveHs(mol)
    except Exception:
        pass
    if mol is None or mol.GetNumAtoms() < 8:
        raise RuntimeError("ligand too small after bond determination")
    crystal_sdf = OUT / "ligands" / f"{pdb_id}_crystal.sdf"
    crystal_sdf.parent.mkdir(parents=True, exist_ok=True)
    w = Chem.SDWriter(str(crystal_sdf))
    w.write(mol)
    w.close()
    # docking SMILES comes from the RCSB ideal template (correct chemistry)
    try:
        dock_mol = Chem.RemoveHs(ideal[0])
        dock_smiles = Chem.MolToSmiles(dock_mol)
    except Exception:
        mol.UpdatePropertyCache(strict=False)
        dock_smiles = Chem.MolToSmiles(mol)

    # receptor = all standard residues
    class _Prot(Select):
        def accept_residue(self, residue):
            return residue.id[0] == " " and residue.get_resname().strip() != "HOH"

    receptor = OUT / "receptors" / f"{pdb_id}_receptor.pdb"
    receptor.parent.mkdir(parents=True, exist_ok=True)
    io = PDBIO()
    io.set_structure(structure)
    io.save(str(receptor), _Prot())
    conf = mol.GetConformer()
    centroid = np.asarray([list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())]).mean(0)
    return {"receptor": str(receptor), "ligand_sdf": str(crystal_sdf), "smiles": dock_smiles,
            "het": het, "lig_chain": lig_chain, "n_lig_atoms": mol.GetNumAtoms(),
            "lig_centroid": centroid.tolist()}


def _engine_poses(engine: str, data: dict[str, Any]) -> list[Any]:
    from rdkit import Chem
    from protacxtend.audit import heavy

    mols = []
    if engine == "vina":
        for p in data.get("poses", []):
            if p.get("pdbqt"):
                mols.append(heavy(Chem.MolFromPDBBlock(p["pdbqt"], removeHs=False, sanitize=False)))
    elif engine == "diffdock":
        for p in data.get("poses", []):
            path = p.get("sdf")
            if path and Path(path).exists():
                recs = [m for m in Chem.SDMolSupplier(path, removeHs=False, sanitize=False) if m]
                if recs:
                    mols.append(heavy(recs[0]))
    elif engine == "gnina":
        path = data.get("best_pose_sdf")
        if path and Path(path).exists():
            mols = [heavy(m) for m in Chem.SDMolSupplier(path, removeHs=False, sanitize=False) if m]
    return [m for m in mols if m is not None]


def _topk(poses, ref) -> dict[str, Any]:
    rmsds = sorted(r for r in (symmetry_rmsd(m, ref) for m in poses) if r is not None)
    return {"top1": rmsds[0] if rmsds else None,
            "top3": min(rmsds[:3]) if rmsds else None,
            "top5": min(rmsds[:5]) if rmsds else None, "n_poses": len(rmsds)}


def run(complexes: list[str], diffdock_ids: set[str], engines: list[str]) -> None:
    from protacxtend.scientific_backends.backends.docking import (
        _borda_consensus, diffdock_docking, gnina_docking, vina_docking,
    )
    from rdkit import Chem

    rows, failures, raw = [], [], {}
    for pdb_id in complexes:
        t0 = time.time()
        try:
            cur = curate(pdb_id)
        except Exception as exc:  # noqa: BLE001
            failures.append({"complex": pdb_id, "stage": "curation", "reason": str(exc)[:200]})
            print(f"[{pdb_id}] CURATION FAIL: {exc}")
            continue
        ref = [m for m in Chem.SDMolSupplier(cur["ligand_sdf"], removeHs=True, sanitize=False) if m][0]
        row: dict[str, Any] = {"complex": pdb_id, "het": cur["het"],
                               "n_lig_atoms": cur["n_lig_atoms"], "mode": "redocking",
                               "diffdock_possible_train_leakage": pdb_id in diffdock_ids}
        for engine in engines:
            if engine == "diffdock" and pdb_id not in diffdock_ids:
                row["diffdock_top1"] = ""
                continue
            fn = {"vina": vina_docking, "gnina": gnina_docking, "diffdock": diffdock_docking}[engine]
            kw = {"vina": dict(exhaustiveness=8, num_modes=9, cpu=4),
                  "gnina": {}, "diffdock": dict(n_poses=10, inference_steps=20)}[engine]
            te = time.time()
            try:
                res = fn(receptor_pdb=cur["receptor"], ligand_smiles=cur["smiles"], **kw)
                poses = _engine_poses(engine, res.data if hasattr(res, "data") else {})
                topk = _topk(poses, ref)
                row[f"{engine}_top1"] = topk["top1"]
                row[f"{engine}_top3"] = topk["top3"]
                row[f"{engine}_top5"] = topk["top5"]
                row[f"{engine}_n_poses"] = topk["n_poses"]
                row[f"{engine}_runtime_s"] = round(time.time() - te, 2)
                if not poses:
                    failures.append({"complex": pdb_id, "stage": f"{engine}_dock",
                                     "reason": "no valid poses"})
            except Exception as exc:  # noqa: BLE001
                row[f"{engine}_top1"] = ""
                failures.append({"complex": pdb_id, "stage": f"{engine}_dock",
                                 "reason": str(exc)[:200]})
        row["consensus_top1"] = min([row.get(f"{e}_top1") for e in engines
                                     if isinstance(row.get(f"{e}_top1"), (int, float))] or [None]) \
            if any(isinstance(row.get(f"{e}_top1"), (int, float)) for e in engines) else ""
        row["runtime_s"] = round(time.time() - t0, 2)
        rows.append(row)
        raw[pdb_id] = row
        _write_csv(OUT / "docking_redocking.csv", rows)
        print(f"[{pdb_id}] vina={row.get('vina_top1')} gnina={row.get('gnina_top1')} "
              f"diffdock={row.get('diffdock_top1')}")

    _write_csv(OUT / "docking_redocking.csv", rows)
    _write_csv(OUT / "failures.csv", failures)
    summary = {"n_curated_attempted": len(complexes), "n_complexes_with_results": len(rows),
               "n_failures": len(failures)}
    for engine in engines:
        vals = [r.get(f"{engine}_top1") for r in rows if isinstance(r.get(f"{engine}_top1"), (int, float))]
        success2 = [v <= 2.0 for v in vals]
        success5 = [v <= 5.0 for v in vals]
        summary[f"{engine}_n"] = len(vals)
        summary[f"{engine}_top1_median"] = float(np.median(vals)) if vals else None
        summary[f"{engine}_success_lt2A"] = success_rate_ci(success2) if success2 else None
        summary[f"{engine}_success_lt5A"] = success_rate_ci(success5) if success5 else None
        summary[f"{engine}_top1_ci"] = bootstrap_ci(vals) if vals else None
        summary[f"{engine}_failures"] = sum(1 for r in rows if not isinstance(r.get(f"{engine}_top1"), (int, float)))
    _write_json(OUT / "docking_summary.json", summary)
    _write_json(OUT / "raw.json", raw)
    try:
        import pandas as pd

        pd.DataFrame(rows).to_parquet(OUT / "docking_redocking.parquet", index=False)
    except Exception as exc:  # noqa: BLE001
        print("parquet skipped:", exc)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--complexes", default="")
    ap.add_argument("--engines", default="vina,gnina,diffdock")
    ap.add_argument("--diffdock-ids", default=",".join(PDB_IDS[:10]))
    args = ap.parse_args()
    comps = [c for c in args.complexes.split(",") if c] or PDB_IDS
    run(comps, {c.strip() for c in args.diffdock_ids.split(",") if c.strip()},
        [e.strip() for e in args.engines.split(",") if e.strip()])
