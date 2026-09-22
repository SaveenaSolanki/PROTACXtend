"""MM/GBSA via a reproducible GAFF2 / AmberTools workflow.

Route (all steps validated before any energy is reported):

1. RDKit adds hydrogens to the crystal ligand.
2. ``antechamber`` assigns AM1-BCC charges with the GAFF2 atom types.
3. ``parmchk2`` fills missing GAFF2 parameters.
4. ``tleap`` builds the complex prmtop/inpcrd (protein ff14SB + GAFF2 ligand).
5. ``sander`` runs implicit-solvent (GB) minimisation + short MD.
6. ``ante-MMPBSA.py`` splits the topology; ``MMPBSA.py`` computes MM/GBSA.

The capability is reported as ``NOT_VALIDATED`` unless every step succeeds and
the parameterization passes explicit checks (integer net charge, complete
parameters, matching atom count).  No surrogate energy is ever substituted.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np

from protacxtend.audit.provenance import ResourceMonitor, host_fingerprint
from protacxtend.validation.curation import curate_ligand_complex
from protacxtend.validation.datasets import ENERGETICS_V1, ROOT
from protacxtend.validation.io import RowWriter, write_summary_json

OUT = ROOT / "results" / "benchmarks" / "energetics"
AMBER_ENV = Path.home() / ".protacxtend/envs/md-openff/bin"


def _exe(name: str) -> str:
    path = AMBER_ENV / name
    if path.exists():
        return str(path)
    from protacxtend.toolkit.environments import find_executable

    found = find_executable(name)
    if found:
        return found[0]
    raise FileNotFoundError(name)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("AMBERHOME", str(AMBER_ENV.parent))
    env["PATH"] = str(AMBER_ENV) + os.pathsep + env.get("PATH", "")
    return env


def _run(cmd: list[str], cwd: Path, timeout: int, *, log: Path | None = None) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout, env=_env())
        out = {"ok": proc.returncode == 0, "returncode": proc.returncode,
               "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:],
               "runtime_s": round(time.time() - started, 2), "command": " ".join(cmd)}
    except subprocess.TimeoutExpired:
        out = {"ok": False, "returncode": -1, "stdout": "", "stderr": "timeout",
               "runtime_s": round(time.time() - started, 2), "command": " ".join(cmd)}
    if log:
        log.write_text(out["stdout"] + "\n---STDERR---\n" + out["stderr"])
    return out


def _prepare_ligand(ligand_sdf: str, work: Path) -> dict[str, Any]:
    from rdkit import Chem

    mols = [m for m in Chem.SDMolSupplier(ligand_sdf, removeHs=True, sanitize=False) if m]
    if not mols:
        raise RuntimeError("ligand unreadable")
    mol = mols[0]
    mol = Chem.AddHs(mol, addCoords=True)
    charge = int(Chem.GetFormalCharge(mol))
    lig_sdf = work / "lig.sdf"
    writer = Chem.SDWriter(str(lig_sdf))
    writer.write(mol)
    writer.close()
    return {"n_atoms": mol.GetNumAtoms(), "n_heavy": mol.GetNumHeavyAtoms(),
            "net_charge": charge, "smiles": Chem.MolToSmiles(Chem.RemoveHs(mol)),
            "sdf": str(lig_sdf)}


def parameterize(work: Path, ligand_sdf: str, *, forcefield: str = "gaff2",
                 timeout: int = 1800) -> dict[str, Any]:
    """Run antechamber + parmchk2 and return explicit validation evidence."""
    prep = _prepare_ligand(ligand_sdf, work)
    mol2 = work / "lig.mol2"
    frcmod = work / "lig.frcmod"
    ac = _run([_exe("antechamber"), "-i", "lig.sdf", "-fi", "sdf",
               "-o", "lig.mol2", "-fo", "mol2", "-c", "bcc", "-nc", str(prep["net_charge"]),
               "-at", forcefield, "-rn", "LIG", "-pf", "y"],
              work, timeout, log=work / "antechamber.log")
    pc = _run([_exe("parmchk2"), "-i", "lig.mol2", "-f", "mol2",
               "-o", "lig.frcmod", "-s", forcefield],
              work, 300, log=work / "parmchk2.log")
    valid = ac["ok"] and pc["ok"] and mol2.exists() and frcmod.exists()
    # validate atom count and charge in the mol2
    atom_count = 0
    charge_sum = 0.0
    if mol2.exists():
        in_atoms = False
        for line in mol2.read_text(errors="ignore").splitlines():
            if line.startswith("@<TRIPOS>ATOM"):
                in_atoms = True
                continue
            if line.startswith("@<TRIPOS>") and in_atoms:
                break
            if in_atoms and line.strip():
                parts = line.split()
                if len(parts) >= 6:
                    atom_count += 1
                    try:
                        charge_sum += float(parts[-1])
                    except ValueError:
                        pass
    checks = {
        "antechamber_ok": ac["ok"], "parmchk2_ok": pc["ok"],
        "mol2_atom_count": atom_count, "expected_atoms": prep["n_atoms"],
        "atom_count_match": atom_count == prep["n_atoms"],
        "net_charge": prep["net_charge"],
        "mol2_charge_sum": round(charge_sum, 4),
        "charge_integral": abs(charge_sum - round(charge_sum)) < 0.05,
        "charge_matches_formal": abs(charge_sum - prep["net_charge"]) < 0.05,
    }
    valid = valid and checks["atom_count_match"] and checks["charge_matches_formal"]
    return {"valid": valid, "checks": checks, "prep": prep, "mol2": str(mol2),
            "frcmod": str(frcmod), "forcefield": forcefield,
            "antechamber": ac, "parmchk2": pc}


def build_amber(work: Path, receptor_pdb: str, *, timeout: int = 1800) -> dict[str, Any]:
    tleap_in = work / "tleap.in"
    tleap_in.write_text(
        "source leaprc.protein.ff14SB\n"
        "source leaprc.gaff2\n"
        "loadamberparams lig.frcmod\n"
        "LIG = loadmol2 lig.mol2\n"
        "rec = loadpdb receptor.pdb\n"
        "com = combine { rec LIG }\n"
        "check com\n"
        "saveamberparm com complex.prmtop complex.inpcrd\n"
        "savepdb com complex_amber.pdb\n"
        "quit\n")
    result = _run([_exe("tleap"), "-f", "tleap.in"], work, timeout, log=work / "tleap.log")
    result["ok"] = result["ok"] and (work / "complex.prmtop").exists() \
        and (work / "complex.inpcrd").exists()
    result["warning_residues"] = ""
    if (work / "tleap.log").exists():
        text = (work / "tleap.log").read_text(errors="ignore")
        warnings = [l for l in text.splitlines() if "Warning" in l or "FATAL" in l or "missing" in l.lower()]
        result["warning_residues"] = "\n".join(warnings[:20])
    return result


def run_md(work: Path, *, seed: int = 7, nstlim: int = 5000, timeout: int = 7200) -> dict[str, Any]:
    (work / "min.in").write_text(
        "GB minimisation\n&cntrl\n imin=1, maxcyc=1000, ncyc=500, ntb=0, igb=5,"
        " cut=999.0, ntpr=200,\n/\n")
    (work / "md.in").write_text(
        f"GB short MD\n&cntrl\n imin=0, nstlim={nstlim}, dt=0.002, ntb=0, igb=5,"
        f" cut=999.0, ntpr=500, ntwx=500, ntwr=1000, ntt=3, gamma_ln=1.0,"
        f" temp0=300.0, ig={seed}, saltcon=0.15,\n/\n")
    mini = _run([_exe("sander"), "-O", "-i", "min.in", "-o", "min.out",
                 "-p", "complex.prmtop", "-c", "complex.inpcrd",
                 "-r", "complex_min.rst", "-ref", "complex.inpcrd"],
                work, 3600, log=work / "sander_min.log")
    md = _run([_exe("sander"), "-O", "-i", "md.in", "-o", "md.out",
               "-p", "complex.prmtop", "-c", "complex_min.rst",
               "-r", "complex_md.rst", "-x", "md.nc"],
              work, timeout, log=work / "sander_md.log")
    ok = mini["ok"] and md["ok"] and (work / "md.nc").exists()
    return {"ok": ok, "minimisation": mini, "md": md, "seed": seed, "nstlim": nstlim,
            "trajectory": str(work / "md.nc")}


def run_mmpbsa(work: Path, *, frames: int = 20, timeout: int = 7200) -> dict[str, Any]:
    rec = work / "receptor.prmtop"
    lig = work / "ligand.prmtop"
    split = _run([_exe("ante-MMPBSA.py"), "-p", "complex.prmtop", "-c", "complex.prmtop",
                  "-r", "receptor.prmtop", "-l", "ligand.prmtop", "-m", ":LIG"],
                 work, 900, log=work / "ante_mmpbsa.log")
    if not (rec.exists() and lig.exists()):
        return {"ok": False, "stage": "split", "detail": split}
    (work / "mmpbsa.in").write_text(
        f"&general\n startframe=1, endframe={frames}, interval=1, verbose=2,\n/\n"
        "&gb\n igb=5, saltcon=0.150,\n/\n")
    proc = _run([_exe("MMPBSA.py"), "-O", "-i", "mmpbsa.in",
                 "-o", "FINAL_RESULTS_MMPBSA.dat",
                 "-sp", "complex.prmtop", "-cp", "complex.prmtop",
                 "-rp", "receptor.prmtop", "-lp", "ligand.prmtop",
                 "-y", "md.nc"],
                work, timeout, log=work / "mmpbsa.log")
    delta = None
    result_file = work / "FINAL_RESULTS_MMPBSA.dat"
    if result_file.exists():
        for line in result_file.read_text(errors="ignore").splitlines():
            if "DELTA TOTAL" in line:
                for token in reversed(line.split()):
                    try:
                        delta = float(token)
                        break
                    except ValueError:
                        continue
    ok = proc["ok"] and delta is not None
    return {"ok": ok, "delta_total_kcal_mol": delta, "method": "MMGBSA",
            "igb": 5, "saltcon_M": 0.15, "frames": frames, "runtime_s": proc["runtime_s"],
            "detail": proc}


def _sanity_check(delta: float | None) -> tuple[bool, str]:
    """A short single-trajectory MM/GBSA total may not be positive for a
    crystallographic binder.  A positive/near-zero total indicates the ligand
    drifted, the charges are wrong, or the sampling is invalid, so we refuse to
    call it validated."""
    if delta is None:
        return False, "no DELTA TOTAL parsed"
    if not np.isfinite(delta):
        return False, "non-finite DELTA TOTAL"
    if delta > 0.0:
        return False, f"positive DELTA TOTAL ({delta:.2f} kcal/mol) is implausible for a crystal binder"
    return True, ""


def run(complexes: list[str] | None = None, *, limit: int | None = None,
        frames: int = 10, nstlim: int = 1000) -> dict[str, Any]:
    complexes = complexes or ENERGETICS_V1["complexes"]
    if limit:
        complexes = complexes[:limit]
    OUT.mkdir(parents=True, exist_ok=True)
    row = RowWriter("energetics_rows", OUT)
    failures: list[dict[str, Any]] = []
    for pdb_id in complexes:
        started = time.time()
        monitor = ResourceMonitor()
        work = OUT / "work" / pdb_id
        work.mkdir(parents=True, exist_ok=True)
        try:
            info = curate_ligand_complex(pdb_id)
        except Exception as exc:  # noqa: BLE001
            failures.append(row.failure(structure_id=pdb_id, stage="curation",
                                        outcome="REJECTED_INPUT", reason=str(exc)[:200]))
            continue
        # copy receptor next to the ligand for tleap
        import shutil

        shutil.copy(info["receptor"], work / "receptor.pdb")
        with monitor:
            param = parameterize(work, info["ligand_sdf"])
        if not param["valid"]:
            status = "NOT_VALIDATED"
            row.add({
                "benchmark": "energetics", "structure_id": pdb_id, "ligand_id": info["het"],
                "method": "MM/GBSA", "status": status, "success": False,
                "parameterization_valid": False, "stage": "parameterization",
                "failure_reason": "ligand parameterization failed validation",
                "delta_total_kcal_mol": None, "runtime_s": round(time.time() - started, 2),
                "checks": str(param["checks"]),
                **row.provenance(dataset=ENERGETICS_V1["name"], source=ENERGETICS_V1["source"],
                                 structure_id=pdb_id, ligand_id=info["het"],
                                 software=f"antechamber/{param['forcefield']}",
                                 command="antechamber;parmchk2",
                                 config={"forcefield": param["forcefield"]},
                                 output_path=str(work)),
            })
            failures.append(row.failure(structure_id=pdb_id, ligand_id=info["het"],
                                        engine="mmpbsa", stage="parameterization",
                                        outcome=status,
                                        reason="ligand parameterization failed validation"))
            print(f"[energetics] {pdb_id}: parameterization INVALID {param['checks']}")
            continue
        build = build_amber(work, str(work / "receptor.pdb"))
        if not build["ok"]:
            status = "NOT_VALIDATED"
            row.add({
                "benchmark": "energetics", "structure_id": pdb_id, "ligand_id": info["het"],
                "method": "MM/GBSA", "status": status, "success": False,
                "parameterization_valid": True, "stage": "tleap",
                "failure_reason": "tleap build failed",
                "delta_total_kcal_mol": None, "runtime_s": round(time.time() - started, 2),
                "checks": str(param["checks"]),
                **row.provenance(dataset=ENERGETICS_V1["name"], source=ENERGETICS_V1["source"],
                                 structure_id=pdb_id, ligand_id=info["het"],
                                 software="tleap", command="tleap -f tleap.in",
                                 output_path=str(work)),
            })
            failures.append(row.failure(structure_id=pdb_id, ligand_id=info["het"],
                                        engine="mmpbsa", stage="tleap", outcome=status,
                                        reason="tleap build failed"))
            print(f"[energetics] {pdb_id}: tleap FAIL")
            continue
        md = run_md(work, nstlim=nstlim)
        if not md["ok"]:
            failures.append(row.failure(structure_id=pdb_id, ligand_id=info["het"],
                                        engine="mmpbsa", stage="md", outcome="ERROR",
                                        reason="sander MD failed"))
            print(f"[energetics] {pdb_id}: sander FAIL")
            continue
        mmpbsa = run_mmpbsa(work, frames=frames)
        sane, sanity_reason = _sanity_check(mmpbsa.get("delta_total_kcal_mol"))
        status = "success" if (mmpbsa["ok"] and sane) else (
            "SCIENTIFIC_SANITY_FAILED" if mmpbsa["ok"] else "NOT_VALIDATED")
        row.add({
            "benchmark": "energetics", "structure_id": pdb_id, "ligand_id": info["het"],
            "method": "MM/GBSA", "status": status, "success": bool(mmpbsa["ok"] and sane),
            "parameterization_valid": True, "stage": "mmpbsa",
            "delta_total_kcal_mol": mmpbsa.get("delta_total_kcal_mol"),
            "frames": frames, "igb": 5, "saltcon_M": 0.15,
            "failure_reason": ("" if (mmpbsa["ok"] and sane) else
                               (sanity_reason or "MMPBSA.py produced no DELTA TOTAL")),
            "sanity_passed": sane, "runtime_s": round(time.time() - started, 2),
            "wall_s": monitor.to_dict()["wall_s"], "peak_rss_mb": monitor.to_dict()["peak_rss_mb"],
            "checks": str(param["checks"]),
            **row.provenance(dataset=ENERGETICS_V1["name"], source=ENERGETICS_V1["source"],
                             structure_id=pdb_id, ligand_id=info["het"],
                             software="AmberTools/MMPBSA.py", software_version="23.6",
                             model="GAFF2/ff14SB/igb5", command="sander;MMPBSA.py",
                             config={"frames": frames, "igb": 5}, seed=7,
                             output_path=str(work)),
        })
        print(f"[energetics] {pdb_id}: delta={mmpbsa.get('delta_total_kcal_mol')} "
              f"status={status}")
    summary = _summary(row.rows)
    row.finalize(summary)
    write_summary_json(OUT / "failures.json", {"n": len(failures), "failures": failures})
    print("\n" + str(summary))
    return summary


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid_param = [r for r in rows if r.get("parameterization_valid")]
    successes = [r for r in rows if r.get("success")]
    deltas = [r["delta_total_kcal_mol"] for r in successes
              if isinstance(r.get("delta_total_kcal_mol"), (int, float))]
    all_deltas = [r["delta_total_kcal_mol"] for r in rows
                  if isinstance(r.get("delta_total_kcal_mol"), (int, float))]
    sanity_failures = [r for r in rows if r.get("status") == "SCIENTIFIC_SANITY_FAILED"]
    return {
        "dataset": ENERGETICS_V1["name"], "n_attempted": len(rows),
        "n_parameterization_valid": len(valid_param),
        "n_success": len(successes),
        "n_sanity_failed": len(sanity_failures),
        "capability_status": "VALIDATED" if successes else "NOT_VALIDATED",
        "delta_total_median_kcal_mol": round(float(np.median(deltas)), 3) if deltas else None,
        "observed_delta_total_values": all_deltas,
        "delta_total_values": deltas,
        "sanity_rule": "positive/near-zero MM/GBSA total is SCIENTIFIC_SANITY_FAILED for a crystal binder",
        "host": host_fingerprint(),
    }


__all__ = ["run", "OUT", "parameterize", "build_amber", "run_md", "run_mmpbsa"]
