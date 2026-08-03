"""Tests for unified PROTAC component wrappers and provenance."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from synglue_agent.tools.protac_component_wrappers import (
    basic_novelty_check,
    bindingdb_api_adapter,
    find_chembl_binders,
    load_bindingdb_binders,
    load_exit_vector_map,
    pubchem_compound_lookup,
    pubchem_similarity_wrapper,
    rdkit_adme_descriptor_output,
    rdkit_assembly_validation_gate,
    require_provenance_fields,
    resolve_target_with_provenance,
    validate_e3_ligand_table,
)


class ProtacComponentWrapperTests(unittest.TestCase):
    def assert_provenance_complete(self, result: dict) -> None:
        check = require_provenance_fields([result])
        self.assertTrue(check["success"], check)

    def test_target_resolution_uses_labeled_local_fallback(self) -> None:
        result = resolve_target_with_provenance("BRD4", allow_network=False)
        self.assertTrue(result["success"], result.get("error"))
        self.assertEqual(result["source"], "local_curated_seed")
        self.assertEqual(result["record"]["uniprot_id"], "O60885")
        self.assertEqual(result["provenance"]["evidence_type"], "local_database")
        self.assertIn("UniProt REST was not called", result["warnings"][0])
        self.assert_provenance_complete(result)

    def test_chembl_wrapper_does_not_call_network_by_default(self) -> None:
        result = find_chembl_binders("BRD4")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "not_run")
        self.assertEqual(result["provenance"]["evidence_type"], "not_run")
        self.assertIn("No ChEMBL binder claim", result["provenance"]["claim_allowed"])
        self.assert_provenance_complete(result)

    def test_bindingdb_local_loader_normalizes_tsv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bindingdb.tsv"
            path.write_text(
                "Target Name\tUniProt (SwissProt) Primary ID of Target Chain\tLigand Name\tLigand SMILES\tIC50 (nM)\tAssay Description\n"
                "BRD4\tO60885\tLigand A\tCCO\t50\tbinding assay\n",
                encoding="utf-8",
            )
            result = load_bindingdb_binders("O60885", path=path)
        self.assertTrue(result["success"], result.get("error"))
        self.assertEqual(result["records"][0]["activity_value"], 50.0)
        self.assertEqual(result["provenance"]["evidence_type"], "local_database")
        self.assertIn("local BindingDB TSV", result["provenance"]["claim_allowed"])
        self.assert_provenance_complete(result)

    def test_bindingdb_api_adapter_is_honest_not_connected(self) -> None:
        result = bindingdb_api_adapter("BRD4", allow_network=True)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "not_connected")
        self.assertIn("No live BindingDB API claim", result["provenance"]["claim_allowed"])
        self.assert_provenance_complete(result)

    def test_pubchem_wrappers_do_not_call_network_by_default(self) -> None:
        compound = pubchem_compound_lookup("aspirin")
        similarity = pubchem_similarity_wrapper("CCO")
        self.assertEqual(compound["status"], "not_run")
        self.assertEqual(similarity["status"], "not_run")
        self.assertIn("No PubChem compound claim", compound["provenance"]["claim_allowed"])
        self.assertIn("No PubChem similarity claim", similarity["provenance"]["claim_allowed"])
        self.assert_provenance_complete(compound)
        self.assert_provenance_complete(similarity)

    def test_e3_ligand_schema_validation(self) -> None:
        result = validate_e3_ligand_table()
        self.assertTrue(result["valid_records"])
        self.assertFalse(result["invalid_records"])
        self.assertTrue(result["success"])
        self.assertEqual(result["provenance"]["evidence_type"], "local_database")
        self.assert_provenance_complete(result)

    def test_exit_vector_curated_map_loader(self) -> None:
        result = load_exit_vector_map()
        self.assertTrue(result["success"], result["invalid_records"])
        self.assertGreaterEqual(len(result["records"]), 3)
        self.assertIn("curated exit-vector", result["provenance"]["claim_allowed"])
        self.assert_provenance_complete(result)

    def test_rdkit_assembly_validation_gate(self) -> None:
        result = rdkit_assembly_validation_gate("[*:1]CCO", "[*:1]CCOCC[*:2]", "O=C1NC(=O)c2ccc([*:1])cc21")
        self.assertTrue(result["success"], result["errors"])
        self.assertEqual(result["status"], "passed")
        self.assertIn("RDKit assembly-input validation", result["provenance"]["claim_allowed"])
        self.assert_provenance_complete(result)

    def test_basic_novelty_exact_and_similarity_check(self) -> None:
        result = basic_novelty_check("CCO")
        self.assertTrue(result["success"], result.get("error"))
        self.assertIn("patent-safe", result["provenance"]["claim_allowed"])
        self.assertEqual(result["provenance"]["evidence_type"], "local_database")
        self.assert_provenance_complete(result)

    def test_rdkit_adme_descriptor_output_claim_language(self) -> None:
        result = rdkit_adme_descriptor_output("CCO")
        self.assertTrue(result["success"], result.get("error"))
        self.assertGreater(result["descriptors"]["mw"], 0)
        self.assertIn("not ML/API-predicted", result["claim_language"])
        self.assertEqual(result["provenance"]["evidence_type"], "rdkit_descriptor")
        self.assert_provenance_complete(result)


if __name__ == "__main__":
    unittest.main()
