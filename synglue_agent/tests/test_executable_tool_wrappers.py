"""Tests for first executable toolkit wrappers."""

from __future__ import annotations

import unittest

from synglue_agent.toolkit.registry import get_tool_status
from synglue_agent.tools.pdb_client import search_rcsb_pdb
from synglue_agent.tools.pubchem_client import lookup_pubchem_by_cid, lookup_pubchem_by_name
from synglue_agent.tools.rdkit_validator import calculate_morgan_fingerprint, calculate_rdkit_descriptors
from synglue_agent.tools.uniprot_client import lookup_uniprot_target


class ExecutableToolWrapperTests(unittest.TestCase):
    def test_empty_network_queries_return_structured_errors(self) -> None:
        for result in [
            lookup_pubchem_by_name(""),
            lookup_pubchem_by_cid(""),
            lookup_uniprot_target(""),
            search_rcsb_pdb(""),
        ]:
            self.assertIn("source", result)
            self.assertIn("query", result)
            self.assertFalse(result["success"])
            self.assertTrue(result["error"])
            self.assertEqual(result["records"], [])

    def test_rdkit_descriptor_and_fingerprint_wrappers_are_structured(self) -> None:
        descriptors = calculate_rdkit_descriptors("CCO")
        self.assertEqual(descriptors["source"], "RDKit")
        self.assertIn("query", descriptors)
        self.assertIn("success", descriptors)
        if not descriptors["success"]:
            self.assertTrue(descriptors["error"])
            return
        self.assertEqual(descriptors["descriptors"]["canonical_smiles"], "CCO")
        self.assertGreater(descriptors["descriptors"]["mw"], 0)

        fingerprint = calculate_morgan_fingerprint("CCO", n_bits=128)
        self.assertTrue(fingerprint["success"])
        self.assertEqual(fingerprint["fingerprint"]["n_bits"], 128)
        self.assertEqual(len(fingerprint["fingerprint"]["bit_string"]), 128)

    def test_registry_contains_wrapper_tool_sources(self) -> None:
        for name in ["RDKit", "PubChem", "UniProt", "RCSB PDB"]:
            status = get_tool_status(name)
            self.assertTrue(status["registered"], name)


if __name__ == "__main__":
    unittest.main()
