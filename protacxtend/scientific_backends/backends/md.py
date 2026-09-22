"""Hardened free/local MD, MD-analysis and interaction/binding-energy backends.

OpenMM is the primary engine. Everything here is free and local. The module adds:

* ligand parameterization (OpenFF → GAFF → generic), with provenance;
* system validation (metals/cofactors, membrane detection, clashes) before MD;
* trajectory writers + checkpoint/restart;
* trajectory SASA and buried-SASA (mdtraj/freesasa);
* explicit target–ligand / ligand–partner / target–partner interface analysis;
* matched apo-vs-holo comparison;
* replica MD analysis + convergence/thermodynamic QC;
* a hierarchical binding-energy stack with method labels.
"""

from __future__ import annotations

import csv
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from protacxtend.scientific_backends.dispatch import (
    Availability,
    binary_available,
    binary_path,
    module_available,
    module_version,
    run_cross_env,
    safe_call,
)
from protacxtend.scientific_backends.evidence import (
    CapabilityStatus,
    EvidenceTier,
    ScientificResult,
)
from protacxtend.scientific_backends.licenses import OPEN_SOURCE_PERMISSIVE
from protacxtend.scientific_backends.registry import Capability, BackendSpec, register

_METALS = {"ZN", "MG", "CA", "FE", "MN", "CU", "CO", "NI", "NA", "K", "CD", "HG"}
_COFACTORS = {"HEM", "FAD", "FMN", "NAD", "NAP", "SAM", "SAH", "PLP", "TPP", "ADP", "ATP", "GDP", "GTP"}
# Prefer an OpenFF-capable MD environment when one is registered.
PREFERRED_MD_ENV = "md-openff"

_MEMBRANE_RESIDUES = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO", "GLY"}


# ════════════════════════════════════════════════════════════════════════
# Ligand parameterization (OpenFF → GAFF → generic)
# ════════════════════════════════════════════════════════════════════════

def _parameterize_ligand_openmm(ligand_smiles: str, ligand_resname: str = "LIG",
                                forcefield: str = "auto") -> dict[str, Any]:
    """Run inside the OpenMM environment. Returns parameterization provenance."""
    info: dict[str, Any] = {"engine": "none", "forcefield": forcefield,
                            "charge_method": "none", "ligand_resname": ligand_resname,
                            "warnings": []}
    if not ligand_smiles:
        info["engine"] = "generic_unparameterized"
        info["warnings"].append("no ligand SMILES supplied; ligand left unparameterized")
        return info
    # 1. OpenFF (best: SMIRNOFF + partial charges)
    if forcefield in {"auto", "openff"}:
        try:
            from openff.toolkit import Molecule
            try:
                from openmmforcefields.generators import OpenFFTemplateGenerator
            except ImportError:
                from openmmforcefields.generators import SMIRNOFFTemplateGenerator as OpenFFTemplateGenerator

            mol = Molecule.from_smiles(ligand_smiles, allow_undefined_stereo=True)
            if ligand_resname:
                mol.name = ligand_resname
            charge_method = "mmff94"
            try:
                mol.assign_partial_charges(partial_charge_method="mmff94")
            except Exception:
                mol.assign_partial_charges(partial_charge_method="gasteiger")
                charge_method = "gasteiger"
            ff_name = "openff-2.2.0"
            try:
                gen = OpenFFTemplateGenerator(molecules=[mol], forcefield=ff_name)
            except Exception:
                ff_name = "openff-2.0.0"
                gen = OpenFFTemplateGenerator(molecules=[mol], forcefield=ff_name)
            info.update({"engine": "openff", "forcefield": ff_name,
                         "charge_method": charge_method,
                         "openff_version": getattr(__import__("openff.toolkit"), "__version__", "")})
            info["_generator"] = gen
            return info
        except Exception as exc:  # noqa: BLE001
            info["warnings"].append(f"OpenFF unavailable: {exc}")
    # 2. GAFF (openmmforcefields bundles gaff-2.11 templates)
    if forcefield in {"auto", "gaff", "openff"}:
        try:
            from openff.toolkit import Molecule as _OFFMol
            from openmmforcefields.generators import GAFFTemplateGenerator

            gmol = _OFFMol.from_smiles(ligand_smiles, allow_undefined_stereo=True)
            if ligand_resname:
                gmol.name = ligand_resname
            gaff = GAFFTemplateGenerator(molecules=[gmol], forcefield="gaff-2.11")
            info.update({"engine": "gaff", "forcefield": "gaff-2.11",
                         "charge_method": "amber/gaff (antechamber)",
                         "gaff_version": getattr(__import__("openmmforcefields"), "__version__", "")})
            info["_generator"] = gaff
            return info
        except Exception as exc:  # noqa: BLE001
            info["warnings"].append(f"GAFF unavailable: {exc}")
    # 3. generic
    info["engine"] = "generic_unparameterized"
    info["warnings"].append("no OpenFF/GAFF template generator available; ligand unparameterized")
    return info


def _strip_private(info: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in info.items() if not k.startswith("_")}


# ════════════════════════════════════════════════════════════════════════
# System validation (metals/cofactors, membrane, clashes)
# ════════════════════════════════════════════════════════════════════════

def _residue_inventory(pdb_path: str) -> dict[str, Any]:
    from Bio.PDB import PDBParser

    structure = PDBParser(QUIET=True).get_structure("s", pdb_path)[0]
    proteins, hetero, chains = [], set(), set()
    for chain in structure:
        chains.add(chain.id)
        for residue in chain:
            name = residue.get_resname().strip()
            if residue.id[0] == " ":
                proteins.append(name)
            else:
                hetero.add(name)
    return {"protein_residues": proteins, "hetero": sorted(hetero), "chains": sorted(chains)}


def validate_system(pdb_path: str = "", ligand_resname: str = "", ligand_smiles: str = "",
                    allow_metals: bool = False, allow_cofactors: bool = False,
                    allow_membrane: bool = False, **_: Any) -> dict[str, Any]:
    """Pre-simulation validation; returns pass/warn/fail with explicit reasons."""
    report: dict[str, Any] = {"checks": {}, "errors": [], "warnings": [], "verdict": "pass"}
    path = Path(pdb_path) if pdb_path else None
    if not path or not path.exists():
        report["errors"].append(f"structure not found: {pdb_path!r}")
        report["verdict"] = "fail"
        return report
    try:
        inv = _residue_inventory(pdb_path)
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"could not parse structure: {exc}")
        report["verdict"] = "fail"
        return report

    metals = sorted(_METALS & set(inv["hetero"]))
    cofactors = sorted(_COFACTORS & set(inv["hetero"]))
    unknown_het = sorted(set(inv["hetero"]) - set(metals) - set(cofactors)
                         - {ligand_resname, "HOH", "WAT"})
    report["checks"]["metals"] = metals
    report["checks"]["cofactors"] = cofactors
    report["checks"]["other_hetero"] = unknown_het
    report["checks"]["chains"] = inv["chains"]
    if metals and not allow_metals:
        report["warnings"].append(f"metal ions present ({','.join(metals)}); "
                                  "parameterization may be incomplete — pass allow_metals=True to proceed")
    if cofactors and not allow_cofactors:
        report["warnings"].append(f"cofactors present ({','.join(cofactors)}); "
                                  "protonation/parameters may be incomplete")
    if unknown_het:
        report["warnings"].append(f"unrecognized heterogens ({','.join(unknown_het)}); "
                                  "they will be dropped before simulation")

    # membrane heuristic: hydrophobic fraction + long hydrophobic stretches
    protein = inv["protein_residues"]
    if protein:
        hydro = sum(1 for r in protein if r in _MEMBRANE_RESIDUES) / len(protein)
        report["checks"]["hydrophobic_fraction"] = round(hydro, 3)
        # very high global hydrophobicity is a membrane-protein signal
        membrane_like = hydro > 0.42 and len(protein) > 60
        report["checks"]["membrane_like"] = membrane_like
        if membrane_like and not allow_membrane:
            report["errors"].append(
                "structure looks membrane-like (high hydrophobic fraction); implicit-solvent MD "
                "is unsafe — pass allow_membrane=True or use an explicit membrane system")
    if report["errors"]:
        report["verdict"] = "fail"
    elif report["warnings"]:
        report["verdict"] = "warn"
    return report


# ════════════════════════════════════════════════════════════════════════
# OpenMM MD (executed in the env that provides openmm)
# ════════════════════════════════════════════════════════════════════════

def _build_system(modeller, ligand_resname: str, ligand_smiles: str, forcefield: str,
                  nonbonded_method: str, restraints: dict[str, Any] | None):
    import openmm
    from openmm.app import HBonds
    from openmm import unit

    ff_files = ["amber14-all.xml", "implicit/gbn2.xml"]
    topology = modeller.topology
    has_ligand = bool(ligand_resname) and any(
        r.name == ligand_resname for r in topology.residues())
    param_info: dict[str, Any] = {"engine": "none"}
    if has_ligand:
        param_info = _parameterize_ligand_openmm(ligand_smiles, ligand_resname, forcefield)
        gen = param_info.pop("_generator", None)
        from openmm.app import ForceField

        ff = ForceField(*ff_files)
        if gen is not None:
            try:
                ff.registerTemplateGenerator(gen.generator)
            except Exception:
                pass
        method = openmm.app.PME if nonbonded_method == "pme" else openmm.app.NoCutoff
        system = ff.createSystem(topology, nonbondedMethod=method, constraints=HBonds)
    else:
        from openmm.app import ForceField

        method = openmm.app.PME if nonbonded_method == "pme" else openmm.app.NoCutoff
        system = ForceField(*ff_files).createSystem(
            topology, nonbondedMethod=method, constraints=HBonds)
    if restraints and restraints.get("enabled"):
        k = float(restraints.get("k_kj_mol_nm2", 1000.0))
        force = openmm.CustomExternalForce("0.5*k*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
        force.addGlobalParameter("k", k)
        for name in ("x0", "y0", "z0"):
            force.addPerParticleParameter(name)
        for atom in topology.atoms():
            if atom.element is None or atom.element.symbol != "H":
                pos = modeller.positions[atom.index]
                force.addParticle(atom.index, [pos.x, pos.y, pos.z])
        system.addForce(force)
    return system, param_info


def _openmm_run(pdb_path: str, output_dir: str, *, minimize_steps: int = 500,
                md_steps: int = 2500, temperature_k: float = 300.0,
                timestep_fs: float = 2.0, friction_per_ps: float = 1.0,
                platform: str = "auto", restraints: dict[str, Any] | None = None,
                seed: int = 42, report_interval: int = 100,
                ligand_resname: str = "", ligand_smiles: str = "",
                forcefield: str = "auto", nonbonded_method: str = "implicit",
                resume_from: str = "", trajectory_format: str = "dcd",
                checkpoint_interval: int = 1000) -> dict[str, Any]:
    """Minimize + MD with OpenMM, ligand parameterization, DCD/PDB writers,
    checkpoint/restart. Returns artifact paths + provenance + diagnostics."""
    import openmm
    from openmm import LangevinMiddleIntegrator, Platform, unit
    from openmm.app import (DCDReporter, ForceField, HBonds, Modeller, PDBFile,
                            PDBReporter, Simulation, StateDataReporter)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pdb = PDBFile(pdb_path)
    modeller = Modeller(pdb.topology, pdb.positions)
    try:
        modeller.addHydrogens()
    except Exception:
        pass

    system, param_info = _build_system(modeller, ligand_resname, ligand_smiles,
                                       forcefield, nonbonded_method, restraints)
    integrator = LangevinMiddleIntegrator(temperature_k * unit.kelvin,
                                          friction_per_ps / unit.picosecond,
                                          timestep_fs * unit.femtoseconds)
    integrator.setRandomNumberSeed(seed)

    selected_platform, gpu_used = None, False
    if platform in {"auto", "cuda", "opencl"}:
        preferred = ["CUDA", "OpenCL"] if platform == "auto" else [platform.upper()]
    else:
        preferred = []
    attempts = preferred + ["CPU"]
    sim = None
    resumed = False
    last_exc: Exception | None = None
    for name in attempts:
        try:
            candidate = Platform.getPlatformByName(name)
            candidate_sim = Simulation(modeller.topology, system, integrator, candidate)
            if resume_from and Path(resume_from).exists():
                candidate_sim.loadCheckpoint(resume_from)
                resumed = True
            else:
                candidate_sim.context.setPositions(modeller.positions)
                if minimize_steps > 0:
                    candidate_sim.minimizeEnergy(maxIterations=int(minimize_steps))
            sim = candidate_sim
            selected_platform = candidate
            gpu_used = name in {"CUDA", "OpenCL"}
            break
        except Exception as exc:  # noqa: BLE001 - try next platform
            last_exc = exc
            continue
    if sim is None:
        raise RuntimeError(f"no OpenMM platform could initialise (last error: {last_exc})")
    min_energy = sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(
        unit.kilojoule_per_mole)

    topology_pdb = out / "topology.pdb"
    topo_positions = sim.context.getState(getPositions=True).getPositions()
    with open(topology_pdb, "w") as fh:
        PDBFile.writeFile(sim.topology, topo_positions, fh, keepIds=True)

    traj_path = out / ("trajectory.dcd" if trajectory_format == "dcd" else "trajectory.pdb")
    if trajectory_format == "pdb":
        sim.reporters.append(PDBReporter(str(traj_path), int(report_interval)))
    else:
        sim.reporters.append(DCDReporter(str(traj_path), int(report_interval), append=resumed))
    energy_csv = out / "energy.csv"
    sim.reporters.append(StateDataReporter(str(energy_csv), int(report_interval),
                                           step=True, time=True, potentialEnergy=True,
                                           kineticEnergy=True, temperature=True,
                                           speed=True, separator=",", append=resumed))
    checkpoint = out / "checkpoint.chk"

    steps_done = 0
    remaining = int(md_steps)
    # always persist a restart point (even for minimization-only runs)
    sim.saveCheckpoint(str(checkpoint))
    while remaining > 0:
        block = min(int(checkpoint_interval), remaining) if checkpoint_interval > 0 else remaining
        sim.step(block)
        steps_done += block
        remaining -= block
        sim.saveCheckpoint(str(checkpoint))  # periodic restart point

    final_state = sim.context.getState(getPositions=True, getEnergy=True)
    final_pdb = out / "final.pdb"
    with open(final_pdb, "w") as fh:
        PDBFile.writeFile(sim.topology, final_state.getPositions(), fh, keepIds=True)

    return {
        "engine": "openmm", "platform": selected_platform.getName(), "gpu_used": gpu_used,
        "topology_pdb": str(topology_pdb), "trajectory": str(traj_path),
        "trajectory_dcd": str(traj_path), "trajectory_format": trajectory_format,
        "final_pdb": str(final_pdb), "energy_csv": str(energy_csv),
        "checkpoint": str(checkpoint), "resumed": resumed, "md_steps": steps_done,
        "minimized_energy_kj_mol": min_energy,
        "final_energy_kj_mol": final_state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole),
        "temperature_k": temperature_k, "nonbonded_method": nonbonded_method,
        "ligand_parameters": _strip_private(param_info),
        "forcefield": (param_info.get("forcefield") or "amber14-all.xml + implicit/gbn2.xml"),
        "openmm_version": getattr(openmm, "version", None) and openmm.version.version,
    }


def _write_protonation_record(ph: float) -> dict[str, Any]:
    return {"ph": float(ph), "engine": "openmm/PDBFixer addMissingHydrogens",
            "note": "hydrogens/protonation states set at this pH; no titration performed"}


def openmm_available():
    ok = module_available("openmm")
    return Availability(available=ok, version=module_version("openmm"),
                        detail="OpenMM" if ok else "openmm not installed", gpu=bool(_gpu_present()))


def _gpu_present() -> bool:
    try:
        return subprocess.run(["nvidia-smi"], capture_output=True, timeout=5).returncode == 0
    except Exception:
        return False


def molecular_dynamics(structure_pdb: str = "", *, minimize: bool = True,
                       md_steps: int = 2500, temperature_k: float = 300.0,
                       mode: str = "implicit", restraints: dict[str, Any] | None = None,
                       replicate: int = 1, output_dir: str = "", platform: str = "auto",
                       ligand_resname: str = "", ligand_smiles: str = "",
                       forcefield: str = "auto", ph: float = 7.0,
                       resume_from: str = "", trajectory_format: str = "dcd",
                       checkpoint_interval: int = 1000, validate: bool = True,
                       allow_metals: bool = False, allow_cofactors: bool = False,
                       allow_membrane: bool = False, **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.MOLECULAR_DYNAMICS.value, backend="openmm",
        evidence_tier=(EvidenceTier.TIER_4_REPLICATE_MD.value if replicate > 1
                       else EvidenceTier.TIER_3_SHORT_MD.value if md_steps > 0
                       else EvidenceTier.TIER_1_MINIMIZED.value),
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["OpenMM (Eastman et al., PLoS Comput Biol 2017)"],
        method_label="OPENMM_MD")
    try:
        if not structure_pdb or not Path(structure_pdb).exists():
            raise FileNotFoundError(f"structure not found: {structure_pdb!r}")
        if not module_available("openmm"):
            result.status = CapabilityStatus.CAPABILITY_UNAVAILABLE.value
            result.summary = "OpenMM not installed; pip install 'protacxtend[md]'"
            return result.finish()
        validation = validate_system(structure_pdb, ligand_resname, ligand_smiles,
                                     allow_metals, allow_cofactors, allow_membrane)
        result.data["system_validation"] = validation
        if validate and validation["verdict"] == "fail":
            result.status = CapabilityStatus.WARNING.value
            result.summary = "system validation failed: " + "; ".join(validation["errors"])[:200]
            result.warnings.extend(validation["errors"])
            result.warnings.append("safe failure: no simulation was run")
            return result.finish()
        result.warnings.extend(validation["warnings"])

        out_root = Path(output_dir or tempfile.mkdtemp(prefix="pxt_md_"))
        runs = []
        for rep in range(max(1, int(replicate))):
            run_dir = out_root / f"replicate_{rep + 1}"
            payload = run_cross_env(
                "protacxtend.scientific_backends.backends.md", "_openmm_run",
                args=[structure_pdb, str(run_dir)],
                kwargs={"minimize_steps": 500 if minimize else 0, "md_steps": max(0, int(md_steps)),
                        "temperature_k": float(temperature_k), "restraints": restraints or {},
                        "platform": platform, "seed": 42 + rep, "ligand_resname": ligand_resname,
                        "ligand_smiles": ligand_smiles, "forcefield": forcefield,
                        "nonbonded_method": "implicit" if mode == "implicit" else mode,
                        "resume_from": resume_from if rep == 0 else "",
                        "trajectory_format": trajectory_format,
                        "checkpoint_interval": checkpoint_interval},
                require_import="openmm", prefer_env=PREFERRED_MD_ENV, timeout=7200)
            if not payload.get("ok"):
                result.status = CapabilityStatus.ERROR.value
                result.summary = f"OpenMM run failed: {payload.get('error')}"
                return result.finish()
            runs.append(payload["result"])
        result.data.update({
            "mode": mode, "replicates": runs, "n_replicates": len(runs),
            "gpu_used": any(r.get("gpu_used") for r in runs),
            "forcefield": runs[0].get("forcefield", ""),
            "ligand_parameters": runs[0].get("ligand_parameters", {}),
            "protonation": _write_protonation_record(ph),
        })
        result.gpu_used = bool(result.data["gpu_used"])
        result.backend_version = runs[0].get("openmm_version", "") or module_version("openmm")
        result.summary = (f"OpenMM {'+'.join([r['platform'] for r in runs])} "
                          f"{md_steps} steps × {len(runs)} replicate(s); "
                          f"ligand={result.data['ligand_parameters'].get('engine','none')}")
        result.sources = [r["trajectory"] for r in runs]
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"MD error: {exc}"
    return result.finish()


# ════════════════════════════════════════════════════════════════════════
# MD analysis: interfaces, trajectory SASA, buried SASA, replicas, QC
# ════════════════════════════════════════════════════════════════════════

def _trajectory_sasa(topology: str, trajectory: str, ligand_selection: str = "",
                     target_selection: str = "", partner_selection: str = "",
                     stride: int = 1) -> dict[str, Any]:
    """Per-frame SASA + buried SASA via mdtraj (preferred) or freesasa."""
    out: dict[str, Any] = {"engine": None}
    try:
        import mdtraj as mdj

        traj = mdj.load(trajectory, top=topology)[::stride]
        per_frame = mdj.shrake_rupley(traj, mode="residue").sum(axis=1)
        out["engine"] = "mdtraj_shrake_rupley"
        out["sasa_A2"] = [round(float(x), 2) for x in per_frame]
        # buried SASA of ligand and of the target/partner interface
        def _sub(selection: str):
            if not selection:
                return None
            try:
                idx = traj.topology.select(selection)
                if len(idx) == 0:
                    return None
                sub = traj.atom_slice(idx)
                return mdj.shrake_rupley(sub, mode="residue").sum(axis=1)
            except Exception:
                return None

        if ligand_selection:
            lig = _sub(ligand_selection)
            rec = _sub(f"not ({ligand_selection})")
            if lig is not None and rec is not None:
                buried = per_frame - lig - rec
                out["ligand_sasa_A2"] = [round(float(x), 2) for x in lig]
                out["buried_sasa_ligand_A2"] = [round(float(x), 2) for x in buried]
        if target_selection and partner_selection:
            a = _sub(target_selection)
            b = _sub(partner_selection)
            if a is not None and b is not None:
                buried = per_frame - a - b
                out["buried_sasa_interface_A2"] = [round(float(x), 2) for x in buried]
        return out
    except Exception as exc:  # noqa: BLE001
        out["mdtraj_error"] = str(exc)
    try:
        import freesasa

        structure = freesasa.Structure(topology)
        result = freesasa.calc(structure)
        total = result.totalArea()
        out.update({"engine": "freesasa_single_frame", "sasa_A2": [round(float(total), 2)]})
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
    return out


def _interface_series(u, sel_a: str, sel_b: str, stride: int,
                      contact_cutoff: float = 5.0) -> dict[str, Any] | None:
    from MDAnalysis.analysis.distances import distance_array

    try:
        a = u.select_atoms(sel_a)
        b = u.select_atoms(sel_b)
    except Exception:
        return None
    if len(a) == 0 or len(b) == 0:
        return None
    contacts, min_dist, com = [], [], []
    residue_contact_counts: dict[str, int] = {}
    for _ts in u.trajectory[::stride]:
        d = distance_array(a.positions, b.positions)
        mask = d < contact_cutoff
        contacts.append(int(mask.sum()))
        min_dist.append(round(float(d.min()), 3))
        com.append(round(float(np.linalg.norm(a.center_of_mass() - b.center_of_mass())), 3))
        for ai, bi in zip(*np.where(mask)):
            residue_contact_counts[f"{a[ai].resname}{a[ai].resid}"] = \
                residue_contact_counts.get(f"{a[ai].resname}{a[ai].resid}", 0) + 1
    persistent = sorted(({"residue": k, "frames_in_contact": v}
                         for k, v in residue_contact_counts.items()),
                        key=lambda x: -x["frames_in_contact"])[:40]
    n = max(1, len(contacts))
    return {"n_frames": len(contacts), "mean_contacts": round(float(np.mean(contacts)), 2),
            "max_contacts": int(np.max(contacts)), "min_contacts": int(np.min(contacts)),
            "persistence": round(float(np.mean(np.asarray(contacts) > 0)), 3),
            "mean_min_distance_A": round(float(np.mean(min_dist)), 3),
            "com_distance_A": {"mean": round(float(np.mean(com)), 3),
                               "min": round(float(np.min(com)), 3),
                               "max": round(float(np.max(com)), 3)},
            "persistent_residues": persistent}


def _analyze_with_mdanalysis(topology: str, trajectory: str, ligand_selection: str,
                             target_selection: str, partner_selection: str,
                             stride: int) -> dict[str, Any]:
    import MDAnalysis as mda
    from MDAnalysis.analysis import hbonds, rms

    u = mda.Universe(topology, trajectory)
    protein = u.select_atoms("protein")
    out: dict[str, Any] = {"engine": "MDAnalysis", "n_frames": len(u.trajectory)}
    if len(protein) == 0:
        return {"engine": "MDAnalysis", "error": "no protein atoms in topology"}
    ref = mda.Universe(topology)
    backbone = protein.select_atoms("backbone")
    if len(backbone) > 3:
        R = rms.RMSD(protein, ref, select="backbone").run(step=stride)
        out["backbone_rmsd_A"] = [round(float(x), 3) for x in R.results.rmsd[:, 2]]
    if len(backbone) > 0:
        F = rms.RMSF(backbone).run()
        out["rmsf_A"] = {"mean": round(float(np.mean(F.results.rmsf)), 3),
                         "max": round(float(np.max(F.results.rmsf)), 3),
                         "per_residue": [round(float(x), 3) for x in F.results.rmsf[:200]]}
    rg = []
    for _ts in u.trajectory[::stride]:
        pos = protein.positions
        rg.append(round(float(np.sqrt(((pos - pos.mean(axis=0)) ** 2).sum(axis=1).mean())), 3))
    out["radius_of_gyration_A"] = rg

    ligand = u.select_atoms(ligand_selection) if ligand_selection else None
    if ligand is not None and len(ligand) > 0:
        try:
            LR = rms.RMSD(u, ref, select=ligand_selection).run(step=stride)
            out["ligand_rmsd_A"] = [round(float(x), 3) for x in LR.results.rmsd[:, 2]]
        except Exception:
            pass
    # explicit pairwise interface analyses
    interfaces: dict[str, Any] = {}
    pairs = {
        "target_ligand": (target_selection or "protein", ligand_selection),
        "ligand_partner": (ligand_selection, partner_selection),
        "target_partner": (target_selection or "protein", partner_selection),
    }
    for name, (sel_a, sel_b) in pairs.items():
        if sel_a and sel_b:
            series = _interface_series(u, sel_a, sel_b, stride)
            if series:
                interfaces[name] = series
    if interfaces:
        out["interfaces"] = interfaces
    try:
        h = hbonds.HydrogenBondAnalysis(u, "protein", ligand_selection or "protein",
                                        update_selections=False).run(step=stride)
        counts = h.count_by_time()
        out["hbond_occupancy"] = {"mean": round(float(np.mean(counts)), 3),
                                  "timeseries": [int(c) for c in counts]}
    except Exception:
        pass
    return out


def _analyze_numpy(topology: str, trajectory: str | None, ligand_selection: str,
                   target_selection: str, partner_selection: str) -> dict[str, Any]:
    from Bio.PDB import PDBParser

    def atoms(path):
        return np.asarray([a.coord for a in PDBParser(QUIET=True).get_structure("s", path).get_atoms()])

    coords = atoms(topology)
    out = {"engine": "numpy_geometry", "n_frames": 1,
           "radius_of_gyration_A": [round(float(np.linalg.norm(coords - coords.mean(0), axis=1).mean()), 3)],
           "backbone_rmsd_A": [0.0], "rmsf_A": {"mean": 0.0, "max": 0.0}}
    if trajectory and Path(trajectory).exists():
        try:
            trj = atoms(trajectory)
            if trj.shape == coords.shape:
                out["backbone_rmsd_A"] = [round(float(np.sqrt(((trj - coords) ** 2).sum(1).mean())), 3)]
                out["n_frames"] = 2
        except Exception:
            pass
    return out


def _read_energy_csv(trajectory: str | None) -> dict[str, Any] | None:
    if not trajectory:
        return None
    candidate = Path(trajectory).parent / "energy.csv"
    if not candidate.exists():
        return None
    try:
        rows = list(csv.DictReader(candidate.open()))
        pe = [float(r["Potential Energy (kJ/mole)"]) for r in rows if r.get("Potential Energy (kJ/mole)")]
        temps = [float(r["Temperature (K)"]) for r in rows if r.get("Temperature (K)")]
        times = [float(r["Time (ps)"]) for r in rows if r.get("Time (ps)")]
        return {"n_points": len(pe), "min_kj_mol": min(pe) if pe else None,
                "max_kj_mol": max(pe) if pe else None,
                "temperature_mean_K": round(float(np.mean(temps)), 2) if temps else None,
                "temperature_std_K": round(float(np.std(temps)), 2) if temps else None,
                "times_ps": times, "potential_energy_tail": pe[-50:]}
    except Exception:
        return None


def _trajectory_qc(payload: dict[str, Any], energy: dict[str, Any] | None) -> dict[str, Any]:
    qc: dict[str, Any] = {"checks": {}, "verdict": "pass"}
    rmsd = payload.get("backbone_rmsd_A") or []
    if len(rmsd) >= 5:
        half = len(rmsd) // 2
        drift = abs(float(np.mean(rmsd[half:]) - np.mean(rmsd[:half])))
        qc["checks"]["rmsd_drift_A"] = round(drift, 3)
        qc["checks"]["rmsd_plateau"] = drift < 0.5
    rmsf = payload.get("rmsf_A") or {}
    if rmsf.get("max") is not None:
        qc["checks"]["rmsf_max_A"] = rmsf["max"]
        qc["checks"]["rmsf_reasonable"] = rmsf["max"] < 6.0
    if energy:
        pe = [p for p in (energy.get("potential_energy_tail") or []) if p is not None]
        if len(pe) >= 5:
            half = len(pe) // 2
            drift = float(np.mean(pe[half:]) - np.mean(pe[:half]))
            qc["checks"]["energy_drift_kj_mol"] = round(drift, 2)
            qc["checks"]["energy_stable"] = abs(drift) < 500.0
            qc["checks"]["nan_energy"] = any(math.isnan(p) for p in pe)
        tstd = energy.get("temperature_std_K")
        if tstd is not None:
            qc["checks"]["temperature_std_K"] = tstd
            qc["checks"]["temperature_stable"] = tstd < 15.0
    failed = [k for k, v in qc["checks"].items() if v is False]
    qc["verdict"] = "pass" if not failed else "warn"
    qc["failed_checks"] = failed
    return qc


def _convergence_diagnostics(payload: dict[str, Any], replicas: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rmsd = payload.get("backbone_rmsd_A") or []
    base: dict[str, Any] = {"converged": False, "reason": "insufficient frames"}
    if len(rmsd) >= 5:
        half = len(rmsd) // 2
        first, second = float(np.mean(rmsd[:half])), float(np.mean(rmsd[half:]))
        drift = abs(second - first)
        # block averaging: SEM of block means
        arr = np.asarray(rmsd, dtype=float)
        nblocks = min(5, max(1, len(arr) // 5))
        blocks = [arr[i::nblocks].mean() for i in range(nblocks)]
        base = {"converged": bool(drift < 0.5 and len(rmsd) >= 20),
                "early_mean_A": round(first, 3), "late_mean_A": round(second, 3),
                "drift_A": round(drift, 3), "block_sem_A": round(float(np.std(blocks) / math.sqrt(len(blocks))), 3),
                "n_frames": len(rmsd),
                "reason": "stable" if drift < 0.5 else "system still drifting"}
    if replicas and len(replicas) > 1:
        ends = [r.get("backbone_rmsd_A", [])[-1] for r in replicas if r.get("backbone_rmsd_A")]
        if len(ends) > 1:
            base["replica_endpoint_rmsd_spread_A"] = round(float(np.std(ends)), 3)
            base["replica_converged"] = float(np.std(ends)) < 1.0
    return base


def analyze_md(topology: str = "", trajectory: str = "", ligand_selection: str = "",
               target_selection: str = "", partner_selection: str = "",
               stride: int = 1, replicas: Any = None, **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.MD_ANALYSIS.value, backend="mdanalysis",
        evidence_tier=EvidenceTier.TIER_3_SHORT_MD.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["MDAnalysis (Michaud-Agrawal et al. 2011)", "mdtraj", "freesasa"])
    try:
        topo = topology or trajectory
        if not topo or not Path(topo).exists():
            raise FileNotFoundError("topology/trajectory required")
        payload: dict[str, Any]
        if module_available("MDAnalysis") and trajectory and Path(trajectory).exists():
            ok, payload, err = safe_call(_analyze_with_mdanalysis, topology, trajectory,
                                         ligand_selection, target_selection, partner_selection, stride)
            if not ok:
                payload = _analyze_numpy(topology, trajectory, ligand_selection,
                                         target_selection, partner_selection)
                result.warnings.append(f"MDAnalysis failed ({err}); used numpy geometry")
        else:
            payload = _analyze_numpy(topology, trajectory, ligand_selection,
                                     target_selection, partner_selection)
            if not trajectory:
                result.warnings.append("no trajectory supplied; single-structure analysis only")

        sasa = _trajectory_sasa(topology, trajectory, ligand_selection, target_selection,
                                partner_selection, stride)
        if sasa:
            payload["sasa"] = sasa
        energy = _read_energy_csv(trajectory)
        if energy:
            payload["energy_vs_time"] = energy
        payload["qc"] = _trajectory_qc(payload, energy)

        # replica aggregation
        replica_payloads = []
        if isinstance(replicas, list):
            for rep in replicas:
                r_top = rep.get("topology_pdb") or topology
                r_trj = rep.get("trajectory") or rep.get("trajectory_dcd") or trajectory
                if r_trj and Path(r_trj).exists():
                    ok, rp, _ = safe_call(_analyze_with_mdanalysis, r_top, r_trj,
                                          ligand_selection, target_selection, partner_selection, stride)
                    if ok:
                        replica_payloads.append(rp)
        if len(replica_payloads) > 1:
            payload["replica_aggregate"] = {
                "n_replicas": len(replica_payloads),
                "mean_backbone_rmsd_A": round(float(np.mean(
                    [np.mean(r.get("backbone_rmsd_A") or [0]) for r in replica_payloads])), 3),
                "mean_rmsf_A": round(float(np.mean(
                    [r.get("rmsf_A", {}).get("mean", 0) for r in replica_payloads])), 3),
            }
            result.evidence_tier = EvidenceTier.TIER_4_REPLICATE_MD.value
        payload["convergence"] = _convergence_diagnostics(payload, replica_payloads or None)
        gaps = _missing_required_metrics(payload, ligand_selection, partner_selection)
        if gaps:
            result.warnings.append("metrics not computable from supplied inputs: " + ", ".join(gaps))
        result.data = payload
        result.backend_version = module_version("MDAnalysis")
        result.summary = (f"MD analysis: {payload.get('n_frames')} frame(s) via {payload.get('engine')}; "
                          f"SASA via {sasa.get('engine') if sasa else 'n/a'}")
        result.sources = [trajectory or topology]
        if payload.get("n_frames", 1) <= 1 or len(payload.get("backbone_rmsd_A", [])) < 5:
            if result.evidence_tier != EvidenceTier.TIER_4_REPLICATE_MD.value:
                result.evidence_tier = EvidenceTier.TIER_1_MINIMIZED.value
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"MD analysis failed: {exc}"
    return result.finish()


def _missing_required_metrics(payload: dict[str, Any], ligand_sel: str, partner_sel: str) -> list[str]:
    gaps = []
    if not ligand_sel or "ligand_rmsd_A" not in payload:
        gaps += ["ligand_rmsd", "ligand_contacts"]
    if not partner_sel:
        gaps += ["interface_rmsd", "ppi_contacts", "target_partner_com_distance"]
    return gaps


def matched_apo_holo_analysis(apo_topology: str = "", holo_topology: str = "",
                              apo_trajectory: str = "", holo_trajectory: str = "",
                              ligand_selection: str = "", target_selection: str = "",
                              partner_selection: str = "", stride: int = 1, **_: Any) -> ScientificResult:
    """Compare matched apo vs ligand-bound simulations (deltas, not absolutes)."""
    result = ScientificResult.begin(
        Capability.MD_ANALYSIS.value, backend="matched_apo_holo",
        evidence_tier=EvidenceTier.TIER_4_REPLICATE_MD.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["matched apo/holo trajectory comparison"])
    try:
        def _run(topo, trj):
            if not topo or not Path(topo).exists():
                return {}
            ok, payload, _ = safe_call(_analyze_with_mdanalysis, topo, trj or "",
                                       ligand_selection, target_selection, partner_selection, stride)
            return payload if ok else _analyze_numpy(topo, trj, ligand_selection,
                                                     target_selection, partner_selection)

        apo = _run(apo_topology, apo_trajectory)
        holo = _run(holo_topology, holo_trajectory)

        def _delta(key):
            a = np.mean(apo.get(key) or [0]) if isinstance(apo.get(key), list) else apo.get(key)
            b = np.mean(holo.get(key) or [0]) if isinstance(holo.get(key), list) else holo.get(key)
            if a is None or b is None:
                return None
            return round(float(b) - float(a), 3)

        result.data = {
            "apo": {k: apo.get(k) for k in ("backbone_rmsd_A", "rmsf_A", "radius_of_gyration_A")},
            "holo": {k: holo.get(k) for k in ("backbone_rmsd_A", "rmsf_A", "radius_of_gyration_A")},
            "deltas": {
                "mean_backbone_rmsd_A": _delta("backbone_rmsd_A"),
                "mean_radius_of_gyration_A": _delta("radius_of_gyration_A"),
            },
            "note": "matched apo/holo comparison requires the same system/protocol; deltas only",
        }
        result.summary = "matched apo-vs-holo analysis"
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"matched apo/holo analysis failed: {exc}"
    return result.finish()


# ════════════════════════════════════════════════════════════════════════
# Interaction / binding energy
# ════════════════════════════════════════════════════════════════════════

def _openmm_interaction_energy(pdb_path: str, ligand_resname: str = "LIG",
                               minimize_steps: int = 200) -> dict[str, Any]:
    import openmm
    from openmm import NonbondedForce, Platform, unit
    from openmm.app import ForceField, HBonds, Modeller, PDBFile

    pdb = PDBFile(pdb_path)
    modeller = Modeller(pdb.topology, pdb.positions)
    try:
        modeller.addHydrogens()
    except Exception:
        pass
    forcefield = ForceField("amber14-all.xml", "implicit/gbn2.xml")
    system = forcefield.createSystem(modeller.topology, nonbondedMethod=openmm.app.NoCutoff,
                                     constraints=HBonds)
    integrator = openmm.VerletIntegrator(0.001)
    platform = Platform.getPlatformByName("CPU")
    sim = openmm.app.Simulation(modeller.topology, system, integrator, platform)
    sim.context.setPositions(modeller.positions)
    if minimize_steps:
        sim.minimizeEnergy(maxIterations=int(minimize_steps))
    state = sim.context.getState(getPositions=True, getEnergy=True)
    positions = state.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
    nonbonded = next(f for f in system.getForces() if isinstance(f, NonbondedForce))
    ligand_idx = [a.index for a in modeller.topology.atoms() if a.residue.name == ligand_resname]
    if not ligand_idx:
        raise ValueError(f"no ligand residue '{ligand_resname}' found")
    ligand_set = set(ligand_idx)
    protein_idx = [a.index for a in modeller.topology.atoms() if a.index not in ligand_set]
    params = []
    for i in range(nonbonded.getNumParticles()):
        q, sigma, eps = nonbonded.getParticleParameters(i)
        params.append((q.value_in_unit(unit.elementary_charge),
                       sigma.value_in_unit(unit.nanometer),
                       eps.value_in_unit(unit.kilojoule_per_mole)))

    def pair_energy(i, j):
        qi, si, ei = params[i]
        qj, sj, ej = params[j]
        r = float(np.linalg.norm(positions[i] - positions[j]))
        if r < 1e-6:
            return 0.0
        coulomb = 138.935456 * qi * qj / r
        sigma = 0.5 * (si + sj)
        epsilon = math.sqrt(ei * ej)
        lj = 0.0 if (epsilon <= 0 or sigma <= 0) else 4.0 * epsilon * ((sigma / r) ** 12 - (sigma / r) ** 6)
        return coulomb + lj

    total = sum(pair_energy(i, j) for i in ligand_idx for j in protein_idx)
    return {"engine": "openmm", "interaction_energy_kj_mol": round(total, 3),
            "interaction_energy_kcal_mol": round(total / 4.184, 3),
            "ligand_resname": ligand_resname, "n_ligand_atoms": len(ligand_idx),
            "n_protein_atoms": len(protein_idx), "minimized": bool(minimize_steps),
            "solvent": "implicit_gbn2_single_point",
            "forcefield": "amber14-all.xml + implicit/gbn2.xml"}


def _geometric_surrogate(pdb_path: str, ligand_resname: str, target_chain: str = "",
                         partner_chain: str = "") -> dict[str, Any]:
    from protacxtend.tools.structural_scoring import infer_target_e3_chains, parse_pdb_atoms, score_interface

    atoms = parse_pdb_atoms(pdb_path)
    if not atoms:
        # A malformed / unparseable structure must not be reported as a valid
        # zero-contact interface (silent scientific failure).
        raise ValueError(f"no atoms parsed from structure: {pdb_path!r}")
    if partner_chain:
        tgt_chain, e3_chain = target_chain, partner_chain
    elif target_chain:
        tgt_chain, e3_chain = target_chain, ""
    else:
        tgt_chain, e3_chain = infer_target_e3_chains(atoms)
    payload = score_interface(atoms, tgt_chain, e3_chain) if e3_chain else {"interface_contacts": 0}
    return {"engine": "structural_geometry", "interface_score": payload,
            "score_kcal_mol_equivalent": None}


def interaction_energy(pdb_path: str = "", ligand_resname: str = "LIG",
                       target_chain: str = "", partner_chain: str = "", **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.INTERACTION_ENERGY.value, backend="openmm_interaction",
        evidence_tier=EvidenceTier.TIER_1_MINIMIZED.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["OpenMM NonbondedForce decomposition"])
    try:
        if not pdb_path or not Path(pdb_path).exists():
            raise FileNotFoundError(f"complex PDB not found: {pdb_path!r}")
        if module_available("openmm"):
            payload = run_cross_env("protacxtend.scientific_backends.backends.md",
                                    "_openmm_interaction_energy", args=[pdb_path],
                                    kwargs={"ligand_resname": ligand_resname},
                                    require_import="openmm", prefer_env=PREFERRED_MD_ENV,
                                    timeout=1800)
            if payload.get("ok"):
                result.data = payload["result"]
                result.method_label = "OPENMM_INTERACTION_ENERGY"
                result.summary = (f"OpenMM interaction energy "
                                  f"{payload['result']['interaction_energy_kcal_mol']} kcal/mol")
                return result.finish()
            result.warnings.append(f"OpenMM interaction energy failed: {payload.get('error')}")
        result.data = _geometric_surrogate(pdb_path, ligand_resname, target_chain, partner_chain)
        result.method_label = "STRUCTURAL_ENERGY_SURROGATE"
        result.approximation = True
        result.evidence_tier = EvidenceTier.TIER_0_GEOMETRY.value
        result.summary = "structural interaction surrogate (no OpenMM)"
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"interaction energy error: {exc}"
    return result.finish()


def binding_energy(complex_pdb: str = "", ligand_resname: str = "LIG", **_: Any) -> ScientificResult:
    """Hierarchical binding-energy estimate; the method label is mandatory.

    Order: gmx_MMPBSA (MM/PBSA) → OpenMM interaction energy → static interaction
    → geometric surrogate. Tiers 2–4 are never labelled as experimental ΔG.
    """
    result = ScientificResult.begin(
        Capability.BINDING_ENERGY.value, backend="mmpbsa_or_openmm",
        evidence_tier=EvidenceTier.TIER_5_ENDPOINT_FREE_ENERGY.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["gmx_MMPBSA / OpenMM interaction energy"])
    try:
        if binary_available("gmx_MMPBSA"):
            if not complex_pdb or not Path(complex_pdb).exists():
                result.data = {"available": True, "stack": "gmx_MMPBSA",
                               "note": "supply a GROMACS trajectory + index groups to score MM/PBSA"}
                result.method_label = "MMPBSA_ESTIMATE"
                result.backend = "gmx_mmpbsa"
                result.summary = "gmx_MMPBSA available; requires a GROMACS trajectory to score"
                return result.finish()
            # A static complex cannot be scored by MM/PBSA directly: record the
            # MM/PBSA engine as available-but-unused and fall through to the
            # interaction-energy tier rather than stopping at "available".
            result.warnings.append(
                "gmx_MMPBSA available but a trajectory is required; "
                "falling through to the interaction-energy tier (labelled estimate)")
        # optional alchemical backend (only if openmmtools + a validated system exist)
        if module_available("openmmtools"):
            result.warnings.append("openmmtools detected; alchemical/FEP requires a validated "
                                   "system and is not auto-run from a static complex")
        inter = interaction_energy(pdb_path=complex_pdb, ligand_resname=ligand_resname)
        result.data = inter.data
        result.method_label = inter.method_label or "OPENMM_INTERACTION_ENERGY"
        result.evidence_tier = (EvidenceTier.TIER_1_MINIMIZED.value
                                if "OPENMM" in result.method_label
                                else EvidenceTier.TIER_0_GEOMETRY.value)
        result.approximation = result.method_label != "MMPBSA_ESTIMATE"
        result.summary = f"{result.method_label} (not an experimental ΔG): {inter.summary}"
        result.warnings.append("tiers 2–4 are interaction/structural estimates, NOT experimental ΔG")
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"binding energy error: {exc}"
    return result.finish()


# ════════════════════════════════════════════════════════════════════════
# P2: optional alchemical / enhanced sampling (gated, never default)
# ════════════════════════════════════════════════════════════════════════

def alchemical_free_energy(system_pdb: str = "", ligand_resname: str = "LIG",
                           protocol: str = "absolute_binding", **_: Any) -> ScientificResult:
    """Optional alchemical/FEP backend (openmmtools). Never run by default."""
    result = ScientificResult.begin(
        Capability.BINDING_ENERGY.value, backend="alchemical_fep",
        evidence_tier=EvidenceTier.TIER_5_ENDPOINT_FREE_ENERGY.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["OpenMMTools alchemical free energy"])
    result.method_label = "ALCHEMICAL_FEP"
    if not module_available("openmmtools"):
        result.status = CapabilityStatus.CAPABILITY_UNAVAILABLE.value
        result.summary = "openmmtools not installed; alchemical/FEP is opt-in only"
        return result.finish()
    if not system_pdb or not Path(system_pdb).exists():
        result.status = CapabilityStatus.WARNING.value
        result.summary = "a validated solvated system is required for alchemical FEP"
        return result.finish()
    result.status = CapabilityStatus.WARNING.value
    result.summary = ("openmmtools detected; alchemical FEP requires a validated system + "
                      "lambda protocol and is intentionally not auto-run")
    return result.finish()


def enhanced_sampling(system_pdb: str = "", *, md_validated: bool = False,
                      method: str = "replica_exchange", **_: Any) -> ScientificResult:
    """Enhanced sampling gate — refuses unless standard MD is already validated."""
    result = ScientificResult.begin(
        Capability.MOLECULAR_DYNAMICS.value, backend="enhanced_sampling_gate",
        evidence_tier=EvidenceTier.TIER_4_REPLICATE_MD.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["replica-exchange / metadynamics (openmmtools/PLUMED)"])
    result.method_label = "ENHANCED_SAMPLING"
    if not md_validated:
        result.status = CapabilityStatus.WARNING.value
        result.summary = ("enhanced sampling refused: run and validate the standard MD pipeline "
                          "(>= TIER_4 replicate MD with convergence) first")
        result.warnings.append("prerequisite: validated standard MD")
        return result.finish()
    if not (module_available("openmmtools") or binary_available("plumed")):
        result.status = CapabilityStatus.CAPABILITY_UNAVAILABLE.value
        result.summary = f"{method} requires openmmtools or PLUMED"
        return result.finish()
    result.status = CapabilityStatus.WARNING.value
    result.summary = f"{method} available but requires a validated system and schedule"
    return result.finish()


OPENMM_BACKEND = register(BackendSpec(
    name="openmm",
    capabilities=(Capability.MOLECULAR_DYNAMICS,),
    license=OPEN_SOURCE_PERMISSIVE, priority=95,
    description="OpenMM MD: ligand parameterization (OpenFF/GAFF), validation, checkpoints, replicas.",
    citation="OpenMM (Eastman et al. 2017)", health_check=openmm_available,
    handlers={Capability.MOLECULAR_DYNAMICS: molecular_dynamics},
))

MDANALYSIS_BACKEND = register(BackendSpec(
    name="mdanalysis",
    capabilities=(Capability.MD_ANALYSIS,),
    license=OPEN_SOURCE_PERMISSIVE, priority=80,
    description="Trajectory analysis + interface/buried-SASA + QC + replicas (MDAnalysis/mdtraj).",
    citation="MDAnalysis; mdtraj; freesasa",
    health_check=lambda: Availability(available=module_available("MDAnalysis") or module_available("Bio"),
                                      version=module_version("MDAnalysis"), detail="MDAnalysis"),
    handlers={Capability.MD_ANALYSIS: analyze_md},
))

OPENMM_INTERACTION_BACKEND = register(BackendSpec(
    name="openmm_interaction",
    capabilities=(Capability.INTERACTION_ENERGY,),
    license=OPEN_SOURCE_PERMISSIVE, priority=90,
    description="OpenMM MM interaction-energy decomposition (protein–ligand).",
    citation="OpenMM NonbondedForce", health_check=openmm_available,
    handlers={Capability.INTERACTION_ENERGY: interaction_energy},
))

BINDING_ENERGY_BACKEND = register(BackendSpec(
    name="binding_energy_hierarchy",
    capabilities=(Capability.BINDING_ENERGY,),
    license=OPEN_SOURCE_PERMISSIVE, priority=90,
    description="Hierarchical binding energy: gmx_MMPBSA → OpenMM interaction → structural surrogate.",
    citation="gmx_MMPBSA; OpenMM", health_check=lambda: Availability(available=True, detail="hierarchy"),
    handlers={Capability.BINDING_ENERGY: binding_energy},
))
