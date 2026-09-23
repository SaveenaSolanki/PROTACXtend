"""Deterministic prediction-error / scientific surprise (Master Prompt §10).

Prediction-error implementation depends on prediction type. Absolute difference
is never used universally. This module is pure application logic: an LLM cannot
influence it.
"""

from __future__ import annotations

import math
from typing import Any

from ..util import clamp01

_NUMERIC = "numeric"
_CLASSIFICATION = "classification"
_PROBABILISTIC = "probabilistic"


def _resolve_scale(predicted: float, observed: float, scale: float | None) -> float:
    if scale is not None and scale > 0:
        return float(scale)
    magnitude = max(abs(predicted), abs(observed))
    return magnitude if magnitude > 1e-12 else 1e-12


def numeric_error(predicted: float, observed: float, scale: float | None = None) -> tuple[float, str]:
    if predicted is None or observed is None:
        return 1.0, "missing_value"
    resolved = _resolve_scale(predicted, observed, scale)
    return clamp01(abs(float(observed) - float(predicted)) / resolved), "normalized_absolute_error"


def brier_score(probability: float, outcome: float) -> tuple[float, str]:
    p = min(max(float(probability), 0.0), 1.0)
    y = 1.0 if float(outcome) >= 0.5 else 0.0
    return clamp01((p - y) ** 2), "brier_score"


def negative_log_likelihood(probability: float, outcome: float) -> tuple[float, str]:
    p = min(max(float(probability), 1e-6), 1 - 1e-6)
    y = 1.0 if float(outcome) >= 0.5 else 0.0
    nll = -(y * math.log(p) + (1 - y) * math.log(1 - p))
    # Normalise by the worst-case NLL for a confident wrong answer (log(1e-6)).
    return clamp01(nll / -math.log(1e-6)), "negative_log_likelihood"


def probabilistic_error(
    predicted_probability: float,
    observed_value: float | None = None,
    observed_probability: float | None = None,
) -> tuple[float, str]:
    if observed_probability is not None:
        # Compare two calibrated probabilities with the Brier/absolute form.
        return clamp01(abs(float(predicted_probability) - float(observed_probability))), "probability_calibration_error"
    return brier_score(predicted_probability, 0.0 if observed_value is None else float(observed_value))


def classification_error(predicted_class: str | None, observed_class: str | None) -> tuple[float, str]:
    if predicted_class is None or observed_class is None:
        return 1.0, "missing_class"
    return (0.0 if str(predicted_class) == str(observed_class) else 1.0), "class_mismatch"


def compute_prediction_error(prediction: dict[str, Any], outcome: dict[str, Any]) -> tuple[float, str, dict[str, Any]]:
    """Return ``(error, method, breakdown)`` for a prediction/outcome pair."""
    ptype = (prediction.get("prediction_type") or _NUMERIC).lower()
    breakdown: dict[str, Any] = {"prediction_type": ptype}

    if ptype == _NUMERIC:
        error, method = numeric_error(
            prediction.get("predicted_value"),
            outcome.get("observed_value"),
            prediction.get("scale"),
        )
        breakdown.update({
            "predicted_value": prediction.get("predicted_value"),
            "observed_value": outcome.get("observed_value"),
            "scale": prediction.get("scale"),
        })
        return error, method, breakdown

    if ptype == _CLASSIFICATION:
        error, method = classification_error(
            prediction.get("predicted_class"), outcome.get("observed_class")
        )
        if outcome.get("observed_probability") is not None and prediction.get("predicted_probability") is not None:
            prob_error, prob_method = probabilistic_error(
                prediction.get("predicted_probability"), observed_probability=outcome.get("observed_probability")
            )
            # Average class error and calibration error.
            error = clamp01(0.5 * error + 0.5 * prob_error)
            method = f"{method}+{prob_method}"
        breakdown.update({
            "predicted_class": prediction.get("predicted_class"),
            "observed_class": outcome.get("observed_class"),
        })
        return error, method, breakdown

    if ptype == _PROBABILISTIC:
        error, method = probabilistic_error(
            prediction.get("predicted_probability"),
            observed_value=outcome.get("observed_value"),
            observed_probability=outcome.get("observed_probability"),
        )
        breakdown.update({
            "predicted_probability": prediction.get("predicted_probability"),
            "observed_probability": outcome.get("observed_probability"),
        })
        return error, method, breakdown

    # Unknown type: explicit, conservative fallback.
    error, method = numeric_error(
        prediction.get("predicted_value"), outcome.get("observed_value"), prediction.get("scale")
    )
    breakdown["fallback"] = True
    return error, method + "+fallback", breakdown


def surprise_from_error(error: float, confidence: float = 0.5) -> float:
    """Confidently wrong predictions are the most surprising.

    A high-error, high-confidence prediction yields surprise → 1.0; a
    high-error, low-confidence prediction is far less surprising.
    """
    return clamp01(float(error) * (0.5 + 0.5 * clamp01(confidence)))


def calibration_error(pairs: list[tuple[float, float]]) -> float:
    """Expected calibration error over (probability, outcome) pairs (coarse bins)."""
    if not pairs:
        return 0.0
    bins = 5
    buckets: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for prob, outcome in pairs:
        idx = min(bins - 1, int(min(max(prob, 0.0), 1.0) * bins))
        buckets[idx].append((prob, outcome))
    total = len(pairs)
    ece = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        avg_prob = sum(p for p, _ in bucket) / len(bucket)
        avg_out = sum(o for _, o in bucket) / len(bucket)
        ece += (len(bucket) / total) * abs(avg_prob - avg_out)
    return clamp01(ece)
