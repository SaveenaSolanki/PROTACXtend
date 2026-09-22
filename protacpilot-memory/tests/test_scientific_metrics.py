"""Scientific-memory metrics (brief §10)."""

from __future__ import annotations

from benchmarks import metrics as M
from protacpilot_memory.domain.protac import ProtacContext


def _ctx(**kwargs):
    return ProtacContext(**kwargs).to_dict()


def test_conflicting_coordinates_and_compatibility():
    q = _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293")
    same = _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293")
    different_cell = _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="MV4-11")
    assert M.conflicting_coordinates(q, same) == []
    assert M.conflicting_coordinates(q, different_cell) == ["cell"]
    assert M.context_compatibility(q, same) == 1.0
    assert 0.0 < M.context_compatibility(q, different_cell) < 1.0


def test_unknown_context_is_not_contamination():
    q = _ctx(target_gene="BRD4", e3_ligase="VHL")
    rows = [{"query_context": q, "retrieved_contexts": [{}, {"target_gene": "BRD4"}]}]
    # empty context = unknown → excluded; matching context → not contaminated
    assert M.context_contamination_rate(rows) == 0.0


def test_context_contamination_rate_counts_conflicts():
    q = _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293")
    rows = [{
        "query_context": q,
        "retrieved_contexts": [
            _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293"),
            _ctx(target_gene="BRD2", e3_ligase="VHL", cell_line="HEK293"),
        ],
    }]
    assert M.context_contamination_rate(rows) == 0.5


def test_provenance_regex_matches_real_ids_only():
    assert M.has_provenance("supported by EXP-142 and DOI 10.1234/x")
    assert M.has_provenance("docking DOCK-77")
    assert not M.has_provenance("internal id PRED_00000000000004b2")
    assert not M.has_provenance("no provenance here")


def test_provenance_fidelity_over_claim_rows():
    rows = [
        {"capability": "provenance", "retrieved_text": "EXP-142", "requires_provenance": True},
        {"capability": "provenance", "retrieved_text": "nothing", "requires_provenance": True},
        {"capability": "episodic_recall", "retrieved_text": "irrelevant"},
    ]
    assert M.provenance_fidelity(rows) == 0.5


def test_contradiction_resolution_and_longitudinal_metrics():
    rows = [
        {"capability": "contradiction", "contradiction_resolved": True},
        {"capability": "contradiction", "contradiction_resolved": False},
    ]
    assert M.contradiction_resolution_accuracy(rows) == 0.5

    decisions = [
        {"expected_candidate": "rigid", "recommended": "rigid", "previously_failed": ["short_peg"]},
        {"expected_candidate": "rigid", "recommended": "short_peg", "previously_failed": ["short_peg"]},
    ]
    assert M.longitudinal_decision_accuracy(decisions) == 0.5
    assert M.repeated_error_rate(decisions) == 0.5


def test_scientific_metrics_are_bounded():
    rows = [{"query_context": _ctx(target_gene="BRD4"), "retrieved_contexts": [{}]}]
    values = M.scientific_metrics(rows)
    assert set(values) == {
        "repeated_error_rate", "context_contamination_rate", "provenance_fidelity",
        "contradiction_resolution_accuracy", "longitudinal_decision_accuracy",
    }
    assert all(0.0 <= v <= 1.0 for v in values.values())
