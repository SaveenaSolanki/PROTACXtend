"""Scaled runs of the Cognitive Memory Benchmark (Master Prompt §46)."""

from __future__ import annotations

from benchmarks import benchmark as B


def test_benchmark_a_exact_recall():
    result = B.benchmark_a_exact_recall()
    assert result.metrics["recall@5"] == 1.0
    assert result.metrics["mrr"] > 0.0


def test_benchmark_b_context_discrimination():
    result = B.benchmark_b_context_discrimination()
    assert result.metrics["top1_correct"] == 1.0
    assert result.metrics["distractor_above"] == 0.0


def test_benchmark_c_contradiction_detection():
    result = B.benchmark_c_contradiction_detection()
    assert result.metrics["accuracy"] == 1.0


def test_benchmark_d_consolidation():
    result = B.benchmark_d_consolidation()
    assert result.metrics["created"] == 1.0
    assert result.metrics["scope_aware_claim"] == 1.0
    assert result.metrics["provenance_linked"] == 1.0


def test_benchmark_e_reconsolidation():
    result = B.benchmark_e_reconsolidation()
    assert result.metrics["not_append_only"] == 1.0


def test_benchmark_f_memory_pollution():
    result = B.benchmark_f_memory_pollution(n_low_value=200, n_important=20)
    assert result.metrics["important_in_top20"] >= 0.5
    assert result.metrics["retrieval_latency_ms"] >= 0.0


def test_benchmark_g_failure_learning():
    result = B.benchmark_g_failure_learning()
    assert result.metrics["negative_in_top3"] == 1.0


def test_benchmark_h_longitudinal():
    result = B.benchmark_h_longitudinal()
    assert result.metrics["recalls_semantic_knowledge"] in (0.0, 1.0)
    assert result.metrics["recalls_failure"] in (0.0, 1.0)


def test_all_benchmarks_run():
    results = B.run_all(pollution_events=50)
    assert set(results) == set(B.BENCHMARKS)
