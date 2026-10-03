"""Executable BindingDB local TSV lookup helpers.

BindingDB is considered executable only when a real local TSV export is present.
No demo warhead CSV is used here.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Sequence

from protacxtend.backend.config import DATA_DIR
from protacxtend.tools.chembl_lookup import normalize_activity_value


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
        from protacxtend.tools.rdkit_chemistry import canonicalize_smiles

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


# ──────────────────────────────────────────────────────────────────────────
# BindingDB public RESTful API (no API key required)
#
# Reference: https://www.bindingdb.org/rwd/bind/BindingDBRESTfulAPI.jsp
#   getLigandsByUniprot?uniprot={UNIPROT};{cutoff}&response=application/json
#   getLigandsByUniprots?uniprot={UNIPROTS}&cutoff={cutoff}&response=application/json
#   getLigandsByPDBs?pdb={PDBs}&cutoff={cutoff}&identity={identity}&response=application/json
#
# The earlier client appended an optional ``api_key`` and warned that one was
# required; the public REST service does not require a key. The response shapes
# differ between the singular and plural endpoints, so both are parsed here.
# ──────────────────────────────────────────────────────────────────────────

BINDINGDB_REST_BASE = "https://bindingdb.org/rest"


def build_bindingdb_uniprot_url(uniprot: str, cutoff: int = 1000) -> str:
    """Singular ``getLigandsByUniprot`` URL (documented, key-free)."""
    uniprot = (uniprot or "").strip()
    return (
        f"{BINDINGDB_REST_BASE}/getLigandsByUniprot"
        f"?uniprot={uniprot};{int(cutoff)}&response=application/json"
    )


def build_bindingdb_uniprots_url(uniprots: Sequence[str], cutoff: int = 1000) -> str:
    """Plural ``getLigandsByUniprots`` URL for several accessions."""
    joined = ",".join(u.strip() for u in uniprots if u and u.strip())
    return (
        f"{BINDINGDB_REST_BASE}/getLigandsByUniprots"
        f"?uniprot={joined}&cutoff={int(cutoff)}&response=application/json"
    )


def build_bindingdb_pdb_url(pdbs: Sequence[str], cutoff: int = 1000, identity: int = 90) -> str:
    """``getLigandsByPDBs`` URL for structure-derived binder search."""
    joined = ",".join(p.strip() for p in pdbs if p and p.strip())
    return (
        f"{BINDINGDB_REST_BASE}/getLigandsByPDBs"
        f"?pdb={joined}&cutoff={int(cutoff)}&identity={int(identity)}&response=application/json"
    )


def _parse_affinity_float(raw: Any) -> float | None:
    if raw in (None, ""):
        return None
    text = str(raw).strip().replace(",", "")
    # BindingDB sometimes returns ranges like "12.4/40" -> take the first value.
    text = text.split("/")[0].strip()
    try:
        value = float(text)
    except (ValueError, TypeError):
        return None
    return value if value > 0 else None


def parse_bindingdb_rest_json(data: Any, *, source_url: str = "") -> list[dict[str, Any]]:
    """Parse either BindingDB REST JSON shape into normalized binder records.

    Handles:
      * ``getLindsByUniprotResponse``  (singular) -> ``bdb.affinities``
      * ``getLindsByUniprotsResponse`` (plural)   -> ``affinities``
      * a bare/empty string or empty payload      -> ``[]``
    """
    if not data or not isinstance(data, dict):
        return []
    payload: Any = None
    for key in ("getLindsByUniprotResponse", "getLindsByUniprotsResponse",
                "getLindsByPDBsResponse", "getLindsByPdbResponse"):
        if key in data:
            payload = data[key]
            break
    if payload is None:
        # Some deployments return {"affinities": [...]} directly.
        payload = data if "affinities" in data or "bdb.affinities" in data else None
    if payload is None:
        return []
    if isinstance(payload, str):
        return []
    entries = payload.get("affinities") or payload.get("bdb.affinities") or []
    if not isinstance(entries, list):
        return []

    records: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        smiles = (entry.get("smile") or entry.get("bdb.smile") or entry.get("smiles") or "").strip()
        if not smiles:
            continue
        activity_type = (entry.get("affinity_type") or entry.get("bdb.affinity_type") or "").strip() or None
        activity_value = _parse_affinity_float(entry.get("affinity") or entry.get("bdb.affinity"))
        monomer_id = entry.get("monomerid") or entry.get("bdb.monomerid")
        records.append({
            "source": "BindingDB REST",
            "target": entry.get("query") or entry.get("bdb.primary") or "",
            "target_id": entry.get("bdb.primary") or "",
            "molecule_name": f"BDB_{monomer_id}" if monomer_id else "BDB_ligand",
            "monomer_id": str(monomer_id) if monomer_id is not None else "",
            "smiles": smiles,
            "canonical_smiles": _canonical_smiles(smiles),
            "activity_type": activity_type,
            "activity_value": activity_value,
            "activity_unit": "nM",
            "pmid": entry.get("pmid", ""),
            "doi": entry.get("doi", ""),
            "assay_description": entry.get("query", ""),
            "confidence_score": 0.6,
            "source_url": source_url or BINDINGDB_REST_BASE,
            "success": activity_value is not None,
            "error": None,
        })
    return [r for r in records if r["activity_value"] is not None]


def fetch_bindingdb_rest(uniprot: str, cutoff: int = 1000, *, fetcher, source_url: str = "") -> dict[str, Any]:
    """Fetch and normalize one UniProt's BindingDB REST binders.

    *fetcher* is a ``url -> parsed JSON | None`` callable (the binder agent's
    cached/deadline-bounded HTTP client), injected to avoid an import cycle.
    """
    uniprot = (uniprot or "").strip()
    url = build_bindingdb_uniprot_url(uniprot, cutoff)
    if not uniprot:
        return {"source": "BindingDB REST", "success": False, "status": "missing_input",
                "error": "UniProt accession required", "records": [], "url": url}
    data = fetcher(url)
    if not data:
        return {"source": "BindingDB REST", "success": False, "status": "empty",
                "error": "empty_or_unreachable", "records": [], "url": url}
    records = parse_bindingdb_rest_json(data, source_url=source_url or url)
    return {"source": "BindingDB REST", "success": bool(records),
            "status": "ok" if records else "empty",
            "error": None if records else "no_records", "records": records, "url": url}
