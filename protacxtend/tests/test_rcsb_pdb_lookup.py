"""Tests for Phase 7 RCSB PDB executable structure lookup."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from protacxtend.backend.pdb_client import enrich_target_with_rcsb_structures
from protacxtend.backend.schemas import TargetRecord
from protacxtend.toolkit.status import get_tool_status
from protacxtend.tools.rcsb_pdb_lookup import (
    get_ligand_bound_structures,
    get_pdb_entry,
    search_pdb_by_gene_or_target,
    search_pdb_by_uniprot,
    summarize_structure_hits,
)


SEARCH_PAYLOAD = {"result_set": [{"identifier": "4LYI", "score": 1.0}, {"identifier": "6BN7", "score": 0.9}]}
GRAPHQL_PAYLOAD = {
    "data": {
        "entries": [
            {
                "rcsb_id": "4LYI",
                "struct": {"title": "BRD4 bromodomain bound to inhibitor"},
                "exptl": [{"method": "X-RAY DIFFRACTION"}],
                "rcsb_accession_info": {"initial_release_date": "2014-09-17T00:00:00Z"},
                "rcsb_entry_info": {"resolution_combined": [1.5]},
                "polymer_entities": [
                    {
                        "entity_poly": {"rcsb_entity_polymer_type": "Protein"},
                        "rcsb_polymer_entity": {"pdbx_description": "Bromodomain-containing protein 4"},
                        "rcsb_polymer_entity_container_identifiers": {"auth_asym_ids": ["A"], "asym_ids": ["A"]},
                    }
                ],
                "nonpolymer_entities": [
                    {
                        "pdbx_entity_nonpoly": {"comp_id": "JQ1", "name": "JQ1 inhibitor"},
                        "rcsb_nonpolymer_entity_container_identifiers": {
                            "auth_asym_ids": ["B"],
                            "asym_ids": ["B"],
                            "nonpolymer_comp_id": "JQ1",
                        },
                    }
                ],
            },
            {
                "rcsb_id": "6BN7",
                "struct": {"title": "BRD4 apo structure"},
                "exptl": [{"method": "X-RAY DIFFRACTION"}],
                "rcsb_accession_info": {"initial_release_date": "2018-01-01T00:00:00Z"},
                "rcsb_entry_info": {"resolution_combined": [2.1]},
                "polymer_entities": [
                    {
                        "entity_poly": {"rcsb_entity_polymer_type": "Protein"},
                        "rcsb_polymer_entity": {"pdbx_description": "Bromodomain-containing protein 4"},
                        "rcsb_polymer_entity_container_identifiers": {"auth_asym_ids": ["A"], "asym_ids": ["A"]},
                    }
                ],
                "nonpolymer_entities": [],
            },
        ]
    }
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


def fake_rcsb_urlopen(request, timeout=10.0):
    if "rcsbsearch" in request.full_url:
        return FakeHTTPResponse(SEARCH_PAYLOAD)
    if "graphql" in request.full_url:
        return FakeHTTPResponse(GRAPHQL_PAYLOAD)
    return FakeHTTPResponse({})


class RCSBPDBLookupTests(unittest.TestCase):
    @patch("urllib.request.urlopen", side_effect=fake_rcsb_urlopen)
    def test_search_pdb_by_uniprot_returns_structured_metadata(self, _mock_urlopen) -> None:
        result = search_pdb_by_uniprot("O60885", top_k=2, timeout=1.0)
        self.assertTrue(result["success"], result.get("error"))
        hit = result["records"][0]
        self.assertEqual(hit["pdb_id"], "4LYI")
        self.assertEqual(hit["title"], "BRD4 bromodomain bound to inhibitor")
        self.assertEqual(hit["method"], "X-RAY DIFFRACTION")
        self.assertEqual(hit["resolution"], 1.5)
        self.assertEqual(hit["release_date"], "2014-09-17T00:00:00Z")
        self.assertEqual(hit["ligand_ids"], ["JQ1"])
        self.assertEqual(hit["chain_ids"], ["A"])
        self.assertIn("rcsb.org/structure/4LYI", hit["source_url"])

    @patch("urllib.request.urlopen", side_effect=fake_rcsb_urlopen)
    def test_gene_search_entry_and_ligand_bound_filter(self, _mock_urlopen) -> None:
        text_result = search_pdb_by_gene_or_target("BRD4", top_k=2, timeout=1.0)
        entry = get_pdb_entry("4LYI", timeout=1.0)
        ligand_bound = get_ligand_bound_structures("O60885", top_k=2, timeout=1.0)
        summary = summarize_structure_hits(text_result)
        self.assertTrue(text_result["success"])
        self.assertTrue(entry["success"])
        self.assertEqual(entry["pdb_id"], "4LYI")
        self.assertTrue(ligand_bound["success"])
        self.assertEqual([record["pdb_id"] for record in ligand_bound["records"]], ["4LYI"])
        self.assertEqual(summary["structure_count"], 2)
        self.assertEqual(summary["ligand_bound_count"], 1)
        self.assertEqual(summary["best_resolution"], 1.5)

    def test_empty_queries_return_structured_failures(self) -> None:
        for result in [search_pdb_by_uniprot(""), search_pdb_by_gene_or_target(""), get_pdb_entry("")]:
            self.assertFalse(result["success"])
            self.assertTrue(result["error"])

    @patch("urllib.request.urlopen", side_effect=fake_rcsb_urlopen)
    def test_target_enrichment_uses_real_rcsb_hits(self, _mock_urlopen) -> None:
        target = TargetRecord(target_name="BRD4", gene_symbol="BRD4", uniprot_id="O60885", structures=["local_seed"])
        enriched, result = enrich_target_with_rcsb_structures(target, top_k=2, timeout=1.0)
        self.assertTrue(result["success"])
        self.assertEqual(enriched.structures, ["4LYI", "6BN7"])
        self.assertEqual(enriched.external_ids["rcsb_pdb_source"], "rcsb_rest_graphql_api")
        self.assertEqual(enriched.biology_context["rcsb_pdb_summary"]["ligand_bound_count"], 1)

    def test_status_system_marks_rcsb_executable(self) -> None:
        status = get_tool_status("RCSB PDB")
        self.assertTrue(status["registered"])
        self.assertTrue(status["available"], status["evidence"])
        self.assertTrue(status["executable"], status["evidence"])
        self.assertEqual(status["classification"], "real")


if __name__ == "__main__":
    unittest.main()
