"""Phase 11 docking/ternary feasibility infrastructure tests."""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from synglue_agent.backend.schemas import CandidateRecord
from synglue_agent.tools.docking_status import detect_docking_backends
from synglue_agent.tools.ternary_feasibility import (
    assess_ternary_feasibility,
    generate_ligand_conformers,
    run_vina_if_available,
)


class Phase11DockingTests(unittest.TestCase):
    def _candidate(self) -> CandidateRecord:
        return CandidateRecord(
            candidate_id="C1",
            target="BRD4",
            e3_ligase="CRBN",
            full_protac_smiles="CCO",
            provenance={},
        )

    def test_backend_detection_works(self) -> None:
        result = detect_docking_backends()
        self.assertTrue(result["success"])
        for name in ["vina", "gnina", "pymol", "openbabel", "rdkit", "haddock", "rfdiffusion", "rosetta"]:
            self.assertIn(name, result["backends"])
            self.assertIn("available", result["backends"][name])

    @patch("shutil.which", return_value=None)
    def test_missing_vina_returns_registered_but_not_executable(self, _mock_which) -> None:
        out = run_vina_if_available(self._candidate())
        self.assertFalse(out["success"])
        self.assertIsNone(out["docking_score"])
        self.assertEqual(out["error"], "registered_but_not_executable")

    def test_rdkit_conformer_generation_or_skip(self) -> None:
        result = generate_ligand_conformers("CCO")
        if not result["success"]:
            self.assertIn("RDKit unavailable", result["error"])
            self.skipTest("RDKit not available in this environment.")
        self.assertIn("ligand_sdf", result["ligand_files"])

    @patch("synglue_agent.tools.ternary_feasibility.run_vina_if_available")
    @patch("synglue_agent.tools.ternary_feasibility.run_gnina_if_available")
    def test_ternary_proxy_label_and_no_docking_score(self, mock_gnina, mock_vina) -> None:
        mock_vina.return_value = {
            "backend": "vina",
            "input_structures": {},
            "ligand_files": {},
            "command_run": None,
            "docking_score": None,
            "success": False,
            "error": "registered_but_not_executable",
            "limitations": "missing vina",
        }
        mock_gnina.return_value = {
            "backend": "gnina",
            "input_structures": {},
            "ligand_files": {},
            "command_run": None,
            "docking_score": None,
            "success": False,
            "error": "registered_but_not_executable",
            "limitations": "missing gnina",
        }
        out = assess_ternary_feasibility(self._candidate(), backend="auto")
        self.assertEqual(out["backend"], "geometry_proxy_stub")
        self.assertIsNone(out["docking_score"])
        self.assertIn("no docking was performed", out["limitations"])

    @patch("shutil.which", side_effect=lambda cmd: "/usr/bin/vina" if cmd == "vina" else None)
    def test_vina_installed_but_incomplete_inputs_does_not_run(self, _mock_which) -> None:
        out = run_vina_if_available(self._candidate())
        self.assertFalse(out["success"])
        self.assertIsNone(out["docking_score"])
        self.assertIn("missing_docking_inputs", out["error"])


if __name__ == "__main__":
    unittest.main()
