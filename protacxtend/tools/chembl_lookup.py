"""Executable ChEMBL warhead mining helpers."""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Sequence


SOURCE = "ChEMBL REST API"
BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
USER_AGENT = "PROTACXtend/0.1"
DEFAULT_TYPES = ["IC50", "Ki", "Kd", "EC50"]


def _get_json(path: str, params: dict[str, Any] | None = None, timeout: float = 10.0) -> tuple[dict[str, Any] | None, str | None, str]:
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
    url = f"{BASE_URL}/{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), None, url
    except urllib.error.HTTPError as exc:
        return None, f"ChEMBL HTTP error {exc.code}: {exc.reason}", url
    except urllib.error.URLError as exc:
        return None, f"ChEMBL network error: {exc.reason}", url
    except TimeoutError:
        return None, "ChEMBL request timed out.", url
    except json.JSONDecodeError as exc:
        return None, f"ChEMBL returned invalid JSON: {exc}", url


def _failure(query: dict[str, Any], error: str, source_url: str | None = None, status: str = "failed") -> dict[str, Any]:
    return {"source": SOURCE, "query": query, "success": False, "error": error, "status": status, "records": [], "source_url": source_url}


def normalize_activity_value(value: Any, unit: str | None) -> float | None:
    try:
        if value in (None, ""):
            return None
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    normalized = str(unit or "nM").replace("µ", "u").strip().lower()
    if normalized in {"nm", "nanomolar", "nanomol/l"}:
        return numeric
    if normalized in {"um", "µm", "micromolar"}:
        return numeric * 1_000.0
    if normalized in {"mm", "millimolar"}:
        return numeric * 1_000_000.0
    if normalized in {"m", "molar"}:
        return numeric * 1_000_000_000.0
    if normalized in {"pm", "picomolar"}:
        return numeric / 1_000.0
    return numeric


def _pchembl_from_nM(value_nM: float | None) -> float | None:
    if value_nM is None or value_nM <= 0:
        return None
    return round(-math.log10(value_nM * 1e-9), 4)


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


def _confidence(record: dict[str, Any]) -> float:
    try:
        confidence = float(record.get("confidence_score") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    return min(max(confidence / 10.0 if confidence > 1 else confidence, 0.0), 1.0)


def _structured_activity(record: dict[str, Any], source_url: str | None = None) -> dict[str, Any]:
    value_nM = normalize_activity_value(record.get("standard_value"), record.get("standard_units"))
    pchembl = record.get("pchembl_value")
    try:
        pchembl_value = float(pchembl) if pchembl not in (None, "") else _pchembl_from_nM(value_nM)
    except (TypeError, ValueError):
        pchembl_value = _pchembl_from_nM(value_nM)
    smiles = record.get("canonical_smiles") or ((record.get("molecule_structures") or {}).get("canonical_smiles"))
    target = record.get("target_pref_name") or record.get("target_chembl_id")
    return {
        "source": SOURCE,
        "target": target,
        "target_id": record.get("target_chembl_id"),
        "molecule_name": record.get("molecule_pref_name") or record.get("molecule_chembl_id"),
        "molecule_id": record.get("molecule_chembl_id"),
        "smiles": smiles,
        "canonical_smiles": _canonical_smiles(smiles),
        "activity_type": record.get("standard_type"),
        "activity_value": value_nM,
        "activity_unit": "nM" if value_nM is not None else record.get("standard_units"),
        "pchembl_value": pchembl_value,
        "assay_description": record.get("assay_description"),
        "confidence_score": _confidence(record),
        "source_url": source_url,
        "success": True,
        "error": None,
    }


def search_targets(query: str, top_k: int = 10, timeout: float = 10.0) -> dict[str, Any]:
    request_query = {"query": query, "top_k": top_k}
    if not query or not str(query).strip():
        return _failure(request_query, "Target query is required.")
    payload, error, url = _get_json("target/search.json", {"q": query, "limit": max(int(top_k), 1)}, timeout=timeout)
    if error:
        return _failure(request_query, error, url)
    records = []
    for target in payload.get("targets", [])[:top_k]:
        records.append(
            {
                "source": SOURCE,
                "target": target.get("pref_name"),
                "target_id": target.get("target_chembl_id"),
                "organism": target.get("organism"),
                "target_type": target.get("target_type"),
                "components": target.get("target_components") or [],
                "source_url": url,
                "success": True,
                "error": None,
            }
        )
    return {
        "source": SOURCE,
        "query": request_query,
        "success": bool(records),
        "error": None if records else "no_hits",
        "status": "ok" if records else "no_hits",
        "records": records,
        "source_url": url,
    }


def search_molecule_by_name(name: str, top_k: int = 10, timeout: float = 10.0) -> dict[str, Any]:
    request_query = {"name": name, "top_k": top_k}
    if not name or not str(name).strip():
        return _failure(request_query, "Molecule name is required.")
    payload, error, url = _get_json("molecule/search.json", {"q": name, "limit": max(int(top_k), 1)}, timeout=timeout)
    if error:
        return _failure(request_query, error, url)
    records = []
    for molecule in payload.get("molecules", [])[:top_k]:
        structures = molecule.get("molecule_structures") or {}
        smiles = structures.get("canonical_smiles")
        records.append(
            {
                "source": SOURCE,
                "target": None,
                "target_id": None,
                "molecule_name": molecule.get("pref_name") or molecule.get("molecule_chembl_id"),
                "molecule_id": molecule.get("molecule_chembl_id"),
                "smiles": smiles,
                "canonical_smiles": _canonical_smiles(smiles),
                "activity_type": None,
                "activity_value": None,
                "activity_unit": None,
                "pchembl_value": None,
                "assay_description": None,
                "confidence_score": None,
                "source_url": url,
                "success": True,
                "error": None,
            }
        )
    return {
        "source": SOURCE,
        "query": request_query,
        "success": bool(records),
        "error": None if records else "no_hits",
        "status": "ok" if records else "no_hits",
        "records": records,
        "source_url": url,
    }


def get_target_activities(
    target_chembl_id: str,
    standard_types: Sequence[str] = DEFAULT_TYPES,
    top_k: int = 100,
    timeout: float = 10.0,
) -> dict[str, Any]:
    request_query = {"target_chembl_id": target_chembl_id, "standard_types": list(standard_types), "top_k": top_k}
    if not target_chembl_id or not str(target_chembl_id).strip():
        return _failure(request_query, "ChEMBL target ID is required.")
    payload, error, url = _get_json(
        "activity.json",
        {
            "target_chembl_id": target_chembl_id,
            "standard_type__in": ",".join(standard_types),
            "limit": max(int(top_k), 1),
        },
        timeout=timeout,
    )
    if error:
        return _failure(request_query, error, url)
    normalized = normalize_activity_table(payload.get("activities", []), source_url=url)
    return {
        "source": SOURCE,
        "query": request_query,
        "success": bool(normalized),
        "error": None if normalized else "no_hits",
        "status": "ok" if normalized else "no_hits",
        "records": normalized,
        "source_url": url,
    }


def normalize_activity_table(records: Sequence[dict[str, Any]], source_url: str | None = None) -> list[dict[str, Any]]:
    normalized = [_structured_activity(record, source_url=source_url) for record in records]
    normalized = [record for record in normalized if record["activity_type"] and record["activity_value"] is not None and record["smiles"]]
    best_by_smiles: dict[str, dict[str, Any]] = {}
    for record in normalized:
        key = record["canonical_smiles"] or record["smiles"]
        existing = best_by_smiles.get(key)
        if existing is None:
            best_by_smiles[key] = record
            continue
        current_rank = (record["activity_value"], -record["confidence_score"])
        existing_rank = (existing["activity_value"], -existing["confidence_score"])
        if current_rank < existing_rank:
            best_by_smiles[key] = record
    return list(best_by_smiles.values())


def rank_warhead_candidates(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for record in records:
        item = dict(record)
        activity = item.get("activity_value")
        confidence = item.get("confidence_score") or 0.0
        pchembl = item.get("pchembl_value")
        potency_score = max(0.0, min(1.0, float(pchembl) / 10.0)) if pchembl is not None else 0.0
        if potency_score == 0.0 and activity not in (None, 0):
            potency_score = max(0.0, min(1.0, (_pchembl_from_nM(float(activity)) or 0.0) / 10.0))
        item["warhead_rank_score"] = round(0.75 * potency_score + 0.25 * confidence, 4)
        ranked.append(item)
    return sorted(ranked, key=lambda item: (-(item.get("warhead_rank_score") or 0), item.get("activity_value") or float("inf")))
