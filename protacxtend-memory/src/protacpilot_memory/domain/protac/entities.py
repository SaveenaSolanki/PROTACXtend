"""Extract associative-memory entities from a PROTAC context (Master Prompt §3E)."""

from __future__ import annotations

from .context import ProtacContext
from .normalization import EntityRef, make_entity_ref


def detect_entities(context: ProtacContext) -> list[EntityRef]:
    """Derive structured entity references from a normalised context.

    Only fields the caller actually populated produce entities. Identity is
    resolved through the curated alias table; unresolved strings stay verbatim.
    """
    refs: list[EntityRef] = []

    def add(entity_type: str, value: str | None, role: str) -> None:
        ref = make_entity_ref(entity_type, value, role)
        if ref is not None:
            refs.append(ref)

    add("Target", context.target_gene, "target")
    add("Target", context.target_uniprot, "target_accession")
    add("TargetDomain", context.target_domain, "target_domain")
    add("E3Ligase", context.e3_ligase, "e3_ligase")
    add("E3Ligase", context.e3_complex, "e3_complex")
    add("Warhead", context.warhead_name, "warhead")
    add("E3Ligand", context.e3_ligand_name, "e3_ligand")
    add("Linker", context.linker_type, "linker_type")
    add("PROTAC", context.compound_id, "compound")
    add("Compound", context.compound_id, "compound")
    add("CellLine", context.cell_line, "cell_line")
    add("Organism", context.organism, "organism")
    add("Tissue", context.tissue, "tissue")
    add("Assay", context.assay_type, "assay")
    add("Model", context.model_name, "model")
    for pdb in context.pdb_ids or []:
        add("PDB", pdb, "structure")

    # de-duplicate by (type, key, role) while preserving order
    seen: set[tuple[str, str, str]] = set()
    out: list[EntityRef] = []
    for ref in refs:
        ident = (ref.entity_type, ref.key, ref.role)
        if ident in seen:
            continue
        seen.add(ident)
        out.append(ref)
    return out


def entity_search_text(refs: list[EntityRef]) -> str:
    """Join canonical entity names + ids for the FTS search_entities column."""
    parts: list[str] = []
    for ref in refs:
        parts.append(ref.name)
        if ref.canonical_id:
            parts.append(ref.canonical_id)
        parts.extend(ref.aliases)
    return " ".join(parts)
