"""Executable PubChem PUG-REST lookup wrappers."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


SOURCE = "PubChem PUG-REST"
BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
USER_AGENT = "PROTACXtend/0.1"
PROPERTY_FIELDS = "CanonicalSMILES,IsomericSMILES,IUPACName,MolecularFormula,MolecularWeight"


def _source_url(path: str) -> str:
    return f"{BASE_URL}/{path}"


def _get_json(path: str, timeout: float = 10.0) -> tuple[dict[str, Any] | None, str | None, str]:
    url = _source_url(path)
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), None, url
    except urllib.error.HTTPError as exc:
        return None, f"PubChem HTTP error {exc.code}: {exc.reason}", url
    except urllib.error.URLError as exc:
        return None, f"PubChem network error: {exc.reason}", url
    except TimeoutError:
        return None, "PubChem request timed out.", url
    except json.JSONDecodeError as exc:
        return None, f"PubChem returned invalid JSON: {exc}", url


def _empty(query: dict[str, Any], source_url: str | None, error: str) -> dict[str, Any]:
    return {
        "source": SOURCE,
        "query": query,
        "cid": None,
        "canonical_smiles": None,
        "isomeric_smiles": None,
        "iupac_name": None,
        "molecular_formula": None,
        "molecular_weight": None,
        "synonyms": [],
        "source_url": source_url,
        "success": False,
        "error": error,
    }


def _record_from_property(row: dict[str, Any], query: dict[str, Any], source_url: str, synonyms: list[str] | None = None) -> dict[str, Any]:
    return {
        "source": SOURCE,
        "query": query,
        "cid": row.get("CID"),
        "canonical_smiles": row.get("CanonicalSMILES"),
        "isomeric_smiles": row.get("IsomericSMILES"),
        "iupac_name": row.get("IUPACName") or row.get("Title"),
        "molecular_formula": row.get("MolecularFormula"),
        "molecular_weight": row.get("MolecularWeight"),
        "synonyms": synonyms or [],
        "source_url": source_url,
        "success": True,
        "error": None,
    }


def _properties_for_cids(cids: list[int | str], query: dict[str, Any], timeout: float, top_k: int | None = None) -> tuple[list[dict[str, Any]], str | None, str | None]:
    selected = [str(cid) for cid in cids[:top_k] if cid not in ("", None)]
    if not selected:
        return [], "No PubChem CIDs were provided.", None
    cid_text = ",".join(selected)
    path = f"compound/cid/{urllib.parse.quote(cid_text)}/property/{PROPERTY_FIELDS}/JSON"
    payload, error, url = _get_json(path, timeout=timeout)
    if error:
        return [], error, url
    rows = (payload.get("PropertyTable") or {}).get("Properties") or []
    records = []
    for row in rows:
        synonyms = _synonyms_for_cid(row.get("CID"), timeout=timeout)
        records.append(_record_from_property(row, query, url, synonyms=synonyms))
    return records, None if records else "PubChem returned no compound properties.", url


def _synonyms_for_cid(cid: int | str | None, timeout: float) -> list[str]:
    if cid in ("", None):
        return []
    path = f"compound/cid/{urllib.parse.quote(str(cid))}/synonyms/JSON"
    payload, error, _url = _get_json(path, timeout=timeout)
    if error:
        return []
    info = (payload.get("InformationList") or {}).get("Information") or []
    if not info:
        return []
    return list(dict.fromkeys(info[0].get("Synonym") or []))[:25]


def _first_or_records(records: list[dict[str, Any]], query: dict[str, Any], source_url: str | None, error: str | None) -> dict[str, Any]:
    if not records:
        result = _empty(query, source_url, error or "PubChem returned no compound records.")
        result["records"] = []
        return result
    result = dict(records[0])
    result["records"] = records
    result["success"] = True
    result["error"] = None
    return result


def search_compound_by_name(name: str, timeout: float = 10.0) -> dict[str, Any]:
    query = {"name": name}
    if not name or not str(name).strip():
        result = _empty(query, None, "Compound name is required.")
        result["records"] = []
        return result
    encoded = urllib.parse.quote(str(name).strip())
    cid_path = f"compound/name/{encoded}/cids/JSON"
    cid_payload, cid_error, cid_url = _get_json(cid_path, timeout=timeout)
    if cid_error:
        result = _empty(query, cid_url, cid_error)
        result["records"] = []
        return result
    infos = (cid_payload.get("IdentifierList") or {}).get("CID") or []
    records, error, prop_url = _properties_for_cids(infos, query, timeout=timeout, top_k=5)
    return _first_or_records(records, query, prop_url or cid_url, error)


def get_compound_by_cid(cid: int | str, timeout: float = 10.0) -> dict[str, Any]:
    query = {"cid": cid}
    if cid in ("", None):
        result = _empty(query, None, "CID is required.")
        result["records"] = []
        return result
    records, error, url = _properties_for_cids([cid], query, timeout=timeout, top_k=1)
    return _first_or_records(records, query, url, error)


def get_cid_from_smiles(smiles: str, timeout: float = 10.0) -> dict[str, Any]:
    query = {"smiles": smiles}
    if not smiles or not str(smiles).strip():
        result = _empty(query, None, "SMILES is required.")
        result["records"] = []
        return result
    path = f"compound/smiles/{urllib.parse.quote(str(smiles).strip(), safe='')}/cids/JSON"
    payload, error, url = _get_json(path, timeout=timeout)
    if error:
        result = _empty(query, url, error)
        result["records"] = []
        return result
    cids = (payload.get("IdentifierList") or {}).get("CID") or []
    records, prop_error, prop_url = _properties_for_cids(cids, query, timeout=timeout, top_k=5)
    return _first_or_records(records, query, prop_url or url, prop_error)


def get_properties_by_cid(cid: int | str, timeout: float = 10.0) -> dict[str, Any]:
    return get_compound_by_cid(cid, timeout=timeout)


def pubchem_similarity_search(smiles: str, threshold: int = 90, top_k: int = 20, timeout: float = 10.0) -> dict[str, Any]:
    query = {"smiles": smiles, "threshold": threshold, "top_k": top_k}
    if not smiles or not str(smiles).strip():
        result = _empty(query, None, "SMILES is required.")
        result["records"] = []
        return result
    threshold = max(0, min(int(threshold), 100))
    path = (
        "compound/fastsimilarity_2d/smiles/"
        f"{urllib.parse.quote(str(smiles).strip(), safe='')}/cids/JSON?Threshold={threshold}"
    )
    payload, error, url = _get_json(path, timeout=timeout)
    if error:
        result = _empty(query, url, error)
        result["records"] = []
        return result
    cids = (payload.get("IdentifierList") or {}).get("CID") or []
    records, prop_error, prop_url = _properties_for_cids(cids, query, timeout=timeout, top_k=top_k)
    result = _first_or_records(records, query, prop_url or url, prop_error)
    result["search_type"] = "pubchem_fastsimilarity_2d"
    return result


def pubchem_substructure_search(smiles: str, top_k: int = 20, timeout: float = 10.0) -> dict[str, Any]:
    query = {"smiles": smiles, "top_k": top_k}
    if not smiles or not str(smiles).strip():
        result = _empty(query, None, "SMILES is required.")
        result["records"] = []
        return result
    path = f"compound/substructure/smiles/{urllib.parse.quote(str(smiles).strip(), safe='')}/cids/JSON"
    payload, error, url = _get_json(path, timeout=timeout)
    if error:
        result = _empty(query, url, error)
        result["records"] = []
        return result
    cids = (payload.get("IdentifierList") or {}).get("CID") or []
    records, prop_error, prop_url = _properties_for_cids(cids, query, timeout=timeout, top_k=top_k)
    result = _first_or_records(records, query, prop_url or url, prop_error)
    result["search_type"] = "pubchem_substructure"
    return result


__all__ = [
    "search_compound_by_name",
    "get_compound_by_cid",
    "get_cid_from_smiles",
    "get_properties_by_cid",
    "pubchem_similarity_search",
    "pubchem_substructure_search",
]
