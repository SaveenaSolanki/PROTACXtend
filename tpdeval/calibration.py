"""Uncertainty calibration (Sections 17 & 21).

Expected Calibration Error, Brier score and reliability bins for stated
confidence vs outcome. Calibration is reported separately, never folded into
"accuracy".
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple


def brier_score(confidences: Sequence[float], outcomes: Sequence[int]) -> float:
    if not confidences:
        return 0.0
    return round(sum((c - o) ** 2 for c, o in zip(confidences, outcomes))
                 / len(confidences), 6)


def expected_calibration_error(confidences: Sequence[float],
                               outcomes: Sequence[int],
                               n_bins: int = 10) -> Dict[str, object]:
    if not confidences:
        return {"ece": None, "bins": []}
    bins: List[List[Tuple[float, int]]] = [[] for _ in range(n_bins)]
    for c, o in zip(confidences, outcomes):
        idx = min(n_bins - 1, max(0, int(c * n_bins)))
        bins[idx].append((c, o))
    n = len(confidences)
    ece = 0.0
    report = []
    for i, b in enumerate(bins):
        if not b:
            report.append({"bin": i, "n": 0, "mean_conf": None, "accuracy": None})
            continue
        mean_conf = sum(c for c, _ in b) / len(b)
        acc = sum(o for _, o in b) / len(b)
        ece += (len(b) / n) * abs(mean_conf - acc)
        report.append({"bin": i, "n": len(b), "mean_conf": round(mean_conf, 4),
                       "accuracy": round(acc, 4),
                       "gap": round(abs(mean_conf - acc), 4)})
    return {"ece": round(ece, 4), "bins": report,
            "brier": brier_score(confidences, outcomes), "n": n}


def overconfidence(confidences: Sequence[float], outcomes: Sequence[int]) -> float:
    """Mean(confidence) - accuracy. Positive = overconfident."""
    if not confidences:
        return 0.0
    return round(sum(confidences) / len(confidences)
                 - sum(outcomes) / len(outcomes), 4)
