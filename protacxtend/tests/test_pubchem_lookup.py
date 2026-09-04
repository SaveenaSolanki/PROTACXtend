"""Tests for Phase 6 PubChem executable compound lookup."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from protacxtend.toolkit.status import get_tool_status
from protacxtend.tools.pubchem_client import search_compound_by_name as local_seed_search
from protacxtend.tools.pubchem_lookup import (
    get_cid_from_smiles,
    get_compound_by_cid,
    get_properties_by_cid,
    pubchem_similarity_search,
    pubchem_substructure_search,
    search_compound_by_name,
)


ASPIRIN_PROPS = {
    "PropertyTable": {
        "Properties": [
            {
                "CID": 2244,
                "CanonicalSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "IsomericSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "IUPACName": "2-acetyloxybenzoic acid",
                "MolecularFormula": "C9H8O4",
                "MolecularWeight": 180.16,
            }
        ]
    }
}

SYNONYMS = {"InformationList": {"Information": [{"CID": 2244, "Synonym": ["aspirin", "acetylsalicylic acid"]}]}}


class FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def fake_pubchem_urlopen(request, timeout=10.0):
    url = request.full_url
    if "/compound/name/definitely-not-a-real-compound/cids/JSON" in url:
        return FakeHTTPResponse({"IdentifierList": {"CID": []}})
    if "/compound/name/aspirin/cids/JSON" in url:
        return FakeHTTPResponse({"IdentifierList": {"CID": [2244]}})
    if "/compound/smiles/" in url and "/cids/JSON" in url:
        return FakeHTTPResponse({"IdentifierList": {"CID": [2244]}})
    if "/fastsimilarity_2d/" in url:
        return FakeHTTPResponse({"IdentifierList": {"CID": [2244]}})
    if "/substructure/" in url:
        return FakeHTTPResponse({"IdentifierList": {"CID": [2244]}})
    if "/synonyms/JSON" in url:
        return FakeHTTPResponse(SYNONYMS)
    if "/property/" in url:
        return FakeHTTPResponse(ASPIRIN_PROPS)
    return FakeHTTPResponse({})


class PubChemLookupTests(unittest.TestCase):
    @patch("urllib.request.urlopen", side_effect=fake_pubchem_urlopen)
    def test_aspirin_name_lookup_returns_structured_record(self, _mock_urlopen) -> None:
        result = search_compound_by_name("aspirin", timeout=1.0)
        self.assertTrue(result["success"], result.get("error"))
        self.assertEqual(result["cid"], 2244)
        self.assertEqual(result["canonical_smiles"], "CC(=O)OC1=CC=CC=C1C(=O)O")
        self.assertEqual(result["isomeric_smiles"], "CC(=O)OC1=CC=CC=C1C(=O)O")
        self.assertEqual(result["iupac_name"], "2-acetyloxybenzoic acid")
        self.assertEqual(result["molecular_formula"], "C9H8O4")
        self.assertEqual(result["molecular_weight"], 180.16)
        self.assertIn("aspirin", result["synonyms"])
        self.assertIn("pubchem.ncbi.nlm.nih.gov", result["source_url"])
        self.assertIsNone(result["error"])

    @patch("urllib.request.urlopen", side_effect=fake_pubchem_urlopen)
    def test_cid_smiles_properties_similarity_and_substructure_are_structured(self, _mock_urlopen) -> None:
        for result in [
            get_compound_by_cid(2244, timeout=1.0),
            get_properties_by_cid(2244, timeout=1.0),
            get_cid_from_smiles("CC(=O)OC1=CC=CC=C1C(=O)O", timeout=1.0),
            pubchem_similarity_search("CC(=O)OC1=CC=CC=C1C(=O)O", timeout=1.0),
            pubchem_substructure_search("c1ccccc1", timeout=1.0),
        ]:
            self.assertIn("query", result)
            self.assertTrue(result["success"], result.get("error"))
            self.assertEqual(result["cid"], 2244)
            self.assertIn("records", result)

    @patch("urllib.request.urlopen", side_effect=fake_pubchem_urlopen)
    def test_invalid_name_returns_structured_failure(self, _mock_urlopen) -> None:
        result = search_compound_by_name("definitely-not-a-real-compound", timeout=1.0)
        self.assertFalse(result["success"])
        self.assertIsNone(result["cid"])
        self.assertEqual(result["records"], [])
        self.assertTrue(result["error"])

    def test_empty_query_returns_failure_without_network(self) -> None:
        result = search_compound_by_name("")
        self.assertFalse(result["success"])
        self.assertEqual(result["records"], [])
        self.assertIn("required", result["error"])

    def test_local_seed_search_is_labeled_stub(self) -> None:
        hits = local_seed_search("JQ1")
        if hits:
            self.assertEqual(hits[0]["execution_mode"], "local_seed")
            self.assertEqual(hits[0]["classification"], "stub")
            self.assertFalse(hits[0]["real_output_generated"])

    def test_status_system_marks_pubchem_executable(self) -> None:
        status = get_tool_status("PubChem")
        self.assertTrue(status["registered"])
        self.assertTrue(status["available"], status["evidence"])
        self.assertTrue(status["executable"], status["evidence"])
        self.assertEqual(status["classification"], "real")


if __name__ == "__main__":
    unittest.main()
