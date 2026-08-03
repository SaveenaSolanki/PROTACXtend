"""Backend-facing RCSB PDB client helpers."""

from __future__ import annotations

from typing import Any

from synglue_agent.backend.schemas import TargetRecord
from synglue_agent.tools.rcsb_pdb_lookup import (
    get_ligand_bound_structures,
    get_pdb_entry,
    search_pdb_by_gene_or_target,
    search_pdb_by_uniprot,
    summarize_structure_hits,
)


def enrich_target_with_rcsb_structures(target_record: TargetRecord, top_k: int = 20, timeout: float = 6.0) -> tuple[TargetRecord, dict[str, Any]]:
    """Attach real RCSB structure IDs only when executable metadata lookup succeeds."""

    query = target_record.uniprot_id or target_record.gene_symbol or target_record.target_name
    if not query:
        return target_record, {
            "source": "RCSB PDB",
            "success": False,
            "error": "Target has no UniProt accession, gene symbol, or target name.",
            "records": [],
        }
    if target_record.uniprot_id:
        result = search_pdb_by_uniprot(target_record.uniprot_id, top_k=top_k, timeout=timeout)
    else:
        result = search_pdb_by_gene_or_target(query, top_k=top_k, timeout=timeout)
    if result["success"]:
        target_record.structures = [record["pdb_id"] for record in result["records"] if record.get("pdb_id")]
        target_record.external_ids["rcsb_pdb_source"] = "rcsb_rest_graphql_api"
        target_record.biology_context["rcsb_pdb_summary"] = summarize_structure_hits(result)
        target_record.biology_context["rcsb_pdb_hits"] = result["records"]
    elif target_record.structures:
        target_record.external_ids["rcsb_pdb_source"] = "local_curated_seed"
        target_record.warnings.append(f"RCSB executable lookup failed; retaining local_curated_seed PDB IDs: {result['error']}")
    return target_record, result


__all__ = [
    "search_pdb_by_uniprot",
    "search_pdb_by_gene_or_target",
    "get_pdb_entry",
    "get_ligand_bound_structures",
    "summarize_structure_hits",
    "enrich_target_with_rcsb_structures",
]
