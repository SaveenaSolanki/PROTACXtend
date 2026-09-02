"""Tests for Phase 4 real RDKit chemistry wrappers."""

from __future__ import annotations

import unittest

from synglue_agent.toolkit.status import get_tool_status
from synglue_agent.tools.rdkit_chemistry import (
    calculate_descriptors,
    calculate_morgan_fingerprint,
    calculate_similarity,
    detect_dummy_atoms,
    detect_exit_vector_atoms,
    run_brics_fragmentation,
    run_recap_fragmentation,
    validate_smiles,
)


ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"
IMATINIB = "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5"


class RDKitChemistryTests(unittest.TestCase):
    def test_aspirin_or_imatinib_validates(self) -> None:
        aspirin = validate_smiles(ASPIRIN)
        imatinib = validate_smiles(IMATINIB)
        self.assertTrue(aspirin["success"], aspirin.get("error"))
        self.assertTrue(aspirin["valid"])
        self.assertTrue(imatinib["success"], imatinib.get("error"))
        self.assertTrue(imatinib["valid"])
        self.assertIn("canonical_smiles", aspirin)

    def test_invalid_smiles_returns_error(self) -> None:
        result = validate_smiles("not-a-smiles")
        self.assertFalse(result["success"])
        self.assertFalse(result["valid"])
        self.assertTrue(result["error"])

    def test_descriptors_are_numerical(self) -> None:
        result = calculate_descriptors(ASPIRIN)
        self.assertTrue(result["success"], result.get("error"))
        descriptors = result["descriptors"]
        for key in [
            "MW",
            "LogP",
            "TPSA",
            "HBD",
            "HBA",
            "rotatable_bonds",
            "ring_count",
            "aromatic_ring_count",
            "heavy_atom_count",
            "formal_charge",
            "fraction_Csp3",
            "QED",
        ]:
            self.assertIsInstance(descriptors[key], (int, float), key)
        self.assertEqual(descriptors["SA_score_status"], "unavailable")

    def test_fingerprint_similarity_works(self) -> None:
        fingerprint = calculate_morgan_fingerprint(ASPIRIN, n_bits=256)
        self.assertTrue(fingerprint["success"], fingerprint.get("error"))
        self.assertEqual(fingerprint["fingerprint"]["n_bits"], 256)
        self.assertEqual(len(fingerprint["fingerprint"]["bit_string"]), 256)

        identical = calculate_similarity(ASPIRIN, ASPIRIN)
        different = calculate_similarity(ASPIRIN, "CCO")
        self.assertTrue(identical["success"], identical.get("error"))
        self.assertTrue(different["success"], different.get("error"))
        self.assertAlmostEqual(identical["similarity"], 1.0)
        self.assertGreater(identical["similarity"], different["similarity"])

    def test_brics_and_recap_return_structured_output(self) -> None:
        for result in [run_brics_fragmentation(ASPIRIN), run_recap_fragmentation(ASPIRIN)]:
            self.assertIn("source", result)
            self.assertIn("query", result)
            self.assertIn("success", result)
            if result["success"]:
                self.assertIn("fragments", result)
                self.assertIsInstance(result["fragments"], list)
            else:
                self.assertTrue(result["error"])

    def test_dummy_and_exit_vector_detection_are_structured(self) -> None:
        smiles = "[*:1]CCO[*:2]"
        dummy = detect_dummy_atoms(smiles)
        exit_vectors = detect_exit_vector_atoms(smiles)
        self.assertTrue(dummy["success"], dummy.get("error"))
        self.assertEqual(dummy["dummy_atom_count"], 2)
        self.assertTrue(exit_vectors["success"], exit_vectors.get("error"))
        self.assertEqual(exit_vectors["exit_vector_atom_count"], 2)

    def test_rdkit_status_requires_smoke_test_for_executable(self) -> None:
        status = get_tool_status("RDKit")
        self.assertTrue(status["registered"])
        self.assertTrue(status["available"], status["evidence"])
        self.assertTrue(status["executable"], status["evidence"])
        self.assertEqual(status["classification"], "real")
        self.assertIn("smoke test succeeded", status["evidence"]["implementation"])


if __name__ == "__main__":
    unittest.main()
