"""Backend-facing UniProt client helpers."""

from __future__ import annotations

from typing import Any

from synglue_agent.backend.schemas import TargetRecord
from synglue_agent.tools.uniprot_lookup import (
    get_function_summary,
    get_protein_sequence,
    get_subcellular_location,
    get_target_synonyms,
    get_uniprot_record,
    search_uniprot,
)


def target_record_from_uniprot(record: dict[str, Any]) -> TargetRecord:
    """Convert a successful UniProt REST record into the project schema."""

    return TargetRecord(
        target_name=record.get("protein_name") or record.get("gene_name") or record.get("accession") or "",
        gene_symbol=record.get("gene_name") or "",
        uniprot_id=record.get("accession"),
        organism=record.get("organism") or "unknown",
        synonyms=record.get("synonyms") or [],
        alphafold_id=f"AF-{record.get('accession')}-F1" if record.get("accession") else None,
        uniprot_confidence=0.98 if record.get("reviewed") else 0.85,
        tractability_score=0.5,
        source="uniprot_rest_api",
        external_ids={"uniprot_source_url": record.get("source_url")},
        biology_context={
            "function": record.get("function"),
            "subcellular_location": record.get("subcellular_location") or [],
            "sequence_length": record.get("sequence_length"),
            "reviewed": record.get("reviewed"),
            "real_output_generated": True,
        },
    )


def resolve_target_via_uniprot(
    query: str,
    accession: str | None = None,
    organism: str = "human",
    reviewed: bool = True,
    timeout: float = 6.0,
) -> tuple[TargetRecord | None, dict[str, Any]]:
    """Resolve a target through UniProt REST without local fallback."""

    if accession:
        result = get_uniprot_record(accession, timeout=timeout)
        if result["success"]:
            return target_record_from_uniprot(result), result
        return None, result

    result = search_uniprot(query, organism=organism, reviewed=reviewed, top_k=1, timeout=timeout)
    if result["success"] and result["records"]:
        return target_record_from_uniprot(result["records"][0]), result
    return None, result


__all__ = [
    "search_uniprot",
    "get_uniprot_record",
    "get_target_synonyms",
    "get_protein_sequence",
    "get_subcellular_location",
    "get_function_summary",
    "target_record_from_uniprot",
    "resolve_target_via_uniprot",
]
