"""Scientific-evaluation layer tests (analysis, statistics, figures, report)."""

from __future__ import annotations

import xml.dom.minidom as minidom

import pytest

from evaluation import analysis, figures, report, stats
from evaluation.corpus import build_programmes


# ── statistics ───────────────────────────────────────────────────────────────
def test_effect_sizes_and_ci():
    diffs = [0.1, 0.2, 0.15, 0.3, 0.05]
    d = stats.cohens_d_paired(diffs)
    assert d is not None and d > 0
    assert stats.cliffs_delta_paired(diffs) == 1.0  # all positive
    low, high = stats.bootstrap_ci(diffs, n_boot=2000, seed=1)
    assert low <= high


def test_zero_variance_effect_size_is_none_not_zero():
    # identical non-zero differences -> Cohen's d undefined, not 0.0
    assert stats.cohens_d_paired([1.0, 1.0, 1.0]) is None
    assert stats.cohens_d_paired([0.0, 0.0, 0.0]) == 0.0


def test_mcnemar_exact_and_holm():
    # 8 discordant all in one direction -> p = 2 * 0.5^8
    result = stats.mcnemar_exact([(1, 0)] * 8)
    assert result["n_discordant"] == 8
    assert result["p"] == pytest.approx(2 * 0.5 ** 8)
    adjusted = stats.holm_bonferroni([0.01, 0.04, 0.03, 0.5])
    assert adjusted[0] == pytest.approx(0.04)
    assert all(p is None or p <= 1.0 for p in adjusted)


def _records():
    rows = []
    for i in range(10):
        rows.append({"system": "cognitive_memory", "programme_id": f"P{i}",
                     "decision_correct": 1, "repeated_error": 0, "provenance": 1,
                     "contradiction": True, "contradiction_resolved": 1,
                     "contamination_rate": 0.0, "mrr": 0.5, "ndcg@k": 0.7,
                     "recall@k": 1.0, "latency_ms": 20.0, "tokens": 200,
                     "failure_recalled": 1, "recommends_improved": 1})
        rows.append({"system": "rag_memory", "programme_id": f"P{i}",
                     "decision_correct": 0, "repeated_error": 1, "provenance": 0,
                     "contradiction": True, "contradiction_resolved": 0,
                     "contamination_rate": 0.4, "mrr": 0.5, "ndcg@k": 0.6,
                     "recall@k": 1.0, "latency_ms": 10.0, "tokens": 300,
                     "failure_recalled": 0, "recommends_improved": 0})
    return rows


def test_compare_systems_paired():
    comparisons = stats.compare_systems(_records(), metrics=["decision_correct", "contamination_rate", "mrr"])
    decision = next(c for c in comparisons if c["metric"] == "decision_correct")
    assert decision["b_reference_only"] == 10 and decision["c_baseline_only"] == 0
    assert decision["significant_0.05"] is True
    contamination = next(c for c in comparisons if c["metric"] == "contamination_rate")
    # lower is better, cognitive is lower: favourable delta positive
    assert contamination["mean_delta_favourable"] > 0
    assert contamination["significant_0.05"] is True


# ── corpus / analysis ────────────────────────────────────────────────────────
def test_corpus_is_deterministic_and_wellformed():
    a = build_programmes(n_programmes=6, seed=1)
    b = build_programmes(n_programmes=6, seed=1)
    assert [p.programme_id for p in a] == [p.programme_id for p in b]
    for programme in a:
        assert programme.failure_events, "failure events must be listed"
        assert programme.failure_event in programme.failure_events
        assert programme.redesign_event.endswith("REDESIGN")
        assert programme.decision_query
        if programme.contradiction:
            assert programme.contra_event and programme.contra_cell


def test_analysis_aggregations():
    records = _records()
    aggregate = analysis.system_aggregate(records)
    cognitive = next(r for r in aggregate if r["system"] == "cognitive_memory")
    assert cognitive["decision_correct_mean"] == 1.0
    assert cognitive["contamination_rate_mean"] == 0.0
    systems, metrics, matrix = analysis.normalised_heatmap(aggregate)
    assert len(systems) == 2 and len(metrics) == len(analysis.REPORT_METRICS)
    assert all(0.0 <= value <= 1.0 for row in matrix for value in row)
    failure = analysis.failure_type_matrix(records)
    assert {r["system"] for r in failure} == {"cognitive_memory", "rag_memory"}
    pareto = analysis.pareto_frontier(aggregate)
    assert any(p["on_frontier"] for p in pareto)
    trajectories = analysis.longitudinal_trajectories(records, [f"P{i}" for i in range(10)])
    assert len(trajectories) == 20


def test_bounded_and_ablation_extractors():
    bounded = {
        "conditions": {
            "before_unbounded": {"questions": [{"qid": "Q1", "candidate_total": 100,
                                                "latency_ms": 10.0, "tokens": 20,
                                                "mrr": 0.5, "ndcg@k": 0.5, "recall@k": 1.0}]},
            "after_bounded": {"questions": [{"qid": "Q1", "candidate_kept": 10,
                                             "latency_ms": 2.0, "tokens": 22,
                                             "mrr": 0.5, "ndcg@k": 0.5, "recall@k": 1.0}]},
        }
    }
    rows = analysis.bounded_per_query(bounded)
    assert rows[0]["candidate_reduction"] == 90
    assert rows[0]["speedup"] == pytest.approx(5.0)
    assert rows[0]["ranking_preserved"] == 1


# ── figures / report ─────────────────────────────────────────────────────────
def test_figure_generation_is_square_600dpi(tmp_path):
    from PIL import Image

    records = _records()
    aggregate = analysis.system_aggregate(records)
    systems, metrics, matrix = analysis.normalised_heatmap(aggregate)
    path = figures.fig_metric_heatmap(systems, metrics, matrix, aggregate, tmp_path)
    assert path.exists()
    image = Image.open(path)
    assert image.size[0] == image.size[1]
    assert image.info.get("dpi", (0,))[0] == pytest.approx(600, abs=1)


def test_report_renders_with_minimal_bundle(tmp_path):
    from evaluation import run as R

    bundle = R.collect(n_programmes=4, background_size=0, repeats=1,
                       run_scaling_sweep=False, run_regime_sweep=False)
    markdown = report.render(bundle)
    for section in ("## 1. Hypotheses", "## 3. Metric definitions",
                    "## 6. Paired comparisons", "## 7. Hypothesis verdicts",
                    "## 14. Limitations"):
        assert section in markdown
    assert "computational engram" in markdown.lower()


def test_evaluation_writes_all_artifacts(tmp_path):
    from evaluation import run as R

    paths = R.run(tmp_path, n_programmes=4, background_size=0, repeats=1,
                  run_scaling_sweep=False, run_regime_sweep=False)
    for key in ("report", "per_programme_metrics", "system_aggregate",
                "paired_binary_tests", "paired_continuous_tests", "effect_sizes",
                "contamination_taxonomy", "failure_type_matrix", "fig04", "fig12"):
        assert key in paths and paths[key].exists(), key
