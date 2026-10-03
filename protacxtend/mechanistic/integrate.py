"""Mechanistic evidence integration (spec §20-23).

- ``build_mechanistic_evidence``: unified M1-M4 evidence block attached to the
  candidate evidence object; every subsection carries status / value /
  evidence_type / source / approximation / confidence / limitations.
- ``rank_dimensions``: keeps M1-M4 scores as separate dimensions; refuses a
  single combined score unless a calibration flag is explicitly set.
- ``nomination_policy_check``: M1-M4 outputs never produce nomination by
  themselves; provenance gates decide.
- evidence-type non-equivalence guard from :mod:`evidence_types`.
"""

from __future__ import annotations

from typing import Any

from protacxtend.mechanistic.evidence_types import assert_no_equivalence

NOMINATION_GATES = (
    "verified_target",
    "verified_binder",
    "verified_e3_ligand",
    "valid_exit_vectors",
    "chemically_valid_assembly",
    "identity_preservation",
    "acceptable_applicability",
    "sufficient_evidence",
)


def _subsection(status: str, value: Any, evidence_type: str, source: str,
                approximation: str, confidence: Any, limitations: list[str]) -> dict[str, Any]:
    return {
        "status": status,
        "value": value,
        "evidence_type": evidence_type,
        "source": source,
        "approximation": approximation,
        "confidence": confidence,
        "limitations": limitations,
    }


def build_mechanistic_evidence(*, m1: dict[str, Any] | None = None,
                               m2: dict[str, Any] | None = None,
                               m3: dict[str, Any] | None = None,
                               m4: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    if m1:
        evidence["hook_dynamics"] = _subsection(
            m1.get("status", "IMPLEMENTED"), m1.get("summaries"), m1.get("evidence_type", "MECHANISTIC_SIMULATION"),
            m1.get("model_source", "m1_hook"), "numerical equilibrium solve; no ML",
            None, m1.get("limitations", []))
    if m2:
        agg = m2.get("aggregate") or {}
        evidence["lysine_accessibility"] = _subsection(
            m2.get("status", "PARTIAL"), {"best_lysine": agg.get("best_lysine"),
                                          "top3": agg.get("top3_lysines"),
                                          "score": agg.get("ubiquitination_geometry_score"),
                                          "e2_reference": agg.get("e2_reference_status")},
            m2.get("evidence_type", "STRUCTURAL/CALCULATED"), "m2_lysine (Shrake-Rupley on structure)",
            "static geometry; no E2~Ub dynamics", agg.get("confidence"), m2.get("limitations", []))
    if m3:
        evidence["cooperativity"] = _subsection(
            m3.get("status", "ALPHA_UNAVAILABLE"), m3.get("structural_cooperativity_proxy"),
            m3.get("evidence_type", "STRUCTURAL_COOPERATIVITY_PROXY"), m3.get("source", "m3_cooperativity"),
            "descriptive structural proxy — never alpha", None, m3.get("limitations", []))
    if m4:
        evidence["degradation_prediction"] = _subsection(
            m4.get("status", "MODEL_PREDICTED"), m4.get("value"), "MODEL_PREDICTED",
            m4.get("model", "UNAVAILABLE"), "ML prediction", m4.get("uncertainty"),
            [f"applicability_domain={m4.get('applicability_domain', 'UNASSESSABLE')}"])

    return {"mechanistic_evidence": evidence}


def rank_dimensions(m1_m4: dict[str, Any], *, calibrated_combined: bool = False) -> dict[str, Any]:
    """Separate ranking dimensions; combined score requires explicit calibration."""
    dims = {}
    me = (m1_m4.get("mechanistic_evidence") or {})
    for key, label in (
        ("ternary_geometry_score", "TERNARY_GEOMETRY"),
        ("lysine_accessibility_score", "LYSINE_ACCESSIBILITY"),
        ("cooperativity_evidence", "COOPERATIVITY"),
        ("hook_risk", "HOOK_RISK"),
        ("degradation_probability", "DEGRADATION_P"),
        ("predicted_DC50", "PREDICTED_DC50"),
        ("predicted_Dmax", "PREDICTED_DMAX"),
        ("uncertainty", "UNCERTAINTY"),
        ("domain_status", "DOMAIN_STATUS"),
    ):
        dims[label] = me.get(key) if key in me else None
    return {
        "dimensions": dims,
        "combined_score_allowed": calibrated_combined,
        "combined_score": None if not calibrated_combined else "needs_calibration",
        "note": "M1-M4 scores are kept separate; no single combined mechanistic score "
                "is used for ranking before calibration.",
        "evidence_non_equivalence_violations": assert_no_equivalence(
            [v.get("evidence_type", "") for v in me.values()] if me else []),
    }


def nomination_policy_check(candidate: dict[str, Any]) -> dict[str, Any]:
    """Nomination eligibility requires provenance gates; M1-M4 are not gates."""
    gate_status = {g: bool(candidate.get(g)) for g in NOMINATION_GATES}
    gates_passed = all(gate_status.values())
    m1_m4_only = bool(candidate.get("mechanistic_evidence")) and not gates_passed
    return {
        "nomination_eligible": gates_passed,
        "gates": gate_status,
        "mechanistic_evidence_alone_cannot_nominate": m1_m4_only,
        "policy": "M1-M4 provide mechanistic evidence; they never replace "
                  "provenance gates (verified target/binder/E3 ligand, exit "
                  "vectors, valid assembly, identity, applicability, evidence).",
    }