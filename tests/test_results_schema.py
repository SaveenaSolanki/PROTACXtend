"""Tests for the shared scientific result schema (commit 2)."""

import json

import pytest

from protacxtend.results.schema import (
    EVIDENCE_KINDS,
    EvidenceItem,
    Provenance,
    ScientificResult,
    from_dict,
)


def test_schema_fields_present():
    res = ScientificResult(
        workflow="validate",
        summary="SMILES ok",
        status="ok",
        result={"mw": 151.16},
        provenance=[Provenance(tool="protacxtend.tools.molecule_standardizer", source="RDKit")],
    )
    d = res.to_dict()
    assert set(d).issuperset({"status", "workflow", "summary", "result", "evidence",
                              "warnings", "provenance"})
    # optional fields must never be invented when the backend did not provide them
    assert "confidence" not in d
    assert "uncertainty" not in d


def test_confidence_only_when_provided():
    res = ScientificResult(workflow="prediction", summary="x", confidence=0.91)
    assert res.to_dict()["confidence"] == 0.91
    res2 = ScientificResult(workflow="prediction", summary="x")
    assert "confidence" not in res2.to_dict()


def test_evidence_kind_guard():
    with pytest.raises(ValueError):
        EvidenceItem(summary="x", kind="guessed")
    for k in EVIDENCE_KINDS:
        e = EvidenceItem(summary="x", kind=k)
        assert e.to_dict()["kind"] == k


def test_roundtrip():
    res = (
        ScientificResult(workflow="admet", summary="props", status="ok", result={"mw": 100})
        .add_evidence("MW calculated", source="rdkit", kind="calculated")
        .add_warning("hbd alert")
    )
    res2 = from_dict(res.to_dict())
    assert res2.to_dict() == res.to_dict()


def test_measured_must_be_explicit():
    # nothing labelled measured unless the caller passes it
    res = ScientificResult(workflow="benchmark", summary="s")
    res.add_evidence("potency reported in publication", source="ref", kind="retrieved")
    assert res.evidence[0].kind == "retrieved"
