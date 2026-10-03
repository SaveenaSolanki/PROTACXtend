from __future__ import annotations

from protacxtend.answer_contracts import (
    AnswerEvidence,
    AnswerState,
    evaluate_answer_contract,
)


def test_supported_answer():
    d = evaluate_answer_contract(AnswerEvidence(
        task_type="binder_retrieval",
        entities={"resolved_target": "BRD4", "exact_compound_identity": "JQ1"},
        evidence={"binding_evidence": "IC50", "source_provenance": "ChEMBL"},
        output_present=True,
        evidence_tier="binding_evidence",
    ))
    assert d.answer_state is AnswerState.SUPPORTED_ANSWER
    assert d.satisfied is True


def test_insufficient_evidence():
    d = evaluate_answer_contract(AnswerEvidence(
        task_type="binder_retrieval",
        entities={"resolved_target": "BRD4"},
        evidence={"source_provenance": "ChEMBL"},
        output_present=True,
        evidence_tier="source_provenance",
    ))
    assert d.answer_state is AnswerState.INSUFFICIENT_EVIDENCE
    assert "exact_compound_identity" in d.missing_entities
    assert "binding_evidence" in d.missing_evidence


def test_ambiguous_target():
    d = evaluate_answer_contract(AnswerEvidence(task_type="target_investigation", ambiguous=True))
    assert d.answer_state is AnswerState.AMBIGUOUS_REQUEST


def test_out_of_domain_prediction():
    d = evaluate_answer_contract(AnswerEvidence(
        task_type="degradation_prediction",
        entities={"valid_candidate": "c1"},
        evidence={"model_output": {"dc50": 100}, "applicability_domain_status": "out_of_domain"},
        output_present=True,
        evidence_tier="computed",
        applicability_status="out_of_domain",
    ))
    assert d.answer_state is AnswerState.OUT_OF_DOMAIN


def test_approximation_forbidden():
    d = evaluate_answer_contract(AnswerEvidence(
        task_type="protac_nomination",
        entities={
            "verified_target": "BRD4",
            "verified_target_binder": "JQ1",
            "verified_e3_ligand": "pomalidomide",
        },
        evidence={
            "verified_exit_vectors": True,
            "valid_assembly": True,
            "applicability_domain_status": "in_domain",
            "mechanistic_evidence_state": "computed",
        },
        output_present=True,
        evidence_tier="curated",
        applicability_status="in_domain",
        approximation=True,
    ))
    assert d.answer_state is AnswerState.INSUFFICIENT_EVIDENCE
    assert any("approximation forbidden" in r for r in d.reasons)


def test_approximation_allowed():
    d = evaluate_answer_contract(AnswerEvidence(
        task_type="docking_question",
        entities={"valid_receptor": "PDB", "valid_ligand": "ligand"},
        evidence={"valid_docking_execution": "score-only"},
        output_present=True,
        evidence_tier="computed",
        applicability_status="in_domain",
        approximation=True,
    ))
    assert d.answer_state is AnswerState.APPROXIMATE_ANSWER
    assert d.satisfied is True


def test_source_unavailable():
    d = evaluate_answer_contract(AnswerEvidence(
        task_type="binder_retrieval",
        source_available=False,
    ))
    assert d.answer_state is AnswerState.TOOL_UNAVAILABLE
    assert any("not scientific negative evidence" in r for r in d.reasons)


def test_conflicting_evidence():
    d = evaluate_answer_contract(AnswerEvidence(task_type="target_investigation", conflicting=True))
    assert d.answer_state is AnswerState.CONFLICTING_EVIDENCE


def test_license_required():
    d = evaluate_answer_contract(AnswerEvidence(task_type="docking_question", license_available=False))
    assert d.answer_state is AnswerState.LICENSE_REQUIRED


def test_design_workflow_abstention():
    d = evaluate_answer_contract(AnswerEvidence(
        task_type="protac_nomination",
        entities={"verified_target": "BRD4", "verified_target_binder": "JQ1"},
        evidence={"valid_assembly": True},
        output_present=False,
        evidence_tier="curated",
        applicability_status="unknown",
    ))
    assert d.answer_state is AnswerState.INSUFFICIENT_EVIDENCE
    assert d.abstention_allowed is True
    assert "verified_e3_ligand" in d.missing_entities
