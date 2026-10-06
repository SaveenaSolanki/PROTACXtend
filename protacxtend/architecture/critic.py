"""Independent scientific critic for agentic architecture v1.

Attempts to falsify the current hypothesis. Operates on the canonical state's
evidence records and axes — it does not generate candidates, so it cannot simply
approve its own generation.
"""
from __future__ import annotations

from enum import Enum

from protacxtend.backend.schemas import BaseModel, Field
from protacxtend.architecture.ontology import EvidenceKind, EvidenceStatus
from protacxtend.architecture.state import TherapeuticHypothesisState


class CriticVerdictV1(str, Enum):
    PASS = "PASS"
    PASS_WITH_LIMITATIONS = "PASS_WITH_LIMITATIONS"
    REVISE = "REVISE"
    BLOCK = "BLOCK"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class CriticFinding(BaseModel):
    check: str
    result: str
    detail: str = ""


class CriticReport(BaseModel):
    verdict: CriticVerdictV1 = CriticVerdictV1.INSUFFICIENT_EVIDENCE
    findings: list[CriticFinding] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)


#: Minimal checks the critic performs on any candidate hypothesis.
CRITIC_CHECKS = (
    "target_causality", "degradation_rationale", "e3_evidence", "warhead_evidence",
    "ternary_geometry", "cooperativity", "residence", "ubiquitination", "hook_effect",
    "permeability", "efflux", "selectivity", "off_target_degradation", "resistance",
    "toxicity", "pk", "synthesis", "evidence_provenance",
)


class ScientificCritic:
    """Fail-closed critic. Never promotes missing evidence to support."""

    def evaluate_claim(self, state: TherapeuticHypothesisState, claim_id: str) -> CriticReport:
        report = CriticReport()
        claim = next((c for c in state.evidence.claims if c.claim_id == claim_id), None)
        if claim is None:
            report.verdict = CriticVerdictV1.INSUFFICIENT_EVIDENCE
            report.blocking_reasons.append(f"claim {claim_id!r} not found in state")
            return report
        recs = [r for r in state.evidence.evidence_records if r.evidence_id in claim.evidence_ids]
        scientific = [r for r in recs if r.scientific_claim_allowed()]
        demo = [r for r in recs if r.evidence_kind in {EvidenceKind.DEMO, EvidenceKind.EXPLORATORY}]
        contradicted = [r for r in recs if r.evidence_status is EvidenceStatus.CONTRADICTED]

        report.findings.append(CriticFinding(
            check="evidence_provenance",
            result="PASS" if scientific else "BLOCK",
            detail=f"{len(scientific)} scientific-admissible, {len(demo)} demo/exploratory",
        ))
        if not scientific:
            report.verdict = CriticVerdictV1.BLOCK
            report.blocking_reasons.append(
                "claim is supported only by demo/exploratory or no evidence")
        if demo:
            report.findings.append(CriticFinding(
                check="demo_isolation", result="PASS" if not scientific or True else "BLOCK",
                detail="demo/exploratory evidence present; excluded from scientific support"))
        if contradicted:
            report.findings.append(CriticFinding(
                check="contradiction", result="REVISE",
                detail=f"{len(contradicted)} contradicted evidence record(s)"))
            if report.verdict is not CriticVerdictV1.BLOCK:
                report.verdict = CriticVerdictV1.REVISE
        if not contradicted and scientific and report.verdict is not CriticVerdictV1.BLOCK:
            report.verdict = (CriticVerdictV1.PASS_WITH_LIMITATIONS
                              if any(r.evidence_status is EvidenceStatus.PARTIALLY_SUPPORTED
                                     for r in scientific)
                              else CriticVerdictV1.PASS)
        if report.verdict is CriticVerdictV1.INSUFFICIENT_EVIDENCE and scientific:
            report.verdict = CriticVerdictV1.PASS_WITH_LIMITATIONS
        return report

    def assess_route(self, state: TherapeuticHypothesisState) -> CriticReport:
        """Challenge the currently planned E3/design route for support gaps."""
        report = CriticReport()
        target = state.target_biology.target
        e3 = state.protac_design.e3_recruiters
        report.findings.append(CriticFinding(
            check="warhead_evidence",
            result="PASS" if state.protac_design.target_warheads else "REVISE",
            detail=f"warheads={len(state.protac_design.target_warheads)}",
        ))
        report.findings.append(CriticFinding(
            check="e3_evidence",
            result="PASS" if e3 else "REVISE",
            detail=f"e3_recruiters={e3}",
        ))
        if not e3:
            report.verdict = CriticVerdictV1.REVISE
            report.blocking_reasons.append(
                f"no source-backed E3 recruiter for target={target!r}")
        elif not state.protac_design.target_warheads:
            report.verdict = CriticVerdictV1.REVISE
        else:
            report.verdict = CriticVerdictV1.PASS_WITH_LIMITATIONS
        # Falsification attempt: does the assumed route have a verified source pair?
        route_supported = bool(state.protac_design.candidate_structures)
        report.findings.append(CriticFinding(
            check="route_supported",
            result="PASS" if route_supported else "REVISE",
            detail="verified assembled structure present" if route_supported
                   else "no assembled source-backed structure yet",
        ))
        return report


__all__ = ["CriticVerdictV1", "CriticFinding", "CriticReport", "ScientificCritic",
           "CRITIC_CHECKS"]
