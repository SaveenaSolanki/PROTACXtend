"""Reproducibility testing: repeat stochastic methods across seeds and quantify
pose consistency, metric variance, replay success and deterministic behaviour.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import numpy as np

from protacxtend.audit.provenance import host_fingerprint
from protacxtend.scientific_backends.consensus import best_rmsd, pose_molecules
from protacxtend.validation.curation import curate_ligand_complex
from protacxtend.validation.datasets import DOCKING_V1, ROOT
from protacxtend.validation.io import RowWriter, write_summary_json

OUT = ROOT / "results" / "benchmarks" / "reproducibility"


def _deterministic_replay() -> dict[str, Any]:
    from protacxtend.scientific_backends import chemistry

    hashes = []
    for _ in range(3):
        result = chemistry("CCO")
        payload = json.dumps({"status": result.status, "backend": result.backend,
                              "data": result.data}, sort_keys=True, default=str)
        hashes.append(hashlib.sha256(payload.encode()).hexdigest()[:16])
    return {"task": "rdkit_chemistry_cCO", "hashes": hashes,
            "deterministic": len(set(hashes)) == 1}


def _run_engine(engine: str, info: dict[str, Any], seed: int) -> dict[str, Any]:
    from protacxtend.scientific_backends.backends.docking import (
        diffdock_docking, geometric_docking, vina_docking,
    )

    fn = {"vina": vina_docking, "diffdock": diffdock_docking,
          "geometric": geometric_docking}[engine]
    kwargs = {"vina": {"exhaustiveness": 4, "num_modes": 5, "cpu": 4},
              "diffdock": {"n_poses": 5, "inference_steps": 20},
              "geometric": {"n_poses": 5}}[engine]
    if engine == "diffdock":
        kwargs["seed"] = seed
    t0 = time.time()
    result = fn(receptor_pdb=info["receptor"], ligand_smiles=info["smiles"], **kwargs)
    mols = pose_molecules(engine, result.data or {}) if result.ok() else []
    return {"engine": engine, "seed": seed, "status": result.status, "ok": result.ok(),
            "n_poses": len(mols), "top_mol": mols[0] if mols else None,
            "pose_export_available": bool(mols),
            "runtime_s": round(time.time() - t0, 2)}


def _top_rmsd(info: dict[str, Any], mol) -> float | None:
    from rdkit import Chem

    if mol is None:
        return None
    mols = [m for m in Chem.SDMolSupplier(info["ligand_sdf"], removeHs=True, sanitize=False) if m]
    if not mols:
        return None
    try:
        from protacxtend.audit import symmetry_rmsd

        return symmetry_rmsd(mol, mols[0])
    except Exception:
        return None


def run(complexes: list[str] | None = None, *, limit: int = 5, seeds: int = 3) -> dict[str, Any]:
    complexes = (complexes or DOCKING_V1["complexes"])[:limit]
    OUT.mkdir(parents=True, exist_ok=True)
    row = RowWriter("reproducibility_rows", OUT)
    deterministic = _deterministic_replay()
    for pdb_id in complexes:
        try:
            info = curate_ligand_complex(pdb_id)
        except Exception as exc:  # noqa: BLE001
            row.failure(structure_id=pdb_id, stage="curation", outcome="REJECTED_INPUT",
                        reason=str(exc)[:200])
            continue
        for engine in ("vina", "diffdock", "geometric"):
            runs = [_run_engine(engine, info, seed=100 + i) for i in range(seeds)]
            ok_runs = [r for r in runs if r["ok"]]
            mol_runs = [r for r in ok_runs if r["top_mol"] is not None]
            # pairwise top-pose RMSD (pose consistency)
            pairwise = []
            for i in range(len(mol_runs)):
                for j in range(i + 1, len(mol_runs)):
                    r = best_rmsd(mol_runs[i]["top_mol"], mol_runs[j]["top_mol"])
                    if r is not None:
                        pairwise.append(r)
            top1 = [_top_rmsd(info, r["top_mol"]) for r in mol_runs]
            top1 = [v for v in top1 if v is not None]
            row.add({
                "benchmark": "reproducibility", "structure_id": pdb_id, "engine": engine,
                "n_repeats": seeds, "n_successful_repeats": len(ok_runs),
                "replay_success_rate": round(len(ok_runs) / seeds, 3),
                "pose_export_available": bool(mol_runs),
                "pose_consistency_median_A": round(float(np.median(pairwise)), 3) if pairwise else None,
                "pose_consistency_max_A": round(float(np.max(pairwise)), 3) if pairwise else None,
                "n_pairwise": len(pairwise),
                "top1_rmsd_mean_A": round(float(np.mean(top1)), 3) if top1 else None,
                "top1_rmsd_variance": round(float(np.var(top1)), 4) if top1 else None,
                "deterministic": engine == "geometric",
                "status": runs[0]["status"], "success": len(ok_runs) > 0,
                "seed_list": "100-102",
                **row.provenance(dataset=DOCKING_V1["name"], source=DOCKING_V1["source"],
                                 structure_id=pdb_id, software=engine,
                                 command=f"{engine} x{seeds} seeds", seed=100,
                                 output_path=str(OUT)),
            })
            print(f"[repro] {pdb_id} {engine}: repeats_ok={len(ok_runs)}/{seeds} "
                  f"pose_rmsd_med={row.rows[-1]['pose_consistency_median_A']}")
    summary = _summary(row.rows, deterministic)
    row.finalize(summary)
    write_summary_json(OUT / "reproducibility_summary.json", summary)
    print("\n" + str(summary))
    return summary


def _summary(rows: list[dict[str, Any]], deterministic: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"deterministic_replay": deterministic,
                           "host": host_fingerprint(), "by_engine": {}}
    for engine in ("vina", "diffdock", "geometric"):
        sub = [r for r in rows if r.get("engine") == engine]
        replay = [r["replay_success_rate"] for r in sub]
        consistency = [r["pose_consistency_median_A"] for r in sub
                       if isinstance(r.get("pose_consistency_median_A"), (int, float))]
        variance = [r["top1_rmsd_variance"] for r in sub
                    if isinstance(r.get("top1_rmsd_variance"), (int, float))]
        out["by_engine"][engine] = {
            "n_complexes": len(sub),
            "replay_success_rate": round(float(np.mean(replay)), 3) if replay else None,
            "pose_consistency_median_A": round(float(np.median(consistency)), 3) if consistency else None,
            "metric_variance_median": round(float(np.median(variance)), 4) if variance else None,
            "deterministic": engine == "geometric",
        }
    return out


__all__ = ["run", "OUT"]
