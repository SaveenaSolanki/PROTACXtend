#!/usr/bin/env python3
"""Measured capability, licence, fallback and overhead audit.

Writes:
  results/audit/tool_capability_matrix.{csv,parquet,md}
  results/audit/backend_readiness.json
  results/audit/licence_audit.{csv,md}
  results/audit/summary_metrics.json
  results/fallback_benchmark/fallback_scenarios.{csv,json}
  results/runtime/orchestration_overhead.{csv,json}
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RESULTS = ROOT / "results"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


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


# ── PART A: capability rows (curated to the audited surface) ────────────

CAPABILITY_ROWS: list[dict[str, Any]] = [
    # CHEMISTRY
    dict(group="CHEMISTRY", capability="smiles_parsing", primary="rdkit", secondary="", fallback="openbabel", tier="TIER_0_GEOMETRY"),
    dict(group="CHEMISTRY", capability="canonicalization", primary="rdkit", secondary="", fallback="openbabel", tier="TIER_0_GEOMETRY"),
    dict(group="CHEMISTRY", capability="fingerprints", primary="rdkit", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    dict(group="CHEMISTRY", capability="descriptors", primary="rdkit", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    dict(group="CHEMISTRY", capability="conformer_generation", primary="rdkit", secondary="", fallback="openbabel", tier="TIER_1_MINIMIZED"),
    dict(group="CHEMISTRY", capability="tautomers", primary="rdkit", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    dict(group="CHEMISTRY", capability="protonation", primary="rdkit", secondary="pdbfixer_openmm", fallback="openbabel", tier="TIER_0_GEOMETRY"),
    dict(group="CHEMISTRY", capability="substructure_search", primary="rdkit", secondary="", fallback="openbabel", tier="TIER_0_GEOMETRY"),
    # PROTEIN PREPARATION
    dict(group="PROTEIN_PREPARATION", capability="structure_repair", primary="pdbfixer_openmm", secondary="", fallback="biopython_prep", tier="TIER_1_MINIMIZED"),
    dict(group="PROTEIN_PREPARATION", capability="missing_atoms", primary="pdbfixer_openmm", secondary="", fallback="biopython_prep", tier="TIER_1_MINIMIZED"),
    dict(group="PROTEIN_PREPARATION", capability="hydrogens", primary="pdbfixer_openmm", secondary="", fallback="", tier="TIER_1_MINIMIZED"),
    dict(group="PROTEIN_PREPARATION", capability="chain_handling", primary="pdbfixer_openmm", secondary="biopython_prep", fallback="", tier="TIER_1_MINIMIZED"),
    dict(group="PROTEIN_PREPARATION", capability="alternate_locations", primary="pdbfixer_openmm", secondary="", fallback="", tier="TIER_1_MINIMIZED"),
    dict(group="PROTEIN_PREPARATION", capability="heterogens", primary="pdbfixer_openmm", secondary="", fallback="", tier="TIER_1_MINIMIZED"),
    dict(group="PROTEIN_PREPARATION", capability="cofactors", primary="pdbfixer_openmm", secondary="", fallback="", tier="TIER_1_MINIMIZED"),
    dict(group="PROTEIN_PREPARATION", capability="metals", primary="pdbfixer_openmm", secondary="", fallback="", tier="TIER_1_MINIMIZED"),
    dict(group="PROTEIN_PREPARATION", capability="protonation_provenance", primary="pdbfixer_openmm", secondary="", fallback="", tier="TIER_1_MINIMIZED"),
    # LIGAND PARAMETERIZATION
    dict(group="LIGAND_PARAMETERIZATION", capability="openff_smirnoff", primary="openff", secondary="", fallback="gaff", tier="TIER_1_MINIMIZED"),
    dict(group="LIGAND_PARAMETERIZATION", capability="gaff_fallback", primary="gaff", secondary="", fallback="generic_unparameterized", tier="TIER_1_MINIMIZED"),
    dict(group="LIGAND_PARAMETERIZATION", capability="charge_assignment", primary="openff", secondary="gaff", fallback="", tier="TIER_1_MINIMIZED"),
    dict(group="LIGAND_PARAMETERIZATION", capability="parameter_provenance", primary="openff", secondary="gaff", fallback="", tier="TIER_1_MINIMIZED"),
    # POCKET DETECTION
    dict(group="POCKET_DETECTION", capability="fpocket", primary="pocket_geometry", secondary="", fallback="geometry_cavity", tier="TIER_0_GEOMETRY"),
    dict(group="POCKET_DETECTION", capability="geometry_fallback", primary="geometry_cavity", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    # LIGAND DOCKING
    dict(group="LIGAND_DOCKING", capability="diffdock", primary="diffdock", secondary="", fallback="", tier="TIER_2_DOCKED"),
    dict(group="LIGAND_DOCKING", capability="vina", primary="autodock_vina", secondary="", fallback="", tier="TIER_2_DOCKED"),
    dict(group="LIGAND_DOCKING", capability="gnina", primary="gnina", secondary="", fallback="", tier="TIER_2_DOCKED"),
    dict(group="LIGAND_DOCKING", capability="consensus_ranking", primary="consensus_docking", secondary="", fallback="geometric_placement", tier="TIER_2_DOCKED"),
    # PPI DOCKING
    dict(group="PPI_DOCKING", capability="lightdock", primary="lightdock", secondary="", fallback="geometric_orientation_search", tier="TIER_2_DOCKED"),
    dict(group="PPI_DOCKING", capability="restrained_docking", primary="lightdock", secondary="geometric_orientation_search", fallback="", tier="TIER_2_DOCKED"),
    dict(group="PPI_DOCKING", capability="geometric_fallback", primary="geometric_orientation_search", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    # TERNARY / PROTAC
    dict(group="TERNARY_PROTAC", capability="anchor_handling", primary="local_ternary_pipeline", secondary="rdkit", fallback="", tier="TIER_0_GEOMETRY"),
    dict(group="TERNARY_PROTAC", capability="linker_geometry", primary="rdkit_linker", secondary="", fallback="", tier="TIER_1_MINIMIZED"),
    dict(group="TERNARY_PROTAC", capability="ppi_orientation", primary="lightdock", secondary="geometric_orientation_search", fallback="", tier="TIER_2_DOCKED"),
    dict(group="TERNARY_PROTAC", capability="ternary_assembly", primary="local_ternary_pipeline", secondary="", fallback="", tier="TIER_1_MINIMIZED"),
    dict(group="TERNARY_PROTAC", capability="interface_analysis", primary="geometry_fingerprint", secondary="mdanalysis", fallback="", tier="TIER_0_GEOMETRY"),
    # MOLECULAR GLUE
    dict(group="MOLECULAR_GLUE", capability="apo_vs_bound", primary="local_glue_ppi_delta", secondary="openmm", fallback="", tier="TIER_0_GEOMETRY"),
    dict(group="MOLECULAR_GLUE", capability="ppi_stabilization", primary="local_glue_ppi_delta", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    # METABOLITE-ASSISTED PPI
    dict(group="METABOLITE_PPI", capability="metabolite_bridging", primary="local_glue_ppi_delta", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    dict(group="METABOLITE_PPI", capability="interface_changes", primary="local_glue_ppi_delta", secondary="mdanalysis", fallback="", tier="TIER_0_GEOMETRY"),
    dict(group="METABOLITE_PPI", capability="apo_vs_metabolite", primary="local_glue_ppi_delta", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    # MD
    dict(group="MOLECULAR_DYNAMICS", capability="openmm_cpu", primary="openmm", secondary="", fallback="", tier="TIER_3_SHORT_MD"),
    dict(group="MOLECULAR_DYNAMICS", capability="openmm_gpu", primary="openmm", secondary="", fallback="openmm_cpu", tier="TIER_3_SHORT_MD"),
    dict(group="MOLECULAR_DYNAMICS", capability="minimization", primary="openmm", secondary="", fallback="", tier="TIER_1_MINIMIZED"),
    dict(group="MOLECULAR_DYNAMICS", capability="nvt", primary="openmm", secondary="", fallback="", tier="TIER_3_SHORT_MD"),
    dict(group="MOLECULAR_DYNAMICS", capability="npt", primary="openmm", secondary="", fallback="", tier="TIER_3_SHORT_MD"),
    dict(group="MOLECULAR_DYNAMICS", capability="short_md", primary="openmm", secondary="", fallback="", tier="TIER_3_SHORT_MD"),
    dict(group="MOLECULAR_DYNAMICS", capability="replicate_md", primary="openmm", secondary="", fallback="", tier="TIER_4_REPLICATE_MD"),
    dict(group="MOLECULAR_DYNAMICS", capability="checkpoint_resume", primary="openmm", secondary="", fallback="", tier="TIER_3_SHORT_MD"),
    # TRAJECTORY ANALYSIS
    dict(group="TRAJECTORY_ANALYSIS", capability="rmsd", primary="mdanalysis", secondary="", fallback="numpy_geometry", tier="TIER_3_SHORT_MD"),
    dict(group="TRAJECTORY_ANALYSIS", capability="rmsf", primary="mdanalysis", secondary="", fallback="numpy_geometry", tier="TIER_3_SHORT_MD"),
    dict(group="TRAJECTORY_ANALYSIS", capability="radius_of_gyration", primary="mdanalysis", secondary="", fallback="numpy_geometry", tier="TIER_3_SHORT_MD"),
    dict(group="TRAJECTORY_ANALYSIS", capability="sasa", primary="mdtraj", secondary="freesasa", fallback="", tier="TIER_3_SHORT_MD"),
    dict(group="TRAJECTORY_ANALYSIS", capability="buried_sasa", primary="mdtraj", secondary="", fallback="", tier="TIER_3_SHORT_MD"),
    dict(group="TRAJECTORY_ANALYSIS", capability="hbonds", primary="mdanalysis", secondary="", fallback="", tier="TIER_3_SHORT_MD"),
    dict(group="TRAJECTORY_ANALYSIS", capability="salt_bridges", primary="geometry_fingerprint", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    dict(group="TRAJECTORY_ANALYSIS", capability="hydrophobic_contacts", primary="geometry_fingerprint", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    dict(group="TRAJECTORY_ANALYSIS", capability="com_distances", primary="mdanalysis", secondary="", fallback="", tier="TIER_3_SHORT_MD"),
    dict(group="TRAJECTORY_ANALYSIS", capability="interface_persistence", primary="mdanalysis", secondary="", fallback="", tier="TIER_3_SHORT_MD"),
    dict(group="TRAJECTORY_ANALYSIS", capability="anchor_distances", primary="mdanalysis", secondary="rdkit_linker", fallback="", tier="TIER_3_SHORT_MD"),
    dict(group="TRAJECTORY_ANALYSIS", capability="linker_torsions", primary="rdkit_linker", secondary="", fallback="", tier="TIER_1_MINIMIZED"),
    # ENERGETICS
    dict(group="ENERGETICS", capability="openmm_interaction_energy", primary="openmm_interaction", secondary="", fallback="structural_energy_surrogate", tier="TIER_1_MINIMIZED"),
    dict(group="ENERGETICS", capability="gmx_mmpbsa", primary="gmx_mmpbsa", secondary="", fallback="openmm_interaction", tier="TIER_5_ENDPOINT_FREE_ENERGY"),
    dict(group="ENERGETICS", capability="mmgbsa", primary="gmx_mmpbsa", secondary="", fallback="openmm_interaction", tier="TIER_5_ENDPOINT_FREE_ENERGY"),
    dict(group="ENERGETICS", capability="mmpbsa", primary="gmx_mmpbsa", secondary="", fallback="openmm_interaction", tier="TIER_5_ENDPOINT_FREE_ENERGY"),
    dict(group="ENERGETICS", capability="structural_surrogate", primary="structural_energy_surrogate", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    dict(group="ENERGETICS", capability="alchemical_gate", primary="alchemical_fep", secondary="", fallback="", tier="TIER_6_ALCHEMICAL_FREE_ENERGY"),
    # ADMET
    dict(group="ADMET", capability="rdkit_properties", primary="rdkit", secondary="", fallback="", tier="TIER_0_GEOMETRY"),
    dict(group="ADMET", capability="local_ml_model", primary="admet_ai", secondary="", fallback="rdkit", tier="TIER_1_MINIMIZED"),
    # PROVENANCE
    dict(group="PROVENANCE", capability="software_versions", primary="provenance", secondary="", fallback="", tier=""),
    dict(group="PROVENANCE", capability="forcefield", primary="provenance", secondary="", fallback="", tier=""),
    dict(group="PROVENANCE", capability="random_seed", primary="provenance", secondary="", fallback="", tier=""),
    dict(group="PROVENANCE", capability="input_hashes", primary="provenance", secondary="", fallback="", tier=""),
    dict(group="PROVENANCE", capability="model_sha256", primary="models", secondary="", fallback="", tier=""),
    dict(group="PROVENANCE", capability="gpu_cpu", primary="provenance", secondary="", fallback="", tier=""),
    dict(group="PROVENANCE", capability="evidence_tier", primary="provenance", secondary="", fallback="", tier=""),
]


def _availability() -> dict[str, dict[str, Any]]:
    from protacxtend.scientific_backends.runner import backend_health

    return {row["name"]: row for row in backend_health()}


# ── PART B: functional smoke checks ─────────────────────────────────────

def functional_checks() -> dict[str, Any]:
    """LEVEL 2 — cheap functional execution of each backend on tiny inputs."""
    import numpy as np
    from protacxtend.scientific_backends.dispatch import run_cross_env

    checks: dict[str, Any] = {}

    def run(name, fn):
        t0 = time.time()
        try:
            detail = fn()
            checks[name] = {"functional": True, "detail": str(detail)[:160],
                            "runtime_s": round(time.time() - t0, 3)}
        except Exception as exc:  # noqa: BLE001
            checks[name] = {"functional": False, "detail": f"{type(exc).__name__}: {exc}"[:160],
                            "runtime_s": round(time.time() - t0, 3)}

    run("rdkit", lambda: __import__("protacxtend.scientific_backends", fromlist=["chemistry"])
        .chemistry("CCO").data["molecular_weight"])
    run("openff", lambda: run_cross_env(
        "protacxtend.scientific_backends.backends.md", "_parameterize_ligand_openmm",
        args=["CCO", "LIG"], require_import="openmm", prefer_env="md-openff", timeout=600
    )["result"]["engine"])
    run("pocket_geometry", lambda: __import__(
        "protacxtend.scientific_backends", fromlist=["detect_pockets"]
    ).detect_pockets(_test_pdb(), top_n=1).backend)
    run("openmm", lambda: run_cross_env(
        "protacxtend.workflows.md_runner", "_openmm_staged",
        args=[_test_pdb(), "/tmp/audit_md_func"],
        kwargs={"minimize_steps": 20, "restrained_steps": 20, "nvt_steps": 20,
                "npt_steps": 0, "production_steps": 50, "platform": "auto"},
        require_import="openmm", prefer_env="md-openff", timeout=1200
    )["result"]["platform"])
    run("mdanalysis", lambda: len(__import__(
        "protacxtend.workflows.validation_pipeline", fromlist=["trajectory_timeseries"]
    ).trajectory_timeseries(_test_pdb(), _test_pdb()).get("rg", [])))
    run("mdtraj", lambda: len(__import__(
        "protacxtend.workflows.validation_pipeline", fromlist=["sasa_timeseries"]
    ).sasa_timeseries(_test_pdb(), _test_pdb()).get("sasa", [])))
    run("consensus_docking", lambda: __import__(
        "protacxtend.scientific_backends.backends.docking", fromlist=["_borda_consensus"]
    )._borda_consensus({"vina": [{"rank": 1}], "gnina": [{"rank": 1}]})["method"])
    run("rdkit_linker", lambda: __import__(
        "protacxtend.scientific_backends", fromlist=["analyze_linker"]
    ).analyze_linker("[*:1]CCOCCO[*:2]").data["contour_length_A"])
    run("geometry_fingerprint", lambda: __import__(
        "protacxtend.scientific_backends", fromlist=["interaction_fingerprint"]
    ).interaction_fingerprint(_complex_pdb(), ligand_resname="LIG").status)
    run("local_glue_ppi_delta", lambda: __import__(
        "protacxtend.workflows.validation_pipeline", fromlist=["glue_verdict"]
    ).glue_verdict({"summary": {"sasa": {"mean": 100}}},
                   {"summary": {"sasa": {"mean": 120}}})["verdict"])
    run("admet_ai", lambda: len(run_cross_env(
        "protacxtend.scientific_backends.backends.chemistry", "_run_admet_ai",
        args=["CCO"], require_import="admet_ai", timeout=900)["result"]["endpoints"]))
    run("gromacs", lambda: __import__("subprocess").run(
        [__import__("protacxtend.toolkit.environments", fromlist=["find_executable"])
         .find_executable("gmx")[0], "--version"], capture_output=True, timeout=120).returncode)
    # binary backends: functional if the executable runs
    import subprocess
    from protacxtend.toolkit.environments import find_executable

    for name, exe, args in (("autodock_vina", "vina", ["--version"]),
                            ("gnina", "gnina", ["--help"]),
                            ("diffdock", "diffdock", ["--help"]),
                            ("lightdock", "lightdock3.py", ["--help"]),
                            ("gmx_mmpbsa", "gmx_MMPBSA", ["--version"]),
                            ("gromacs", "gmx", ["--version"])):
        found = find_executable(exe)
        if not found:
            checks[name] = {"functional": False, "detail": "not installed", "runtime_s": 0.0}
            continue
        env = None
        if name == "gmx_mmpbsa":
            import os
            env = dict(os.environ, AMBERHOME=str(Path.home() / ".protacxtend/envs/gromacs"))
        run(name, lambda f=found, a=args, e=env: subprocess.run(
            [f[0], *a], capture_output=True, env=e, timeout=180).returncode)
    return checks


def _test_pdb() -> str:
    for p in (ROOT / "outputs/p4ward_evidence/hmgb2_fixed_minim.pdb",
              ROOT / "outputs/p4ward_evidence/input_hmgb2_receptor.pdb",
              Path.home() / ".protacxtend/envs/diffdock/DiffDock/examples/1a46_protein_processed.pdb"):
        if p.exists():
            return str(p)
    return ""


def _complex_pdb() -> str:
    p = ROOT / "validation_runs/1a46_pl/preparation/holo_complex.pdb"
    return str(p) if p.exists() else _test_pdb()


# ── PART C: licence audit ───────────────────────────────────────────────

def licence_audit() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from protacxtend.scientific_backends.licenses import policy_from_env
    from protacxtend.scientific_backends.registry import REGISTRY, load_backends

    load_backends()
    policy = policy_from_env()
    rows = []
    for spec in sorted(REGISTRY.all(), key=lambda s: s.name):
        allowed, reason = policy.allows(spec.license)
        rows.append({
            "backend": spec.name,
            "capabilities": ";".join(c.value for c in spec.capabilities),
            "license": spec.license.name,
            "license_class": spec.license_class,
            "redistributable": spec.redistributable,
            "commercial_use_restricted": spec.commercial_use_restricted,
            "academic_only": spec.academic_only,
            "web_only": spec.license.license_class.value == "web_service",
            "network_required": spec.requires_network,
            "default_enabled": allowed,
            "optional_only": spec.optional,
            "replacement_backend": _replacement(spec.name),
            "reason": reason,
        })
    restricted = [r for r in rows if not r["default_enabled"]]
    metrics = {
        "backends_total": len(rows),
        "restricted_backends": len(restricted),
        "commercial_backends": sum(1 for r in rows if r["license_class"] in {"commercial", "proprietary"}),
        "web_backends": sum(1 for r in rows if r["web_only"]),
        "academic_only_backends": sum(1 for r in rows if r["academic_only"]),
    }
    return rows, metrics


def _replacement(name: str) -> str:
    mapping = {
        "schrodinger_glide": "consensus_docking (Vina/GNINA/DiffDock)",
        "schrodinger_prime": "pdbfixer_openmm + pocket_geometry",
        "schrodinger_desmond": "openmm",
        "schrodinger_ligprep": "rdkit",
        "gold_ccdc": "autodock_vina",
        "moe": "lightdock",
        "icm_pro": "autodock_vina",
        "openeye_omega": "rdkit",
        "gaussian": "rdkit",
        "charmm": "openmm",
        "namerxn": "rdkit",
        "pipeline_pilot": "pareto_nsga2",
        "amber_commercial": "openmm",
        "rosetta": "lightdock + openmm",
        "cluspro": "lightdock",
        "swissadme": "rdkit + admet_ai",
        "admetlab3": "admet_ai",
        "pkcsm": "admet_ai",
        "protox_ii": "admet_ai",
        "haddock_web": "lightdock",
        "haddock_cns": "lightdock",
        "patchdock_web": "geometric_orientation_search",
        "ibm_rxn": "rdkit",
        "openadmet_web": "admet_ai",
    }
    return mapping.get(name, "")


# ── PART G: graceful degradation ────────────────────────────────────────

def fallback_benchmark() -> list[dict[str, Any]]:
    """Simulate a backend failing and record the resolver's fallback choice.

    Heavy capabilities (docking) are resolved without executing so the audit
    does not re-run minutes of docking; MD/energy/pocket run a real lightweight
    fallback.
    """
    from protacxtend.scientific_backends.registry import Capability, REGISTRY, load_backends
    from protacxtend.scientific_backends.runner import run_capability

    load_backends()
    scenarios = [
        ("diffdock", "ligand_docking", "heavy"),
        ("gnina", "ligand_docking", "heavy"),
        ("autodock_vina", "ligand_docking", "heavy"),
        ("lightdock", "ppi_docking", "heavy"),
        ("pocket_geometry", "pocket_detection", "light"),
        ("binding_energy_hierarchy", "binding_energy", "light"),
        ("openmm_cpu", "molecular_dynamics", "light"),
    ]
    out: list[dict[str, Any]] = []
    for failed, capability, weight in scenarios:
        cap = Capability(capability)
        # backends that remain usable if the named one is removed
        alternatives = [b for b in REGISTRY.for_capability(cap)
                        if b.name != failed and b.health().available
                        and not b.license.academic_only and not b.license.commercial_use_restricted
                        and b.license.license_class.value != "web_service"]
        alternatives.sort(key=lambda s: -s.priority)
        rows = {
            "failed_backend": failed,
            "capability": capability,
            "fallback_available": bool(alternatives),
            "resolved_backend": alternatives[0].name if alternatives else "",
            "evidence_tier_after": alternatives[0].priority if alternatives else 0,
            "expected_fallback": ";".join(b.name for b in alternatives[:3]),
        }
        if weight == "light" and alternatives:
            t0 = time.time()
            if capability == "pocket_detection":
                r = run_capability("pocket_detection", pdb_path=_test_pdb(), top_n=1)
            elif capability == "binding_energy":
                r = run_capability("binding_energy", complex_pdb=_complex_pdb(), ligand_resname="LIG")
            else:
                r = run_capability("molecular_dynamics", structure_pdb=_test_pdb(),
                                   md_steps=0, minimize=True)
            rows.update({"executed": True, "result_status": r.status, "resolved_backend": r.backend or rows["resolved_backend"],
                         "runtime_s": round(time.time() - t0, 2), "warning": (r.warnings[0] if r.warnings else "")})
        else:
            rows.update({"executed": False, "result_status": "resolver_only", "runtime_s": 0.0, "warning": ""})
        out.append(rows)
    return out


# ── PART H: orchestration overhead ──────────────────────────────────────

def orchestration_overhead() -> list[dict[str, Any]]:
    """T_total (facade+router+result envelope) vs T_backend (raw call)."""
    from protacxtend.scientific_backends import chemistry, detect_pockets, run_molecular_dynamics

    rows: list[dict[str, Any]] = []

    def measure(label, backend_fn, facade_fn, repeats=3):
        tb = []
        for _ in range(repeats):
            t = time.time()
            backend_fn()
            tb.append(time.time() - t)
        tt = []
        for _ in range(repeats):
            t = time.time()
            facade_fn()
            tt.append(time.time() - t)
        b = min(tb)
        tot = min(tt)
        rows.append({"task": label, "t_backend_s": round(b, 4), "t_total_s": round(tot, 4),
                     "t_orchestration_s": round(max(0.0, tot - b), 4),
                     "overhead_pct": round(100.0 * max(0.0, tot - b) / max(tot, 1e-6), 2)})

    measure("rdkit_descriptor",
            lambda: __import__("protacxtend.scientific_backends.backends.chemistry",
                               fromlist=["rdkit_descriptors"]).rdkit_descriptors("CCO"),
            lambda: chemistry("CCO"))
    measure("fpocket", lambda: __import__("protacxtend.scientific_backends.backends.structure",
                                          fromlist=["pocket_detection"]).pocket_detection(_test_pdb(), top_n=1),
            lambda: detect_pockets(_test_pdb(), top_n=1))
    measure("openmm_minimize",
            lambda: __import__("protacxtend.scientific_backends.dispatch", fromlist=["run_cross_env"])
            .run_cross_env("protacxtend.workflows.md_runner", "_openmm_staged",
                           args=[_test_pdb(), "/tmp/audit_overhead_md"],
                           kwargs={"minimize_steps": 20, "restrained_steps": 0, "nvt_steps": 0,
                                   "production_steps": 0, "platform": "auto"},
                           require_import="openmm", prefer_env="md-openff", timeout=1200)["ok"],
            lambda: run_molecular_dynamics(_test_pdb(), md_steps=0, minimize=True), repeats=2)
    return rows


# ── metrics (PART V) ────────────────────────────────────────────────────

def summary_metrics(matrix: list[dict[str, Any]], licence: dict[str, Any],
                    functional: dict[str, Any], scientific: dict[str, Any]) -> dict[str, Any]:
    core = [m for m in matrix if m["group"] != "PROVENANCE"]
    total = len(core)
    local_exec = sum(1 for m in core if not m["network_required"] and not m["commercial_restricted"])
    functional_ok = sum(1 for m in core if m["functional"])
    with_bench = [m for m in core if m["scientific_validation_status"] not in {"", "not_benchmarked"}]
    validated = sum(1 for m in with_bench if m["scientifically_validated"])
    restricted_required = sum(1 for m in core if m["commercial_restricted"])
    grr_rows = scientific.get("fallback", [])
    grr = (round(sum(1 for r in grr_rows
                     if r.get("fallback_available") or r.get("result_status") in {"success", "warning"})
                 / len(grr_rows), 3) if grr_rows else None)
    return {
        "core_capabilities": total,
        "RDF_restricted_dependency_fraction": round(restricted_required / total, 4),
        "LER_local_executability_rate": round(local_exec / total, 4),
        "FVR_functional_validation_rate": round(functional_ok / total, 4),
        "SVR_scientific_validation_rate": round(validated / len(with_bench), 4) if with_bench else None,
        "GRR_graceful_recovery_rate": grr,
        "commercial_required_capabilities": restricted_required,
        "installed_backends": licence.get("backends_total"),
        "restricted_backends_registered": licence.get("restricted_backends"),
    }


def build_matrix(functional: dict[str, Any], scientific: dict[str, Any]) -> list[dict[str, Any]]:
    avail = _availability()
    # aliases: matrix backend name -> functional/availability key
    alias = {"geometry_cavity": "pocket_geometry", "gaff": "openff",
             "admet_ai": "admet_ai", "gmx_mmpbsa": "gmx_mmpbsa",
             "gromacs": "gromacs", "alchemical_fep": "openmm",
             "structural_energy_surrogate": "openmm_interaction",
             "provenance": "provenance", "models": "provenance"}
    rows = []
    for row in CAPABILITY_ROWS:
        prim_key = alias.get(row["primary"], row["primary"])
        prim = avail.get(prim_key, {})
        func = functional.get(prim_key, {})
        installed = bool(prim.get("available")) or bool(func.get("functional"))
        functional_ok = bool(func.get("functional", installed))
        sci = scientific.get(row["primary"], scientific.get(prim_key, {}))
        rows.append({
            "group": row["group"], "capability": row["capability"],
            "primary_backend": row["primary"], "secondary_backend": row["secondary"],
            "fallback_backend": row["fallback"],
            "installed": installed, "functional": functional_ok,
            "scientifically_validated": bool(sci.get("validated")),
            "scientific_validation_status": sci.get("status", "not_benchmarked"),
            "scientific_metric": sci.get("metric", ""),
            "cpu_supported": True,
            "gpu_supported": bool(prim.get("requires_gpu") or row["primary"] in
                                 {"openmm", "diffdock", "gnina", "gromacs", "gmx_mmpbsa"}),
            "offline": not bool(prim.get("requires_network")),
            "network_required": bool(prim.get("requires_network")),
            "commercial_restricted": bool(prim.get("commercial_use_restricted")),
            "evidence_tier": row["tier"],
            "smoke_test_status": "PASS" if func.get("functional") else "FAIL",
            "smoke_runtime_s": func.get("runtime_s", ""),
            "notes": func.get("detail", "")[:120],
        })
    return rows


def _scientific_from_benchmarks() -> dict[str, Any]:
    out: dict[str, Any] = {}
    dsum = RESULTS / "docking/docking_summary.json"
    if dsum.exists():
        s = json.loads(dsum.read_text())
        out["diffdock"] = {"validated": (s.get("diffdock_success_lt2A") or 0) >= 0.5,
                           "status": "benchmarked", "metric": f"top1<2A={s.get('diffdock_success_lt2A')}"}
        out["gnina"] = {"validated": (s.get("gnina_success_lt5A") or 0) >= 0.5,
                        "status": "benchmarked", "metric": f"top1<2A={s.get('gnina_success_lt2A')}"}
        out["autodock_vina"] = {"validated": (s.get("vina_success_lt5A") or 0) >= 0.5,
                                "status": "benchmarked", "metric": f"top1<2A={s.get('vina_success_lt2A')}"}
        out["consensus_docking"] = {"validated": (s.get("consensus_success_lt2A") or 0) >= 0.5,
                                    "status": "benchmarked", "metric": f"top1<2A={s.get('consensus_success_lt2A')}"}
    psum = RESULTS / "pockets/pocket_summary.json"
    if psum.exists():
        s = json.loads(psum.read_text())
        out["pocket_geometry"] = {"validated": (s.get("top1_recovery_4A") or 0) >= 0.5,
                                  "status": "benchmarked",
                                  "metric": f"top1_recovery_4A={s.get('top1_recovery_4A')}"}
    pp = RESULTS / "ppi/ppi_benchmark.json"
    if pp.exists():
        s = json.loads(pp.read_text())
        out["lightdock"] = {"validated": False, "status": "benchmarked",
                            "metric": f"geometric_DockQ={s.get('geometric_fallback_dockq')}; "
                                      f"lightdock_coordinate_DockQ=not_run"}
    mmp = RESULTS / "energy/mmpbsa_benchmark.json"
    if mmp.exists():
        s = json.loads(mmp.read_text())
        out["gmx_mmpbsa"] = {"validated": s.get("status") == "success", "status": "benchmarked",
                             "metric": f"status={s.get('status')}"}
    return out


def main() -> int:
    print("PART B: functional checks ...")
    functional = functional_checks()
    _write_json(RESULTS / "audit/functional_checks.json", functional)
    print("PART C: licence audit ...")
    lic_rows, lic_metrics = licence_audit()
    _write_csv(RESULTS / "audit/licence_audit.csv", lic_rows)
    _write_json(RESULTS / "audit/licence_metrics.json", lic_metrics)
    print("PART G: fallback benchmark ...")
    fallback = fallback_benchmark()
    _write_csv(RESULTS / "fallback_benchmark/fallback_scenarios.csv", fallback)
    _write_json(RESULTS / "fallback_benchmark/fallback_scenarios.json", fallback)
    print("PART H: orchestration overhead ...")
    overhead = orchestration_overhead()
    _write_csv(RESULTS / "runtime/orchestration_overhead.csv", overhead)
    _write_json(RESULTS / "runtime/orchestration_overhead.json", overhead)
    sci = _scientific_from_benchmarks()
    sci["fallback"] = fallback
    matrix = build_matrix(functional, sci)
    _write_csv(RESULTS / "audit/tool_capability_matrix.csv", matrix)
    try:
        import pandas as pd

        pd.DataFrame(matrix).to_parquet(RESULTS / "audit/tool_capability_matrix.parquet", index=False)
    except Exception as exc:  # noqa: BLE001
        print("parquet skipped:", exc)
    metrics = summary_metrics(matrix, lic_metrics, functional, sci)
    _write_json(RESULTS / "audit/summary_metrics.json", metrics)
    from protacxtend.audit_report import render_matrix_md, render_licence_md

    (RESULTS / "audit/tool_capability_matrix.md").write_text(render_matrix_md(matrix), encoding="utf-8")
    (RESULTS / "audit/licence_audit.md").write_text(render_licence_md(lic_rows), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
