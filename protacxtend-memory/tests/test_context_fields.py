"""PROTAC context fields + fingerprint extension (brief §4)."""

from __future__ import annotations

from protacpilot_memory.domain.protac.context import FINGERPRINT_FIELDS, ProtacContext


def test_new_coordinates_participate_in_fingerprint():
    base = ProtacContext(
        project="p", target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293",
        compound_id="P17", linker_type="PEG", experiment_type="degradation_assay",
        endpoint="dmax", construct="full-length", structural_context="ternary-interface",
        organism="human", warhead_name="JQ1",
    )
    for field in (
        "project", "warhead", "linker", "organism", "experiment_type",
        "endpoint", "construct", "structural_context",
    ):
        assert field in FINGERPRINT_FIELDS
    changed = ProtacContext.from_dict(base.to_dict())
    setattr(changed, "construct", "truncated")
    assert changed.fingerprint() != base.fingerprint()


def test_match_score_uses_new_coordinates():
    a = ProtacContext(target_gene="BRD4", experiment_type="degradation_assay", endpoint="dmax")
    b = ProtacContext(target_gene="BRD4", experiment_type="degradation_assay", endpoint="dc50")
    assert 0.0 < a.match_score(b) < 1.0
    assert "endpoint" in a.diff(b)


def test_scope_round_trips_new_fields():
    ctx = ProtacContext(
        target_gene="BRD4", e3_ligase="VHL", linker_type="rigid",
        experiment_type="degradation_assay", endpoint="dmax", construct="full-length",
        structural_context="ternary-interface", project="proj",
    )
    scope = ctx.scope()
    for key in (
        "linker_scope", "experiment_type_scope", "endpoint_scope",
        "construct_scope", "structural_context_scope", "project_scope",
    ):
        assert key in scope
    restored = ProtacContext.from_scope(scope)
    assert restored.linker_type == "rigid"
    assert restored.experiment_type == "degradation_assay"
    assert restored.endpoint == "dmax"
    assert restored.construct == "full-length"
    assert restored.structural_context == "ternary-interface"
    assert restored.project == "proj"


def test_empty_new_coordinates_do_not_change_identity():
    a = ProtacContext(target_gene="BRD4", e3_ligase="VHL")
    b = ProtacContext(target_gene="BRD4", e3_ligase="VHL")
    assert a.fingerprint() == b.fingerprint()
    assert a.match_score(b) == 1.0
