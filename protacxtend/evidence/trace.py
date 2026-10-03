"""Capability-specific retrieval and answer-synthesis tracer (GOLD-FREE).

Control-flow contract (2026-09-24 repair):

1. retrieval queries are constructed ONLY from the question (deterministic
   token map) — no hard-coded gold concepts, no ground-truth refs;
2. tool calls use each tool's DECLARED parameter names (``term`` for
   ChEMBL/PubChem, ``query`` for literature tools) — the old caller passed
   ``query``/``q`` for every tool, which silently produced empty ``term``
   (ChEMBL HTTP 400 "No search query provided"; PubChem "Compound name is
   required.");
3. record extraction consumes the tool's structured payloads (title,
   abstract, doi/pmid/pmcid, and chemical structure SMILES where present) —
   never ``sources`` strings used as titles (raw-response repair for
   KNOW-06 / REASON-03);
4. relevance judging matches ONLY question-derived terms against retrieved
   text; gold references and required concepts NEVER enter retrieval,
   filtering, or answer synthesis — they may be recorded as inert metadata
   and consumed only by :mod:`protacxtend.evidence.evaluate` AFTER the run;
5. when live services are unavailable, a versioned, source-attributed local
   evidence snapshot is served and every record is labelled ``snapshot=True``
   with schema version, fetch time and live source URL;
6. answer claims derive exclusively from retrieved records
   (raw record -> passage/chemical structure -> supported claim), and empty
   claims force the caller to abstain rather than fabricate.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from protacxtend.evidence.snapshot import (
    load_snapshot,
    save_snapshot,
    snapshot_status,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "evidence_traces"
OUT.mkdir(parents=True, exist_ok=True)

TRACE_VERSION = "evidence-trace-v2-gold-free"

_STOP = {
    "which", "what", "are", "the", "for", "with", "and", "that", "this", "these",
    "supplied", "context", "documented", "family", "retains", "critical", "motifs",
    "assess", "explain", "mechanistic", "liabilities", "replacing", "via", "whether",
}
_TOOLS = {
    "KNOW": ["search_europe_pmc", "search_pubmed", "search_chembl", "search_pubchem"],
    "REASON": ["search_europe_pmc", "search_pubmed", "retrieve_e3_evidence"],
}
# Tool -> declared parameter names (repairs the empty-term ChEMBL/PubChem 400s)
_TOOL_PARAMS = {
    "search_europe_pmc": {"query"},
    "search_pubmed": {"query"},
    "deep_research": {"query"},
    "search_chembl": {"term"},
    "search_pubchem": {"term"},
    "retrieve_e3_evidence": {"e3"},
    "resolve_target": {"target_name"},
}


def question_tokens(question: str) -> list[str]:
    toks = []
    for t in re.split(r"[^A-Za-z0-9]+", (question or "").lower()):
        if len(t) >= 4 and t not in _STOP:
            toks.append(t)
    return toks


def build_queries(capability: str, question: str) -> list[str]:
    """Deterministic queries derived ONLY from the question (never gold text)."""
    q = (question or "").strip()
    if not q:
        return []
    toks = question_tokens(q)
    queries = [q]
    if len(toks) >= 3:
        queries.append(" ".join(toks[:3]))
    return queries


def _params_for(tool: str, query: str, capability: str) -> dict[str, Any]:
    """Build params using the tool's declared parameter names."""
    keys = _TOOL_PARAMS.get(tool) or {"query"}
    p: dict[str, Any] = {}
    for k in keys:
        if k == "query" or k == "term":
            p[k] = query
        else:
            p[k] = query if k in ("q", "search") else ""
    if tool == "retrieve_e3_evidence":
        # pull the E3 token from the query if any (e.g. VHL); never invent one
        m = re.search(r"\b(VHL|CRBN|DCAF15|DCAF16|KEAP1|RNF114|FEM1B)\b", query, re.I)
        p["e3"] = (m.group(1).upper() if m else "")
    return p


def _normalise_records(tool: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract structured records (title/abstract/identifiers/structures)."""
    rows = (data or {}).get("results") or []
    out: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        rec: dict[str, Any] = {"tool": tool}
        ident = (r.get("id") or r.get("chembl_id") or r.get("cid") or r.get("pmid") or "")
        rec["id"] = ident
        rec["title"] = (r.get("title") or r.get("pref_name") or r.get("name") or str(ident))
        rec["abstract"] = (r.get("abstract") or r.get("abstractText") or "")[:800]
        rec["doi"] = r.get("doi") or ""
        rec["pmid"] = r.get("pmid") or ""
        rec["pmcid"] = r.get("pmcid") or ""
        rec["year"] = r.get("year") or r.get("pubYear") or ""
        rec["journal"] = r.get("journal") or r.get("journalTitle") or ""
        # chemical structure for chemistry tools (ChEMBL/PubChem)
        rec["structure"] = (r.get("structure") or r.get("smiles")
                            or r.get("canonical_smiles") or r.get("canonicalSmiles") or "")
        out.append(rec)
    return out


def _live_or_snapshot(tool: str, query: str, params: dict[str, Any],
                      capability: str, offline: bool) -> tuple[list[dict[str, Any]], str, str, dict]:
    """Call the tool live; on failure/unavailable serve versioned snapshot.

    Returns (records, status, summary, source_meta). status is success |
    error | snapshot. Snapshot records carry explicit snapshot attribution.
    """
    from protacxtend.agentic.registry import execute_tool

    if not offline:
        try:
            res = execute_tool(tool, params)
            if res.status.value == "success":
                recs = _normalise_records(tool, res.data or {})
                src_meta = {
                    "kind": "live_" + tool,
                    "url": (getattr(res, "sources", None) or [""])[0] if getattr(res, "sources", None) else "",
                }
                try:
                    save_snapshot(tool, query, recs, src_meta)
                except Exception:  # pragma: no cover - snapshot never crashes
                    pass
                return recs, "success", res.summary[:200], src_meta
            if res.status.value == "error":
                return [], "error", res.summary[:200], {}
        except Exception as exc:  # noqa: BLE001
            return [], "error", f"{type(exc).__name__}: {str(exc)[:120]}", {}
    # offline or live unavailable -> versioned snapshot (never fabricated)
    snap = load_snapshot(tool, query)
    if snap:
        recs = [dict(r, **snapshot_status(snap)) for r in (snap.get("records") or [])]
        return recs, "snapshot", (f"{tool} -> {len(recs)} records from local evidence snapshot "
                                  f"(schema {snap.get('schema_version')}, fetched {snap.get('fetched_at')})"), snap.get("source") or {}
    return [], "unavailable", f"{tool} unavailable (live off/no snapshot)", {}


def run_retrieval(queries: list[str], capability: str, *, offline: bool = True) -> list[dict]:
    results: list[dict] = []
    for tool in _TOOLS.get(capability, []):
        for i, query in enumerate(queries):
            params = _params_for(tool, query, capability)
            recs, status, summary, src_meta = _live_or_snapshot(tool, query, params, capability, offline)
            results.append({
                "tool": tool, "query": query, "status": status, "summary": summary,
                "top_results": recs[:5],
                "snapshot": bool(recs and recs[0].get("snapshot")),
                "source_meta": src_meta,
            })
    return results


def judge_relevance(results: list[dict], terms: list[str]) -> list[dict]:
    """Relevance against QUESTION-DERIVED terms only (never gold concepts)."""
    terms = [t.lower().strip() for t in (terms or []) if t and t.strip()]
    judged = []
    for r in results:
        text_parts = [r.get("summary") or ""]
        for t in r.get("top_results", []):
            text_parts += [t.get("title") or "", t.get("abstract") or "", t.get("structure") or ""]
        text = " ".join(text_parts).lower()
        hits = [t for t in terms if t in text]
        judged.append({**r, "relevance": "supporting" if hits else "irrelevant",
                       "matched_terms": hits[:6]})
    return judged


def synthesize_claims(judged: list[dict]) -> list[dict]:
    """Claims derive ONLY from retrieved supporting records; empty when none."""
    claims = []
    for r in judged:
        if r.get("relevance") != "supporting":
            continue
        for t in r.get("top_results", [])[:3]:
            passage = (t.get("abstract") or t.get("structure") or t.get("title") or "")[:400]
            ident = t.get("doi") or t.get("pmid") or t.get("id")
            claims.append({
                "claim": f"retrieved: {t.get('title') or t.get('id')}",
                "passage": passage,
                "source_ids": [ident] if ident else [t.get("id", "")],
                "tool": r.get("tool"),
                "snapshot": bool(t.get("snapshot")),
            })
    return claims


def missing_support(terms: list[str], judged: list[dict]) -> list[str]:
    """Question terms with no supporting retrieved record (honest gap list)."""
    terms = [t.lower().strip() for t in (terms or []) if t and t.strip()]
    found = {c for r in judged for c in r.get("matched_terms", [])}
    return [t for t in terms if t not in found]


def trace_query_to_evidence(capability: str, question: str, required: list[str] | None = None,
                            *, task: str, offline: bool = True) -> dict:
    """Run retrieval + synthesis WITHOUT gold access.

    ``required`` is accepted ONLY as inert metadata (recorded verbatim so a
    post-run evaluator can audit against it). It is never used to build
    queries, judge relevance, or synthesize claims.
    """
    terms = question_tokens(question)
    queries = build_queries(capability, question)
    results = run_retrieval(queries, capability, offline=offline)
    judged = judge_relevance(results, terms)
    claims = synthesize_claims(judged)
    missing = missing_support(terms, judged)
    row = {
        "trace_version": TRACE_VERSION,
        "task": task, "capability": capability, "scientific_question": question,
        "query_terms": terms,
        "required_evidence_metadata": list(required or []),   # inert: evaluator-only
        "gold_access_note": ("required_evidence recorded as metadata ONLY; never consumed by "
                             "query building, relevance judging, or answer synthesis"),
        "generated_queries": queries,
        "results": judged,
        "relevance_judgments": [
            {"query": r.get("query"), "tool": r.get("tool"), "status": r.get("status"),
             "relevance": r.get("relevance"), "matched_terms": r.get("matched_terms"),
             "snapshot": r.get("snapshot")} for r in judged],
        "answer_claims": claims,
        "missing_support": missing,
        "synthesis_rule": "claims derived only from retrieved supporting results; abstain when claims empty",
    }
    path = OUT / f"{task}.json"
    with open(path, "w") as f:
        json.dump(row, f, indent=1, default=str)
    row["artifact"] = str(path)
    return row