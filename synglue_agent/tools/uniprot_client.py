"""Compatibility UniProt lookup helpers."""

from __future__ import annotations

from typing import Any, Optional

from synglue_agent.backend.schemas import TargetRecord
from synglue_agent.tools.target_resolver import resolve_target
from synglue_agent.tools.uniprot_lookup import search_uniprot


def lookup_uniprot_target(query: str, organism_id: int = 9606, size: int = 5, timeout: float = 10.0) -> dict[str, Any]:
    """Lookup target records from UniProt REST without local fallback."""

    organism = str(organism_id) if organism_id != 9606 else "human"
    return search_uniprot(query, organism=organism, reviewed=False, top_k=size, timeout=timeout)


def retrieve_uniprot_record(target_name: str, uniprot_id: Optional[str] = None) -> TargetRecord:
    return resolve_target(target_name, uniprot_id)


def retrieve_target_synonyms(target_name: str, uniprot_id: Optional[str] = None) -> list[str]:
    return retrieve_uniprot_record(target_name, uniprot_id).synonyms
