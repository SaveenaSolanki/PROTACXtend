"""evaluate.py — POST-RUN evaluator (the only place gold is consumed).

This module is strictly downstream of execution: it reads a completed trace
row and — only then — compares against the ground-truth evidence refs and
required concepts. Nothing here can affect tool calls or answers. It also
classifies each case into fixed-denominator buckets:

    answered                 -> at least one retrieval-supported claim produced
    source_unavailable       -> every retrieval tool failed / served nothing live
    no_relevant_evidence     -> tools ran but no question-term-supporting record
    answer_failed            -> the run itself errored

``fixed_denominator_report`` reports every bucket over n_cases (the fixed
denominator), never per-bucket.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def gold_concepts(gt: Optional[Dict[str, Any]], capability: str) -> List[str]:
    """Derive evaluator-only concept terms from the gold evidence sources.

    Called ONLY after the run has finished; never inside retrieval/synthesis.
    """
    concepts: List[str] = []
    for e in (gt or {}).get("evidence_sources") or []:
        ref = str(e.get("ref") or e.get("doi") or e.get("url") or "")
        if ref:
            concepts.append(ref.lower())
    if capability == "KNOW":
        concepts += ["dimethylisoxazole", "bet", "warhead", "ligand", "bromodomain"]
    elif capability == "REASON":
        concepts += ["pharmacophore", "sar", "vhl", "vh032", "amide", "amine", "junction", "liability"]
    return concepts


def evaluate_trace(trace_row: Optional[Dict[str, Any]],
                   gt: Optional[Dict[str, Any]] = None,
                   capability: str = "") -> Dict[str, Any]:
    """Gold-gated audit of a COMPLETED trace; returns an evaluator record."""
    row = trace_row or {}
    concepts = gold_concepts(gt, capability or row.get("capability", ""))
    ids_text = []
    passages = []
    for r in row.get("results") or []:
        for t in r.get("top_results") or []:
            ids_text.append(str(t.get("doi") or t.get("pmid") or t.get("id") or "").lower())
            passages.append(str(t.get("abstract") or t.get("structure") or "")[:400])
    joined_ids = " ".join(ids_text)
    matched = [c for c in concepts if c and c in joined_ids or (c and any(c in p.lower() for p in passages))]
    missing = [c for c in concepts if c not in matched]
    claimed_dois = sorted({s for c in row.get("answer_claims") or [] for s in c.get("source_ids", [])})
    gold_refs = [str(e.get("doi") or e.get("ref") or "").lower()
                 for e in (gt or {}).get("evidence_sources") or [] if e.get("doi") or e.get("ref")]
    gold_hits = [g for g in gold_refs if g and any(g in s.lower() for s in claimed_dois)]
    return {
        "evaluator": "gold-gated (post-run only)",
        "gold_concepts_total": len(concepts),
        "gold_concepts_matched": matched,
        "gold_concepts_missing": missing,
        "gold_evidence_refs_total": len(gold_refs),
        "gold_evidence_refs_cited": gold_hits,
        "gold_evidence_refs_missing": [g for g in gold_refs if g not in gold_hits],
    }


def classify_outcome(trace_row: Optional[Dict[str, Any]], run_error: str = "") -> str:
    """Fixed classification; one bucket per case, never both."""
    row = trace_row or {}
    if run_error:
        return "answer_failed"
    results = row.get("results") or []
    if not results:
        return "answer_failed"
    ok = [r for r in results if r.get("status") in ("success", "snapshot")]
    if not ok:
        return "source_unavailable"
    if row.get("answer_claims"):
        return "answered"
    return "no_relevant_evidence"


def fixed_denominator_report(case_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate over a FIXED denominator: n_cases (never per-bucket)."""
    n = len(case_rows)
    buckets = {k: 0 for k in ("answered", "source_unavailable", "no_relevant_evidence", "answer_failed")}
    per_case = []
    for cr in case_rows:
        outcome = classify_outcome(cr.get("trace"), cr.get("error") or "")
        buckets[outcome] += 1
        per_case.append({"task": cr.get("task_id"), "outcome": outcome,
                         "claims": len((cr.get("trace") or {}).get("answer_claims") or []),
                         "status": cr.get("status")})
    return {
        "denominator": "fixed: n_cases = " + str(n),
        "n_cases": n,
        "buckets": {k: {"count": v, "fraction_of_all": round(v / n, 4) if n else 0.0}
                    for k, v in buckets.items()},
        "per_case": per_case,
        "note": "all fractions use the fixed denominator n_cases; buckets are mutually exclusive",
    }