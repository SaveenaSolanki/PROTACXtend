"""Pose-backed cooperativity potential model for PROTAC ternary complexes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from synglue_agent.tools.structural_scoring import score_ternary_pose_for_candidate


@dataclass
class CooperativityPotentialResult:
    candidate_id: str
    status: str
    predicted_alpha: float
    log_alpha: float
    cooperativity_score: float
    confidence: float
    features: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    backend: str = "protacxtend_cooperativity_potential_v0.1"

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _safe_log_alpha(alpha: float) -> float:
    import math

    return round(math.log10(max(alpha, 1e-6)), 3)


def score_cooperativity_potential(
    candidate_id: str,
    pose_pdb: str | Path,
    smiles: str = "",
    target_chain: str = "",
    e3_chain: str = "",
) -> CooperativityPotentialResult:
    structural = score_ternary_pose_for_candidate(candidate_id, pose_pdb, smiles, target_chain, e3_chain)
    if not Path(pose_pdb).exists():
        return CooperativityPotentialResult(
            candidate_id=candidate_id,
            status="INSUFFICIENT EVIDENCE",
            predicted_alpha=1.0,
            log_alpha=0.0,
            cooperativity_score=0.5,
            confidence=0.0,
            warnings=["No ternary pose supplied; cooperativity cannot be structure-scored."],
        )
    clash_penalty = min(1.0, structural.clash_count / 12.0)
    contact_score = min(1.0, structural.interface_contact_count / 120.0)
    polar_score = min(1.0, structural.polar_contact_count / 18.0)
    strain = structural.linker_strain_score
    frustration_proxy = max(0.0, clash_penalty + max(0.0, 0.35 - polar_score) * 0.5)
    coop_score = max(
        0.0,
        min(
            1.0,
            0.42 * structural.interface_quality_score
            + 0.20 * contact_score
            + 0.16 * polar_score
            + 0.14 * strain
            + 0.08 * structural.lysine_geometry_score
            - 0.30 * frustration_proxy,
        ),
    )
    predicted_alpha = round(10 ** ((coop_score - 0.5) * 1.4), 3)
    status = "SUPPORTED" if coop_score >= 0.64 and structural.confidence >= 0.55 else "REVISE"
    warnings = list(structural.warnings)
    if frustration_proxy >= 0.35:
        warnings.append("Interface frustration/clash proxy is high; measured ternary Kd/alpha is needed.")
    return CooperativityPotentialResult(
        candidate_id=candidate_id,
        status=status,
        predicted_alpha=predicted_alpha,
        log_alpha=_safe_log_alpha(predicted_alpha),
        cooperativity_score=round(coop_score, 3),
        confidence=round(min(structural.confidence, 0.78), 3),
        features={
            "interface_quality_score": structural.interface_quality_score,
            "interface_contact_count": structural.interface_contact_count,
            "polar_contact_count": structural.polar_contact_count,
            "clash_count": structural.clash_count,
            "frustration_proxy": round(frustration_proxy, 3),
            "linker_strain_score": structural.linker_strain_score,
            "lysine_geometry_score": structural.lysine_geometry_score,
        },
        warnings=warnings,
    )

