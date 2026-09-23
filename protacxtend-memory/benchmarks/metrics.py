"""Scientific-memory metrics (brief §10).

These complement generic retrieval metrics (Recall@k, MRR, nDCG) with measures
that reflect *scientific* memory behaviour:

* **Repeated Error Rate (RER)** — how often a design/experiment that already
  failed is recommended again. Lower is better.
* **Context Contamination Rate (CCR)** — fraction of retrieved memories whose
  context *conflicts* with the query context on a coordinate both define (e.g.
  a BRD2 memory retrieved for a BRD4 query). Lower is better.
* **Provenance Fidelity (PF)** — fraction of claim-bearing answers that surface a
  verifiable provenance identifier. Higher is better.
* **Contradiction Resolution Accuracy (CRA)** — fraction of contradiction tasks
  where both sides of the conflict are surfaced / correctly resolved.
* **Longitudinal Decision Accuracy (LDA)** — fraction of redesign decisions that
  correctly move away from a failed design. Higher is better.

All functions are pure and operate on plain dict records, so they are testable
in isolation and shared by every benchmark harness.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

from protacpilot_memory.domain.protac.context import FINGERPRINT_FIELDS, ProtacContext

#: Coordinates that represent scientific identity rather than provenance.
_CONFLICT_COORDINATES = tuple(f for f in FINGERPRINT_FIELDS if f != "source_type")

#: A verifiable provenance identifier (experiment / docking id, DOI, PMID, PDB).
#: Deliberately narrow so internal record ids (PRED_…, EP_…) are not mistaken
#: for provenance.
PROVENANCE_RE = re.compile(
    r"(doi[:\s]?10\.\d{3,}|pmid[:\s]?\d{4,}|pdb[:\s]?[0-9a-z]{4}|"
    r"exp[-_ ]?\d+|dock[-_ ]?\d+)",
    re.IGNORECASE,
)


# ── context helpers ──────────────────────────────────────────────────────────
def conflicting_coordinates(
    query_context: dict[str, Any] | None,
    memory_context: dict[str, Any] | None,
) -> list[str]:
    """Coordinates defined by *both* sides with different values."""
    q = ProtacContext.from_dict(query_context or {}).fingerprint_coordinates()
    m = ProtacContext.from_dict(memory_context or {}).fingerprint_coordinates()
    out: list[str] = []
    for name in _CONFLICT_COORDINATES:
        qv, mv = q.get(name, ""), m.get(name, "")
        if qv and mv and qv != mv:
            out.append(name)
    return out


def context_compatibility(
    query_context: dict[str, Any] | None,
    memory_context: dict[str, Any] | None,
) -> float:
    """Fraction of shared *known* coordinates (``ProtacContext.match_score``)."""
    q = ProtacContext.from_dict(query_context or {})
    m = ProtacContext.from_dict(memory_context or {})
    return q.match_score(m)


def has_provenance(text: str | None) -> bool:
    return bool(PROVENANCE_RE.search(text or ""))


# ── scientific metrics ───────────────────────────────────────────────────────
def context_contamination_rate(rows: Sequence[dict[str, Any]]) -> float:
    """Retrieved memories conflicting with the query context, over all retrievals.

    A memory with no context is *unknown*, not contaminated, and is excluded.
    Queries that define no coordinate are skipped (nothing to contaminate).
    """
    retrieved = 0
    contaminated = 0
    for row in rows:
        qctx = row.get("query_context") or {}
        if not any(ProtacContext.from_dict(qctx).fingerprint_coordinates().values()):
            continue
        for mctx in row.get("retrieved_contexts") or []:
            if not mctx:
                continue
            retrieved += 1
            if conflicting_coordinates(qctx, mctx):
                contaminated += 1
    return contaminated / retrieved if retrieved else 0.0


def provenance_fidelity(rows: Sequence[dict[str, Any]]) -> float:
    """Fraction of claim-bearing rows whose retrieved text carries provenance.

    Rows may set ``requires_provenance``; when absent, the ``provenance`` and
    ``recommendation`` capabilities are treated as claim-bearing.
    """
    claim_rows = [
        r for r in rows
        if r.get("requires_provenance")
        or r.get("capability") in ("provenance", "recommendation", "claim", "contradiction")
    ]
    if not claim_rows:
        return 0.0
    return sum(1 for r in claim_rows if has_provenance(r.get("retrieved_text", ""))) / len(claim_rows)


def contradiction_resolution_accuracy(rows: Sequence[dict[str, Any]]) -> float:
    """Fraction of contradiction rows that surfaced / resolved both sides."""
    claim_rows = [r for r in rows if r.get("capability") == "contradiction"]
    if not claim_rows:
        # Fall back to an explicit flag if present on any row.
        claim_rows = [r for r in rows if "contradiction_resolved" in r]
    if not claim_rows:
        return 0.0
    return sum(1 for r in claim_rows if r.get("contradiction_resolved")) / len(claim_rows)


def repeated_error_rate(rows: Sequence[dict[str, Any]]) -> float:
    """Fraction of decisions that re-recommend a previously failed design."""
    decision_rows = [r for r in rows if r.get("previously_failed")]
    if not decision_rows:
        return 0.0
    return sum(
        1 for r in decision_rows
        if r.get("recommended") in set(r.get("previously_failed") or [])
    ) / len(decision_rows)


def longitudinal_decision_accuracy(rows: Sequence[dict[str, Any]]) -> float:
    """Fraction of decisions that select the expected (improved) candidate."""
    decision_rows = [r for r in rows if r.get("expected_candidate")]
    if not decision_rows:
        return 0.0
    return sum(
        1 for r in decision_rows if r.get("recommended") == r.get("expected_candidate")
    ) / len(decision_rows)


def accuracy(rows: Sequence[dict[str, Any]], key: str = "answer_correct") -> float:
    if not rows:
        return 0.0
    return sum(float(bool(r.get(key))) for r in rows) / len(rows)


def scientific_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    """Compute every scientific metric that is defined for these rows."""
    return {
        "repeated_error_rate": repeated_error_rate(rows),
        "context_contamination_rate": context_contamination_rate(rows),
        "provenance_fidelity": provenance_fidelity(rows),
        "contradiction_resolution_accuracy": contradiction_resolution_accuracy(rows),
        "longitudinal_decision_accuracy": longitudinal_decision_accuracy(rows),
    }


def compare_to_full(
    full_rows: Sequence[dict[str, Any]],
    condition_rows: Sequence[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Δ of every scientific metric for a condition relative to the full system."""
    full = scientific_metrics(full_rows)
    cond = scientific_metrics(condition_rows)
    return {
        metric: {"full": full[metric], "value": cond[metric], "delta": cond[metric] - full[metric]}
        for metric in full
    }


__all__ = [
    "PROVENANCE_RE",
    "accuracy",
    "compare_to_full",
    "conflicting_coordinates",
    "context_compatibility",
    "context_contamination_rate",
    "contradiction_resolution_accuracy",
    "has_provenance",
    "longitudinal_decision_accuracy",
    "provenance_fidelity",
    "repeated_error_rate",
    "scientific_metrics",
]
