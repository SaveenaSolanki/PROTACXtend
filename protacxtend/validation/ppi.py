"""Experimental binary PPI redocking validation (LightDock + DockQ/iRMSD/LRMSD/Fnat).

For each curated two-chain experimental complex the partners are separated,
re-docked, and the predictions evaluated against the native assembly.  A native
control and an unbound-decoy control are always run so the metric is anchored.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

from protacxtend.audit import capri_class, dockq, success_rate_ci
from protacxtend.audit.provenance import ResourceMonitor, host_fingerprint
from protacxtend.validation.curation import curate_binary_complex
from protacxtend.validation.datasets import PPI_V1, ROOT
from protacxtend.validation.io import RowWriter, write_summary_json

OUT = ROOT / "results" / "benchmarks" / "ppi"
LIGHTDOCK = {
    "n_swarms": 15, "glowworms": 10, "steps": 30, "cores": 6, "top": 5, "clash": 10.0,
}


def _find(binary: str) -> str | None:
    from protacxtend.toolkit.environments import find_executable

    try:
        found = find_executable(binary)
        return found[0] if found else None
    except Exception:
        return None


def _clean_pdb(src: str, dst: Path) -> None:
    from Bio.PDB import PDBIO, PDBParser, Select

    structure = PDBParser(QUIET=True).get_structure("s", src)

    class _Clean(Select):
        def accept_residue(self, residue):
            return residue.id[0] == " "

        def accept_atom(self, atom):
            element = (atom.element or atom.get_name()[0]).strip().upper()
            if element == "H":
                return False
            return atom.get_name().strip().upper() not in {"OXT", "OT1", "OT2"}

    io = PDBIO()
    io.set_structure(structure)
    io.save(str(dst), _Clean())


def run_lightdock(info: dict[str, Any], work: Path, config: dict[str, Any]) -> dict[str, Any]:
    setup = _find("lightdock3_setup.py")
    runner = _find("lightdock3.py")
    ranker = _find("lgd_rank.py")
    top_tool = _find("lgd_top.py")
    if not all([setup, runner, ranker, top_tool]):
        return {"ok": False, "stage": "binary", "reason": "LightDock tools not installed"}
    work.mkdir(parents=True, exist_ok=True)
    rec = work / "receptor.pdb"
    lig = work / "ligand.pdb"
    _clean_pdb(info["receptor_pdb"], rec)
    _clean_pdb(info["ligand_pdb"], lig)
    env = dict(os.environ)
    env["PATH"] = str(Path(setup).parent) + os.pathsep + env.get("PATH", "")
    try:
        proc = subprocess.run(
            [setup, "receptor.pdb", "ligand.pdb", "-s", str(config["n_swarms"]),
             "-g", str(config["glowworms"])],
            cwd=work, capture_output=True, text=True, timeout=900, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "stage": "setup", "reason": "setup timeout"}
    if proc.returncode != 0:
        return {"ok": False, "stage": "setup", "reason": (proc.stderr or proc.stdout)[-300:]}
    try:
        proc = subprocess.run(
            [runner, "setup.json", str(config["steps"]), "-c", str(config["cores"])],
            cwd=work, capture_output=True, text=True, timeout=5400, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "stage": "gso", "reason": "GSO timeout"}
    if proc.returncode != 0:
        return {"ok": False, "stage": "gso", "reason": (proc.stderr or proc.stdout)[-300:]}
    try:
        proc = subprocess.run(
            [ranker, str(config["n_swarms"]), str(config["steps"]), "-c", str(config["clash"])],
            cwd=work, capture_output=True, text=True, timeout=600, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "stage": "rank", "reason": "rank timeout"}
    ranking = work / "rank_by_scoring.list"
    if not ranking.exists():
        return {"ok": False, "stage": "rank", "reason": "rank_by_scoring.list not produced"}
    try:
        proc = subprocess.run(
            [top_tool, "receptor.pdb", "ligand.pdb",
             "rank_by_scoring.list", str(config["top"])],
            cwd=work, capture_output=True, text=True, timeout=900, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "stage": "top", "reason": "top timeout"}
    poses = sorted(work.glob("top_*.pdb"),
                   key=lambda p: int(p.stem.split("_")[1]) if p.stem.split("_")[1].isdigit() else 0)
    if not poses:
        return {"ok": False, "stage": "top", "reason": "no top poses generated"}
    return {"ok": True, "poses": [str(p) for p in poses], "work": str(work),
            "ranking": str(ranking)}


def _decoy_control(native: Any, rec_chain: str, lig_chain: str, seed: int = 7) -> dict[str, Any]:
    import copy

    rng = np.random.default_rng(seed)
    model = copy.deepcopy(native)
    chain = model[lig_chain]
    coords = np.asarray([a.coord for a in chain.get_atoms()], float)
    center = coords.mean(0)
    axis = rng.normal(size=3)
    axis /= np.linalg.norm(axis)
    angle = rng.uniform(0, 2 * np.pi)
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)
    translated = (coords - center) @ R.T + center + rng.normal(scale=10.0, size=3)
    for atom, xyz in zip(chain.get_atoms(), translated):
        atom.set_coord(xyz.astype(np.float32))
    return dockq(native, model, rec_chain, lig_chain)


def run(complexes: list[str] | None = None, *, limit: int | None = None,
        config: dict[str, Any] | None = None, out_dir: Path | None = None,
        tag: str = "") -> dict[str, Any]:
    complexes = complexes or PPI_V1["complexes"]
    if limit:
        complexes = complexes[:limit]
    config = {**LIGHTDOCK, **(config or {})}
    base = Path(out_dir) if out_dir else OUT
    base.mkdir(parents=True, exist_ok=True)
    row = RowWriter(f"ppi_rows{('_' + tag) if tag else ''}", base)
    failures: list[dict[str, Any]] = []
    n_curated = 0
    from Bio.PDB import PDBParser

    for pdb_id in complexes:
        started = time.time()
        monitor = ResourceMonitor()
        try:
            info = curate_binary_complex(pdb_id)
            n_curated += 1
        except Exception as exc:  # noqa: BLE001
            failures.append(row.failure(structure_id=pdb_id, stage="curation",
                                        outcome="REJECTED_INPUT", reason=str(exc)[:200]))
            print(f"[ppi] {pdb_id} curation fail: {exc}")
            continue
        native = PDBParser(QUIET=True).get_structure(pdb_id, info["native_pdb"])[0]
        rec_chain, lig_chain = info["receptor_chain"], info["ligand_chain"]
        control = dockq(native, native, rec_chain, lig_chain)
        row.add({"benchmark": "ppi", "structure_id": pdb_id, "engine": "native_control",
                 "status": "success", "success": True, **control,
                 "runtime_s": 0.0,
                 **row.provenance(dataset=PPI_V1["name"], source=PPI_V1["source"],
                                  structure_id=pdb_id, software="native",
                                  output_path=info["native_pdb"])})
        decoy = _decoy_control(native, rec_chain, lig_chain)
        row.add({"benchmark": "ppi", "structure_id": pdb_id, "engine": "rigid_decoy",
                 "status": "success", "success": decoy.get("dockq") is not None, **decoy,
                 "runtime_s": 0.0,
                 **row.provenance(dataset=PPI_V1["name"], source=PPI_V1["source"],
                                  structure_id=pdb_id, software="random_rigid_transform",
                                  seed=7, output_path=info["native_pdb"])})

        work = base / "work" / pdb_id
        with monitor:
            ld = run_lightdock(info, work, config)
        if not ld["ok"]:
            failures.append(row.failure(structure_id=pdb_id, engine="lightdock",
                                        stage=ld["stage"], outcome="ERROR",
                                        reason=ld["reason"]))
            print(f"[ppi] {pdb_id} lightdock FAIL ({ld['stage']}): {ld['reason'][:120]}")
            continue
        best = None
        for rank, pose in enumerate(ld["poses"], start=1):
            try:
                model = PDBParser(QUIET=True).get_structure("m", pose)[0]
                metrics = dockq(native, model, rec_chain, lig_chain)
            except Exception as exc:  # noqa: BLE001
                metrics = {"fnat": None, "irms": None, "lrms": None, "dockq": None,
                           "capri": "n/a"}
            score = metrics.get("dockq")
            if score is not None and (best is None or score > best["dockq"]):
                best = {**metrics, "rank": rank, "pose": pose}
            row.add({"benchmark": "ppi", "structure_id": pdb_id, "engine": "lightdock",
                     "rank": rank, "status": "success" if score is not None else "OUTPUT_INVALID",
                     "success": score is not None,
                     **{k: v for k, v in metrics.items()},
                     "runtime_s": round(time.time() - started, 3),
                     "wall_s": monitor.to_dict()["wall_s"],
                     "peak_rss_mb": monitor.to_dict()["peak_rss_mb"],
                     **row.provenance(dataset=PPI_V1["name"], source=PPI_V1["source"],
                                      structure_id=pdb_id, software="lightdock",
                                      command="lightdock3_setup/gso/lgd_rank/lgd_top",
                                      config=config, seed=config.get("seed"),
                                      output_path=pose)})
        # top-1/top-5 metrics for this complex
        top_rows = [r for r in row.rows if r.get("structure_id") == pdb_id
                    and r.get("engine") == "lightdock"]
        t1 = next((r for r in top_rows if r.get("rank") == 1), {})
        top5 = [r for r in top_rows if isinstance(r.get("dockq"), (int, float))]
        best_dockq = max((r["dockq"] for r in top5), default=None)
        row.add({"benchmark": "ppi", "structure_id": pdb_id, "engine": "lightdock_summary",
                 "status": "success", "success": best_dockq is not None,
                 "dockq_top1": t1.get("dockq"), "fnat_top1": t1.get("fnat"),
                 "irms_top1": t1.get("irms"), "lrms_top1": t1.get("lrms"),
                 "capri_top1": t1.get("capri"), "dockq_best_top5": best_dockq,
                 "runtime_s": round(time.time() - started, 3),
                 **row.provenance(dataset=PPI_V1["name"], source=PPI_V1["source"],
                                  structure_id=pdb_id, software="lightdock",
                                  command="top5", config=config, output_path=str(work))})
        print(f"[ppi] {pdb_id}: dockq_top1={t1.get('dockq')} best_top5={best_dockq} "
              f"({round(time.time() - started, 1)}s)")
    summary = _summary(row.rows, n_curated)
    row.finalize(summary)
    write_summary_json(base / f"failures{('_' + tag) if tag else ''}.json",
                       {"n": len(failures), "failures": failures})
    print("\n" + str(summary))
    return summary


def _summary(rows: list[dict[str, Any]], n_attempted: int) -> dict[str, Any]:
    from protacxtend.audit import bootstrap_ci

    top1 = [r for r in rows if r.get("engine") == "lightdock" and r.get("rank") == 1]
    summaries = [r for r in rows if r.get("engine") == "lightdock_summary"]
    controls = [r for r in rows if r.get("engine") == "native_control"]
    decoys = [r for r in rows if r.get("engine") == "rigid_decoy"]
    dockq_top1 = [r["dockq"] for r in top1 if isinstance(r.get("dockq"), (int, float))]
    dockq_best5 = [r["dockq_best_top5"] for r in summaries
                   if isinstance(r.get("dockq_best_top5"), (int, float))]
    fnat = [r["fnat_top1"] for r in summaries if isinstance(r.get("fnat_top1"), (int, float))]
    irms = [r["irms_top1"] for r in summaries if isinstance(r.get("irms_top1"), (int, float))]
    lrms = [r["lrms_top1"] for r in summaries if isinstance(r.get("lrms_top1"), (int, float))]
    return {
        "dataset": PPI_V1["name"], "n_attempted": n_attempted,
        "n_evaluated": len(summaries),
        "failure_rate": round(1 - len(summaries) / n_attempted, 4) if n_attempted else None,
        "native_control_dockq_median": _median([r.get("dockq") for r in controls]),
        "rigid_decoy_dockq_median": _median([r.get("dockq") for r in decoys]),
        "dockq_top1_median": _median(dockq_top1),
        "dockq_top1_ci": bootstrap_ci(dockq_top1) if dockq_top1 else None,
        "dockq_best_top5_median": _median(dockq_best5),
        "fnat_top1_median": _median(fnat), "irms_top1_median": _median(irms),
        "lrms_top1_median": _median(lrms),
        "success_dockq_ge_0.23": success_rate_ci([bool(v is not None and v >= 0.23) for v in
                                                  [r.get("dockq") for r in top1]]) if top1 else None,
        "capri_high": sum(1 for r in top1 if r.get("capri") == "High"),
        "capri_medium": sum(1 for r in top1 if r.get("capri") == "Medium"),
        "capri_acceptable": sum(1 for r in top1 if r.get("capri") == "Acceptable"),
        "capri_incorrect": sum(1 for r in top1 if r.get("capri") == "Incorrect"),
        "host": host_fingerprint(),
    }


def _median(values: list[Any]) -> float | None:
    numeric = [float(v) for v in values if isinstance(v, (int, float))]
    return round(float(np.median(numeric)), 4) if numeric else None


def merge(shard_dirs: list[str | Path], *, out_dir: Path | None = None) -> dict[str, Any]:
    """Merge sharded PPI row files into the final summary."""
    base = Path(out_dir) if out_dir else OUT
    base.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for shard in shard_dirs:
        shard = Path(shard)
        for row_file in sorted(shard.glob("ppi_rows*.json")):
            try:
                payload = json.loads(row_file.read_text())
            except Exception:
                continue
            for r in payload.get("rows", []):
                key = (r.get("structure_id"), r.get("engine"), r.get("rank"))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(r)
    n_attempted = len({r.get("structure_id") for r in rows if r.get("engine") == "lightdock"})
    n_attempted += sum(1 for r in rows if r.get("stage") in {"curation", "setup", "gso", "rank", "top"})
    summary = _summary(rows, n_attempted or len({r.get("structure_id") for r in rows}))
    writer = RowWriter("ppi_rows", base)
    writer.rows = rows
    writer.finalize(summary)
    write_summary_json(base / "ppi_rows_summary.json", summary)
    print("merged", len(rows), "PPI rows")
    return summary


__all__ = ["run", "merge", "OUT"]
