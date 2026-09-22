"""PROTAC domain: context fingerprints, aliases, compound identity."""

from __future__ import annotations

from protacpilot_memory.domain.protac import (
    ProtacContext,
    canonical_id_for,
    compound_identity,
    entities_in_text,
    entity_key,
    normalize_entity_name,
)
from protacpilot_memory.domain.protac.entities import (
    detect_entities,
    entity_search_text,
)


def test_fingerprint_identity_and_separation():
    a = ProtacContext(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293",
                      assay_type="degradation assay", compound_id="P17")
    b = ProtacContext(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293",
                      assay_type="degradation assay", compound_id="P17")
    c = ProtacContext(target_gene="BRD2", e3_ligase="VHL", cell_line="HEK293",
                      assay_type="degradation assay", compound_id="P17")
    d = ProtacContext(target_gene="BRD4", e3_ligase="VHL", cell_line="MV4-11",
                      assay_type="degradation assay", compound_id="P17")
    assert a.fingerprint() == b.fingerprint()
    assert a.fingerprint() != c.fingerprint()
    assert a.fingerprint() != d.fingerprint()


def test_context_match_and_diff():
    a = ProtacContext(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293")
    b = ProtacContext(target_gene="BRD4", e3_ligase="VHL", cell_line="MV4-11")
    assert 0.0 < a.match_score(b) < 1.0
    diff = a.diff(b)
    assert "cell" in diff
    assert a.match_score(a) == 1.0


def test_scope_is_machine_readable():
    ctx = ProtacContext(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293")
    scope = ctx.scope(evidence_scope="experimental")
    assert scope["target_scope"] == "BRD4"
    assert scope["e3_scope"] == "VHL"
    assert scope["evidence_scope"] == "experimental"


def test_entity_aliasing():
    assert normalize_entity_name("Target", "BRD-4") == "BRD4"
    assert normalize_entity_name("Target", "Q15059") == "BRD4"
    assert normalize_entity_name("E3Ligase", "pVHL") == "VHL"
    assert normalize_entity_name("E3Ligase", "cereblon") == "CRBN"
    assert normalize_entity_name("CellLine", "mv411") == "MV4-11"
    assert canonical_id_for("Target", "BRD4") == "Q15059"
    assert entity_key("Target", "BRD4", "Q15059").startswith("target:")


def test_detect_entities_from_context():
    ctx = ProtacContext(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293",
                        assay_type="degradation assay", pdb_ids=["5T35"])
    refs = detect_entities(ctx)
    types = {r.entity_type for r in refs}
    assert {"Target", "E3Ligase", "CellLine", "Assay", "PDB"} <= types
    assert "BRD4" in entity_search_text(refs)


def test_entities_in_text_only_known_aliases():
    refs = entities_in_text("We tested BRD4 with pVHL in HEK293 cells")
    names = {r.name for r in refs}
    assert "BRD4" in names
    assert "VHL" in names
    assert entities_in_text("some totally unknown molecule zzz") == []


def test_compound_identity_without_rdkit():
    identity = compound_identity(protac_smiles="CCO", compound_id="P17")
    assert identity["original_smiles"] == "CCO"
    assert identity["internal_compound_id"] == "P17"
    assert identity["canonicalised"] in (True, False)  # RDKit may or may not be installed
