"""Medvar/Knepper definite E3 ligase source import.

The attached Definite Ligase List is a catalytic E3 ligase source.  It should
augment the E3 catalog with references, but it must not be treated as evidence
of PROTAC recruiter ligand availability or used to back non-catalytic complex
components such as CRBN/VHL adaptors.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TAG = "definite_ligase_list_medvar2016 (Medvar et al. PMID:27199454)"


def _rows(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_medvar_source_file_has_reference_and_expected_size():
    rows = _rows("data/definite_ligase_list_medvar2016.csv")
    assert len(rows) == 377
    assert {"gene", "protein_name", "e3_class", "refseq", "swiss_prot", "reference", "source_url"} <= set(rows[0])
    assert rows[0]["reference"] == "Medvar et al. PubMed:27199454"
    refs = json.loads((ROOT / "data/e3_catalog_sources.json").read_text(encoding="utf-8"))
    assert refs["definite_ligase_list_medvar2016"]["pubmed_id"] == "27199454"
    assert "non-catalytic" in refs["definite_ligase_list_medvar2016"]["notes"]


def test_medvar_ligases_are_merged_into_catalog_with_reference():
    catalog = {row["gene"]: row for row in _rows("data/e3_catalog_v2.csv")}
    assert "AFF4" in catalog  # newly added from spreadsheet
    assert catalog["AFF4"]["accession"] == "Q9UHB7"
    assert catalog["AFF4"]["family"] == "UBOX"
    assert catalog["AFF4"]["mode"] == "catalytic_ligase"
    assert SOURCE_TAG in catalog["AFF4"]["sources"]
    assert SOURCE_TAG in catalog["AMFR"]["sources"]  # existing UniProt row augmented


def test_medvar_source_does_not_rewrite_non_catalytic_recruiters():
    catalog = {row["gene"]: row for row in _rows("data/e3_catalog_v2.csv")}
    assert SOURCE_TAG not in catalog["CRBN"]["sources"]
    assert SOURCE_TAG not in catalog["VHL"]["sources"]
    assert catalog["CRBN"]["mode"] == "crl4_adapter"
    assert catalog["VHL"]["mode"] == "crl2_adapter"
