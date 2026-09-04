"""Tests for Phase 8 executable ChEMBL and BindingDB warhead mining."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from protacxtend.toolkit.status import get_tool_status
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
from protacxtend.tools.bindingdb_lookup import (
    load_bindingdb_local_tsv,
    normalize_bindingdb_activity,
    search_bindingdb_local,
)
from protacxtend.tools.chembl_lookup import (
    get_target_activities,
    normalize_activity_table,
    normalize_activity_value,
    rank_warhead_candidates,
    search_molecule_by_name,
    search_targets,
)


TARGET_PAYLOAD = {
    "targets": [
        {
            "pref_name": "Bromodomain-containing protein 4",
            "target_chembl_id": "CHEMBL1163125",
            "organism": "Homo sapiens",
            "target_type": "SINGLE PROTEIN",
            "target_components": [{"accession": "O60885"}],
        }
    ]
}

ACTIVITY_PAYLOAD = {
    "activities": [
        {
            "target_chembl_id": "CHEMBL1163125",
            "target_pref_name": "BRD4",
            "molecule_chembl_id": "CHEMBL1",
            "molecule_pref_name": "Ligand A",
            "canonical_smiles": "CCO",
            "standard_type": "IC50",
            "standard_value": "0.5",
            "standard_units": "uM",
            "pchembl_value": "6.3",
            "assay_description": "inhibition assay",
            "confidence_score": 9,
        },
        {
            "target_chembl_id": "CHEMBL1163125",
            "target_pref_name": "BRD4",
            "molecule_chembl_id": "CHEMBL2",
            "molecule_pref_name": "Ligand A duplicate",
            "canonical_smiles": "C(C)O",
            "standard_type": "IC50",
            "standard_value": "900",
            "standard_units": "nM",
            "assay_description": "duplicate weaker assay",
            "confidence_score": 8,
        },
        {
            "target_chembl_id": "CHEMBL1163125",
            "target_pref_name": "BRD4",
            "molecule_chembl_id": "CHEMBL3",
            "molecule_pref_name": "Ligand B",
            "canonical_smiles": "CCN",
            "standard_type": "Ki",
            "standard_value": "100",
            "standard_units": "nM",
            "assay_description": "binding assay",
            "confidence_score": 7,
        },
    ]
}

MOLECULE_PAYLOAD = {
    "molecules": [
        {
            "molecule_chembl_id": "CHEMBL25",
            "pref_name": "ASPIRIN",
            "molecule_structures": {"canonical_smiles": "CC(=O)Oc1ccccc1C(=O)O"},
        }
    ]
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


def fake_chembl_urlopen(request, timeout=10.0):
    url = request.full_url
    if "target/search" in url:
        return FakeHTTPResponse(TARGET_PAYLOAD)
    if "activity" in url:
        return FakeHTTPResponse(ACTIVITY_PAYLOAD)
    if "molecule/search" in url:
        return FakeHTTPResponse(MOLECULE_PAYLOAD)
    return FakeHTTPResponse({})


class WarheadMiningTests(unittest.TestCase):
    def test_unit_normalization(self) -> None:
        self.assertEqual(normalize_activity_value(1, "nM"), 1)
        self.assertEqual(normalize_activity_value(1, "uM"), 1000)
        self.assertEqual(normalize_activity_value(1, "M"), 1_000_000_000)
        self.assertEqual(normalize_activity_value(1000, "pM"), 1)

    def test_deduplication_by_canonical_smiles(self) -> None:
        normalized = normalize_activity_table(ACTIVITY_PAYLOAD["activities"])
        smiles = {record["canonical_smiles"] for record in normalized}
        self.assertEqual(len(normalized), 2)
        self.assertIn("CCO", smiles)
        ethanol = [record for record in normalized if record["canonical_smiles"] == "CCO"][0]
        self.assertEqual(ethanol["activity_value"], 500.0)

    def test_ranking_by_potency_and_confidence(self) -> None:
        ranked = rank_warhead_candidates(normalize_activity_table(ACTIVITY_PAYLOAD["activities"]))
        self.assertEqual(ranked[0]["molecule_name"], "Ligand B")
        self.assertGreater(ranked[0]["warhead_rank_score"], ranked[-1]["warhead_rank_score"])

    @patch("urllib.request.urlopen", side_effect=fake_chembl_urlopen)
    def test_chembl_api_wrappers_are_structured(self, _mock_urlopen) -> None:
        targets = search_targets("BRD4", top_k=1, timeout=1.0)
        activities = get_target_activities("CHEMBL1163125", top_k=10, timeout=1.0)
        molecule = search_molecule_by_name("aspirin", top_k=1, timeout=1.0)
        self.assertTrue(targets["success"], targets.get("error"))
        self.assertEqual(targets["records"][0]["target_id"], "CHEMBL1163125")
        self.assertTrue(activities["success"], activities.get("error"))
        self.assertEqual(len(activities["records"]), 2)
        self.assertTrue(molecule["success"], molecule.get("error"))
        self.assertEqual(molecule["records"][0]["molecule_name"], "ASPIRIN")

    def test_bindingdb_graceful_failure_when_local_file_unavailable(self) -> None:
        result = load_bindingdb_local_tsv("/tmp/definitely_missing_bindingdb.tsv")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "not_available")

    def test_bindingdb_local_tsv_search_and_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bindingdb.tsv"
            path.write_text(
                "Target Name\tUniProt (SwissProt) Primary ID of Target Chain\tLigand Name\tLigand SMILES\tIC50 (nM)\tAssay Description\n"
                "BRD4\tO60885\tLigand A\tCCO\t50\tbinding assay\n"
                "BRD4\tO60885\tLigand A duplicate\tC(C)O\t100\tbinding assay\n",
                encoding="utf-8",
            )
            loaded = load_bindingdb_local_tsv(path)
            normalized = normalize_bindingdb_activity(loaded["records"])
            searched = search_bindingdb_local("O60885", path=path)
            self.assertTrue(loaded["success"])
            self.assertEqual(len(normalized), 1)
            self.assertEqual(normalized[0]["activity_value"], 50.0)
            self.assertTrue(searched["success"], searched.get("error"))
            self.assertEqual(searched["records"][0]["molecule_name"], "Ligand A")

    def test_status_marks_chembl_real_and_bindingdb_not_executable_without_tsv(self) -> None:
        chembl = get_tool_status("ChEMBL")
        bindingdb = get_tool_status("BindingDB")
        self.assertTrue(chembl["registered"])
        self.assertTrue(chembl["executable"], chembl["evidence"])
        self.assertEqual(chembl["classification"], "real")
        self.assertTrue(bindingdb["registered"])
        self.assertFalse(bindingdb["executable"])
        self.assertIn("TSV", bindingdb["failure_reason"])

    def test_external_warhead_seed_is_used_as_local_curated_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            (tmp / "curated_warheads.csv").write_text(
                "name,target,smiles,activity_type,activity_nM,assay_confidence\n",
                encoding="utf-8",
            )
            (tmp / "warhead_seed_metaboglue_gold.csv").write_text(
                "SMILES,uniprot_id,gt_affinity_type,gt_affinity_nM,gt_activity_text,gt_source_column,gt_training_reliability\n"
                "CCO,P00533,IC50,50,IC50(nM)=50,affinity_nM,medium\n",
                encoding="utf-8",
            )
            toolbox = ProtacDesignToolbox(data_dir=tmp)
            from protacxtend.backend.schemas import TargetRecord

            target = TargetRecord(target_name="EGFR", gene_symbol="EGFR", uniprot_id="P00533")
            binders = toolbox.retrieve_known_binders(target, potency_threshold_nM=100.0)
            self.assertEqual(len(binders), 1)
            self.assertEqual(binders[0].activity_nM, 50.0)
            self.assertIn("local_curated_seed", binders[0].source)


if __name__ == "__main__":
    unittest.main()
