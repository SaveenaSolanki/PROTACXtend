"""Transparent evidence-confidence model (Master Prompt §22).

Confidence is computed from observable evidence features — never from an LLM's
self-reported certainty. The formula is deliberately simple and documented so it
can be audited and later replaced by a calibrated model.

    confidence = base
               + support_gain      · sat(n_supporting)
               + independence_gain · sat(n_independent_sources)
               + replication_gain  · min(1, replication_count / 3)
               + quality_gain      · mean_quality
               + consistency_gain  · context_consistency
               + accuracy_gain     · prediction_accuracy
               − contradiction_penalty · contradiction_ratio

where sat(n) = 1 − 1/(1 + n). The result is clamped to [0, ceiling].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import ConfidenceConfig
from .util import clamp01


@dataclass
class ConfidenceFeatures:
    n_supporting: int = 0
    n_contradicting: int = 0
    n_independent_sources: int = 0
    replication_count: int = 0
    mean_quality: float = 0.0
    context_consistency: float = 1.0
    prediction_accuracy: float = 0.0
    contradiction_ratio: float | None = None

    def effective_contradiction_ratio(self) -> float:
        if self.contradiction_ratio is not None:
            return clamp01(self.contradiction_ratio)
        total = self.n_supporting + self.n_contradicting
        if total == 0:
            return 0.0
        return self.n_contradicting / total

    def as_dict(self) -> dict[str, float]:
        return {
            "n_supporting": float(self.n_supporting),
            "n_contradicting": float(self.n_contradicting),
            "n_independent_sources": float(self.n_independent_sources),
            "replication_count": float(self.replication_count),
            "mean_quality": float(self.mean_quality),
            "context_consistency": float(self.context_consistency),
            "prediction_accuracy": float(self.prediction_accuracy),
            "contradiction_ratio": float(self.effective_contradiction_ratio()),
        }


@dataclass
class ConfidenceResult:
    confidence: float
    breakdown: dict[str, float] = field(default_factory=dict)


def _sat(n: float) -> float:
    n = max(0.0, float(n))
    return 1.0 - 1.0 / (1.0 + n)


def compute_confidence(
    features: ConfidenceFeatures, config: ConfidenceConfig | None = None
) -> ConfidenceResult:
    cfg = config or ConfidenceConfig()
    support = cfg.support_gain * _sat(features.n_supporting)
    independence = cfg.independence_gain * _sat(features.n_independent_sources)
    replication = cfg.replication_gain * min(1.0, max(0.0, features.replication_count) / 3.0)
    quality = cfg.quality_gain * clamp01(features.mean_quality)
    consistency = cfg.consistency_gain * clamp01(features.context_consistency)
    accuracy = cfg.accuracy_gain * clamp01(features.prediction_accuracy)
    penalty = cfg.contradiction_penalty * clamp01(features.effective_contradiction_ratio())

    raw = cfg.base + support + independence + replication + quality + consistency + accuracy - penalty
    confidence = max(0.0, min(cfg.ceiling, raw))
    breakdown = {
        "base": cfg.base,
        "support": support,
        "independence": independence,
        "replication": replication,
        "quality": quality,
        "consistency": consistency,
        "accuracy": accuracy,
        "contradiction_penalty": -penalty,
        "raw": raw,
        "confidence": confidence,
    }
    return ConfidenceResult(confidence=confidence, breakdown=breakdown)


def confidence_from_bundle(
    bundle: Any,
    *,
    config: ConfidenceConfig | None = None,
    context_consistency: float = 1.0,
    prediction_accuracy: float = 0.0,
    replication_count: int | None = None,
) -> ConfidenceResult:
    """Convenience wrapper around an ``EvidenceBundle``."""
    features = ConfidenceFeatures(
        n_supporting=bundle.n_supporting,
        n_contradicting=bundle.n_contradicting,
        n_independent_sources=bundle.independent_sources(),
        replication_count=(
            bundle.n_supporting if replication_count is None else replication_count
        ),
        mean_quality=bundle.mean_quality,
        context_consistency=context_consistency,
        prediction_accuracy=prediction_accuracy,
        contradiction_ratio=bundle.contradiction_ratio,
    )
    return compute_confidence(features, config)
