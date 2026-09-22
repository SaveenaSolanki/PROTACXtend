"""Staged OpenMM production runner + Amber export for MM/PBSA.

Executed inside the OpenFF/OpenMM environment via the cross-env bridge. Runs:

    minimize → restrained NVT equilibration → NVT → NPT (explicit) → production

with periodic checkpoints, restart support, a production trajectory, an energy
log, and optional Amber topology/trajectory export for MM/PBSA.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _build_system(modeller, ligand_resname: str, ligand_smiles: str, solvent: str,
                  ligand_forcefield: str = "auto"):
    import openmm
    from openmm.app import ForceField, HBonds
    from protacxtend.scientific_backends.backends.md import _parameterize_ligand_openmm

    ff_files = ["amber14-all.xml"]
    if solvent == "explicit":
        ff_files.append("amber14/tip3pfb.xml")
        nonbonded = openmm.app.PME
    else:
        ff_files.append("implicit/gbn2.xml")
        nonbonded = openmm.app.NoCutoff
    topology = modeller.topology
    has_ligand = bool(ligand_resname) and any(r.name == ligand_resname for r in topology.residues())
    param_info: dict[str, Any] = {"engine": "none"}
    ff = ForceField(*ff_files)
    if has_ligand:
        param_info = _parameterize_ligand_openmm(ligand_smiles, ligand_resname, ligand_forcefield)
        gen = param_info.pop("_generator", None)
        if gen is not None:
            try:
                ff.registerTemplateGenerator(gen.generator)
            except Exception:
                pass
    system = ff.createSystem(topology, nonbondedMethod=nonbonded, constraints=HBonds)
    return system, {k: v for k, v in param_info.items() if not k.startswith("_")}


def _select_platform(Simulation, top, system, integrator, platforms):
    from openmm import Platform

    sim, chosen, last = None, None, None
    for name in platforms:
        try:
            plat = Platform.getPlatformByName(name)
            sim = Simulation(top, system, integrator, plat)
            chosen = name
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
            sim = None
    if sim is None:
        raise RuntimeError(f"no OpenMM platform initialised (last: {last})")
    return sim, chosen


def _openmm_staged(
    pdb_path: str,
    output_dir: str,
    *,
    ligand_resname: str = "",
    ligand_smiles: str = "",
    minimize_steps: int = 500,
    restrained_steps: int = 1000,
    nvt_steps: int = 1000,
    npt_steps: int = 1000,
    production_steps: int = 2500,
    temperature_k: float = 300.0,
    pressure_bar: float = 1.0,
    solvent: str = "implicit",
    ionic_strength: float = 0.15,
    seed: int = 42,
    checkpoint_interval: int = 1000,
    report_interval: int = 50,
    resume_from: str = "",
    platform: str = "auto",
    export_amber: bool = False,
    ligand_forcefield: str = "auto",
) -> dict[str, Any]:
    import openmm
    from openmm import LangevinMiddleIntegrator, MonteCarloBarostat, unit
    from openmm.app import (DCDReporter, Modeller, PDBFile, Simulation,
                            StateDataReporter)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pdb = PDBFile(pdb_path)
    modeller = Modeller(pdb.topology, pdb.positions)
    try:
        modeller.addHydrogens()
    except Exception:
        pass
    if solvent == "explicit":
        from openmm.app import ForceField
        ff_solv = ForceField("amber14-all.xml", "amber14/tip3pfb.xml")
        modeller.addSolvent(ff_solv, padding=1.0 * unit.nanometer,
                            ionicStrength=ionic_strength * unit.molar)

    system, param_info = _build_system(modeller, ligand_resname, ligand_smiles, solvent,
                                       ligand_forcefield)
    add_barostat = solvent == "explicit"
    if add_barostat:
        system.addForce(MonteCarloBarostat(pressure_bar * unit.bar, temperature_k * unit.kelvin))

    # positional restraints with a settable force constant (kJ/mol/nm^2)
    restraint = openmm.CustomExternalForce("0.5*k*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
    restraint.addGlobalParameter("k", 0.0)
    for name in ("x0", "y0", "z0"):
        restraint.addPerParticleParameter(name)
    for atom in modeller.topology.atoms():
        if atom.element is None or atom.element.symbol != "H":
            pos = modeller.positions[atom.index]
            restraint.addParticle(atom.index, [pos.x, pos.y, pos.z])
    system.addForce(restraint)

    integrator = LangevinMiddleIntegrator(temperature_k * unit.kelvin,
                                          1.0 / unit.picosecond, 2.0 * unit.femtoseconds)
    integrator.setRandomNumberSeed(seed)

    platforms = (["CUDA", "OpenCL", "CPU"] if platform == "auto"
                 else [platform.upper(), "CPU"])
    sim, chosen_platform = _select_platform(Simulation, modeller.topology, system,
                                            integrator, platforms)
    gpu_used = chosen_platform in {"CUDA", "OpenCL"}
    resumed = False
    checkpoint = out / "checkpoint.chk"
    if resume_from and Path(resume_from).exists():
        sim.loadCheckpoint(resume_from)
        resumed = True
    else:
        sim.context.setPositions(modeller.positions)

    stage_log: list[dict[str, Any]] = []

    def _run_stage(name: str, steps: int, k: float = 0.0):
        sim.context.setParameter("k", k)
        if steps > 0:
            sim.step(int(steps))
        try:
            sim.saveCheckpoint(str(checkpoint))
        except Exception:
            pass
        state = sim.context.getState(getPositions=True, getEnergy=True)
        stage_pdb = out / f"stage_{name}.pdb"
        with open(stage_pdb, "w") as fh:
            PDBFile.writeFile(sim.topology, state.getPositions(), fh, keepIds=True)
        stage_log.append({
            "stage": name, "steps": int(steps), "restraint_k": k,
            "potential_energy_kj_mol": state.getPotentialEnergy().value_in_unit(
                unit.kilojoule_per_mole),
            "pdb": str(stage_pdb),
        })

    if minimize_steps > 0 and not resumed:
        sim.minimizeEnergy(maxIterations=int(minimize_steps))
        sim.saveCheckpoint(str(checkpoint))
        stage_log.append({"stage": "minimize", "steps": int(minimize_steps),
                          "restraint_k": 0.0, "pdb": ""})

    # restrained equilibration (release restraints over the stage)
    if restrained_steps > 0:
        _run_stage("restrained_nvt", restrained_steps, k=1000.0)
    # unrestrained NVT
    _run_stage("nvt", nvt_steps, k=0.0)
    # NPT only meaningful with a periodic explicit system
    if add_barostat and npt_steps > 0:
        _run_stage("npt", npt_steps, k=0.0)

    # production trajectory
    traj = out / "trajectory.dcd"
    energy_csv = out / "energy.csv"
    sim.reporters.clear()
    sim.reporters.append(DCDReporter(str(traj), int(report_interval), append=resumed))
    netcdf = out / "trajectory.nc"
    amber: dict[str, Any] = {}
    if export_amber:
        try:
            from parmed.openmm.reporters import NetCDFReporter

            sim.reporters.append(NetCDFReporter(str(netcdf), int(report_interval), crds=True))
            amber = _export_amber(sim.topology, system, str(out), traj)
            amber["netcdf"] = str(netcdf)
        except Exception as exc:  # noqa: BLE001
            amber = {"error": str(exc)}
    sim.reporters.append(StateDataReporter(str(energy_csv), int(report_interval),
                                           step=True, time=True, potentialEnergy=True,
                                           kineticEnergy=True, temperature=True,
                                           volume=True, density=True, speed=True,
                                           separator=",", append=resumed))
    steps_done = 0
    if production_steps > 0:
        remaining = int(production_steps)
        while remaining > 0:
            block = min(int(checkpoint_interval), remaining) if checkpoint_interval > 0 else remaining
            sim.step(block)
            steps_done += block
            remaining -= block
            sim.saveCheckpoint(str(checkpoint))
    final_state = sim.context.getState(getPositions=True, getEnergy=True)
    final_pdb = out / "final.pdb"
    with open(final_pdb, "w") as fh:
        PDBFile.writeFile(sim.topology, final_state.getPositions(), fh, keepIds=True)
    topology_pdb = out / "topology.pdb"
    with open(topology_pdb, "w") as fh:
        PDBFile.writeFile(sim.topology,
                          sim.context.getState(getPositions=True).getPositions(), fh, keepIds=True)

    amber: dict[str, Any] = dict(amber)

    return {
        "engine": "openmm", "platform": chosen_platform, "gpu_used": gpu_used,
        "solvent": solvent, "resumed": resumed,
        "topology_pdb": str(topology_pdb), "trajectory": str(traj),
        "final_pdb": str(final_pdb), "checkpoint": str(checkpoint),
        "energy_csv": str(energy_csv), "production_steps": steps_done,
        "stage_log": stage_log,
        "ligand_parameters": param_info,
        "forcefield": ("amber14-all.xml + amber14/tip3pfb.xml" if solvent == "explicit"
                       else "amber14-all.xml + implicit/gbn2.xml"),
        "n_atoms": int(sum(1 for _ in sim.topology.atoms())),
        "openmm_version": getattr(openmm, "version", None) and openmm.version.version,
        "amber": amber,
    }


def _export_amber(topology, system, out_dir: str, traj: str) -> dict[str, Any]:
    """Write Amber prmtop/inpcrd from the OpenMM system (ParmEd)."""
    import parmed as pmd

    out = Path(out_dir)
    structure = pmd.openmm.load_topology(topology, xyz=None, system=system)
    prmtop = out / "complex.prmtop"
    inpcrd = out / "complex.inpcrd"
    structure.save(str(prmtop), overwrite=True)
    structure.save(str(inpcrd), overwrite=True)
    return {"prmtop": str(prmtop), "inpcrd": str(inpcrd),
            "note": "Amber topology exported; run ante-MMPBSA.py + MMPBSA.py for MM/PBSA"}
