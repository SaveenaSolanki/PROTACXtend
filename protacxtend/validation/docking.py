"""Expanded redocking benchmark with provenance, failures and prospective consensus."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from protacxtend.audit import bootstrap_ci, success_rate_ci, symmetry_rmsd
from protacxtend.audit.provenance import ResourceMonitor, host_fingerprint
from protacxtend.scientific_backends.consensus import (
    best_rmsd,
    pose_molecules,
    prospective_consensus,
)
from protacxtend.validation.curation import curate_ligand_complex
from protacxtend.validation.datasets import DOCKING_V1, ROOT
from protacxtend.validation.io import RowWriter, write_summary_json

OUT = ROOT / "results" / "benchmarks" / "docking"

ENGINE_CONFIG: dict[str, dict[str, Any]] = {
    "vina": {"exhaustiveness": 8, "num_modes": 9, "cpu": 4, "timeout": 1800},
    "gnina": {"timeout": 3600},
    "diffdock": {"n_poses": 10, "inference_steps": 20, "timeout": 7200},
}


def _persist_poses(engine: str, data: dict[str, Any], out_dir: Path) -> Path:
    """Write heavy-atom pose SDFs so consensus is reproducible post-hoc."""
    from rdkit import Chem

    pose_out = out_dir / "poses_sdf"
    pose_out.mkdir(parents=True, exist_ok=True)
    mols = pose_molecules(engine, data)
    for i, mol in enumerate(mols[:10], start=1):
        try:
            w = Chem.SDWriter(str(pose_out / f"rank{i}.sdf"))
            w.write(mol)
            w.close()
        except Exception:
            pass
    return pose_out


def _engine_fn(engine: str):
    from protacxtend.scientific_backends.backends.docking import (
        diffdock_docking, gnina_docking, vina_docking,
    )

    return {"vina": vina_docking, "gnina": gnina_docking, "diffdock": diffdock_docking}[engine]


def _crystal_ref(ligand_sdf: str):
    from rdkit import Chem

    mols = [m for m in Chem.SDMolSupplier(ligand_sdf, removeHs=True, sanitize=False) if m]
    if not mols:
        raise RuntimeError("crystal ligand unreadable")
    return mols[0]


def _topk_rmsd(engine: str, data: dict[str, Any], ref) -> dict[str, Any]:
    mols = pose_molecules(engine, data)
    rmsds = sorted(r for r in (symmetry_rmsd(m, ref) for m in mols) if r is not None)
    return {
        "top1": rmsds[0] if rmsds else None,
        "top3": min(rmsds[:3]) if rmsds else None,
        "top5": min(rmsds[:5]) if rmsds else None,
        "n_poses": len(rmsds),
        "n_pose_mols": len(mols),
    }


def run_engine(complex_info: dict[str, Any], engine: str, *, out_dir: Path,
               row: RowWriter, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run one engine on one curated complex; always returns/records a row."""
    pdb_id = complex_info["pdb_id"]
    config = config or ENGINE_CONFIG.get(engine, {})
    engine_out = out_dir / "poses" / pdb_id / engine
    engine_out.mkdir(parents=True, exist_ok=True)
    fn = _engine_fn(engine)
    started = time.time()
    monitor = ResourceMonitor()
    status = ""
    error = ""
    with monitor:
        try:
            result = fn(receptor_pdb=complex_info["receptor"], ligand_smiles=complex_info["smiles"],
                        output_dir=str(engine_out),
                        **{k: v for k, v in config.items() if k != "timeout"})
            status = result.status
            error = "" if result.ok() else result.summary
        except Exception as exc:  # noqa: BLE001
            result = None
            status = "error"
            error = f"{type(exc).__name__}: {exc}"
    wall = round(time.time() - started, 3)

    metrics: dict[str, Any] = {"top1": None, "top3": None, "top5": None,
                               "n_poses": 0, "n_pose_mols": 0}
    ref = None
    pose_dir = ""
    try:
        ref = _crystal_ref(complex_info["ligand_sdf"])
    except Exception:
        pass
    if result is not None and result.ok() and ref is not None:
        metrics = _topk_rmsd(engine, result.data or {}, ref)
        pose_dir = str(_persist_poses(engine, result.data or {}, engine_out))

    row_data = {
        "benchmark": "docking", "structure_id": pdb_id, "ligand_id": complex_info["het"],
        "ligand_smiles": complex_info["smiles"], "engine": engine,
        "mode": "redocking", "status": status, "success": bool(status in
            {"success", "warning", "FALLBACK_SUCCESS"} and metrics["top1"] is not None),
        "failure_reason": error[:300],
        "rmsd_top1": metrics["top1"], "rmsd_top3": metrics["top3"], "rmsd_top5": metrics["top5"],
        "n_poses": metrics["n_poses"], "runtime_s": wall,
        "wall_s": monitor.to_dict()["wall_s"], "cpu_s": monitor.to_dict()["cpu_s"],
        "peak_rss_mb": monitor.to_dict()["peak_rss_mb"],
        "pose_dir": pose_dir, "output_path": str(engine_out),
    }
    row_data.update(row.provenance(
        dataset=DOCKING_V1["name"], source=DOCKING_V1["source"], structure_id=pdb_id,
        ligand_id=complex_info["het"], software=engine,
        software_version=_engine_version(engine),
        model="diffdock_confidence" if engine == "diffdock" else "",
        model_version="v1.1" if engine == "diffdock" else "",
        command=engine, config=config, seed=config.get("seed"),
        output_path=str(engine_out)))
    row.add(row_data)
    return {"result": result, "metrics": metrics, "row": row_data, "ref": ref,
            "wall": wall, "status": status, "error": error}


def _engine_version(engine: str) -> str:
    import os
    import subprocess

    from protacxtend.toolkit.environments import find_executable

    if engine == "diffdock":
        return "DiffDock v1.1 (best_ema_inference_epoch_model.pt)"
    binary = {"vina": "vina", "gnina": "gnina"}.get(engine, engine)
    try:
        found = find_executable(binary)
        if not found:
            return "not_found"
        env = dict(os.environ)
        if engine == "gnina":
            from protacxtend.scientific_backends.backends.docking import _nvidia_lib_dirs

            nv = _nvidia_lib_dirs()
            if nv:
                env["LD_LIBRARY_PATH"] = nv + (":" + env["LD_LIBRARY_PATH"]
                                               if env.get("LD_LIBRARY_PATH") else "")
        proc = subprocess.run([found[0], "--version"], capture_output=True, text=True,
                              timeout=60, env=env)
        text = (proc.stdout or proc.stderr or "").strip().splitlines()
        return (text[0][:120] if text else Path(found[0]).name)
    except Exception:
        return ""


def run_consensus(complex_info: dict[str, Any], engine_payloads: dict[str, Any],
                  *, row: RowWriter, out_dir: Path) -> dict[str, Any]:
    """Prospective consensus + oracle upper bound for one complex."""
    pdb_id = complex_info["pdb_id"]
    ok = {e: p["result"] for e, p in engine_payloads.items()
          if p["result"] is not None and p["result"].ok() and p["metrics"]["n_pose_mols"]}
    ref = next((p["ref"] for p in engine_payloads.values() if p.get("ref") is not None), None)
    if not ok or ref is None:
        row.add({
            "benchmark": "docking", "structure_id": pdb_id, "ligand_id": complex_info["het"],
            "engine": "prospective_consensus", "mode": "redocking",
            "status": "BACKEND_UNAVAILABLE", "success": False,
            "failure_reason": "no usable engine poses for consensus",
            "rmsd_top1": None, "oracle_top1": None,
            **row.provenance(dataset=DOCKING_V1["name"], source=DOCKING_V1["source"],
                             structure_id=pdb_id, ligand_id=complex_info["het"],
                             software="consensus_docking")})
        return {}

    prospective = prospective_consensus(ok, receptor_pdb=complex_info["receptor"])
    selected = prospective.get("selected") or {}
    mols = pose_molecules(selected.get("engine", ""), ok[selected["engine"]].data or {})
    idx = int(selected.get("rank", 1)) - 1
    selected_rmsd = None
    if 0 <= idx < len(mols):
        selected_rmsd = symmetry_rmsd(mols[idx], ref)

    oracle = None
    for payload in engine_payloads.values():
        v = payload["metrics"].get("top1")
        if v is not None:
            oracle = v if oracle is None else min(oracle, v)

    row.add({
        "benchmark": "docking", "structure_id": pdb_id, "ligand_id": complex_info["het"],
        "engine": "prospective_consensus", "mode": "redocking",
        "status": "success" if selected_rmsd is not None else "OUTPUT_INVALID",
        "success": selected_rmsd is not None,
        "selected_engine": selected.get("engine"), "selected_rank": selected.get("rank"),
        "consensus_score": selected.get("consensus_score"),
        "rmsd_top1": selected_rmsd, "oracle_top1": oracle,
        "n_engines_used": len(ok), "n_candidates": prospective.get("n_candidates"),
        "weights": str(prospective.get("weights")),
        "failure_reason": "",
        **row.provenance(dataset=DOCKING_V1["name"], source=DOCKING_V1["source"],
                         structure_id=pdb_id, ligand_id=complex_info["het"],
                         software="consensus_docking", model="prospective_consensus",
                         config=prospective.get("weights"), output_path=str(out_dir)),
    })
    return {"selected_rmsd": selected_rmsd, "oracle": oracle,
            "selected_engine": selected.get("engine")}


def _summary(rows: list[dict[str, Any]], failures: list[dict[str, Any]],
             n_attempted: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "dataset": DOCKING_V1["name"], "n_curated_attempted": n_attempted,
        "n_complexes_with_results": len({r["structure_id"] for r in rows}),
        "n_rows": len(rows), "n_failures": len(failures),
        "failure_outcomes": _count(failures, "outcome"),
        "host": host_fingerprint(),
    }
    for engine in ("vina", "gnina", "diffdock", "prospective_consensus", "oracle"):
        engine_rows = [r for r in rows if r.get("engine") == engine]
        attempted = {r["structure_id"]: r for r in engine_rows}
        if engine == "oracle":
            aligned = [r.get("oracle_top1") for r in
                       [x for x in rows if x.get("engine") == "prospective_consensus"]]
        else:
            aligned = [r.get("rmsd_top1") for r in engine_rows]
        numeric = [float(v) for v in aligned if isinstance(v, (int, float))]
        # denominator = every attempted complex for this engine (failures retained)
        denominator = len(aligned)
        success_flags2 = [isinstance(v, (int, float)) and v <= 2.0 for v in aligned]
        success_flags5 = [isinstance(v, (int, float)) and v <= 5.0 for v in aligned]
        summary[engine] = {
            "n_attempted": denominator,
            "n_with_pose": len(numeric),
            "n_failures": denominator - len(numeric),
            "failure_rate": round((denominator - len(numeric)) / denominator, 4) if denominator else None,
            "median_rmsd": round(float(np.median(numeric)), 3) if numeric else None,
            "mean_rmsd": round(float(np.mean(numeric)), 3) if numeric else None,
            "rmsd_distribution": numeric,
            "success_lt2A": success_rate_ci(success_flags2) if denominator else None,
            "success_lt5A": success_rate_ci(success_flags5) if denominator else None,
            "median_ci": bootstrap_ci(numeric) if numeric else None,
        }
    return summary


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[str(r.get(key))] = out.get(str(r.get(key)), 0) + 1
    return out


def run(complexes: list[str] | None = None, engines: list[str] | None = None,
        *, limit: int | None = None, out_dir: Path | None = None,
        tag: str = "") -> dict[str, Any]:
    complexes = complexes or DOCKING_V1["complexes"]
    if limit:
        complexes = complexes[:limit]
    engines = engines or ["vina", "gnina", "diffdock"]
    base = Path(out_dir) if out_dir else OUT
    base.mkdir(parents=True, exist_ok=True)
    row = RowWriter(f"docking_rows{('_' + tag) if tag else ''}", base)
    failures: list[dict[str, Any]] = []
    n_curated = 0
    for pdb_id in complexes:
        try:
            info = curate_ligand_complex(pdb_id)
            n_curated += 1
        except Exception as exc:  # noqa: BLE001
            failures.append(row.failure(structure_id=pdb_id, stage="curation",
                                        outcome="REJECTED_INPUT", reason=str(exc)[:200]))
            print(f"[docking] {pdb_id} CURATION FAIL: {exc}")
            continue
        payloads: dict[str, Any] = {}
        for engine in engines:
            p = run_engine(info, engine, out_dir=base, row=row)
            payloads[engine] = p
            if not p["row"]["success"]:
                outcome = p["status"] if p["status"] else "ERROR"
                failures.append(row.failure(
                    structure_id=pdb_id, ligand_id=info["het"], engine=engine,
                    stage=f"{engine}_dock", outcome=outcome,
                    reason=p["error"] or "no valid pose"))
            print(f"[docking] {pdb_id} {engine}: status={p['status']} "
                  f"top1={p['metrics'].get('top1')}")
        if payloads and len(engines) > 1:
            cons = run_consensus(info, payloads, row=row, out_dir=base)
            print(f"[docking] {pdb_id} consensus: {cons.get('selected_rmsd')} "
                  f"oracle={cons.get('oracle')}")
    summary = _summary(row.rows, failures, n_curated)
    row.finalize(summary)
    write_summary_json(base / f"failures{('_' + tag) if tag else ''}.json",
                       {"n": len(failures), "failures": failures})
    (base / f"failures{('_' + tag) if tag else ''}.csv").write_text(_csv(failures), encoding="utf-8")
    write_summary_json(base / f"docking_summary{('_' + tag) if tag else ''}.json", summary)
    print("\n" + str(summary))
    return summary


def _csv(rows: list[dict[str, Any]]) -> str:
    import csv
    import io

    if not rows:
        return ""
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=keys)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def merge(shard_dirs: list[str | Path], *, out_dir: Path | None = None) -> dict[str, Any]:
    """Merge sharded benchmark row files and recompute the combined summary."""
    base = Path(out_dir) if out_dir else OUT
    base.mkdir(parents=True, exist_ok=True)
    merged: dict[tuple[str, str, Any], dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    for shard in shard_dirs:
        shard = Path(shard)
        for row_file in sorted(shard.glob("docking_rows*.json")):
            try:
                payload = json.loads(row_file.read_text())
            except Exception:
                continue
            for r in payload.get("rows", []):
                key = (r.get("structure_id"), r.get("engine"), r.get("selected_engine", ""))
                merged.setdefault(key, r)
        for fail_file in sorted(shard.glob("failures*.json")):
            try:
                failures.extend(json.loads(fail_file.read_text()).get("failures", []))
            except Exception:
                pass
    rows = list(merged.values())
    n_complexes = len({r.get("structure_id") for r in rows})
    summary = _summary(rows, failures, n_complexes)
    writer = RowWriter("docking_rows", base)
    writer.rows = rows
    writer.finalize(summary)
    write_summary_json(base / "docking_summary.json", summary)
    write_summary_json(base / "failures.json", {"n": len(failures), "failures": failures})
    print("merged", len(rows), "rows from", len(list(shard_dirs)))
    return summary


__all__ = ["run", "run_engine", "run_consensus", "merge", "recompute_consensus", "OUT"]


def _load_pose_sdffiles(path: Path) -> list:
    from rdkit import Chem

    if not path.exists():
        return []
    mols = []
    for sdf in sorted(path.glob("rank*.sdf"),
                      key=lambda p: int("".join(ch for ch in p.stem if ch.isdigit()) or 0)):
        recs = [m for m in Chem.SDMolSupplier(str(sdf), removeHs=True, sanitize=False) if m]
        if recs:
            mols.append(recs[0])
    return mols


def recompute_consensus(primary_dir: str | Path, diffdock_dir: str | Path,
                        *, out_dir: str | Path | None = None) -> dict[str, Any]:
    """Two- and three-engine prospective consensus from persisted pose SDFs."""
    from protacxtend.scientific_backends.consensus import consensus_from_pose_sets
    from protacxtend.validation.datasets import CACHE

    primary = Path(primary_dir)
    diffdock = Path(diffdock_dir)
    base = Path(out_dir) if out_dir else primary.parent
    base.mkdir(parents=True, exist_ok=True)
    row = RowWriter("consensus_rows", base)
    complexes = sorted({p.parent.parent.name
                        for pattern in ("poses/*/vina/poses_sdf", "poses/*/gnina/poses_sdf")
                        for p in primary.glob(pattern)})
    for pdb_id in complexes:
        ref = None
        ref_file = CACHE / f"{pdb_id}_crystal.sdf"
        if ref_file.exists():
            try:
                ref = _crystal_ref(str(ref_file))
            except Exception:
                ref = None
        for label, engines in (("two_engine", ["vina", "gnina"]),
                               ("three_engine", ["vina", "gnina", "diffdock"])):
            engine_mols: dict[str, list] = {}
            engine_scores: dict[str, list] = {}
            for engine in engines:
                source = primary if engine in {"vina", "gnina"} else diffdock
                mols = _load_pose_sdffiles(source / "poses" / pdb_id / engine / "poses_sdf")
                if not mols:
                    continue
                engine_mols[engine] = mols
                n = len(mols)
                if engine == "diffdock":
                    engine_scores[engine] = [float(n - i) for i in range(n)]
                else:
                    engine_scores[engine] = [float(i) for i in range(n)]
            if len(engine_mols) < len(engines):
                missing = [e for e in engines if e not in engine_mols]
                row.add({
                    "benchmark": "docking", "structure_id": pdb_id, "ligand_id": "",
                    "engine": f"prospective_consensus_{label}", "mode": "redocking",
                    "status": "MISSING_ENGINE", "success": False,
                    "rmsd_top1": None, "oracle_top1": None,
                    "n_engines_used": len(engine_mols),
                    "failure_reason": f"missing engines: {','.join(missing)}",
                    **row.provenance(dataset=DOCKING_V1["name"], source=DOCKING_V1["source"],
                                     structure_id=pdb_id, software="consensus_docking",
                                     model="prospective_consensus", output_path=str(base)),
                })
                continue
            pocket = None
            consensus = consensus_from_pose_sets(
                engine_mols, engine_scores, receptor_pdb="", pocket_center=pocket,
                score_is_confidence={"diffdock"})
            selected = consensus.get("selected") or {}
            sel_mols = engine_mols.get(selected.get("engine"), [])
            idx = int(selected.get("rank", 1)) - 1
            selected_rmsd = (symmetry_rmsd(sel_mols[idx], ref)
                             if ref is not None and 0 <= idx < len(sel_mols) else None)
            oracle = None
            for engine, mols in engine_mols.items():
                r = symmetry_rmsd(mols[0], ref) if (ref is not None and mols) else None
                if r is not None:
                    oracle = r if oracle is None else min(oracle, r)
            row.add({
                "benchmark": "docking", "structure_id": pdb_id, "ligand_id": "",
                "engine": f"prospective_consensus_{label}", "mode": "redocking",
                "status": "success" if selected_rmsd is not None else "OUTPUT_INVALID",
                "success": selected_rmsd is not None,
                "selected_engine": selected.get("engine"), "selected_rank": selected.get("rank"),
                "consensus_score": selected.get("consensus_score"),
                "rmsd_top1": selected_rmsd, "oracle_top1": oracle,
                "n_engines_used": len(engine_mols),
                "n_candidates": consensus.get("n_candidates"),
                "weights": str(consensus.get("weights")),
                "failure_reason": "",
                **row.provenance(dataset=DOCKING_V1["name"], source=DOCKING_V1["source"],
                                 structure_id=pdb_id, software="consensus_docking",
                                 model="prospective_consensus",
                                 config=consensus.get("weights"), output_path=str(base)),
            })
            print(f"[consensus] {pdb_id} {label}: selected={selected.get('engine')} "
                  f"rmsd={selected_rmsd} oracle={oracle}")
    # summary over consensus rows
    summary: dict[str, Any] = {"dataset": DOCKING_V1["name"], "host": host_fingerprint()}
    for label in ("two_engine", "three_engine"):
        vals = [r.get("rmsd_top1") for r in row.rows
                if r.get("engine") == f"prospective_consensus_{label}"]
        numeric = [float(v) for v in vals if isinstance(v, (int, float))]
        summary[label] = {
            "n_attempted": len(vals), "n_with_pose": len(numeric),
            "n_failures": len(vals) - len(numeric),
            "median_rmsd": round(float(np.median(numeric)), 3) if numeric else None,
            "success_lt2A": success_rate_ci([isinstance(v, (int, float)) and v <= 2.0 for v in vals]) if vals else None,
            "success_lt5A": success_rate_ci([isinstance(v, (int, float)) and v <= 5.0 for v in vals]) if vals else None,
        }
    writer = RowWriter("consensus_rows", base)
    writer.rows = row.rows
    writer.finalize(summary)
    write_summary_json(base / "consensus_summary.json", summary)
    print("\n" + str(summary))
    return summary
