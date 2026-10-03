"""literature_synthesis.py — bounded, citation-backed literature anchors for
PROTAC design runs.

Uses the PROTACXtend deep-research framework (protacxtend.research) which is
LangGraph-orchestrated over Europe PMC/PubMed/OpenAlex/Crossref. Lazy import
keeps the module light; every call is bounded (few sources, no web crawl,
LLM synthesis optional/off by default) so a campaign can fetch literature
anchors without a long tail.

Public API:
    literature_block(query, top_k=4, timeout_s=120) -> dict
        {ok, query, n_evidence, evidence:[...], answer_md, error}
    dimension_queries() -> dict[str, str]      # default query per dimension
    literature_block_markdown(lit) -> str      # markdown "Literature anchors"
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("protacpilot.literature")

LITERATURE_TOOL_VERSION = "literature_synthesis-v1.0"

DIMENSION_QUERIES: Dict[str, str] = {
    "cell_permeability": "PROTAC cell permeability prediction Caco-2 PAMPA beyond rule of five",
    "metabolic_stability": "PROTAC metabolic stability microsomal clearance linker optimization",
    "solubility": "PROTAC solubility prediction bRo5 aqueous solubility linker design",
    "selectivity": "PROTAC selectivity neosubstrate degradation off-target risk CRBN",
    "ternary_complex": "PROTAC ternary complex structure prediction benchmark P4ward PRosettaC AlphaFold3",
    "e3_choice": "PROTAC E3 ligase selection CRBN VHL DCAF15 ligand tissue expression",
    "synthesis_feasibility": "PROTAC retrosynthesis planning buyable precursors ASKCOS",
    "in_vivo_efficacy": "PROTAC in vivo efficacy pharmacokinetics oral bioavailability degraders",
    "safety": "PROTAC toxicity neosubstrate haematological safety hERG DILI degraders",
    "developability": "PROTAC developability physicochemical properties bRo5 drug-like formulation",
}


def dimension_queries() -> Dict[str, str]:
    return dict(DIMENSION_QUERIES)


def _bounded_config():
    """Small, offline-friendly ResearchConfig: scientific APIs only, no crawl,
    no LLM synthesis, one sub-query, no reformulation loops."""
    from protacxtend.research.config import ResearchConfig

    cfg = ResearchConfig.from_env()
    cfg.max_sub_queries = 1
    cfg.max_iterations = 0
    cfg.results_per_source = 4
    cfg.top_k_evidence = 6
    cfg.min_evidence = 1
    cfg.enrich_top_works = 0
    cfg.enrich_ref_cap = 0
    cfg.web_results_per_query = 0
    cfg.crawl_limit = 0
    cfg.searxng_disabled = True
    cfg.crawl4ai_disabled = True
    cfg.trace_persist = False
    cfg.llm_always_off = True
    return cfg


def _run(query: str, top_k: int):
    from protacxtend.research import deep_research_sync

    cfg = _bounded_config()
    cfg.top_k_evidence = max(1, min(int(top_k), 8))
    report = deep_research_sync(query, config=cfg, persist_trace=False)
    return report


def literature_block(query: str, top_k: int = 4, timeout_s: int = 120) -> Dict[str, Any]:
    """Fetch up to `top_k` primary-literature anchors for `query`.

    Returns a dict with ok/n_evidence/evidence/answer_md/error; on timeout or
    network failure ok=False with the error string (the caller must mark the
    literature slot as blocked rather than fabricate references).
    """
    if not query or not query.strip():
        return {"ok": False, "query": query, "n_evidence": 0, "evidence": [],
                "answer_md": "", "error": "empty query"}

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_run, query.strip(), top_k)
            try:
                report = future.result(timeout=timeout_s)
            except concurrent.futures.TimeoutError:
                return {"ok": False, "query": query, "n_evidence": 0, "evidence": [],
                        "answer_md": "", "error": f"timed out after {timeout_s}s (search thread continues in background)"}
    except Exception as exc:  # network/config/import failures
        logger.debug("literature_block failed: %s", exc)
        return {"ok": False, "query": query, "n_evidence": 0, "evidence": [],
                "answer_md": "", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}

    evidence: List[Dict[str, Any]] = []
    for e in getattr(report, "evidence", []) or []:
        evidence.append({
            "title": e.title or "",
            "doi": e.doi or "",
            "pmid": e.pmid or "",
            "pmcid": e.pmcid or "",
            "url": e.url or "",
            "year": e.year,
            "journal": e.journal or "",
            "source": e.source or "api",
            "is_primary": bool(getattr(e, "is_primary", True)),
            "relevance_score": round(float(getattr(e, "relevance_score", 0.0) or 0.0), 3),
            "authority_score": round(float(getattr(e, "authority_score", 0.0) or 0.0), 3),
        })
    evidence = evidence[: top_k]

    answer = getattr(report, "answer_md", "") or ""
    verification = getattr(report, "verification", None)
    claims_ok = None
    unsupported = None
    if verification is not None:
        claims = list(getattr(verification, "claims", []) or [])
        claims_ok = len(claims)
        unsupported = int(getattr(verification, "unsupported_count", 0) or 0)

    return {
        "ok": True,
        "query": query,
        "tool_version": LITERATURE_TOOL_VERSION,
        "n_evidence": len(evidence),
        "evidence": evidence,
        "answer_md": (answer or "")[:2000],
        "claims_checked": claims_ok,
        "unsupported_claims": unsupported,
        "error": "",
    }


def literature_block_markdown(lit: Dict[str, Any]) -> str:
    """Render a literature_block result as a unified 'Literature anchors' block."""
    if not lit.get("ok"):
        return (
            "### Literature anchors\n\n"
            f"`blocked` — {lit.get('error', 'unknown error')}. "
            "No references were fabricated; rerun with network access or a configured SearXNG."
        )
    ev = lit.get("evidence") or []
    if not ev:
        return "### Literature anchors\n\n`no primary literature returned for this query`."
    lines = ["### Literature anchors", "", f"Query: *{lit.get('query')}*", ""]
    for i, e in enumerate(ev, 1):
        ref = e.get("doi") or e.get("pmid") or e.get("url") or "no-identifier"
        year = f", {e['year']}" if e.get("year") else ""
        journal = f" · {e['journal']}" if e.get("journal") else ""
        src = f" · source={e.get('source')}" if e.get("source") else ""
        rel = f" · rel={e.get('relevance_score'):.2f}" if isinstance(e.get("relevance_score"), float) else ""
        lines.append(f"{i}. **{e.get('title')}**{year}{journal} — [{ref}]({ref}){src}{rel}")
    if lit.get("claims_checked") is not None:
        lines.append(
            f"\nClaim verification: {lit['claims_checked']} claims checked, "
            f"{lit.get('unsupported_claims', 0)} unsupported."
        )
    return "\n".join(lines)


def campaign_literature(workflow: Dict[str, Any], candidate_id: Optional[str] = None,
                        top_k: int = 3, timeout_s: int = 120,
                        dimensions: Optional[List[str]] = None) -> Dict[str, Any]:
    """Fetch literature anchors for the candidate's key dimensions.

    Includes a target-specific query when the workflow has a target name.
    """
    target = "PROTAC"
    obj = workflow.get("parsed_objective") or {}
    if isinstance(obj, dict):
        target = obj.get("target") or "PROTAC"
    cands = workflow.get("assembled_candidates") or []
    cid = candidate_id or (cands[0].get("candidate_id") if cands else "?")
    dims = dimensions or ["ternary_complex", "cell_permeability", "in_vivo_efficacy"]

    blocks: Dict[str, Dict[str, Any]] = {}
    for d in dims:
        q = DIMENSION_QUERIES.get(d)
        if not q:
            continue
        q = f"{target}: {q}"
        blocks[d] = literature_block(q, top_k=top_k, timeout_s=timeout_s)
    return {"candidate_id": cid, "target": target, "blocks": blocks}


def campaign_literature_markdown(lit: Dict[str, Any]) -> str:
    lines = [f"## Literature anchors — `{lit.get('candidate_id')}`", ""]
    blocks = lit.get("blocks") or {}
    if not blocks:
        lines.append("*no literature requested*")
        return "\n".join(lines)
    for dim, blk in blocks.items():
        lines.append(f"### {dim.replace('_', ' ').title()}")
        lines.append("")
        lines.append(literature_block_markdown(blk))
        lines.append("")
    return "\n".join(lines)