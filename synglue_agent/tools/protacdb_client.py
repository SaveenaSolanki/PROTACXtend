"""Local PROTAC-DB / PROTACpedia style accessors.

The rich PROTAC-DB 3.0 workbook contains degradation, binding, ternary,
cellular, permeability, PK-adjacent, physicochemical, DOI, warhead, and E3
ligand evidence. This module normalizes those columns into compact evidence
records so agents can rank by evidence diversity instead of only raw activity.
"""

from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()
ROOT = Path(__file__).resolve().parents[2]
PROTACDB_XLSX = ROOT / "data" / "benchmark" / "PROTAC-DB_3.0_protacs.xlsx"


EVIDENCE_FIELDS: dict[str, list[str]] = {
    "degradation_capacity": [
        "DC50 (nM)",
        "Dmax (%)",
        "Percent degradation (%)",
        "Assay (DC50/Dmax)",
        "Assay (Percent degradation)",
    ],
    "target_binding_affinity": [
        "IC50 (nM, Protac to Target)",
        "EC50 (nM, Protac to Target)",
        "Kd (nM, Protac to Target)",
        "Ki (nM, Protac to Target)",
        "delta G (kcal/mol, Protac to Target)",
        "delta H (kcal/mol, Protac to Target)",
        "-T*delta S (kcal/mol, Protac to Target)",
        "kon (1/Ms, Protac to Target)",
        "koff (1/s, Protac to Target)",
        "t1/2 (s, Protac to Target)",
    ],
    "e3_binding_affinity": [
        "IC50 (nM, Protac to E3)",
        "EC50 (nM, Protac to E3)",
        "Kd (nM, Protac to E3)",
        "Ki (nM, Protac to E3)",
        "delta G (kcal/mol, Protac to E3)",
        "delta H (kcal/mol, Protac to E3)",
        "-T*delta S (kcal/mol, Protac to E3)",
        "kon (1/Ms, Protac to E3)",
        "koff (1/s, Protac to E3)",
        "t1/2 (s, Protac to E3)",
    ],
    "ternary_complex_affinity": [
        "IC50 (nM, Ternary complex)",
        "EC50 (nM, Ternary complex)",
        "Kd (nM, Ternary complex)",
        "Ki (nM, Ternary complex)",
        "delta G (kcal/mol, Ternary complex)",
        "delta H (kcal/mol, Ternary complex)",
        "-T*delta S (kcal/mol, Ternary complex)",
        "kon (1/Ms, Ternary complex)",
        "koff (1/s, Ternary complex)",
        "t1/2 (s, Ternary complex)",
    ],
    "cellular_activity": [
        "IC50 (nM, Cellular activities)",
        "EC50 (nM, Cellular activities)",
        "GI50 (nM, Cellular activities)",
        "ED50 (nM, Cellular activities)",
        "GR50 (nM, Cellular activities)",
    ],
    "cell_permeability": [
        "PAMPA Papp (nm/s, Permeability)",
        "Caco-2 A2B Papp (nm/s, Permeability)",
        "Caco-2 B2A Papp (nm/s, Permeability)",
    ],
    "physicochemical_properties": [
        "Molecular Weight",
        "Exact Mass",
        "XLogP3",
        "Heavy Atom Count",
        "Ring Count",
        "Hydrogen Bond Acceptor Count",
        "Hydrogen Bond Donor Count",
        "Rotatable Bond Count",
        "Topological Polar Surface Area",
        "Molecular Formula",
        "InChI",
        "InChI Key",
    ],
    "structure_metadata": ["PDB", "Smiles", "Article DOI"],
}


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    try:
        if isinstance(value, float) and math.isnan(value):
            return False
    except Exception:
        pass
    text = str(value).strip()
    return bool(text and text.lower() not in {"nan", "none", "null", "na", "n/a"})


def _clean_value(value: Any) -> Any:
    if not _is_present(value):
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    return value


@lru_cache(maxsize=1)
def _load_protacdb_workbook() -> list[dict[str, Any]]:
    if not PROTACDB_XLSX.exists():
        return []
    try:
        import pandas as pd

        frame = pd.read_excel(PROTACDB_XLSX)
        return [
            {key: _clean_value(value) for key, value in row.items()}
            for row in frame.to_dict(orient="records")
        ]
    except Exception:
        return []


def load_local_protacdb() -> list[dict[str, Any]]:
    rows = _load_protacdb_workbook()
    if rows:
        return rows
    return _TOOLBOX.load_table("protacdb_local.csv")


def normalize_protacdb_record(row: dict[str, Any]) -> dict[str, Any]:
    evidence = {
        family: {field: _clean_value(row.get(field)) for field in fields if _is_present(row.get(field))}
        for family, fields in EVIDENCE_FIELDS.items()
    }
    evidence = {family: values for family, values in evidence.items() if values}
    return {
        "compound_id": row.get("Compound ID") or row.get("compound_id") or row.get("id", ""),
        "name": row.get("Name") or row.get("name", ""),
        "target": row.get("Target") or row.get("target", ""),
        "uniprot": row.get("Uniprot") or row.get("uniprot", ""),
        "e3_ligase": row.get("E3 ligase") or row.get("e3_ligase", ""),
        "smiles": row.get("Smiles") or row.get("smiles", ""),
        "doi": row.get("Article DOI") or row.get("doi", ""),
        "inchikey": row.get("InChI Key") or row.get("inchikey", ""),
        "evidence": evidence,
        "evidence_families": sorted(evidence),
        "evidence_family_count": len(evidence),
        "source": "PROTAC-DB 3.0 workbook" if "Compound ID" in row else "local protacdb csv",
    }


@lru_cache(maxsize=1)
def _load_normalized_protacdb_all() -> tuple[dict[str, Any], ...]:
    rows = [normalize_protacdb_record(row) for row in load_local_protacdb()]
    return tuple(rows)


def load_normalized_protacdb(limit: int | None = None) -> list[dict[str, Any]]:
    rows = list(_load_normalized_protacdb_all())
    if limit is not None:
        return rows[: max(0, limit)]
    return rows


def search_by_target(target: str) -> list[dict[str, Any]]:
    target_u = target.upper()
    return [
        row for row in load_normalized_protacdb()
        if str(row.get("target", "")).upper() == target_u
    ]


def search_by_e3(e3_ligase: str) -> list[dict[str, Any]]:
    e3_u = e3_ligase.upper()
    return [
        row for row in load_normalized_protacdb()
        if str(row.get("e3_ligase", "")).upper() == e3_u
    ]


def search_protacdb_evidence(
    target: str | None = None,
    e3_ligase: str | None = None,
    required_families: list[str] | None = None,
    min_evidence_families: int = 1,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search normalized PROTAC-DB records by target/E3/evidence diversity."""
    target_u = target.upper() if target else ""
    e3_u = e3_ligase.upper() if e3_ligase else ""
    required = set(required_families or [])
    matches: list[dict[str, Any]] = []
    for row in load_normalized_protacdb():
        if target_u and str(row.get("target", "")).upper() != target_u:
            continue
        if e3_u and str(row.get("e3_ligase", "")).upper() != e3_u:
            continue
        families = set(row.get("evidence_families", []))
        if required and not required.issubset(families):
            continue
        if int(row.get("evidence_family_count", 0)) < min_evidence_families:
            continue
        matches.append(row)
    matches.sort(key=lambda item: (item["evidence_family_count"], bool(item.get("doi"))), reverse=True)
    return matches[: max(0, limit)]


def summarize_protacdb_diversity(target: str | None = None, e3_ligase: str | None = None) -> dict[str, Any]:
    rows = search_protacdb_evidence(target=target, e3_ligase=e3_ligase, min_evidence_families=0, limit=1_000_000)
    family_counts: dict[str, int] = {family: 0 for family in EVIDENCE_FIELDS}
    targets: set[str] = set()
    e3s: set[str] = set()
    dois: set[str] = set()
    for row in rows:
        if row.get("target"):
            targets.add(str(row["target"]))
        if row.get("e3_ligase"):
            e3s.add(str(row["e3_ligase"]))
        if row.get("doi"):
            dois.add(str(row["doi"]))
        for family in row.get("evidence_families", []):
            family_counts[family] = family_counts.get(family, 0) + 1
    return {
        "source": "PROTAC-DB 3.0 workbook" if _load_protacdb_workbook() else "local protacdb csv",
        "records": len(rows),
        "distinct_targets": len(targets),
        "distinct_e3_ligases": len(e3s),
        "distinct_dois": len(dois),
        "evidence_family_counts": family_counts,
        "query": {"target": target, "e3_ligase": e3_ligase},
    }


def export_protacdb_evidence_summary(path: str | Path) -> dict[str, Any]:
    """Write one CSV row per normalized PROTAC-DB compound/evidence family."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["compound_id", "target", "e3_ligase", "evidence_family", "field", "value", "doi", "smiles", "inchikey"]
    count = 0
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in load_normalized_protacdb():
            for family, values in record["evidence"].items():
                for field, value in values.items():
                    writer.writerow({
                        "compound_id": record["compound_id"],
                        "target": record["target"],
                        "e3_ligase": record["e3_ligase"],
                        "evidence_family": family,
                        "field": field,
                        "value": value,
                        "doi": record["doi"],
                        "smiles": record["smiles"],
                        "inchikey": record["inchikey"],
                    })
                    count += 1
    return {"path": str(output), "rows_written": count}


def extract_warheads(target: str | None = None) -> list[dict[str, Any]]:
    rows = _TOOLBOX.load_curated_warheads()
    return [row for row in rows if target is None or row.get("target", "").upper() == target.upper()]


def extract_linkers(linker_class: str | None = None) -> list[dict[str, Any]]:
    rows = _TOOLBOX.load_curated_linkers()
    return [row for row in rows if linker_class is None or row.get("linker_class", "").upper() == linker_class.upper()]


def extract_e3_ligands(e3_ligase: str | None = None) -> list[dict[str, Any]]:
    rows = _TOOLBOX.load_curated_e3_ligands()
    return [row for row in rows if e3_ligase is None or row.get("e3_ligase", "").upper() == e3_ligase.upper()]


def get_known_protac_smiles() -> list[str]:
    return [row.get("smiles", "") for row in _TOOLBOX.load_known_protacs() if row.get("smiles")]
