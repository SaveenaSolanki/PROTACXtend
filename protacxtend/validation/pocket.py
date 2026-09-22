"""Expanded pocket-prediction validation (DCC, DCA, top-k, residue P/R/F1)."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from protacxtend.audit.provenance import ResourceMonitor, host_fingerprint
from protacxtend.validation.curation import curate_ligand_complex
from protacxtend.validation.datasets import POCKET_V1, ROOT
from protacxtend.validation.io import RowWriter, write_summary_json

OUT = ROOT / "results" / "benchmarks" / "pockets"
RECOVERY_CUTOFF = 4.0
CONTACT_CUTOFF = 5.0


def _ligand_atoms(ligand_sdf: str) -> tuple[np.ndarray, str]:
    from rdkit import Chem

    mols = [m for m in Chem.SDMolSupplier(ligand_sdf, removeHs=True, sanitize=False) if m]
    if not mols:
        raise RuntimeError("ligand unreadable")
    mol = mols[0]
    conf = mol.GetConformer()
    coords = np.asarray([list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())], float)
    return coords, Chem.MolToSmiles(mol)


def _binding_residues(receptor_pdb: str, ligand_coords: np.ndarray) -> set[str]:
    from Bio.PDB import PDBParser

    structure = PDBParser(QUIET=True).get_structure("s", receptor_pdb)
    residues: set[str] = set()
    for residue in structure.get_residues():
        if residue.id[0] != " ":
            continue
        for atom in residue:
            if (atom.element or "").strip().upper() == "H":
                continue
            if float(np.linalg.norm(ligand_coords - np.asarray(atom.coord), axis=1).min()) < CONTACT_CUTOFF:
                residues.add(f"{residue.get_resname()}{residue.id[1]}")
                break
    return residues


def _prf(predicted: set[str], truth: set[str]) -> tuple[float, float, float]:
    tp = len(predicted & truth)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(truth) if truth else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return round(precision, 3), round(recall, 3), round(f1, 3)


def run(complexes: list[str] | None = None, *, limit: int | None = None,
        out_dir: Path | None = None, tag: str = "") -> dict[str, Any]:
    complexes = complexes or POCKET_V1["complexes"]
    if limit:
        complexes = complexes[:limit]
    base = Path(out_dir) if out_dir else OUT
    base.mkdir(parents=True, exist_ok=True)
    row = RowWriter(f"pocket_rows{('_' + tag) if tag else ''}", base)
    failures: list[dict[str, Any]] = []
    n_curated = 0
    for pdb_id in complexes:
        started = time.time()
        monitor = ResourceMonitor()
        try:
            info = curate_ligand_complex(pdb_id)
            n_curated += 1
        except Exception as exc:  # noqa: BLE001
            failures.append(row.failure(structure_id=pdb_id, stage="curation",
                                        outcome="REJECTED_INPUT", reason=str(exc)[:200]))
            continue
        try:
            lig_coords, smiles = _ligand_atoms(info["ligand_sdf"])
            truth = _binding_residues(info["receptor"], lig_coords)
        except Exception as exc:  # noqa: BLE001
            failures.append(row.failure(structure_id=pdb_id, ligand_id=info["het"],
                                        stage="ligand", outcome="REJECTED_INPUT",
                                        reason=str(exc)[:200]))
            continue
        with monitor:
            try:
                from protacxtend.scientific_backends import detect_pockets

                res = detect_pockets(info["receptor"], top_n=5)
                pockets = res.data.get("pockets", []) if res.ok() else []
                status = res.status
                error = "" if res.ok() else res.summary
            except Exception as exc:  # noqa: BLE001
                pockets, status, error = [], "error", f"{type(exc).__name__}: {exc}"
        centroid = lig_coords.mean(0)
        # recovery / DCC / DCA
        rec: dict[str, Any] = {}
        for k in (1, 3, 5):
            hit = False
            for pocket in pockets[:k]:
                center = pocket.get("center")
                if not center:
                    continue
                c = np.asarray(center, float)
                if float(np.linalg.norm(lig_coords - c, axis=1).min()) <= RECOVERY_CUTOFF:
                    hit = True
                    break
            rec[f"top{k}_recovery_4A"] = hit
        top1 = pockets[0] if pockets else {}
        dcc = dca = coverage = None
        precision = recall = f1 = None
        if top1.get("center"):
            c = np.asarray(top1["center"], float)
            dcc = round(float(np.linalg.norm(c - centroid)), 3)
            dca = round(float(np.linalg.norm(lig_coords - c, axis=1).min()), 3)
            coverage = round(float((np.linalg.norm(lig_coords - c, axis=1) < 8.0).mean()), 3)
            predicted = set(top1.get("residues") or [])
            if not predicted:
                # fall back to residues within 8 A of the pocket centre
                from Bio.PDB import PDBParser

                structure = PDBParser(QUIET=True).get_structure("s", info["receptor"])
                predicted = set()
                for residue in structure.get_residues():
                    if residue.id[0] != " ":
                        continue
                    for atom in residue:
                        if (atom.element or "").strip().upper() == "H":
                            continue
                        if float(np.linalg.norm(np.asarray(atom.coord) - c)) < 8.0:
                            predicted.add(f"{residue.get_resname()}{residue.id[1]}")
                            break
            precision, recall, f1 = _prf(predicted, truth)
        success = bool(pockets)
        row.add({
            "benchmark": "pocket", "structure_id": pdb_id, "ligand_id": info["het"],
            "smiles": smiles, "engine": "fpocket_pocket_geometry", "status": status,
            "success": success, "failure_reason": error[:300],
            "n_pockets": len(pockets), "dcc": dcc, "dca": dca,
            "ligand_atom_coverage_8A": coverage,
            "residue_precision": precision, "residue_recall": recall, "residue_f1": f1,
            "n_binding_residues": len(truth),
            "top1_recovery_4A": rec.get("top1_recovery_4A"),
            "top3_recovery_4A": rec.get("top3_recovery_4A"),
            "top5_recovery_4A": rec.get("top5_recovery_4A"),
            "runtime_s": round(time.time() - started, 3),
            "wall_s": monitor.to_dict()["wall_s"], "peak_rss_mb": monitor.to_dict()["peak_rss_mb"],
            **row.provenance(dataset=POCKET_V1["name"], source=POCKET_V1["source"],
                             structure_id=pdb_id, ligand_id=info["het"],
                             software="fpocket/geometry_cavity",
                             command="detect_pockets", config={"top_n": 5},
                             output_path=str(base)),
        })
        if not success:
            failures.append(row.failure(structure_id=pdb_id, ligand_id=info["het"],
                                        engine="pocket", stage="detect", outcome=status,
                                        reason=error or "no pockets"))
        print(f"[pocket] {pdb_id}: n={len(pockets)} dcc={dcc} f1={f1} "
              f"top1={rec.get('top1_recovery_4A')}")
    summary = _summary(row.rows, len(complexes))
    row.finalize(summary)
    write_summary_json(base / f"failures{('_' + tag) if tag else ''}.json",
                       {"n": len(failures), "failures": failures})
    print("\n" + str(summary))
    return summary


def _frac(rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    from protacxtend.audit import success_rate_ci

    flags = [bool(r.get(key)) for r in rows]
    return success_rate_ci(flags) if flags else None


def _summary(rows: list[dict[str, Any]], n_attempted: int) -> dict[str, Any]:
    from protacxtend.audit import bootstrap_ci

    dcc = [r["dcc"] for r in rows if isinstance(r.get("dcc"), (int, float))]
    prec = [r["residue_precision"] for r in rows if isinstance(r.get("residue_precision"), (int, float))]
    rec = [r["residue_recall"] for r in rows if isinstance(r.get("residue_recall"), (int, float))]
    f1 = [r["residue_f1"] for r in rows if isinstance(r.get("residue_f1"), (int, float))]
    return {
        "dataset": POCKET_V1["name"], "n_attempted": n_attempted,
        "n_with_pockets": sum(1 for r in rows if r.get("success")),
        "failure_rate": round(1 - (sum(1 for r in rows if r.get("success")) / len(rows)), 4) if rows else None,
        "top1_recovery_4A": _frac(rows, "top1_recovery_4A"),
        "top3_recovery_4A": _frac(rows, "top3_recovery_4A"),
        "top5_recovery_4A": _frac(rows, "top5_recovery_4A"),
        "dcc_median": round(float(np.median(dcc)), 3) if dcc else None,
        "dcc_ci": bootstrap_ci(dcc) if dcc else None,
        "residue_precision_median": round(float(np.median(prec)), 3) if prec else None,
        "residue_recall_median": round(float(np.median(rec)), 3) if rec else None,
        "residue_f1_median": round(float(np.median(f1)), 3) if f1 else None,
        "residue_f1_ci": bootstrap_ci(f1) if f1 else None,
        "host": host_fingerprint(),
    }


__all__ = ["run", "OUT"]
