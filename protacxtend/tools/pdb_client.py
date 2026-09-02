"""Compatibility RCSB PDB structure search helpers."""

from __future__ import annotations

from typing import Any

from protacxtend.tools.target_resolver import resolve_target
from protacxtend.tools.rcsb_pdb_lookup import search_pdb_by_gene_or_target, search_pdb_by_uniprot


def search_rcsb_pdb(query: str, query_type: str = "auto", rows: int = 25, timeout: float = 10.0) -> dict[str, Any]:
    """Search RCSB PDB by UniProt accession or gene/name text."""

    request_payload = {"query": query, "query_type": query_type, "rows": rows}
    if not query:
        return {"source": "RCSB PDB Search API", "query": request_payload, "success": False, "error": "Query is required.", "records": []}
    normalized_type = query_type.lower()
    if normalized_type == "auto":
        normalized_type = "uniprot" if any(char.isdigit() for char in query) and len(query) <= 10 else "text"
    if normalized_type in {"uniprot", "accession"}:
        return search_pdb_by_uniprot(query, top_k=rows, timeout=timeout)
    else:
        return search_pdb_by_gene_or_target(query, top_k=rows, timeout=timeout)


def retrieve_pdb_structures(target_name: str) -> list[str]:
    record = resolve_target(target_name)
    if record.structures and record.external_ids.get("rcsb_pdb_source") != "rcsb_rest_graphql_api":
        record.external_ids["rcsb_pdb_source"] = "local_curated_seed"
    return record.structures


def has_structure(target_name: str) -> bool:
    return bool(retrieve_pdb_structures(target_name))
