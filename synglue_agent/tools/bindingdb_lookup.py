"""Executable BindingDB local TSV lookup helpers.

BindingDB is considered executable only when a real local TSV export is present.
No demo warhead CSV is used here.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Sequence

from synglue_agent.backend.config import DATA_DIR
from synglue_agent.tools.chembl_lookup import normalize_activity_value


SOURCE = "BindingDB local TSV"
DEFAULT_BINDINGDB_PATHS = [
    DATA_DIR / "bindingdb.tsv",
    DATA_DIR / "BindingDB_All.tsv",
    DATA_DIR / "BindingDB.tsv",
]


def _failure(query: dict[str, Any], error: str, status: str = "failed") -> dict[str, Any]:
    return {"source": SOURCE, "query": query, "success": False, "error": error, "status": status, "records": []}


def find_bindingdb_local_tsv() -> Path | None:
    for path in DEFAULT_BINDINGDB_PATHS:
        if path.exists():
            return path
    return None


def _pick(row: dict[str, Any], candidates: Sequence[str]) -> Any:
    normalized = {key.lower().strip(): value for key, value in row.items()}
    for candidate in candidates:
        if candidate in row and row[candidate] not in (None, ""):
            return row[candidate]
        value = normalized.get(candidate.lower().strip())
        if value not in (None, ""):
            return value
    return None


def _canonical_smiles(smiles: str | None) -> str | None:
    if not smiles:
        return None
    try:
        from synglue_agent.tools.rdkit_chemistry import canonicalize_smiles

        result = canonicalize_smiles(smiles)
        if result["success"]:
            return result["canonical_smiles"]
    except Exception:
        pass
    return smiles


def _activity_from_row(row: dict[str, Any]) -> tuple[str | None, float | None, str | None]:
    definitions = [
        ("IC50", ["IC50 (nM)", "IC50", "IC50_nM"]),
        ("Ki", ["Ki (nM)", "Ki", "Ki_nM"]),
        ("Kd", ["Kd (nM)", "Kd", "Kd_nM"]),
        ("EC50", ["EC50 (nM)", "EC50", "EC50_nM"]),
    ]
    for activity_type, columns in definitions:
        value = _pick(row, columns)
        if value not in (None, ""):
            return activity_type, normalize_activity_value(value, "nM"), "nM"
    value = _pick(row, ["activity_value", "standard_value", "Value"])
    unit = _pick(row, ["activity_unit", "standard_units", "Units"]) or "nM"
    activity_type = _pick(row, ["activity_type", "standard_type", "Type"]) or None
    return activity_type, normalize_activity_value(value, unit), "nM" if value not in (None, "") else unit


def load_bindingdb_local_tsv(path: str | Path | None = None) -> dict[str, Any]:
    selected = Path(path) if path else find_bindingdb_local_tsv()
    query = {"path": str(selected) if selected else None}
    if selected is None:
        return _failure(query, "BindingDB local TSV is not present.", status="not_available")
    if not selected.exists():
        return _failure(query, f"BindingDB local TSV not found: {selected}", status="not_available")
    try:
        with selected.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            records = list(reader)
    except Exception as exc:
        return _failure(query, f"BindingDB TSV could not be read: {exc}")
    return {"source": SOURCE, "query": query, "success": True, "error": None, "status": "ok", "records": records}


def normalize_bindingdb_activity(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in records:
        activity_type, activity_value, activity_unit = _activity_from_row(row)
        smiles = _pick(row, ["Ligand SMILES", "SMILES", "smiles", "Ligand_SMILES"])
        target = _pick(row, ["Target Name", "target", "Target", "UniProt (SwissProt) Primary ID of Target Chain"])
        item = {
            "source": SOURCE,
            "target": target,
            "target_id": _pick(row, ["UniProt (SwissProt) Primary ID of Target Chain", "uniprot_id", "target_id"]),
            "molecule_name": _pick(row, ["Ligand Name", "molecule_name", "Name"]),
            "smiles": smiles,
            "canonical_smiles": _canonical_smiles(smiles),
            "activity_type": activity_type,
            "activity_value": activity_value,
            "activity_unit": activity_unit,
            "pchembl_value": None,
            "assay_description": _pick(row, ["Assay Description", "assay_description"]),
            "confidence_score": 0.55,
            "source_url": "https://www.bindingdb.org",
            "success": True,
            "error": None,
        }
        if item["smiles"] and item["activity_type"] and item["activity_value"] is not None:
            normalized.append(item)
    best_by_smiles: dict[str, dict[str, Any]] = {}
    for item in normalized:
        key = item["canonical_smiles"] or item["smiles"]
        existing = best_by_smiles.get(key)
        if existing is None or item["activity_value"] < existing["activity_value"]:
            best_by_smiles[key] = item
    return list(best_by_smiles.values())


def search_bindingdb_local(target_name_or_uniprot: str, top_k: int = 100, path: str | Path | None = None) -> dict[str, Any]:
    query = {"target_name_or_uniprot": target_name_or_uniprot, "top_k": top_k, "path": str(path) if path else None}
    if not target_name_or_uniprot or not str(target_name_or_uniprot).strip():
        return _failure(query, "BindingDB target query is required.")
    loaded = load_bindingdb_local_tsv(path)
    if not loaded["success"]:
        loaded["query"] = query
        return loaded
    needle = str(target_name_or_uniprot).strip().lower()
    hits = []
    for row in loaded["records"]:
        haystack = " ".join(str(value) for value in row.values() if value is not None).lower()
        if needle in haystack:
            hits.append(row)
    normalized = normalize_bindingdb_activity(hits)
    normalized.sort(key=lambda item: (item["activity_value"], -(item["confidence_score"] or 0)))
    records = normalized[: max(int(top_k), 1)]
    return {
        "source": SOURCE,
        "query": query,
        "success": bool(records),
        "error": None if records else "no_hits",
        "status": "ok" if records else "no_hits",
        "records": records,
    }
