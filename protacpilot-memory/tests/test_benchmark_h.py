"""Four-way Benchmark H tests (Sprint V2).

These run the real harness on the synthetic project and assert structural
properties, not fabricated performance numbers.
"""

from __future__ import annotations

import json

import pytest
from benchmarks import benchmark_h as H

CONDITIONS = {"no_memory", "transcript_rag", "rag_memory", "curated_memory", "cognitive_memory"}


@pytest.fixture(scope="module")
def results():
    return H.run_all()


def test_all_five_conditions_present(results):
    assert set(results["conditions"]) == CONDITIONS
    assert results["n_questions"] == 8
    assert results["n_events"] == 10 + len(H.background_events())


def test_no_memory_is_the_control(results):
    agg = results["conditions"]["no_memory"]["aggregate"]
    assert agg["recall@k"] == 0.0
    assert agg["factual_accuracy"] == 0.0
    assert agg["mean_tokens_injected"] == 0.0


def test_metrics_are_bounded(results):
    bounded = ["recall@k", "mrr", "ndcg@k", "factual_accuracy", "stale_belief_rate",
               "context_accuracy", "contradiction_accuracy", "provenance_accuracy"]
    for name, condition in results["conditions"].items():
        for key in bounded:
            value = condition["aggregate"][key]
            assert 0.0 <= value <= 1.0, f"{name}.{key}={value}"
        assert condition["aggregate"]["mean_retrieval_latency_ms"] >= 0.0
        assert condition["aggregate"]["mean_assembly_latency_ms"] >= 0.0


def test_lexical_baselines_beat_no_memory(results):
    for name in ("transcript_rag", "rag_memory", "curated_memory"):
        assert results["conditions"][name]["aggregate"]["recall@k"] > 0.0


def test_cognitive_surfaces_the_contradicting_context(results):
    rows = results["conditions"]["cognitive_memory"]["questions"]
    q4 = next(q for q in rows if q["qid"] == "Q4")
    assert q4["answer_correct"] == 1.0
    # the MV4-11 contradiction must be in the retrieved sources
    flat = [src for item in q4["retrieved_sources"] for src in item]
    assert "H-S5-MV411" in flat


def test_cognitive_recovers_the_experimental_outcome(results):
    rows = results["conditions"]["cognitive_memory"]["questions"]
    q5 = next(q for q in rows if q["qid"] == "Q5")
    assert q5["answer_correct"] == 1.0
    assert q5["mrr"] > 0.0


def test_outputs_are_written(results, tmp_path):
    paths = H.write_results(results, tmp_path)
    assert paths["json"].exists() and paths["csv"].exists() and paths["md"].exists()
    payload = json.loads(paths["json"].read_text())
    assert set(payload["conditions"]) == CONDITIONS
    assert "Benchmark H" in paths["md"].read_text()


def test_scientific_metrics_present(results):
    for condition in results["conditions"].values():
        agg = condition["aggregate"]
        for key in (
            "context_contamination_rate",
            "provenance_fidelity",
            "contradiction_resolution_accuracy",
            "repeated_error_rate",
            "longitudinal_decision_accuracy",
        ):
            assert key in agg
            assert 0.0 <= agg[key] <= 1.0
