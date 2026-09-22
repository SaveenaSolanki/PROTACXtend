"""Natural-language understanding layer.

The :mod:`protacxtend.nlp.entity_extraction` module is the scientific front
door: it turns a free-text user request into a typed :class:`ExtractedEntities`
record. Downstream agents consume the structured record instead of guessing
entities positionally from the raw string.
"""

from protacxtend.nlp.entity_extraction import (
    E3_ALIASES,
    GENE_SYMBOLS,
    ExtractionError,
    extract_entities,
    normalize_gene_symbol,
)

__all__ = [
    "E3_ALIASES",
    "GENE_SYMBOLS",
    "ExtractionError",
    "extract_entities",
    "normalize_gene_symbol",
]
