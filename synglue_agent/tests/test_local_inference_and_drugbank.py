"""Tests for Lean MagnetDB local adapter and DrugBank credential-gated API."""

from __future__ import annotations

import os
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from synglue_agent.toolkit.status import get_tool_status
from synglue_agent.tools.drugbank_client import drugbank_api_status, search_drugbank_compounds
from synglue_agent.tools import magnetdb_lookup
from synglue_agent.tools.magnetdb_lookup import LeanTrie, run_lean_magnetdb_inference


class LocalInferenceAndDrugBankTests(unittest.TestCase):
    def _make_magnetdb_files(self, directory: Path, fragment: str) -> tuple[Path, Path]:
        trie = LeanTrie()
        node = trie.root
        for char in (fragment + "$")[::-1]:
            node.children.setdefault(char, type(node)())
            node = node.children[char]
        node.is_end_of_word = True
        node.tag_ids.add("DB001")

        metadata = {
            "DB001": {
                "Target_Atom_Count": 8,
                "Target_ID": "P00533",
                "Target_Name": "EGFR",
                "Ligand_Name": "test_ligand",
                "Organism": "Homo sapiens",
                "Assay": "test assay",
                "Original_SMILES": "CC(=O)O",
            }
        }

        trie_path = directory / "Lean_MagnetDB_Trie.pkl"
        metadata_path = directory / "Clean_Metadata_Hash.pkl"
        with trie_path.open("wb") as handle:
            pickle.dump(trie, handle)
        with metadata_path.open("wb") as handle:
            pickle.dump(metadata, handle)
        return trie_path, metadata_path

    def test_magnetdb_graceful_failure_when_files_missing(self) -> None:
        result = run_lean_magnetdb_inference("CC(=O)O", trie_path="/tmp/missing_trie.pkl", metadata_path="/tmp/missing_meta.pkl")
        self.assertFalse(result["success"])
        self.assertTrue(result["error"])
        self.assertEqual(result["records"], [])

    def test_magnetdb_runs_when_local_files_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            user_smiles = "CC(=O)NC1=CC=CC=C1"
            fragments = magnetdb_lookup._terminal_fragments(user_smiles)  # noqa: SLF001 - test-only probe
            if not fragments:
                self.skipTest("RDKit RECAP did not produce terminal fragments in this environment.")
            trie_path, metadata_path = self._make_magnetdb_files(Path(directory), fragments[0])
            result = run_lean_magnetdb_inference(
                user_smiles,
                min_query_cov=0.0,
                min_target_cov=0.0,
                trie_path=trie_path,
                metadata_path=metadata_path,
            )
            self.assertTrue(result["success"], result.get("error"))
            self.assertGreater(len(result["records"]), 0)
            record = result["records"][0]
            self.assertEqual(record["target_id"], "P00533")
            self.assertEqual(record["molecule_name"], "test_ligand")

    def test_drugbank_api_requires_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            status = drugbank_api_status()
            self.assertFalse(status["available"])
            result = search_drugbank_compounds("imatinib")
            self.assertFalse(result["success"])
            self.assertIn("credentials", result["error"])

    def test_status_for_legacy_tools_is_honest(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            drugbank = get_tool_status("DrugBank")
            self.assertTrue(drugbank["registered"])
            self.assertFalse(drugbank["executable"])
            magnetdb = get_tool_status("Lean MagnetDB inference")
            if magnetdb["registered"]:
                self.assertFalse(magnetdb["executable"])
            else:
                self.assertEqual(magnetdb["section"], "legacy_internal")
            self.assertFalse(magnetdb["executable"])


if __name__ == "__main__":
    unittest.main()
