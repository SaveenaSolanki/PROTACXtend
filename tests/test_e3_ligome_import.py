"""Human E3 Ligome source import.

The E3-Ligome workbook contains catalytic and non-catalytic E3-system roles.
We merge e3_cat/receptor/adaptor/scaffold rows into the E3 catalog with source
provenance, while keeping E1/E2-only rows out of the E3-Ligome import and not
turning non-catalytic components into recruiter-ligand evidence.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TAG = "e3_ligome_202508 (Dutta et al. Nat Commun 2025; doi:10.1038/s41467-025-67433-4)"


def _rows(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_e3_ligome_source_file_and_reference_metadata():
    rows = _rows("data/e3_ligome_202508_systems.csv")
    assert len(rows) == 728
    assert {"gene", "upt_acc", "upt_id", "roles", "mode", "db_confidence", "reference", "license"} <= set(rows[0])
    assert {"catalytic_ligase", "e3_receptor_component", "e3_adaptor_component", "e3_scaffold_component"} <= {r["mode"] for r in rows}
    refs = json.loads((ROOT / "data/e3_catalog_sources.json").read_text(encoding="utf-8"))
    meta = refs["e3_ligome_202508"]
    assert meta["database_version"] == "e3Ligome_202508"
    assert meta["doi"] == "10.1038/s41467-025-67433-4"
    assert "CC BY-NC-SA 4.0" in meta["license"]


def test_e3_ligome_rows_are_merged_without_losing_roles():
    catalog = {row["gene"]: row for row in _rows("data/e3_catalog_v2.csv")}
    assert len(catalog) == 800
    assert SOURCE_TAG in catalog["ZMY11"]["sources"]
    assert catalog["ZMY11"]["accession"] == "Q15326"
    assert catalog["ZMY11"]["mode"] == "catalytic_ligase"
    assert SOURCE_TAG in catalog["CRBN"]["sources"]
    assert catalog["CRBN"]["mode"] == "crl4_adapter"
    assert SOURCE_TAG in catalog["VHL"]["sources"]
    assert catalog["VHL"]["mode"] == "crl2_adapter"


def test_e3_ligome_import_does_not_mark_e1_e2_only_rows_as_ligome_e3_systems():
    catalog = {row["gene"]: row for row in _rows("data/e3_catalog_v2.csv")}
    assert "UBA1" not in catalog  # E1-only in the Ligome workbook, intentionally excluded.
    assert SOURCE_TAG not in catalog.get("UBE2D1", {}).get("sources", "")  # existing E2-like row not imported from Ligome.
