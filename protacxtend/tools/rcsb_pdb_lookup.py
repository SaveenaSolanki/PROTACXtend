"""Executable RCSB PDB structure lookup wrappers."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


SOURCE = "RCSB PDB"
SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
GRAPHQL_URL = "https://data.rcsb.org/graphql"
USER_AGENT = "PROTACXtend/0.1"


ENTRY_QUERY = """
query Entries($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    struct { title }
    exptl { method }
    rcsb_accession_info { initial_release_date }
    rcsb_entry_info { resolution_combined }
    polymer_entities {
      entity_poly { rcsb_entity_polymer_type }
      rcsb_polymer_entity { pdbx_description }
      rcsb_polymer_entity_container_identifiers {
        auth_asym_ids
        asym_ids
      }
    }
    nonpolymer_entities {
      pdbx_entity_nonpoly { comp_id name }
      rcsb_nonpolymer_entity_container_identifiers {
        auth_asym_ids
        asym_ids
        nonpolymer_comp_id
      }
    }
  }
}
"""


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[dict[str, Any] | None, str | None]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return None, f"RCSB HTTP error {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        return None, f"RCSB network error: {exc.reason}"
    except TimeoutError:
        return None, "RCSB request timed out."
    except json.JSONDecodeError as exc:
        return None, f"RCSB returned invalid JSON: {exc}"


def _empty(query: dict[str, Any], error: str, source_url: str | None = None) -> dict[str, Any]:
    return {"source": SOURCE, "query": query, "success": False, "error": error, "records": [], "source_url": source_url}


def _entry_source_url(pdb_id: str | None) -> str | None:
    return f"https://www.rcsb.org/structure/{pdb_id}" if pdb_id else None


def _search_payload_by_uniprot(accession: str, top_k: int) -> dict[str, Any]:
    return {
        "query": {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                "operator": "exact_match",
                "value": accession,
            },
        },
        "return_type": "entry",
        "request_options": {"paginate": {"start": 0, "rows": top_k}},
    }


def _search_payload_by_text(query: str, top_k: int) -> dict[str, Any]:
    return {
        "query": {"type": "terminal", "service": "full_text", "parameters": {"value": query}},
        "return_type": "entry",
        "request_options": {"paginate": {"start": 0, "rows": top_k}},
    }


def _search_ids(payload: dict[str, Any], timeout: float) -> tuple[list[str], str | None]:
    data, error = _post_json(SEARCH_URL, payload, timeout=timeout)
    if error:
        return [], error
    ids = []
    for item in data.get("result_set", []) or []:
        identifier = item.get("identifier")
        if identifier:
            ids.append(str(identifier).split("_")[0].upper())
    return list(dict.fromkeys(ids)), None


def _entry_from_graphql(item: dict[str, Any]) -> dict[str, Any]:
    pdb_id = item.get("rcsb_id")
    resolution_values = (item.get("rcsb_entry_info") or {}).get("resolution_combined") or []
    polymer_entities = []
    chain_ids = []
    for entity in item.get("polymer_entities") or []:
        identifiers = entity.get("rcsb_polymer_entity_container_identifiers") or {}
        auth_chains = identifiers.get("auth_asym_ids") or []
        asym_chains = identifiers.get("asym_ids") or []
        chain_ids.extend(auth_chains or asym_chains)
        polymer_entities.append(
            {
                "description": (entity.get("rcsb_polymer_entity") or {}).get("pdbx_description"),
                "polymer_type": (entity.get("entity_poly") or {}).get("rcsb_entity_polymer_type"),
                "chain_ids": auth_chains or asym_chains,
            }
        )
    ligand_ids = []
    ligand_entities = []
    for entity in item.get("nonpolymer_entities") or []:
        nonpoly = entity.get("pdbx_entity_nonpoly") or {}
        identifiers = entity.get("rcsb_nonpolymer_entity_container_identifiers") or {}
        comp_id = nonpoly.get("comp_id") or identifiers.get("nonpolymer_comp_id")
        if comp_id:
            ligand_ids.append(comp_id)
        ligand_entities.append(
            {
                "comp_id": comp_id,
                "name": nonpoly.get("name"),
                "chain_ids": identifiers.get("auth_asym_ids") or identifiers.get("asym_ids") or [],
            }
        )
    return {
        "source": SOURCE,
        "pdb_id": pdb_id,
        "title": (item.get("struct") or {}).get("title"),
        "method": ", ".join(method.get("method", "") for method in item.get("exptl", []) if method.get("method")) or None,
        "resolution": min(resolution_values) if resolution_values else None,
        "release_date": (item.get("rcsb_accession_info") or {}).get("initial_release_date"),
        "polymer_entity": polymer_entities,
        "ligand_ids": sorted({ligand for ligand in ligand_ids if ligand}),
        "ligand_entities": ligand_entities,
        "chain_ids": sorted({chain for chain in chain_ids if chain}),
        "source_url": _entry_source_url(pdb_id),
        "success": True,
        "error": None,
    }


def _fetch_entries(pdb_ids: list[str], timeout: float) -> tuple[list[dict[str, Any]], str | None]:
    if not pdb_ids:
        return [], "No PDB IDs were provided."
    payload = {"query": ENTRY_QUERY, "variables": {"ids": pdb_ids}}
    data, error = _post_json(GRAPHQL_URL, payload, timeout=timeout)
    if error:
        return [], error
    if data.get("errors"):
        return [], f"RCSB GraphQL errors: {data['errors']}"
    entries = ((data.get("data") or {}).get("entries") or [])
    return [_entry_from_graphql(entry) for entry in entries if entry], None


def _search_and_fetch(search_payload: dict[str, Any], request_query: dict[str, Any], timeout: float) -> dict[str, Any]:
    pdb_ids, search_error = _search_ids(search_payload, timeout=timeout)
    if search_error:
        return _empty(request_query, search_error, SEARCH_URL)
    records, fetch_error = _fetch_entries(pdb_ids, timeout=timeout)
    if fetch_error:
        return _empty(request_query, fetch_error, GRAPHQL_URL)
    return {
        "source": SOURCE,
        "query": request_query,
        "success": bool(records),
        "error": None if records else "RCSB returned no structure metadata.",
        "records": records,
        "source_url": SEARCH_URL,
    }


def search_pdb_by_uniprot(accession: str, top_k: int = 20, timeout: float = 10.0) -> dict[str, Any]:
    query = {"accession": accession, "top_k": top_k}
    if not accession or not str(accession).strip():
        return _empty(query, "UniProt accession is required.", SEARCH_URL)
    payload = _search_payload_by_uniprot(str(accession).strip(), max(int(top_k), 1))
    return _search_and_fetch(payload, query, timeout=timeout)


def search_pdb_by_gene_or_target(query: str, top_k: int = 20, timeout: float = 10.0) -> dict[str, Any]:
    request_query = {"query": query, "top_k": top_k}
    if not query or not str(query).strip():
        return _empty(request_query, "Gene or target query is required.", SEARCH_URL)
    payload = _search_payload_by_text(str(query).strip(), max(int(top_k), 1))
    return _search_and_fetch(payload, request_query, timeout=timeout)


def get_pdb_entry(pdb_id: str, timeout: float = 10.0) -> dict[str, Any]:
    query = {"pdb_id": pdb_id}
    if not pdb_id or not str(pdb_id).strip():
        result = _empty(query, "PDB ID is required.", GRAPHQL_URL)
        return {**result, "pdb_id": None}
    records, error = _fetch_entries([str(pdb_id).strip().upper()], timeout=timeout)
    if error or not records:
        result = _empty(query, error or "RCSB returned no structure metadata.", GRAPHQL_URL)
        return {**result, "pdb_id": str(pdb_id).strip().upper()}
    record = dict(records[0])
    record["query"] = query
    return record


def get_ligand_bound_structures(accession_or_query: str, top_k: int = 20, timeout: float = 10.0) -> dict[str, Any]:
    query_text = str(accession_or_query or "").strip()
    request_query = {"accession_or_query": accession_or_query, "top_k": top_k}
    if not query_text:
        return _empty(request_query, "Accession or target query is required.", SEARCH_URL)
    if any(char.isdigit() for char in query_text) and len(query_text) <= 12:
        result = search_pdb_by_uniprot(query_text, top_k=top_k, timeout=timeout)
    else:
        result = search_pdb_by_gene_or_target(query_text, top_k=top_k, timeout=timeout)
    if not result["success"]:
        result["query"] = request_query
        return result
    ligand_records = [record for record in result["records"] if record.get("ligand_ids")]
    return {
        "source": SOURCE,
        "query": request_query,
        "success": bool(ligand_records),
        "error": None if ligand_records else "RCSB returned structures, but no ligand metadata was present.",
        "records": ligand_records,
        "source_url": result.get("source_url"),
    }


def summarize_structure_hits(hits: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    records = hits.get("records", []) if isinstance(hits, dict) else hits
    ligand_bound = [record for record in records if record.get("ligand_ids")]
    methods = sorted({record.get("method") for record in records if record.get("method")})
    best_resolution = min((record["resolution"] for record in records if record.get("resolution") is not None), default=None)
    return {
        "source": SOURCE,
        "success": bool(records),
        "error": None if records else "No RCSB structure hits to summarize.",
        "structure_count": len(records),
        "ligand_bound_count": len(ligand_bound),
        "pdb_ids": [record.get("pdb_id") for record in records if record.get("pdb_id")],
        "ligand_bound_pdb_ids": [record.get("pdb_id") for record in ligand_bound if record.get("pdb_id")],
        "methods": methods,
        "best_resolution": best_resolution,
    }


__all__ = [
    "search_pdb_by_uniprot",
    "search_pdb_by_gene_or_target",
    "get_pdb_entry",
    "get_ligand_bound_structures",
    "summarize_structure_hits",
]
