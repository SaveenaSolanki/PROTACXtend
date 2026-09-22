"""End-to-end and scientific-validation tests for the free/local stack.

Heavy tests are marked ``slow`` and are skipped when their engine/asset is not
installed. Unit tests run offline.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from protacxtend.workflows.convergence import assess_convergence
from protacxtend.workflows.validation_pipeline import (
    ValidationRequest, _stats, glue_verdict, sasa_timeseries, structure_qc,
    trajectory_timeseries,
)

ROOT = Path(__file__).resolve().parents[2]
DD = Path.home() / ".protacxtend/envs/diffdock/DiffDock/examples"
RECEPTOR = ROOT / "outputs/p4ward_evidence/input_hmgb2_receptor.pdb"
MD_READY = ROOT / "outputs/p4ward_evidence/hmgb2_fixed_minim.pdb"
PPI_A = Path("/tmp/ld_receptor.pdb")
PPI_B = Path("/tmp/ld_ligand.pdb")


def _need(*paths):
    for p in paths:
        if not Path(p).exists():
            pytest.skip(f"missing test asset: {p}")


# ── unit tests ──────────────────────────────────────────────────────────

def test_structure_qc():
    _need(RECEPTOR)
    qc = structure_qc(str(RECEPTOR))
    assert qc["verdict"] in {"PASS", "WARN"}
    assert "steric_clashes_lt2A" in qc["checks"]
    assert qc["checks"]["n_residues"] > 50


def test_convergence_detection():
    converged = assess_convergence(rmsd=[2.0 + 0.01 * (i % 3) for i in range(60)],
                                   bsa=[100 + 0.5 * (i % 4) for i in range(60)],
                                   replica_means={"r1": 2.0, "r2": 2.05, "r3": 1.99})
    assert converged["verdict"] == "CONVERGED"
    drifting = assess_convergence(rmsd=[1.0 + 0.2 * i for i in range(60)],
                                  bsa=[100 + 5 * i for i in range(60)])
    assert drifting["verdict"] == "NOT_CONVERGED"
    short = assess_convergence(rmsd=[1.0, 1.1, 1.2])
    assert short["verdict"] == "INSUFFICIENT_TRAJECTORY"


def test_glue_verdict_never_says_proved():
    v = glue_verdict(
        {"summary": {"sasa": {"mean": 100}, "bsa_target_partner": {"mean": 200}},
         "timeseries": {"interfaces": {"target_partner": {"contacts": [10] * 30}}}},
        {"summary": {"sasa": {"mean": 120}, "bsa_target_partner": {"mean": 260}},
         "timeseries": {"interfaces": {"target_partner": {"contacts": [30] * 30}}}})
    assert v["verdict"] in {"POTENTIAL_STABILIZATION", "POTENTIAL_DESTABILIZATION",
                            "NO_CLEAR_EFFECT", "INSUFFICIENT_EVIDENCE"}
    assert "proved" not in v["disclaimer"].lower()
    assert "proof" in v["disclaimer"].lower()


def test_stats():
    s = _stats([1, 2, 3, 4, 5])
    assert s["mean"] == 3.0 and s["n"] == 5


def test_trajectory_sasa_single_structure():
    _need(MD_READY)
    sa = sasa_timeseries(str(MD_READY), str(MD_READY))
    assert sa.get("sasa")


def test_three_interface_analysis_single_frame():
    _need(MD_READY)
    ts = trajectory_timeseries(str(MD_READY), str(MD_READY), target_sel="protein")
    assert "rmsd" in ts or "rg" in ts


# ── real engine tests ───────────────────────────────────────────────────

@pytest.mark.slow
def test_real_ligand_parameterization():
    from protacxtend.scientific_backends.dispatch import module_available, run_cross_env

    if not module_available("openmm"):
        pytest.skip("openmm unavailable")
    out = run_cross_env("protacxtend.scientific_backends.backends.md", "_parameterize_ligand_openmm",
                        args=["CCO", "LIG"], require_import="openmm",
                        prefer_env="md-openff", timeout=900)
    assert out["ok"], out.get("error")
    assert out["result"]["engine"] in {"openff", "gaff", "generic_unparameterized"}


@pytest.mark.slow
def test_vina_real_pose(tmp_path):
    from protacxtend.scientific_backends.backends.docking import vina_docking

    _need(MD_READY)
    r = vina_docking(receptor_pdb=str(MD_READY), ligand_smiles="CC(=O)Nc1ccc(O)cc1",
                     exhaustiveness=1, num_modes=2, cpu=2)
    assert r.data.get("poses"), r.summary


@pytest.mark.slow
def test_gnina_real_pose():
    from protacxtend.scientific_backends.backends.docking import gnina_docking
    from protacxtend.toolkit.environments import find_executable

    if not find_executable("gnina"):
        pytest.skip("gnina not installed")
    _need(MD_READY)
    r = gnina_docking(receptor_pdb=str(MD_READY), ligand_smiles="CCO")
    assert r.status in {"success", "warning"}
    assert r.data.get("poses") or r.status == "warning"


@pytest.mark.slow
def test_diffdock_real_pose():
    from protacxtend.scientific_backends.backends.docking import diffdock_docking
    from protacxtend.toolkit.environments import find_executable

    if not find_executable("diffdock") or not (DD / "1a46_protein_processed.pdb").exists():
        pytest.skip("DiffDock not installed")
    from rdkit import Chem

    mol = [m for m in Chem.SDMolSupplier(str(DD / "1a46_ligand.sdf"), removeHs=False) if m][0]
    r = diffdock_docking(receptor_pdb=str(DD / "1a46_protein_processed.pdb"),
                         ligand_smiles=Chem.MolToSmiles(Chem.RemoveHs(mol)),
                         n_poses=2, inference_steps=10)
    assert r.status in {"success", "warning"}


def test_consensus_docking_borda():
    from protacxtend.scientific_backends.backends.docking import _borda_consensus

    out = _borda_consensus({"vina": [{"rank": 1}, {"rank": 2}],
                            "gnina": [{"rank": 1}, {"rank": 2}]})
    assert out["method"] == "BORDA"
    assert "not averaged" in out["note"].lower() or "never averaged" in out["note"].lower()


@pytest.mark.slow
def test_lightdock_real_complex(tmp_path):
    from protacxtend.scientific_backends.backends.docking import lightdock_ppi_docking
    from protacxtend.toolkit.environments import find_executable

    if not find_executable("lightdock3.py"):
        pytest.skip("LightDock not installed")
    if not (PPI_A.exists() and PPI_B.exists()):
        pytest.skip("PPI test structures not prepared")
    r = lightdock_ppi_docking(receptor_pdb=str(PPI_A), ligand_pdb=str(PPI_B),
                              n_swarms=2, glowworms=5, steps=5, top_n=2)
    assert r.status in {"success", "warning"}


@pytest.mark.slow
def test_openmm_minimize_short_md_checkpoint(tmp_path):
    from protacxtend.scientific_backends.dispatch import module_available, run_cross_env

    if not module_available("openmm"):
        pytest.skip("openmm unavailable")
    _need(MD_READY)
    out = run_cross_env("protacxtend.workflows.md_runner", "_openmm_staged",
                        args=[str(MD_READY), str(tmp_path / "md")],
                        kwargs={"minimize_steps": 50, "restrained_steps": 50,
                                "nvt_steps": 50, "production_steps": 100},
                        require_import="openmm", prefer_env="md-openff", timeout=1800)
    assert out["ok"], out.get("error")
    r = out["result"]
    assert Path(r["checkpoint"]).exists()
    assert Path(r["trajectory"]).exists()
    assert any(s["stage"] == "nvt" for s in r["stage_log"])
    ts = trajectory_timeseries(r["topology_pdb"], r["trajectory"])
    assert len(ts.get("rmsd", [])) >= 2


@pytest.mark.slow
def test_gmx_mmpbsa_available():
    from protacxtend.toolkit.environments import find_executable
    import subprocess, os

    exe = find_executable("gmx_MMPBSA")
    if not exe:
        pytest.skip("gmx_MMPBSA not installed")
    env = dict(os.environ, AMBERHOME=str(Path.home() / ".protacxtend/envs/gromacs"))
    proc = subprocess.run([exe[0], "--version"], capture_output=True, text=True, env=env, timeout=180)
    assert proc.returncode == 0


def test_final_report_provenance(tmp_path):
    from protacxtend.workflows.validation_pipeline import _finalize

    report = {"run_id": "t", "evidence_tier": "TIER_3_SHORT_MD", "warnings": []}
    _finalize(tmp_path, report, {"inputs": {}}, [], 0.0)
    assert (tmp_path / "final_report.json").exists()
    assert (tmp_path / "final_report.md").exists()
    assert (tmp_path / "provenance" / "provenance.json").exists()
