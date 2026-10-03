"""Canonical run verdict.

A run that did not resolve a target or retrieve target-matched binders must
never present its demonstration candidates as a scientific result. This module
turns the raw workflow state into one explicit verdict plus reasons, so
``run.json`` / ``summary.json`` / ``report.md`` / the TUI all show the same
final line.

Verdicts (strongest first):

* ``SCIENTIFIC RESULT``   target resolved, binders retrieved, candidates
                          carry verified component provenance, engine ran.
* ``DESIGN BRIEF ONLY``   candidates exist but rely on demo/hypothetical
                          components; attachments require chemist review.
* ``ABSTAINED``           no candidates and no fabricated fallback.
* ``HOLLOW RUN``          target unresolved and/or no binders: any scores are
                          demonstration-only and must not be cited.
"""

from __future__ import annotations

from typing import Any

from protacxtend.identity_gate import candidate_passes_identity_gate

VERDICTS = ("SCIENTIFIC RESULT", "DESIGN BRIEF ONLY", "ABSTAINED", "HOLLOW RUN")

#: Substrings that indicate a hollow/demonstration run.
_NO_TARGET = ("no target resolved", "target not resolved", "no target name provided",
              "could not resolve")
_NO_BINDERS = ("no known binders retrieved", "no binders found", "no target-matched warheads",
               "warhead evidence is weak", "included demo warheads")
_ENGINE_FALSE = ("engine_ran=false",)


def _warnings(state: Any) -> list[str]:
    return [str(w) for w in (getattr(state, "warnings", None) or [])]


def _has(warnings: list[str], needles: tuple[str, ...]) -> bool:
    low = [w.lower() for w in warnings]
    return any(n in w for w in low for n in needles)


def compute_verdict(state: Any) -> dict[str, Any]:
    """Return {verdict, reason, scientific_result, reasons, counts}."""
    warnings = _warnings(state)
    errors = [str(e) for e in (getattr(state, "errors", None) or [])]

    target_record = getattr(state, "target_record", None)
    target_name = (getattr(getattr(state, "parsed_objective", None), "target_name", "") or "").strip()
    binders = list(getattr(state, "retrieved_binders", None) or [])
    candidates = list(getattr(state, "valid_candidates", None) or [])
    ranked = list(getattr(state, "ranking_results", None) or [])

    verified = [c for c in candidates if candidate_passes_identity_gate(c)]

    no_target = (target_record is None) or _has(warnings, _NO_TARGET)
    no_binders = (len(binders) == 0) or _has(warnings, _NO_BINDERS)
    engine_false = _has(warnings, _ENGINE_FALSE)
    demo = _has(warnings, _NO_BINDERS)
    # A parsed name that failed to resolve a UniProt record is NOT resolved.
    target_resolved = target_record is not None

    reasons: list[str] = []
    if no_target:
        reasons.append("target not resolved from the request or curated data")
    if no_binders:
        reasons.append("no target-matched binders retrieved (warhead evidence weak or demo-only)")
    if demo:
        reasons.append("demonstration warheads were substituted, not target-matched evidence")
    if engine_false:
        reasons.append("scientific engine provenance reports engine_ran=False")
    if candidates and not verified:
        reasons.append("candidates lack verified component/attachment provenance")
    reasons.extend(f"error: {e}" for e in errors[:3])

    if no_target or no_binders:
        verdict = "HOLLOW RUN"
    elif candidates and verified and not engine_false:
        verdict = "SCIENTIFIC RESULT"
    elif candidates:
        verdict = "DESIGN BRIEF ONLY"
    else:
        verdict = "ABSTAINED"

    return {
        "verdict": verdict,
        "scientific_result": verdict == "SCIENTIFIC RESULT",
        "reason": reasons[0] if reasons else (
            "verified target-matched components with valid candidates"
            if verdict == "SCIENTIFIC RESULT" else "no scientific result produced"),
        "reasons": reasons,
        "counts": {
            "target_resolved": target_resolved,
            "binders_retrieved": len(binders),
            "candidates_valid": len(candidates),
            "candidates_verified": len(verified),
            "candidates_ranked": len(ranked),
        },
        "warnings_total": len(warnings),
    }


def verdict_line(verdict: dict[str, Any]) -> str:
    """One-line final result for the TUI / logs."""
    counts = verdict.get("counts", {})
    return (f"VERDICT: {verdict.get('verdict')} — {verdict.get('reason')} "
            f"[target={'yes' if counts.get('target_resolved') else 'no'} "
            f"binders={counts.get('binders_retrieved', 0)} "
            f"verified={counts.get('candidates_verified', 0)}/"
            f"{counts.get('candidates_valid', 0)}]")


def write_decision_ledger(state: Any, verdict: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministic decision records (the deterministic path wrote none).

    These are honest gate outcomes, not model chain-of-thought.
    """
    counts = verdict["counts"]
    gates = [
        ("resolve_target", "accept" if counts["target_resolved"] else "abstain",
         "target resolved" if counts["target_resolved"] else "no target resolved"),
        ("retrieve_binders", "accept" if counts["binders_retrieved"] else "abstain",
         f"{counts['binders_retrieved']} binder(s) retrieved"),
        ("construct_candidates", "accept" if counts["candidates_valid"] else "abstain",
         f"{counts['candidates_valid']} valid candidate(s)"),
        ("verify_provenance", "accept" if counts["candidates_verified"] else "reject",
         f"{counts['candidates_verified']} candidate(s) with verified components"),
        ("rank", "accept" if counts["candidates_ranked"] else "skip",
         f"{counts['candidates_ranked']} ranked candidate(s)"),
        ("run_verdict", verdict["verdict"].lower().replace(" ", "_"), verdict["reason"]),
    ]
    return [
        {"stage": stage, "decision_type": decision, "reason": reason,
         "verdict": verdict["verdict"]}
        for stage, decision, reason in gates
    ]
