#!/usr/bin/env python3
"""PPI DockQ benchmark, 3-replica MD reproducibility + ns/day, and MM/GBSA via a
GAFF/Amber export path (the OpenFF→Amber workaround)."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from protacxtend.audit import (  # noqa: E402
    bootstrap_ci, capri_class, dockq, ns_per_day, replica_agreement, symmetry_rmsd,
)

RES = ROOT / "results"
HOLO = ROOT / "validation_runs/1a46_pl/preparation/holo_complex.pdb"
TEST_PDB = ROOT / "outputs/p4ward_evidence/hmgb2_fixed_minim.pdb"


def _json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


# ── PPI ─────────────────────────────────────────────────────────────────

def ppi_benchmark() -> dict[str, Any]:
    from Bio.PDB import PDBIO, PDBParser, Select

    out = RES / "ppi"
    src = Path.home() / ".protacxtend/envs/diffdock/DiffDock/examples/1a46_protein_processed.pdb"
    native = PDBParser(QUIET=True).get_structure("n", str(src))[0]

    class _Ch(Select):
        def __init__(self, chain): self.chain = chain
        def accept_chain(self, c): return c.id == self.chain
        def accept_residue(self, r): return r.id[0] == " "

    rec_pdb, lig_pdb = out / "receptor.pdb", out / "ligand.pdb"
    out.mkdir(parents=True, exist_ok=True)
    for ch, dest in (("L", rec_pdb), ("H", lig_pdb)):
        io = PDBIO(); io.set_structure(native); io.save(str(dest), _Ch(ch))

    rows = []
    # control: native vs native
    ctrl = dockq(native, native, "L", "H")
    rows.append({"system": "1a46_LH", "method": "native_control", **ctrl})
    # decoys: random rigid-body transform of the ligand chain
    from Bio.PDB import Structure, Model, Chain
    import copy

    rng = np.random.default_rng(7)
    decoys = []
    for i in range(20):
        model = copy.deepcopy(native)
        chain = model["L"].get_parent()["H"]
        coords = np.asarray([a.coord for a in chain.get_atoms()], float)
        c = coords.mean(0)
        axis = rng.normal(size=3); axis /= np.linalg.norm(axis)
        ang = rng.uniform(0, 2 * np.pi)
        K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
        R = np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * (K @ K)
        t = rng.normal(scale=8.0, size=3)
        new = (coords - c) @ R.T + c + t
        for atom, xyz in zip(chain.get_atoms(), new):
            atom.set_coord(xyz.astype(np.float32))
        d = dockq(native, model, "L", "H")
        decoys.append(d)
        rows.append({"system": "1a46_LH", "method": f"decoy_{i+1}", **d})
    decoy_dockq = [d["dockq"] for d in decoys if d["dockq"] is not None]

    # geometric fallback: reconstruct the top orientation and score it
    import math
    from protacxtend.scientific_backends.backends.docking import _parse_structure_atoms
    rec_atoms, _ = _parse_structure_atoms(str(rec_pdb))
    lig_atoms, _ = _parse_structure_atoms(str(lig_pdb))
    rng2 = np.random.default_rng(11)
    rec_centre = rec_atoms.mean(0)
    lig_centre = lig_atoms.mean(0)
    lig_local = lig_atoms - lig_centre
    radius = float(np.linalg.norm(rec_atoms - rec_centre, axis=1).max()) + 6.0
    best = None
    for i in range(24):
        axis = rng2.normal(size=3); axis /= np.linalg.norm(axis)
        ang = rng2.uniform(0, 2 * math.pi)
        K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
        R = np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * (K @ K)
        direction = rng2.normal(size=3); direction /= np.linalg.norm(direction)
        placement = rec_centre + direction * radius
        placed = (lig_local @ R.T) + placement
        d = np.linalg.norm(rec_atoms[:, None, :] - placed[None, :, :], axis=2)
        contacts = int((d < 5.0).sum()); clashes = int((d < 2.2).sum()); burial = int((d < 8.0).sum())
        score = 0.02 * contacts + 0.005 * burial - 3.0 * clashes
        if best is None or score > best["score"]:
            best = {"score": score, "coords": placed, "center": placement.tolist()}
    # build the model complex with the best-placed ligand coordinates
    model = copy.deepcopy(native)
    chain = model["L"].get_parent()["H"]
    for atom, xyz in zip(chain.get_atoms(), best["coords"]):
        atom.set_coord(xyz.astype(np.float32))
    geo = dockq(native, model, "L", "H")
    rows.append({"system": "1a46_LH", "method": "geometric_fallback", **geo})

    _csv(out / "ppi_dockq.csv", rows)
    summary = {
        "native_control_dockq": ctrl["dockq"], "native_control_capri": ctrl["capri"],
        "decoy_dockq_mean": round(float(np.mean(decoy_dockq)), 4) if decoy_dockq else None,
        "decoy_dockq_max": round(float(np.max(decoy_dockq)), 4) if decoy_dockq else None,
        "geometric_fallback_dockq": geo["dockq"], "geometric_fallback_capri": geo["capri"],
        "n_decoys": len(decoy_dockq),
        "native_interface_recovery_geometric": geo["fnat"],
        "lightdock_note": "LightDock swarm ranking validated functionally; coordinate-level "
                          "DockQ requires its post-processing (lgd_top) and is reported as not run.",
    }
    _json(out / "ppi_benchmark.json", summary)
    return summary


# ── MD reproducibility + ns/day ─────────────────────────────────────────

def md_benchmark(replicas: int = 3) -> dict[str, Any]:
    from protacxtend.scientific_backends.dispatch import run_cross_env
    from protacxtend.workflows.validation_pipeline import sasa_timeseries, trajectory_timeseries

    out = RES / "md"
    structure = str(HOLO) if HOLO.exists() else str(TEST_PDB)
    ligand_smiles = "CCO"
    runs = []
    for rep in range(1, replicas + 1):
        payload = run_cross_env("protacxtend.workflows.md_runner", "_openmm_staged",
                                args=[structure, str(out / f"replica_{rep}")],
                                kwargs={"ligand_resname": "LIG", "ligand_smiles": ligand_smiles,
                                        "minimize_steps": 200, "restrained_steps": 500,
                                        "nvt_steps": 500, "production_steps": 2500,
                                        "seed": 100 + rep, "platform": "auto"},
                                require_import="openmm", prefer_env="md-openff", timeout=7200)
        if not payload.get("ok"):
            runs.append({"replica": rep, "error": payload.get("error")})
            continue
        r = payload["result"]
        lsel = "resname LIG" if "LIG" in Path(r["topology_pdb"]).read_text()[:200000] else ""
        ts = trajectory_timeseries(r["topology_pdb"], r["trajectory"], ligand_sel=lsel)
        sa = sasa_timeseries(r["topology_pdb"], r["trajectory"], ligand_sel=lsel)
        runs.append({"replica": rep, "platform": r["platform"], "seed": 100 + rep,
                     "rmsd": ts.get("rmsd", []), "rmsf": ts.get("rmsf", []),
                     "rg": ts.get("rg", []), "sasa": sa.get("sasa", []),
                     "bsa_ligand": sa.get("bsa_target_ligand", []), "trajectory": r["trajectory"]})
    ok = [r for r in runs if "error" not in r]
    agreement = replica_agreement([r["rmsd"] for r in ok])
    summary = {"n_replicas": len(ok), "replica_agreement": agreement,
               "rmsd_mean": round(float(np.mean([np.mean(r["rmsd"]) for r in ok if r["rmsd"]])), 3) if ok else None,
               "rmsd_ci": bootstrap_ci([np.mean(r["rmsd"]) for r in ok if r["rmsd"]]),
               "failures": [r for r in runs if "error" in r]}
    _json(out / "md_reproducibility.json", summary)

    # ns/day CPU vs GPU on a fixed protocol
    throughput = []
    for platform in ("CPU", "auto"):
        payload = run_cross_env("protacxtend.workflows.md_runner", "_openmm_staged",
                                args=[str(TEST_PDB), str(out / f"throughput_{platform}")],
                                kwargs={"minimize_steps": 50, "restrained_steps": 0,
                                        "nvt_steps": 0, "production_steps": 2000,
                                        "platform": platform},
                                require_import="openmm", prefer_env="md-openff", timeout=3600)
        if not payload.get("ok"):
            throughput.append({"platform": platform, "error": payload.get("error")})
            continue
        r = payload["result"]
        wall = _energy_wall(r["energy_csv"])
        throughput.append({"platform": r["platform"], "requested": platform,
                           "steps": 2000, "wall_s": wall,
                           "ns_per_day": ns_per_day(2000, 2.0, wall) if wall else None,
                           "atoms": r["n_atoms"]})
    _csv(out / "md_throughput.csv", throughput)
    summary["throughput"] = throughput
    _json(out / "md_benchmark.json", summary)
    return summary


def _energy_wall(energy_csv: str) -> float | None:
    path = Path(energy_csv)
    if not path.exists():
        return None
    rows = list(csv.DictReader(path.open()))
    times = [float(r["Time (ps)"]) for r in rows if r.get("Time (ps)")]
    speeds = [float(r["Speed (ns/day)"]) for r in rows if r.get("Speed (ns/day)")]
    if speeds:
        return round(2000 * 2.0 / 1e6 / (speeds[-1] / 86400.0), 3) if speeds[-1] else None
    return None


# ── MM/GBSA via GAFF/Amber export ───────────────────────────────────────

def mmpbsa_benchmark() -> dict[str, Any]:
    from protacxtend.scientific_backends.dispatch import run_cross_env

    out = RES / "energy"
    structure = str(HOLO)
    smi_file = ROOT / "validation_runs/1a46_pl/preparation/ligand_parameterization.json"
    ligand_smiles = json.loads(smi_file.read_text())["canonical_smiles"] if smi_file.exists() else "CCO"
    if not Path(structure).exists():
        result = {"status": "unavailable", "reason": "no holo complex"}
        _json(out / "mmpbsa_benchmark.json", result)
        return result
    payload = run_cross_env("protacxtend.workflows.md_runner", "_openmm_staged",
                            args=[structure, str(out / "mmpbsa_md")],
                            kwargs={"ligand_resname": "LIG", "ligand_smiles": ligand_smiles,
                                    "minimize_steps": 200, "restrained_steps": 200,
                                    "nvt_steps": 200, "production_steps": 1000,
                                    "platform": "auto", "export_amber": True,
                                    "ligand_forcefield": "gaff"},
                            require_import="openmm", prefer_env="md-openff", timeout=7200)
    if not payload.get("ok"):
        result = {"status": "failed", "stage": "md_export", "reason": payload.get("error")}
        _json(out / "mmpbsa_benchmark.json", result)
        return result
    amber = payload["result"].get("amber") or {}
    if amber.get("error") or not amber.get("prmtop"):
        result = {"status": "failed", "stage": "amber_export",
                  "reason": amber.get("error", "no prmtop")}
        _json(out / "mmpbsa_benchmark.json", result)
        return result
    amberhome = Path.home() / ".protacxtend/envs/gromacs"
    env = dict(os.environ, AMBERHOME=str(amberhome))
    work = out / "mmpbsa_work"
    work.mkdir(parents=True, exist_ok=True)
    rec = work / "receptor.prmtop"
    lig = work / "ligand.prmtop"
    cmd1 = [str(amberhome / "bin/ante-MMPBSA.py"), "-p", amber["prmtop"],
            "-c", amber["prmtop"], "-r", str(rec), "-l", str(lig),
            "-m", ":LIG", "-s", ":WAT,Na+,Cl-"]
    p1 = subprocess.run(cmd1, capture_output=True, text=True, env=env, timeout=1800)
    if p1.returncode != 0:
        result = {"status": "failed", "stage": "ante-MMPBSA", "reason": p1.stderr[-400:]}
        _json(out / "mmpbsa_benchmark.json", result)
        return result
    inp = work / "mmpbsa.in"
    inp.write_text("&general\n  startframe=1, endframe=5, interval=1, verbose=2, keep_files=0,\n/\n"
                   "&gb\n  igb=5, saltcon=0.150,\n/\n")
    nc = amber.get("netcdf")
    cmd2 = [str(amberhome / "bin/MMPBSA.py"), "-O", "-i", str(inp),
            "-o", str(work / "FINAL_RESULTS_MMPBSA.dat"),
            "-sp", amber["prmtop"], "-cp", amber["prmtop"],
            "-rp", str(rec), "-lp", str(lig), "-y", str(nc)]
    t0 = time.time()
    p2 = subprocess.run(cmd2, capture_output=True, text=True, env=env, cwd=str(work), timeout=7200)
    runtime = round(time.time() - t0, 1)
    result_file = work / "FINAL_RESULTS_MMPBSA.dat"
    delta = None
    per_residue = []
    if result_file.exists():
        for line in result_file.read_text(errors="ignore").splitlines():
            if "DELTA TOTAL" in line:
                for tok in reversed(line.split()):
                    try:
                        delta = float(tok); break
                    except ValueError:
                        continue
            if line.strip().startswith(("Residue", "R  ")):
                per_residue.append(line.strip())
    result = {"status": "success" if (p2.returncode == 0 and delta is not None) else "failed",
              "method_label": "MMGBSA_ESTIMATE", "igb": 5, "saltcon_M": 0.15,
              "frames_used": 5, "solvent_model": "GB (igb=5)", "entropy_treatment": "none",
              "delta_total_kcal_mol": delta, "runtime_s": runtime,
              "per_residue_lines": per_residue[:50],
              "forcefield": "GAFF ligand (OpenFF→Amber export is unsupported by ParmEd)",
              "reason": "" if p2.returncode == 0 else (p2.stderr or p2.stdout)[-400:]}
    _json(out / "mmpbsa_benchmark.json", result)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["ppi", "md", "mmpbsa", "all"])
    ap.add_argument("--replicas", type=int, default=3)
    args = ap.parse_args()
    if args.stage in ("ppi", "all"):
        print("PPI:", json.dumps(ppi_benchmark(), indent=2))
    if args.stage in ("md", "all"):
        print("MD:", json.dumps(md_benchmark(args.replicas), indent=2))
    if args.stage in ("mmpbsa", "all"):
        print("MMPBSA:", json.dumps(mmpbsa_benchmark(), indent=2))
