"""Ablation-framework tests (Sprint V3)."""

from __future__ import annotations

import json

import pytest
from benchmarks import ablation as A


@pytest.fixture(scope="module")
def results():
    return A.run_all_ablations()


def test_all_conditions_present(results):
    keys = set(results["conditions"])
    assert "FULL" in keys
    assert {
        "minus_prediction_error", "minus_consolidation", "minus_reconsolidation",
        "minus_semantic_layer", "minus_evidence_weighting", "minus_context_entity_graph",
        "minus_adaptive_decay", "minus_negative_memory", "minus_prospective_memory",
    } <= keys


def test_every_removal_is_verified(results):
    for key, condition in results["conditions"].items():
        assert condition["ablation"]["component_removed_verified"] is True, (
            key, condition["ablation"]["verification_error"]
        )


def test_comparisons_cover_all_metrics(results):
    for deltas in results["comparisons"].values():
        assert set(deltas) == set(A.COMPARED_METRICS)
        for metric, d in deltas.items():
            assert d["full"] == pytest.approx(results["conditions"]["FULL"]["aggregate"][metric])
            assert d["delta"] == pytest.approx(d["value"] - d["full"])


def test_consolidation_removal_changes_semantic_dependent_metrics(results):
    # removing consolidation must not create semantic memories
    assert results["conditions"]["minus_consolidation"]["stats"]["semantic_memories"] == 0
    assert results["conditions"]["FULL"]["stats"]["semantic_memories"] > 0


def test_writers_produce_artifacts(results, tmp_path):
    paths = A.write_results(results, tmp_path)
    assert paths["json"].exists() and paths["csv"].exists() and paths["md"].exists()
    payload = json.loads(paths["json"].read_text())
    assert "comparisons" in payload and "conditions" in payload
