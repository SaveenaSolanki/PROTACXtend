"""Tests for the warhead docking pipeline."""

from __future__ import annotations

import os
import pytest
from pathlib import Path

pytestmark = [
    pytest.mark.docking,
    pytest.mark.skipif(
        not os.environ.get("PROTACPILOT_TEST_DOCKING"),
        reason="Set PROTACPILOT_TEST_DOCKING=1 to run docking tests. "
               "Requires Vina + OpenBabel installed."
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hmgb2_pdb():
    """Path to a test HMGB2 structure."""
    # Try a few locations
    candidates = [
        Path(__file__).resolve().parents[2] / "test_data" / "hmgb2.pdb",
        Path("/tmp/hmgb2_alphafold.pdb"),
        Path("/tmp/hmgb2.pdb"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    # If not found, download from AlphaFold DB
    pytest.skip("No HMGB2 PDB found. Run: fetch_alphafold P26583")


@pytest.fixture
def inflachromene_smiles():
    """Inflachromene SMILES."""
    return "CC1(C2=CCN3C(=O)N(C(=O)N3C2C4=C(C=CC(=C4O)C1)O)C5=CC=CC=C5)"


@pytest.fixture
def crbn_pdb():
    """Path to CRBN PDB for E3 ligand preparation."""
    candidates = [
        Path(__file__).resolve().parents[2] / "test_data" / "4ci3.pdb",
        Path("/tmp/4ci3.pdb"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    # If not found, download from RCSB
    pytest.skip("No CRBN PDB found (4CI3). Run: fetch_pdb 4CI3")


# ---------------------------------------------------------------------------
# Module-level tests
# ---------------------------------------------------------------------------

class TestProteinPreparation:
    """Test receptor preparation for docking."""

    def test_import(self):
        from synglue_agent.tools.docking_pipeline import (
            prepare_receptor_for_docking, prepare_warhead_for_docking,
        )
        assert callable(prepare_receptor_for_docking)
        assert callable(prepare_warhead_for_docking)

    def test_prepare_receptor(self, hmgb2_pdb, tmp_path):
        from synglue_agent.tools.docking_pipeline import prepare_receptor_for_docking

        result = prepare_receptor_for_docking(
            pdb_path=hmgb2_pdb,
            output_dir=str(tmp_path / "receptor_prep"),
        )
        assert result["success"], result.get("error")
        assert result["pdbqt_file"] is not None
        pdbqt = Path(result["pdbqt_file"])
        assert pdbqt.exists()
        assert pdbqt.stat().st_size > 0

    def test_prepare_warhead(self, inflachromene_smiles, tmp_path):
        from synglue_agent.tools.docking_pipeline import prepare_warhead_for_docking

        result = prepare_warhead_for_docking(
            smiles=inflachromene_smiles,
            output_dir=str(tmp_path / "warhead_prep"),
            num_conformers=10,
        )
        assert result["success"], result.get("error")
        assert result["mol2_file"] is not None
        assert result["pdbqt_file"] is not None

    def test_invalid_smiles(self, tmp_path):
        from synglue_agent.tools.docking_pipeline import prepare_warhead_for_docking

        result = prepare_warhead_for_docking(
            smiles="invalid_smiles_!!!",
            output_dir=str(tmp_path / "invalid"),
        )
        assert not result["success"]


class TestVinaDocking:
    """Test Vina docking execution."""

    def test_vina_available(self):
        """Verify Vina is installed and callable."""
        import subprocess
        try:
            result = subprocess.run(
                ["vina", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            assert result.returncode == 0 or "Vina" in result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            pytest.skip(f"Vina not available: {e}")

    def test_run_vina(self, hmgb2_pdb, inflachromene_smiles, tmp_path):
        from synglue_agent.tools.docking_pipeline import (
            prepare_receptor_for_docking,
            prepare_warhead_for_docking,
            run_vina_docking,
        )

        # Prepare inputs
        rec = prepare_receptor_for_docking(
            hmgb2_pdb, str(tmp_path / "rec"),
        )
        assert rec["success"]
        war = prepare_warhead_for_docking(
            inflachromene_smiles, str(tmp_path / "war"), num_conformers=10,
        )
        assert war["success"]

        # Run Vina with a generous box
        result = run_vina_docking(
            receptor_pdbqt=rec["pdbqt_file"],
            warhead_pdbqt=war["pdbqt_file"],
            output_dir=str(tmp_path / "vina"),
            center_x=0.0, center_y=0.0, center_z=0.0,
            size_x=30.0, size_y=30.0, size_z=30.0,
            exhaustiveness=2,  # fast for test
            num_modes=5,
            cpu=2,
        )
        assert result["success"], result.get("error")
        assert len(result["poses"]) > 0

        # Check pose structure
        pose = result["poses"][0]
        assert pose.rank == 1
        assert pose.affinity_kcal_mol < 0  # binding should be favorable
        assert pose.pdbqt_block


class TestExitVector:
    """Test exit vector detection."""

    def test_analyze_exit_vectors(self, hmgb2_pdb, inflachromene_smiles, tmp_path):
        from synglue_agent.tools.docking_pipeline import (
            prepare_receptor_for_docking,
            prepare_warhead_for_docking,
            run_vina_docking,
            analyze_exit_vectors,
        )

        rec = prepare_receptor_for_docking(hmgb2_pdb, str(tmp_path / "rec"))
        war = prepare_warhead_for_docking(inflachromene_smiles, str(tmp_path / "war"))
        vina = run_vina_docking(
            rec["pdbqt_file"], war["pdbqt_file"],
            str(tmp_path / "vina"),
            exhaustiveness=2, num_modes=5, cpu=2,
        )
        if not vina["poses"]:
            pytest.skip("No docking poses to analyze")

        ev = analyze_exit_vectors(
            pose=vina["poses"][0],
            warhead_smiles=inflachromene_smiles,
            receptor_pdbqt=rec["pdbqt_file"],
        )
        if ev:
            assert ev.atom_index > 0
            assert ev.solvent_accessibility >= 0
            assert len(ev.vector_direction) == 3
            print(f"Exit vector: atom {ev.atom_index} ({ev.atom_symbol}), "
                  f"solvent acc.={ev.solvent_accessibility:.2f}")


class TestMol2Export:
    """Test MOL2 export for P4ward."""

    def test_export_pose_to_mol2(self, hmgb2_pdb, inflachromene_smiles, tmp_path):
        from synglue_agent.tools.docking_pipeline import (
            prepare_receptor_for_docking,
            prepare_warhead_for_docking,
            run_vina_docking,
            export_pose_to_mol2,
        )

        rec = prepare_receptor_for_docking(hmgb2_pdb, str(tmp_path / "rec"))
        war = prepare_warhead_for_docking(inflachromene_smiles, str(tmp_path / "war"))
        vina = run_vina_docking(
            rec["pdbqt_file"], war["pdbqt_file"],
            str(tmp_path / "vina"),
            exhaustiveness=2, num_modes=3, cpu=2,
        )
        if not vina["poses"]:
            pytest.skip("No poses to export")

        mol2_path = tmp_path / "receptor_ligand.mol2"
        result = export_pose_to_mol2(
            pose=vina["poses"][0],
            output_path=str(mol2_path),
        )
        assert result["success"], result.get("error")
        assert mol2_path.exists()
        assert mol2_path.stat().st_size > 0

    def test_prepare_e3_ligand_mol2(self, tmp_path):
        from synglue_agent.tools.docking_pipeline import prepare_e3_ligand_mol2

        # Test CRBN
        result = prepare_e3_ligand_mol2("CRBN", str(tmp_path / "crbn"))
        assert result["success"], result.get("error")
        assert result["ligand_mol2"] is not None
        assert Path(result["ligand_mol2"]).exists()

        # Test VHL
        result = prepare_e3_ligand_mol2("VHL", str(tmp_path / "vhl"))
        assert result["success"], result.get("error")

        # Test invalid
        result = prepare_e3_ligand_mol2("INVALID", str(tmp_path / "bad"))
        assert not result["success"]


class TestFullPipeline:
    """Test the full docking pipeline end-to-end."""

    def test_run_docking_pipeline(self, hmgb2_pdb, inflachromene_smiles, tmp_path):
        from synglue_agent.tools.docking_pipeline import run_docking_pipeline

        result = run_docking_pipeline(
            receptor_pdb=hmgb2_pdb,
            warhead_smiles=inflachromene_smiles,
            e3_name="CRBN",
            output_dir=str(tmp_path / "pipeline"),
            fast=True,
        )

        assert result["status"] in ("completed", "partial"), result.get("error")
        assert "receptor_prep" in result
        assert "warhead_prep" in result

        if result["status"] == "completed":
            assert len(result["poses"]) > 0
            assert result["best_pose"] is not None
            assert result["mol2_set"] is not None
            assert result["mol2_set"].receptor_ligand_mol2
            assert result["mol2_set"].ligase_ligand_mol2

    def test_dock_and_prepare_for_p4ward(self, hmgb2_pdb, inflachromene_smiles, tmp_path):
        from synglue_agent.tools.docking_pipeline import (
            dock_and_prepare_for_p4ward,
        )

        result = dock_and_prepare_for_p4ward(
            receptor_pdb=hmgb2_pdb,
            warhead_smiles=inflachromene_smiles,
            e3_name="CRBN",
            protac_smiles_list=["CCCOCCC"],
            output_dir=str(tmp_path / "dock2p4ward"),
            fast=True,
        )

        assert "docking_result" in result
        assert "p4ward_ready" in result
        if result["p4ward_ready"]:
            assert "receptor_ligand_mol2" in result["p4ward_ready"]
            assert "ligase_ligand_mol2" in result["p4ward_ready"]
