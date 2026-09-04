"""Integration tests for P4ward wrapper."""

from __future__ import annotations

import os
import pytest
from pathlib import Path
from typing import Dict, List, Optional

# Mark all tests in this module
pytestmark = [
    pytest.mark.p4ward,
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.environ.get("PROTACPILOT_TEST_P4WARD"),
        reason="Set PROTACPILOT_TEST_P4WARD=1 to run P4ward integration tests"
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p4ward_wrapper():
    """Create a P4ward wrapper for testing."""
    from protacxtend.tools.p4ward_wrapper import P4wardWrapper
    return P4wardWrapper(
        mode=os.environ.get("PROTACPILOT_P4WARD_MODE", "docker"),
        num_processors=int(os.environ.get("PROTACPILOT_P4WARD_CPU", "4")),
    )


@pytest.fixture(scope="module")
def benchmark_data() -> Dict[str, Path]:
    """Locate P4ward benchmark data."""
    repo_path = Path("/tmp/pi-github-repos/SKTeamLab/P4ward/benchmark")

    # Try 5T35 (VHL-based)
    bm_5t35 = repo_path / "5T35"
    if bm_5t35.exists():
        return {
            "5T35": {
                "receptor_pdb": bm_5t35 / "receptor.pdb",
                "ligase_pdb": bm_5t35 / "ligase.pdb",
                "receptor_ligand_mol2": bm_5t35 / "receptor_ligand.mol2",
                "ligase_ligand_mol2": bm_5t35 / "ligase_ligand.mol2",
                "protac_smiles": bm_5t35 / "protac.smiles",
            }
        }
    # Try other known benchmarks
    for pdb_id in ["6BOY", "6BN7", "6HAX"]:
        bm_dir = repo_path / pdb_id
        if bm_dir.exists():
            return {
                pdb_id: {
                    "receptor_pdb": bm_dir / "receptor.pdb",
                    "ligase_pdb": bm_dir / "ligase.pdb",
                    "receptor_ligand_mol2": bm_dir / "receptor_ligand.mol2",
                    "ligase_ligand_mol2": bm_dir / "ligase_ligand.mol2",
                    "protac_smiles": bm_dir / "protac.smiles",
                }
            }

    pytest.skip("No benchmark data found. Clone P4ward repo first.")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestP4wardWrapper:
    """Test suite for the P4ward wrapper."""

    def test_import(self):
        """Verify the wrapper module imports cleanly."""
        from protacxtend.tools.p4ward_wrapper import (
            P4wardWrapper,
            P4wardRunResult,
            P4wardTernaryComplex,
            run_ternary_screening,
        )
        assert P4wardWrapper is not None
        assert P4wardRunResult is not None
        assert P4wardTernaryComplex is not None

    def test_config_generation(self):
        """Verify config generation produces valid INI."""
        from protacxtend.tools.p4ward_wrapper import P4wardWrapper

        config_vhl = P4wardWrapper.generate_config(e3="VHL", num_processors=4, mode="fast")
        assert "[general]" in config_vhl
        assert "e3 = VHL" in config_vhl
        assert "num_processors = 4" in config_vhl

        config_crbn = P4wardWrapper.generate_config(e3="CRBN", num_processors=8, mode="exhaustive")
        assert "e3 = CRBN" in config_crbn
        assert "num_predictions = 162000" in config_crbn

    def test_config_all_modes(self):
        """Verify both fast and exhaustive configs are valid."""
        from protacxtend.tools.p4ward_wrapper import P4wardWrapper

        for mode in ["fast", "exhaustive"]:
            for e3 in ["VHL", "CRBN"]:
                config = P4wardWrapper.generate_config(e3=e3, num_processors=4, mode=mode)
                assert config.strip(), f"Config for {e3}/{mode} should not be empty"
                assert f"e3 = {e3}" in config

    def test_docker_available(self, p4ward_wrapper):
        """Verify Docker image is available."""
        import subprocess
        result = subprocess.run(
            ["docker", "inspect", p4ward_wrapper.docker_image],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, \
            f"Docker image '{p4ward_wrapper.docker_image}' not available. Run: docker pull paulajlr/p4ward"

    def test_run_on_benchmark(self, p4ward_wrapper, benchmark_data, tmp_path):
        """Run P4ward on a benchmark system (smoke test)."""
        bm = list(benchmark_data.values())[0]

        # Read PROTAC SMILES
        with open(bm["protac_smiles"]) as f:
            protac_smis = [line.strip() for line in f if line.strip()]

        # Run P4ward in fast mode
        result = p4ward_wrapper.run(
            receptor_pdb=str(bm["receptor_pdb"]),
            ligase_pdb=str(bm["ligase_pdb"]),
            receptor_ligand_mol2=str(bm["receptor_ligand_mol2"]),
            ligase_ligand_mol2=str(bm["ligase_ligand_mol2"]),
            protac_smiles=protac_smis,
            e3="VHL",
            output_dir=str(tmp_path / "p4ward_test"),
            config_mode="fast",
            timeout_hours=2,
        )

        # Check results
        assert result.status in ("completed", "no_valid_complexes"), \
            f"P4ward run failed: {result.error_message}"
        assert result.runtime_seconds > 0
        assert result.protac_smiles == protac_smis

        # If complexes were found, verify their structure
        if result.top_complexes:
            tc = result.top_complexes[0]
            assert tc.rank == 1
            assert isinstance(tc.score, float)
            assert tc.protac_conformer_file
        else:
            # No complexes — this can happen with fast mode
            # Check that the run completed without error
            assert result.status == "no_valid_complexes", \
                f"Unexpected status when no complexes: {result.status}"

    def test_multi_linker_screen(self, p4ward_wrapper, benchmark_data, tmp_path):
        """Test screening multiple linkers."""
        bm = list(benchmark_data.values())[0]

        with open(bm["protac_smiles"]) as f:
            protac_smis = [line.strip() for line in f if line.strip()]

        # Group PROTACs by a mock linker label
        protac_by_linker = {"test_linker": protac_smis}

        results = p4ward_wrapper.multi_linker_screen(
            receptor_pdb=str(bm["receptor_pdb"]),
            ligase_pdb=str(bm["ligase_pdb"]),
            receptor_ligand_mol2=str(bm["receptor_ligand_mol2"]),
            ligase_ligand_mol2=str(bm["ligase_ligand_mol2"]),
            protac_smiles_by_linker=protac_by_linker,
            e3="VHL",
            output_dir=str(tmp_path / "p4ward_screen"),
            config_mode="fast",
        )

        assert "test_linker" in results
        result = results["test_linker"]
        assert result.status in ("completed", "no_valid_complexes")

    def test_failure_diagnosis(self, p4ward_wrapper, benchmark_data, tmp_path):
        """Test the failure diagnosis function."""
        from protacxtend.tools.p4ward_wrapper import _diagnose_failure

        # Create mock results
        from protacxtend.tools.p4ward_wrapper import P4wardRunResult

        empty_result = P4wardRunResult(
            status="no_valid_complexes",
            run_dir=str(tmp_path),
            config_path=str(tmp_path / "config.ini"),
            top_complexes=[],
            protac_smiles=["smiles1"],
            e3_ligase="VHL",
            linker_type="C4",
        )

        diagnosis = _diagnose_failure(
            {"short_linker": empty_result},
            [],
        )

        assert diagnosis["has_valid_complexes"] is False
        assert len(diagnosis["possible_causes"]) > 0
        assert "linker too short" in diagnosis["possible_causes"][0].lower() or \
               "exit vector" in diagnosis["possible_causes"][0].lower()


class TestTernaryAgent:
    """Test the updated TernaryFeasibilityAgent."""

    def test_agent_import(self):
        """Verify the updated ternary agent imports."""
        from protacxtend.agents.ternary_agent import TernaryFeasibilityAgent
        assert TernaryFeasibilityAgent is not None

    def test_agent_instantiation(self):
        """Verify agent can be instantiated."""
        from protacxtend.agents.ternary_agent import TernaryFeasibilityAgent
        agent = TernaryFeasibilityAgent()
        assert agent.name == "TernaryFeasibilityAgent"
        assert agent.action == "assess_ternary_feasibility"


class TestRunTernaryScreening:
    """Test the high-level run_ternary_screening function."""

    def test_function_import(self):
        """Verify the convenience function imports."""
        from protacxtend.tools.p4ward_wrapper import run_ternary_screening
        assert callable(run_ternary_screening)
