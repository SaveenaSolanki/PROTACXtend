"""Prediction lifecycle and deterministic prediction error."""

from __future__ import annotations

import pytest
from helpers import brd4_vhl, ev
from protacpilot_memory.cognitive.prediction_error import (
    brier_score,
    classification_error,
    compute_prediction_error,
    negative_log_likelihood,
    numeric_error,
    surprise_from_error,
)


def test_numeric_error_is_scale_normalised():
    error, method = numeric_error(0.89, 0.22, scale=1.0)
    assert method == "normalized_absolute_error"
    assert abs(error - 0.67) < 1e-6
    # custom scale changes sensitivity
    error2, _ = numeric_error(100.0, 120.0, scale=200.0)
    assert abs(error2 - 0.1) < 1e-6


def test_brier_and_nll():
    assert brier_score(0.9, 1.0)[0] == pytest.approx(0.01)
    assert brier_score(0.9, 0.0)[0] == pytest.approx(0.81)
    confident_wrong, _ = negative_log_likelihood(0.95, 0.0)
    confident_right, _ = negative_log_likelihood(0.95, 1.0)
    assert confident_wrong > confident_right


def test_classification_error():
    assert classification_error("active", "active")[0] == 0.0
    assert classification_error("active", "inactive")[0] == 1.0
    assert classification_error(None, "inactive")[1] == "missing_class"


def test_compute_prediction_error_dispatch():
    numeric = {"prediction_type": "numeric", "predicted_value": 0.8, "scale": 1.0}
    error, method, _ = compute_prediction_error(numeric, {"observed_value": 0.2})
    assert method == "normalized_absolute_error" and error == pytest.approx(0.6)

    classification = {"prediction_type": "classification", "predicted_class": "yes",
                      "predicted_probability": 0.8}
    error, method, _ = compute_prediction_error(classification, {"observed_class": "no"})
    assert "class_mismatch" in method and error > 0.5

    probabilistic = {"prediction_type": "probabilistic", "predicted_probability": 0.9}
    error, method, _ = compute_prediction_error(probabilistic, {"observed_value": 0.0})
    assert method == "brier_score" and error == pytest.approx(0.81)


def test_surprise_increases_with_error_and_confidence():
    low = surprise_from_error(0.2, confidence=0.5)
    high_error = surprise_from_error(0.9, confidence=0.5)
    high_conf = surprise_from_error(0.9, confidence=1.0)
    assert high_error > low
    assert high_conf > high_error


def test_prediction_stored_before_outcome_and_linked(mem, project):
    prediction_id = mem.predict(
        project_id=project, candidate_id="P17", metric="dmax", predicted_value=0.89,
        confidence=0.78, scale=1.0, context=brd4_vhl(),
    )
    pending = mem.unresolved_predictions(project)
    assert any(p["id"] == prediction_id for p in pending)

    outcome = mem.record_outcome(
        prediction_id, observed_value=0.22, evidence_type="internal_experiment",
        experiment_id="EXP-119", project_id=project,
    )
    assert outcome["prediction_error"] == pytest.approx(0.67, abs=1e-6)
    assert mem.store.get_prediction(prediction_id)["resolved"] == 1
    assert mem.unresolved_predictions(project) == []

    episode_id = outcome["episode"]["episode_id"]
    episode = mem.store.get_episode(episode_id)
    assert episode["prediction_id"] == prediction_id
    assert episode["outcome_id"] == outcome["id"]
    # The high-error outcome is a negative, surprising memory.
    assert episode["is_negative"] == 1
    assert mem.store.require_trace(episode_id)["surprise"] > 0.5


def test_prediction_accuracy_metric(mem, project):
    p1 = mem.predict(project_id=project, metric="dmax", predicted_value=1.0, scale=1.0, context={})
    mem.record_outcome(p1, observed_value=1.0, evidence_type="internal_experiment", project_id=project)
    p2 = mem.predict(project_id=project, metric="dmax", predicted_value=0.0, scale=1.0, context={})
    mem.record_outcome(p2, observed_value=1.0, evidence_type="internal_experiment", project_id=project)
    accuracy = mem.store.prediction_accuracy(project)
    assert 0.4 < accuracy < 0.6  # mean of (1 - 0.0) and (1 - 1.0)
