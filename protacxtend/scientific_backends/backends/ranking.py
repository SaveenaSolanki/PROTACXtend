"""Local candidate ranking backend (Pareto, no external service)."""

from __future__ import annotations

from typing import Any

from protacxtend.scientific_backends.dispatch import module_available
from protacxtend.scientific_backends.evidence import (
    CapabilityStatus,
    EvidenceTier,
    ScientificResult,
)
from protacxtend.scientific_backends.licenses import OPEN_SOURCE_PERMISSIVE
from protacxtend.scientific_backends.registry import Capability, BackendSpec, register


def candidate_ranking(candidates: Any = None, **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.CANDIDATE_RANKING.value, backend="pareto_nsga2",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["NSGA-II non-dominated sorting"])
    try:
        rows = candidates if isinstance(candidates, list) else []
        if not rows:
            result.status = CapabilityStatus.WARNING.value
            result.summary = "no candidates supplied"
            return result.finish()
        from protacxtend.tools.pareto_ranking import pareto_rank_candidates

        ranked = pareto_rank_candidates(rows)
        result.data = {"ranking": [r.__dict__ if hasattr(r, "__dict__") else dict(r) for r in ranked]}
        result.summary = f"ranked {len(ranked)} candidates"
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"ranking failed: {exc}"
    return result.finish()


RANKING_BACKEND = register(BackendSpec(
    name="pareto_nsga2",
    capabilities=(Capability.CANDIDATE_RANKING,),
    license=OPEN_SOURCE_PERMISSIVE, priority=80,
    description="Pareto/NSGA-II candidate ranking (pure local).",
    citation="NSGA-II", health_check=lambda: __import__(
        "protacxtend.scientific_backends.dispatch", fromlist=["Availability"]
    ).Availability(available=True, detail="local"),
    handlers={Capability.CANDIDATE_RANKING: candidate_ranking},
))
