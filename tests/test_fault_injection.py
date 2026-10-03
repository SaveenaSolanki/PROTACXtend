"""Integration fault-injection tests for the live retrieval path."""

from __future__ import annotations

import pytest

from protacxtend.runtime.fault_injection import all_scenarios, run_fault_scenario


@pytest.mark.parametrize("scenario", all_scenarios(), ids=lambda s: s.name)
def test_fault_is_detected_and_never_hallucinated(scenario):
    result = run_fault_scenario(scenario)
    assert result["detected"] is True, result
    assert result["hallucinated_continuation"] is False, result


def test_recovery_after_faults():
    result = run_fault_scenario(all_scenarios()[1])  # timeout
    assert result["recovered"] is True


def test_fallback_recovery_scenario():
    result = run_fault_scenario(next(s for s in all_scenarios() if s.name == "fallback_recovery"))
    assert result["detected"] is True
    assert result["recovered"] is True


def test_abstention_when_no_fallback_exists():
    result = run_fault_scenario(next(s for s in all_scenarios() if s.name == "abstention_no_fallback"))
    assert result["abstained"] is True
    assert result["hallucinated_continuation"] is False


def test_bindingdb_rest_parses_both_documented_shapes():
    from protacxtend.tools.bindingdb_lookup import (
        build_bindingdb_uniprot_url,
        parse_bindingdb_rest_json,
    )

    singular = {"getLindsByUniprotResponse": {"bdb.affinities": [
        {"bdb.monomerid": 1, "bdb.smile": "CCO", "bdb.affinity_type": "IC50", "bdb.affinity": "20"},
    ]}}
    plural = {"getLindsByUniprotsResponse": {"affinities": [
        {"monomerid": "2", "smile": "CCC", "affinity_type": "Ki", "affinity": "5", "doi": "x"},
    ]}}
    assert len(parse_bindingdb_rest_json(singular)) == 1
    assert len(parse_bindingdb_rest_json(plural)) == 1
    assert parse_bindingdb_rest_json("") == []
    assert parse_bindingdb_rest_json({"getLindsByUniprotResponse": {"bdb.affinities": []}}) == []
    assert "response=application/json" in build_bindingdb_uniprot_url("O60885")


def test_bindingdb_rest_requires_no_api_key():
    from protacxtend.agents.binder_agent import TargetBinderRetrievalAgent

    assert TargetBinderRetrievalAgent()._bindingdb_needs_key() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
