"""Real fallback testing: deliberately disable a primary backend and execute the
next registered backend for the same capability.

Fallback success rate is reported **separately** from normal execution success.
The runner-level fallback is exercised end-to-end (the fallback handler does real
work), not merely resolved on paper.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from protacxtend.audit.provenance import host_fingerprint
from protacxtend.validation.datasets import CACHE, ROOT
from protacxtend.validation.io import RowWriter, write_summary_json

OUT = ROOT / "results" / "benchmarks" / "fallback"


def _cached_inputs() -> dict[str, Any]:
    rec = CACHE / "1a46_receptor.pdb"
    lig_sdf = CACHE / "1a46_crystal.sdf"
    smiles = "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O"  # ibuprofen fallback if ligand missing
    if lig_sdf.exists():
        try:
            from rdkit import Chem

            mols = [m for m in Chem.SDMolSupplier(str(lig_sdf), removeHs=True, sanitize=False) if m]
            if mols:
                smiles = Chem.MolToSmiles(mols[0])
        except Exception:
            pass
    ppi_dir = CACHE / "1ppe_ppi"
    return {
        "receptor_pdb": str(rec) if rec.exists() else "",
        "ligand_smiles": smiles,
        "pdb_path": str(rec) if rec.exists() else "",
        "complex_pdb": str(rec) if rec.exists() else "",
        "structure_pdb": str(rec) if rec.exists() else "",
        "ppi_receptor": str(ppi_dir / "receptor.pdb") if (ppi_dir / "receptor.pdb").exists() else "",
        "ppi_ligand": str(ppi_dir / "ligand.pdb") if (ppi_dir / "ligand.pdb").exists() else "",
    }


def _scenarios(inputs: dict[str, Any], fast: bool) -> list[dict[str, Any]]:
    scenarios = [
        {"capability": "chemistry", "primary": "rdkit", "kwargs": {"smiles": "CCO"}},
        {"capability": "admet", "primary": "rdkit", "kwargs": {"smiles": "CCO"}},
        {"capability": "pocket_detection", "primary": "pocket_geometry",
         "kwargs": {"pdb_path": inputs["pdb_path"]}},
        {"capability": "molecular_dynamics", "primary": "openmm",
         "kwargs": {"structure_pdb": inputs["structure_pdb"], "md_steps": 0, "minimize": True}},
        {"capability": "binding_energy", "primary": "binding_energy_hierarchy",
         "kwargs": {"complex_pdb": inputs["complex_pdb"], "ligand_resname": "LIG"}},
        {"capability": "ligand_docking", "primary": "consensus_docking",
         "kwargs": {"receptor_pdb": inputs["receptor_pdb"],
                    "ligand_smiles": inputs["ligand_smiles"]}},
        {"capability": "ligand_docking", "primary": "autodock_vina",
         "kwargs": {"receptor_pdb": inputs["receptor_pdb"],
                    "ligand_smiles": inputs["ligand_smiles"]}},
        {"capability": "ligand_docking", "primary": "diffdock",
         "kwargs": {"receptor_pdb": inputs["receptor_pdb"],
                    "ligand_smiles": inputs["ligand_smiles"]}},
        {"capability": "ppi_docking", "primary": "lightdock",
         "kwargs": {"receptor_pdb": inputs["ppi_receptor"], "ligand_pdb": inputs["ppi_ligand"]}},
    ]
    if fast:
        return [s for s in scenarios if s["capability"] in
                {"chemistry", "admet", "pocket_detection", "binding_energy"}]
    return scenarios


def run(*, fast: bool = False) -> dict[str, Any]:
    from protacxtend.scientific_backends.registry import REGISTRY, load_backends
    from protacxtend.scientific_backends.runner import run_capability

    load_backends()
    OUT.mkdir(parents=True, exist_ok=True)
    row = RowWriter("fallback_rows", OUT)
    inputs = _cached_inputs()

    for scenario in _scenarios(inputs, fast):
        capability = scenario["capability"]
        primary = scenario["primary"]
        kwargs = {k: v for k, v in scenario["kwargs"].items() if v}
        # 1) normal execution with the primary present
        t0 = time.time()
        try:
            normal = run_capability(capability, **kwargs)
            normal_status, normal_backend = normal.status, normal.backend
        except Exception as exc:  # noqa: BLE001
            normal_status, normal_backend = "error", f"{type(exc).__name__}: {exc}"
        normal_runtime = round(time.time() - t0, 2)
        # 2) primary deliberately disabled
        t0 = time.time()
        try:
            disabled = run_capability(capability, disabled_backends={primary},
                                      mark_fallback_after=primary, **kwargs)
            fallback_status, fallback_backend = disabled.status, disabled.backend
            fallback_summary = disabled.summary
            fallback_used = fallback_backend not in {"", primary}
            fallback_succeeded = bool(disabled.ok() and fallback_used)
        except Exception as exc:  # noqa: BLE001
            fallback_status, fallback_backend = "error", ""
            fallback_summary, fallback_used, fallback_succeeded = str(exc), False, False
        fallback_runtime = round(time.time() - t0, 2)
        row.add({
            "benchmark": "fallback", "capability": capability, "primary_backend": primary,
            "normal_status": normal_status, "normal_backend": normal_backend,
            "normal_runtime_s": normal_runtime,
            "primary_disabled": True,
            "fallback_backend": fallback_backend,
            "fallback_used": fallback_used,
            "fallback_status": fallback_status,
            "fallback_succeeded": fallback_succeeded,
            "fallback_runtime_s": fallback_runtime,
            "failure_reason": "" if fallback_succeeded else fallback_summary[:300],
            **row.provenance(dataset="fallback_v1", source="live backend registry",
                             software="capability_runner", command="run_capability",
                             config={"disabled": primary}, output_path=str(OUT)),
        })
        print(f"[fallback] {capability}: primary={primary}({normal_status}) -> "
              f"fallback={fallback_backend}({fallback_status}) used={fallback_used} "
              f"ok={fallback_succeeded}")

    summary = _summary(row.rows)
    row.finalize(summary)
    write_summary_json(OUT / "fallback_summary.json", summary)
    print("\n" + str(summary))
    return summary


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    normal_ok = [r["normal_status"] in {"success", "warning", "FALLBACK_SUCCESS"} for r in rows]
    fallback_used = [bool(r["fallback_used"]) for r in rows]
    fallback_ok = [bool(r["fallback_succeeded"]) for r in rows]
    n = len(rows)
    return {
        "n_scenarios": n,
        "normal_successes": sum(normal_ok),
        "normal_success_rate": round(sum(normal_ok) / n, 4) if n else None,
        "fallback_used": sum(fallback_used),
        "fallback_used_rate": round(sum(fallback_used) / n, 4) if n else None,
        "fallback_successes": sum(fallback_ok),
        "fallback_success_rate": round(sum(fallback_ok) / n, 4) if n else None,
        "fallback_success_rate_when_used": round(sum(fallback_ok) / sum(fallback_used), 4)
        if sum(fallback_used) else None,
        "no_fallback_available": [r["capability"] for r in rows if not r["fallback_used"]],
        "host": host_fingerprint(),
    }


__all__ = ["run", "OUT"]
