"""Tests for Phase 5 UniProt executable target lookup."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from synglue_agent.backend.schemas import TargetRecord
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox
from synglue_agent.tools.uniprot_lookup import (
    get_function_summary,
    get_protein_sequence,
    get_subcellular_location,
    get_uniprot_record,
    search_uniprot,
)


UNIPROT_ITEM = {
    "primaryAccession": "O60885",
    "uniProtkbId": "BRD4_HUMAN",
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "organism": {"scientificName": "Homo sapiens"},
    "genes": [{"geneName": {"value": "BRD4"}, "synonyms": [{"value": "HUNK1"}]}],
    "proteinDescription": {"recommendedName": {"fullName": {"value": "Bromodomain-containing protein 4"}}},
    "sequence": {"value": "M" * 42, "length": 42},
    "comments": [
        {"commentType": "FUNCTION", "texts": [{"value": "Chromatin reader protein."}]},
        {
            "commentType": "SUBCELLULAR LOCATION",
            "subcellularLocations": [{"location": {"value": "Nucleus"}}],
        },
    ],
}


class FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def fake_urlopen(request, timeout=10.0):
    url = request.full_url
    if "/search?" in url:
        return FakeHTTPResponse({"results": [UNIPROT_ITEM]})
    return FakeHTTPResponse(UNIPROT_ITEM)


class UniProtLookupTests(unittest.TestCase):
    @patch("urllib.request.urlopen", side_effect=fake_urlopen)
    def test_search_uniprot_returns_structured_records(self, _mock_urlopen) -> None:
        result = search_uniprot("BRD4", top_k=1, timeout=1.0)
        self.assertTrue(result["success"], result.get("error"))
        record = result["records"][0]
        self.assertEqual(record["accession"], "O60885")
        self.assertEqual(record["gene_name"], "BRD4")
        self.assertEqual(record["protein_name"], "Bromodomain-containing protein 4")
        self.assertEqual(record["organism"], "Homo sapiens")
        self.assertTrue(record["reviewed"])
        self.assertEqual(record["sequence_length"], 42)
        self.assertEqual(record["sequence"], "M" * 42)
        self.assertIn("HUNK1", record["synonyms"])
        self.assertIn("Chromatin reader", record["function"])
        self.assertEqual(record["subcellular_location"], ["Nucleus"])
        self.assertIn("rest.uniprot.org", record["source_url"])
        self.assertIsNone(record["error"])

    @patch("urllib.request.urlopen", side_effect=fake_urlopen)
    def test_record_accessors_return_structured_fields(self, _mock_urlopen) -> None:
        record = get_uniprot_record("O60885", timeout=1.0)
        sequence = get_protein_sequence("O60885", timeout=1.0)
        location = get_subcellular_location("O60885", timeout=1.0)
        function = get_function_summary("O60885", timeout=1.0)
        self.assertTrue(record["success"])
        self.assertEqual(sequence["sequence_length"], 42)
        self.assertEqual(location["subcellular_location"], ["Nucleus"])
        self.assertEqual(function["function"], "Chromatin reader protein.")

    def test_missing_query_returns_error_without_fallback(self) -> None:
        result = search_uniprot("")
        self.assertFalse(result["success"])
        self.assertEqual(result["records"], [])
        self.assertIn("required", result["error"])

    @patch("synglue_agent.backend.uniprot_client.resolve_target_via_uniprot")
    def test_target_resolution_prefers_uniprot_api(self, mock_resolve) -> None:
        mock_resolve.return_value = (
            TargetRecord(
                target_name="Bromodomain-containing protein 4",
                gene_symbol="BRD4",
                uniprot_id="O60885",
                source="uniprot_rest_api",
                biology_context={"real_output_generated": True},
            ),
            {"success": True},
        )
        record = ProtacDesignToolbox().resolve_target("BRD4")
        self.assertEqual(record.source, "uniprot_rest_api")
        self.assertEqual(record.uniprot_id, "O60885")

    @patch("synglue_agent.backend.uniprot_client.resolve_target_via_uniprot")
    def test_local_curated_seed_is_labeled_when_api_fails(self, mock_resolve) -> None:
        mock_resolve.return_value = (None, {"success": False, "error": "network unavailable"})
        record = ProtacDesignToolbox().resolve_target("BRD4")
        self.assertEqual(record.source, "local_curated_seed")
        self.assertTrue(any("UniProt REST lookup" in warning for warning in record.warnings))


if __name__ == "__main__":
    unittest.main()
