"""Ubiquitination geometry scorer for pose-backed PROTAC triage."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from synglue_agent.tools.structural_scoring import score_ternary_pose_for_candidate


@dataclass
class UbiquitinationGeometryResult:
    candidate_id: str
    status: str
    score: float
    confidence: float
    features: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    backend: str = "protacxtend_ubiquitination_geometry_v0.1"

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def score_ubiquitination_geometry(
    candidate_id: str,
    pose_pdb: str | Path,
    smiles: str = "",
    target_chain: str = "",
    e3_chain: str = "",
) -> UbiquitinationGeometryResult:
    """Score lysine/E3 reach from a ternary pose.

    This is a local, dependency-light geometry scorer. If no pose exists, it
    returns INSUFFICIENT EVIDENCE rather than pretending proxy binding is enough.
    """

    structural = score_ternary_pose_for_candidate(candidate_id, pose_pdb, smiles, target_chain, e3_chain)
    features = structural.model_dump()
    warnings = list(structural.warnings)
    if not Path(pose_pdb).exists() or not features.get("nearest_lysine"):
        status = "INSUFFICIENT EVIDENCE"
        next_actions = ["Generate or supply ternary POI-PROTAC-E3 pose with chain assignments."]
    elif features.get("productive_lysine_count", 0) <= 0:
        status = "REVISE"
        next_actions = ["Change linker length/exit vector or sample alternative ternary orientations."]
    elif structural.real_structural_score >= 0.62 and structural.confidence >= 0.65:
        status = "SUPPORTED"
        next_actions = ["Advance to cooperativity and dose-response checks."]
    else:
        status = "REVISE"
        next_actions = ["Improve pose support, lysine accessibility, or interface quality before finalist promotion."]
    return UbiquitinationGeometryResult(
        candidate_id=candidate_id,
        status=status,
        score=round(float(structural.lysine_geometry_score or 0.0), 3),
        confidence=round(float(structural.confidence or 0.0), 3),
        features={
            "nearest_lysine": structural.nearest_lysine,
            "nearest_lysine_distance_A": structural.nearest_lysine_distance_A,
            "accessible_lysine_count": structural.accessible_lysine_count,
            "productive_lysine_count": structural.productive_lysine_count,
            "lysine_geometry_score": structural.lysine_geometry_score,
            "interface_quality_score": structural.interface_quality_score,
            "real_structural_score": structural.real_structural_score,
        },
        warnings=warnings,
        next_actions=next_actions,
    )

