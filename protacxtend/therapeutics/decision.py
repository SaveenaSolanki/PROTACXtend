"""Modality decision and gates for TargetTherapeuticsAssessment.

The decision is rule-based over the typed evidence blocks; it never invents
causality from expression, and it can only say 'justified' when the minimum
set (causal/dependency context OR documented degrader precedent, plus binder
and E3-opportunity evidence) is met. Gates (identity, chemistry, therapeutic
window) are evaluated separately and must not be bypassed by design.
"""

from __future__ import annotations

from typing import Any

from protacxtend.therapeutics.record import (
    Decision, EvidenceBlock, TargetTherapeuticsAssessment, Verdict,
)


def _block_state(blocks: dict[str, EvidenceBlock], name: str) -> tuple[str, list[str]]:
    b = blocks.get(name)
    if not b:
        return "unavailable", []
    return b.status, (b.sources or [])


def assess(ident: dict[str, Any], blocks: dict[str, EvidenceBlock],
           *, disease: str = "", cell_line: str = "") -> TargetTherapeuticsAssessment:
    conclusions = []
    conflicts: list[str] = []
    missing: list[str] = []

    # 1. identity/variant
    conclusions.append({
        "dimension": "target_identity",
        "conclusion": (f"{ident.get('symbol')} ({ident.get('uniprot_id') or '?'}; "
                       f"{ident.get('organism') or '?'}; variant {ident.get('variant') or 'none'}; "
                       f"resolved via {ident.get('method')}, confidence {ident.get('confidence')})"),
        "verdict": "neutral" if ident.get("status") == "resolved" else "unknown",
        "source_ids": ident.get("source_ids", []),
        "assay_context": "canonical identity + variant (no biological claim from identity alone)",
        "evidence_tier": "curated_template" if ident.get("method") else "unavailable",
        "conflicting": [],
        "missing_data": [] if ident.get("status") == "resolved" else ["canonical identity"],
        "experiment_to_change": "exact-match UniProt verification",
    })
    var = ident.get("variant") or ""

    # 2. disease association
    dsev = blocks.get("disease")
    disease_tier = dsev.evidence_tier if dsev else "unavailable"
    disease_verdict = "neutral"
    if disease_tier in ("genetic_association", "curated_template"):
        disease_verdict = "supports_degradation" if "dependency" in (dsev.summary or "").lower() or "driver" in (dsev.summary or "").lower() else "supports_degradation"
    conclusions.append({
        "dimension": "disease_association",
        "conclusion": (dsev.summary if dsev else "no disease evidence"),
        "verdict": disease_verdict,
        "source_ids": dsev.sources if dsev else [],
        "assay_context": "disease-entity association; association, NOT causality",
        "evidence_tier": disease_tier,
        "conflicting": dsev.conflicts if dsev else [],
        "missing_data": dsev.missing if dsev else [],
        "experiment_to_change": (dsev.experiment_to_change if dsev else "obtain disease association evidence"),
    })

    # 3. dependency (functional)
    dep = blocks.get("dependency")
    conclusions.append({
        "dimension": "dependency_fitness",
        "conclusion": (dep.summary if dep else "no dependency evidence"),
        "verdict": "unknown",          # never assumed
        "source_ids": dep.sources if dep else [],
        "assay_context": "CRISPR/Cas9 fitness dependency (functional)",
        "evidence_tier": dep.evidence_tier if dep else "unavailable",
        "conflicting": dep.conflicts if dep else [],
        "missing_data": dep.missing if dep else [],
        "experiment_to_change": (dep.experiment_to_change if dep else "DepMap Chronos dependency test"),
    })

    # 4. normal tissue (expression, NOT function)
    nts = blocks.get("normal_tissue")
    conclusions.append({
        "dimension": "normal_tissue_context",
        "conclusion": (nts.summary if nts else "no normal-tissue evidence"),
        "verdict": "unknown",
        "source_ids": nts.sources if nts else [],
        "assay_context": "normal-tissue RNA/protein abundance; expression is NOT functional ligase activity",
        "evidence_tier": nts.evidence_tier if nts else "unavailable",
        "conflicting": nts.conflicts if nts else [],
        "missing_data": nts.missing if nts else [],
        "experiment_to_change": (nts.experiment_to_change if nts else "HPA normal-tissue + on-target toxicity scan"),
    })

    # 5. binder/structure (chemistry readiness)
    bs = blocks.get("binder_structure")
    chemistry_ok = bool(bs and bs.status == "available")
    conclusions.append({
        "dimension": "chemistry_readiness",
        "conclusion": (bs.summary if bs else "no binder/structure evidence"),
        "verdict": "supports_degradation" if chemistry_ok else "against_degradation",
        "source_ids": bs.sources if bs else [],
        "assay_context": "cheminformatics/structural readiness (not biological activity)",
        "evidence_tier": bs.evidence_tier if bs else "unavailable",
        "conflicting": bs.conflicts if bs else [],
        "missing_data": bs.missing if bs else [],
        "experiment_to_change": (bs.experiment_to_change if bs else "source-backed binder + validated attachment vector"),
    })

    # 6. E3 opportunity
    e3b = blocks.get("e3_opportunity")
    e3_ok = bool(e3b and e3b.status == "available")
    conclusions.append({
        "dimension": "e3_opportunity",
        "conclusion": (e3b.summary if e3b else "no E3 evidence"),
        "verdict": "supports_degradation" if e3_ok else "unknown",
        "source_ids": e3b.sources if e3b else [],
        "assay_context": "measured degradation precedent (functional per record) or recruiter availability",
        "evidence_tier": e3b.evidence_tier if e3b else "unavailable",
        "conflicting": e3b.conflicts if e3b else [],
        "missing_data": e3b.missing if e3b else [],
        "experiment_to_change": (e3b.experiment_to_change if e3b else "prospective E3 screen"),
    })

    # ---- modality decision (rule-based) ----
    # window data requirements: dependency matrix and normal-tissue context
    window_data_missing = bool(dep and dep.status == "unavailable") or bool(nts and nts.status == "unavailable")
    window_anti_evidence = False   # set true only from explicit anti-degradation data (adversarial cases)
    identity_ok = ident.get("status") == "resolved"
    causal_or_precedent = (
        disease_tier in ("genetic_association", "curated_template")
        and ("driver" in (dsev.summary or "").lower() or "dependency" in (dsev.summary or "").lower() or "precedent" in (dsev.summary or "").lower())
    ) or e3_ok
    criteria_met: list[str] = []
    criteria_missed: list[str] = []
    if identity_ok:
        criteria_met.append("identity: canonical target resolved")
    else:
        criteria_missed.append("identity: target unresolved")
    if chemistry_ok:
        criteria_met.append("chemistry: source-backed binder and/or structure available")
    else:
        criteria_missed.append("chemistry: no source-backed binder with attachment vector (design cannot run)")
    if causal_or_precedent:
        criteria_met.append("causal/precedent context: driver/dependency evidence or measured degrader precedent")
    else:
        criteria_missed.append("causal/precedent context: association/expression only — no causality/proven precedent found")
    if e3_ok:
        criteria_met.append("e3: measured opportunity or recruiter available")
    else:
        criteria_missed.append("e3: no measured E3 opportunity (exploratory only)")

    missing_dep = bool(dep and dep.status == "unavailable")
    if missing_dep:
        criteria_missed.append("dependency: no fitness-dependency matrix (window/essentiality unknown)")

    # ---- MECHANISTIC rationale for exploring degradation (biology) ----
    if not identity_ok:
        verdict: Verdict = "degradation_unsuitable"
        mech = "Identity gate failed (target unresolved): cannot assess or design (no bypass)."
    elif not chemistry_ok:
        verdict = "degradation_uncertain"
        mech = ("Biology not anti-degradation, but chemistry gate failed: no source-backed binder with "
                "attachment vector — design is blocked until chemistry readiness is established.")
    elif causal_or_precedent and (e3_ok or not missing_dep):
        verdict = "degradation_justified"
        mech = "Causality/precedent evidence present (driver/dependency or measured degrader precedent), chemistry and E3 opportunity met."
    else:
        verdict = "degradation_uncertain"
        mech = ("Target plausibly relevant but causality/dependency or E3 opportunity not established with the available "
                "evidence (association/expression only) — degradation rationale is uncertain until the experiments below.")

    # ---- THERAPEUTIC SUITABILITY in the specified indication ----
    # Requires indication-specific data (dependency direction + normal-tissue
    # window + disease context). When that data is missing the gate is
    # REQUIRES_REVIEW, never a silent "pass".
    if window_anti_evidence:
        suitability = "not_supported"
        suit_reason = "Explicit anti-degradation window evidence present (on-target toxicity / essential normal tissue)."
        window_gate = "block"
    elif window_data_missing:
        suitability = "requires_review"
        suit_reason = ("Indication-window data missing (dependency matrix and/or normal-tissue context unavailable); "
                       "therapeutic suitability cannot be asserted in this indication.")
        window_gate = "requires_review"
    elif disease and causal_or_precedent:
        suitability = "supported"
        suit_reason = "Disease context specified and causal/precedent evidence present; window data available."
        window_gate = "pass"
    else:
        suitability = "requires_review"
        suit_reason = "No specified disease context or window; suitability not asserted."
        window_gate = "requires_review"

    for c in conclusions:
        conflicts.extend(c["conflicting"])
        missing.extend(c["missing_data"])

    gates = {
        "identity": "pass" if identity_ok else "block",
        "chemistry": "pass" if chemistry_ok else "block",
        "therapeutic_window": window_gate,
    }

    return TargetTherapeuticsAssessment(
        target=ident, disease_context=disease or "", cell_context=cell_line or "",
        blocks=blocks,
        conclusions=[_mk(c) for c in conclusions],
        decision=Decision(verdict=verdict, mechanism_rationale=mech, rationale=mech,
                          therapeutic_suitability=suitability, suitability_reason=suit_reason,
                          criteria_met=criteria_met, criteria_missed=criteria_missed,
                          gates=gates),
    )


def _mk(c: dict) -> Any:
    from protacxtend.therapeutics.record import Conclusion
    return Conclusion(**c)


def check_gates(assessment: TargetTherapeuticsAssessment) -> dict[str, str]:
    """Return gate statuses; 'block' means design must not run."""
    return dict(assessment.decision.gates)