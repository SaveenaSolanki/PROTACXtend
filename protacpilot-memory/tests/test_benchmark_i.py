"""Benchmark I — longitudinal failure feedback (brief §8)."""

from __future__ import annotations

import json

import pytest
from benchmarks import benchmark_i as I

CONDITIONS = {
    "no_memory", "transcript_rag", "rag_memory", "curated_memory", "cognitive_memory",
}


@pytest.fixture(scope="module")
def results():
    return I.run_all()


def test_all_conditions_and_programs_present(results):
    assert set(results["conditions"]) == CONDITIONS
    assert results["n_programs"] == 4


def test_cognitive_chain_is_complete(results):
    chain = results["conditions"]["cognitive_memory"]["chain"]
    assert chain["available"] is True
    assert chain["predictions"] >= 4
    assert chain["outcomes"] >= 4
    assert chain["outcomes_with_prediction_error"] >= 4
    assert chain["max_prediction_error"] > 0.0
    assert chain["negative_episodes"] >= 8
    assert chain["semantic_memories"] >= 1
    assert chain["chain_complete"] is True


def test_scientific_metrics_are_bounded(results):
    for condition in results["conditions"].values():
        for key in (
            "repeated_error_rate", "context_contamination_rate", "provenance_fidelity",
            "contradiction_resolution_accuracy", "longitudinal_decision_accuracy",
        ):
            value = condition["aggregate"][key]
            assert 0.0 <= value <= 1.0, (condition["backend"], key, value)


def test_cognitive_learns_from_failure(results):
    agg = results["conditions"]["cognitive_memory"]["aggregate"]
    assert agg["decision_accuracy"] == 1.0
    assert agg["failure_recall"] == 1.0
    assert agg["repeated_error_rate"] == 0.0
    assert agg["provenance_fidelity"] > 0.0


def test_naive_lexical_memory_fails_the_decision(results):
    # The generic RAG baselines surface the improved text but not the failure.
    for name in ("transcript_rag", "rag_memory"):
        assert results["conditions"][name]["aggregate"]["longitudinal_decision_accuracy"] == 0.0


def test_writers_produce_artifacts(results, tmp_path):
    paths = I.write_results(results, tmp_path)
    for key in ("json", "csv", "md", "tidy"):
        assert paths[key].exists()
    payload = json.loads(paths["json"].read_text())
    assert set(payload["conditions"]) == CONDITIONS
    assert "Benchmark I" in paths["md"].read_text()
