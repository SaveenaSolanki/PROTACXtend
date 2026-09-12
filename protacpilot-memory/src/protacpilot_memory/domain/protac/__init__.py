"""PROTAC domain layer for protacpilot-memory."""

from .context import ProtacContext, context_from_any
from .entities import detect_entities, entity_search_text
from .evidence import EvidenceBundle, EvidenceRef
from .normalization import (
    EntityRef,
    canonical_id_for,
    compound_identity,
    entities_in_text,
    entity_key,
    make_entity_ref,
    normalize_entity_name,
    normalize_smiles,
)

__all__ = [
    "ProtacContext",
    "context_from_any",
    "detect_entities",
    "entity_search_text",
    "EvidenceBundle",
    "EvidenceRef",
    "EntityRef",
    "canonical_id_for",
    "compound_identity",
    "entities_in_text",
    "entity_key",
    "make_entity_ref",
    "normalize_entity_name",
    "normalize_smiles",
]
