"""LangGraph research state machine — routing, parallel search, retries and
iterative reformulation.

Pipeline (retrieval priority):
  analyze -> search scientific APIs (Europe PMC/PubMed/OpenAlex) -> merge
  -> citation-graph enrichment (OpenAlex/Crossref) -> free web search (SearXNG)
  -> full-text crawling (Crawl4AI/clean extractor) -> dedup/score/rerank
  -> sufficiency gate (loop w/ reformulation while budget remains)
  -> synthesis (cheap LLM, strong reserved) -> claim verification -> report.

Every node is async, isolated, logged and failure-tolerant: an unavailable
source records an error and the graph continues (no fabricated results).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from synglue_agent.research.config import ResearchConfig
from synglue_agent.research.reasoning import plan_query, synthesize
from synglue_agent.research.retrieval import (
    dedup_and_merge,
    evidence_sufficiency,
    reformulate_query,
    score_and_rank,
    verify_claims,
)
from synglue_agent.research.schemas import EvidenceItem, SearchPlan, StepLog
from synglue_agent.research.sources import (
    GRAPH_SOURCES,
    SCIENTIFIC_FIRST,
    WEB_SOURCES,
    make_clients,
)

logger = logging.getLogger("protacpilot.research.graph")


class ResearchState(TypedDict, total=False):
    query: str
    active_query: str
    iteration: int
    max_iterations: int
    plan: SearchPlan
    raw_records: list[dict[str, Any]]
    evidence: list[EvidenceItem]
    crawled_urls: list[str]
    crawl_count: int
    sources_searched: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    errors: list[str]
    reformulations: list[str]
    rerank_meta: dict[str, Any]
    sufficiency: dict[str, Any]
    answer_md: str
    used_strong_llm: bool
    llm_usage: dict[str, Any]
    verification: dict[str, Any]
    warnings: list[str]
    config_snapshot: dict[str, Any]
    final_report: dict[str, Any] | None


def _now_ms(t0: float) -> float:
    return round((time.monotonic() - t0) * 1000, 1)


def _log_step(state: ResearchState, node: str, detail: str, items: int = 0,
              error: str = "", t0: float | None = None) -> list[dict[str, Any]]:
    step = StepLog(node=node, detail=detail, items=items, error=error)
    if t0 is not None:
        step.duration_ms = _now_ms(t0)
    return [*state.get("steps", []), step.model_dump()]


def _merge_now(state: ResearchState) -> list[EvidenceItem]:
    """Merge raw records on top of current (possibly enriched/crawled) evidence
    so in-place enrichments (Crossref flags, fulltext, journal fills) survive."""
    items, _ = dedup_and_merge(state.get("raw_records", []),
                               existing=state.get("evidence", []))
    return items


# ── node: analyze / plan ────────────────────────────────────────────────────

async def _node_analyze(state: ResearchState, cfg: ResearchConfig,
                        clients: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    query = state["query"]
    web_available = "searxng" in clients
    plan, used_llm, err = await asyncio.to_thread(plan_query, query, cfg, web_available)
    if err and used_llm is False:
        logger.debug("planner fallback: %s", err)
    sub = plan.sub_queries or [query]
    detail = (f"plan: {len(sub)} sub-query/ies, domain={plan.domain}, "
              f"complexity={plan.complexity}, web={'yes' if plan.include_web else 'no'}"
              + (f", llm={used_llm}" if used_llm else ", llm=fallback"))
    return {
        "active_query": query,
        "iteration": 0,
        "plan": plan,
        "steps": _log_step(state, "analyze", detail, t0=t0),
    }


# ── node: scientific API search ─────────────────────────────────────────────

async def _run_one_search(client: Any, source: str, subq: str, cfg: ResearchConfig,
                          ) -> tuple[str, str, list[dict[str, Any]]]:
    """search one source+subquery; returns (source, subq, records)."""
    try:
        if source in ("searxng",):
            records, err = await asyncio.wait_for(
                client.search(subq, n_results=cfg.web_results_per_query),
                timeout=cfg.request_timeout_s * 4)
        else:
            records, err = await asyncio.wait_for(
                client.search(subq, page_size=cfg.results_per_source),
                timeout=cfg.request_timeout_s * 4)
        if err:
            raise RuntimeError(err)
        return source, subq, list(records or [])
    except asyncio.TimeoutError:
        return source, subq, []
    except Exception:
        return source, subq, []


async def _node_search_scientific(state: ResearchState, cfg: ResearchConfig,
                                  clients: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    plan: SearchPlan = state.get("plan") or SearchPlan(sub_queries=[state["active_query"]])
    subs = plan.sub_queries or [state["active_query"]]
    records: list[dict[str, Any]] = []
    src_hits: dict[str, int] = {}
    src_notes: dict[str, str] = {}
    tasks: list[Callable] = []
    for source in SCIENTIFIC_FIRST:
        client = clients.get(source)
        if client is None:
            src_notes[source] = "client unavailable"
            continue
        for subq in subs:
            tasks.append(_run_one_search(client, source, subq, cfg))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, BaseException):
                continue
            source, subq, recs = res  # type: ignore[misc]
            records.extend(recs)
            src_hits[source] = src_hits.get(source, 0) + len(recs)
            src_notes.setdefault(source, "ok" if recs else "no hits")

    merged, merge_log = dedup_and_merge([*state.get("raw_records", []), *records])
    detail = (f"scientific search over {list(src_hits) or list(src_notes)} "
              f"({len(subs)} sub-queries) -> {len(records)} raw, {len(merged)} unique")
    sources = _update_sources(state, SCIENTIFIC_FIRST, src_hits, src_notes)
    return {
        "raw_records": [*state.get("raw_records", []), *records],
        "evidence": merged,
        "sources_searched": sources,
        "steps": _log_step(state, "search_scientific", detail, items=len(records), t0=t0),
    }


def _update_sources(state: ResearchState, names: list[str], hits: dict[str, int],
                    notes: dict[str, str]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {s["name"]: s for s in state.get("sources_searched", [])}
    for name in names:
        n = hits.get(name, 0)
        err = "" if n or notes.get(name, "ok") == "ok" else notes.get(name, "")
        if notes.get(name) not in (None, "ok", "no hits") and not err:
            err = notes[name]
        out[name] = {
            "name": name,
            "label": _SOURCE_LABELS.get(name, name),
            "queried": True,
            "available": not err,          # adapter worked (may still be 0 hits)
            "hits": n,
            "error": err[:200],
            "note": (notes.get(name, "") or "")[:200],
        }
    return list(out.values())


_SOURCE_LABELS = {
    "europepmc": "Europe PMC (EBI)",
    "pubmed": "PubMed / NCBI E-utilities",
    "openalex": "OpenAlex",
    "crossref": "Crossref",
    "searxng": "SearXNG (self-hosted)",
    "crawl": "Web full-text (Crawl4AI / clean extractor)",
}


# ── node: citation-graph enrichment (OpenAlex related/cited-by/refs + Crossref) ──

async def _node_enrich(state: ResearchState, cfg: ResearchConfig,
                       clients: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    items = _merge_now(state)
    if not items:
        return {"steps": _log_step(state, "enrich_graph", "no evidence to enrich", t0=t0)}

    def _sort_key(e: EvidenceItem):
        return ((e.cited_by_count or 0), len(e.abstract or ""), e.is_primary)

    tops = sorted(items, key=_sort_key, reverse=True)[: cfg.enrich_top_works]
    openalex = clients.get("openalex")
    crossref = clients.get("crossref")
    new_raw: list[dict[str, Any]] = []
    caps: dict[str, int] = {}
    task_count = 0

    async def enrich_one(item: EvidenceItem) -> None:
        nonlocal task_count
        oid = (item.provenance.get("extra") or {}).get("openalex_id") if openalex else ""
        if openalex and oid:
            try:
                cited = await asyncio.wait_for(openalex.cited_by(oid, limit=4), timeout=30)
                for rec in cited:
                    if caps.get("cited", 0) >= 8:
                        break
                    caps["cited"] = caps.get("cited", 0) + 1
                    new_raw.append(rec)
            except Exception as exc:
                logger.debug("cited_by enrich failed: %s", exc)
            try:
                ref_tasks = []
                for ref_id in item.references[: cfg.enrich_ref_cap]:
                    ref_tasks.append(asyncio.wait_for(openalex.work_by_openalex_id(str(ref_id)), timeout=25))
                if ref_tasks:
                    refs = await asyncio.gather(*ref_tasks, return_exceptions=True)
                    for rec in refs:
                        if isinstance(rec, BaseException) or not rec:
                            continue
                        if caps.get("refs", 0) >= 10:
                            break
                        caps["refs"] = caps.get("refs", 0) + 1
                        new_raw.append(rec)
            except Exception as exc:
                logger.debug("references enrich failed: %s", exc)

        if crossref and item.doi:
            try:
                rec = await asyncio.wait_for(crossref.work_by_doi(item.doi), timeout=30)
                if rec:
                    # metadata validation: record DOI validation + title consistency
                    extra = dict(item.provenance.get("extra") or {})
                    extra["doi_validated"] = True
                    cr_title = str(rec["title"] or "")
                    extra["crossref_title"] = cr_title[:250]
                    from synglue_agent.research.retrieval import normalize_title
                    if cr_title and normalize_title(item.title) and \
                            normalize_title(cr_title) != normalize_title(item.title):
                        extra["crossref_title_conflict"] = True
                    item.provenance["extra"] = extra
                    if not item.journal:
                        item.journal = rec["journal"]
                    if item.cited_by_count is None:
                        item.cited_by_count = rec["cited_by_count"]
                    if not item.references:
                        item.references = rec["references"][:10]
            except Exception:
                pass

    for item in tops:
        if task_count >= cfg.enrich_top_works * 2:
            break
        task_count += 1
        try:
            await asyncio.wait_for(enrich_one(item), timeout=45)
        except Exception as exc:
            logger.debug("enrich item failed: %s", exc)

    # DOI<->title validation across the widest useful set (top items by cited
    # count / abstract availability) so reference-table entries are Crossref-
    # checked rather than registry-DOI-only.
    validate_items = sorted(items, key=_sort_key, reverse=True)[: max(cfg.enrich_top_works, 12)]
    crossref_checked = 0
    if crossref:
        for item in validate_items:
            if not item.doi:
                continue
            try:
                rec = await asyncio.wait_for(crossref.work_by_doi(item.doi), timeout=25)
            except Exception:
                continue
            if not rec:
                continue
            crossref_checked += 1
            extra = dict(item.provenance.get("extra") or {})
            extra["doi_validated"] = True
            cr_title = str(rec["title"] or "")
            extra["crossref_title"] = cr_title[:250]
            from synglue_agent.research.retrieval import normalize_title as _nt
            if cr_title and _nt(item.title) and _nt(cr_title) != _nt(item.title):
                extra["crossref_title_conflict"] = True
            item.provenance["extra"] = extra
            if not item.journal:
                item.journal = rec["journal"]
            if item.cited_by_count is None:
                item.cited_by_count = rec["cited_by_count"]

    detail = (f"enriched {len(tops)} top works (+{len(new_raw)} citation-graph records, "
              f"crossref DOI validation on {crossref_checked} DOIs)")
    steps = _log_step(state, "enrich_graph", detail, items=len(new_raw), t0=t0)
    return {"raw_records": [*state.get("raw_records", []), *new_raw],
            "evidence": items, "steps": steps}


# ── node: free web search (SearXNG) ─────────────────────────────────────────

async def _node_web_search(state: ResearchState, cfg: ResearchConfig,
                           clients: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    plan: SearchPlan = state.get("plan") or SearchPlan(sub_queries=[state["active_query"]])
    searxng = clients.get("searxng")
    records: list[dict[str, Any]] = []
    src_hits: dict[str, int] = {}
    src_notes: dict[str, str] = {}

    if searxng is None or not (plan.include_web or plan.domain == "general"):
        src_notes["searxng"] = ("skipped (web not in plan)" if plan.domain != "general"
                                else "searxng client unavailable (set SEARXNG_URL)")
    else:
        subs = plan.sub_queries or [state["active_query"]]
        tasks = [asyncio.wait_for(searxng.search(subq, n_results=cfg.web_results_per_query),
                                  timeout=cfg.request_timeout_s * 4) for subq in subs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, BaseException):
                continue
            recs, err = res
            records.extend(recs)
            if err and not src_notes.get("searxng"):
                src_notes["searxng"] = err[:200]
        src_hits["searxng"] = len(records)
        src_notes.setdefault("searxng", "ok" if records else "no hits")

    sources = _update_sources(state, WEB_SOURCES, src_hits, src_notes)
    steps = _log_step(state, "web_search", f"searxng -> {len(records)} records",
                      items=len(records), t0=t0)
    return {"raw_records": [*state.get("raw_records", []), *records],
            "sources_searched": sources, "steps": steps}


# ── node: full-text crawl ───────────────────────────────────────────────────

async def _node_crawl(state: ResearchState, cfg: ResearchConfig,
                      clients: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    crawler = clients.get("crawl")
    if crawler is None:
        return {"steps": _log_step(state, "crawl_fulltext", "crawler unavailable", t0=t0)}
    items = _merge_now(state)
    if not items:
        return {"steps": _log_step(state, "crawl_fulltext", "no evidence to crawl", t0=t0)}

    crawled = set(state.get("crawled_urls", []))
    budget = max(0, cfg.crawl_limit - state.get("crawl_count", 0))
    candidates = [
        e for e in sorted(items, key=lambda x: (x.is_primary, bool(x.abstract)), reverse=True)
        if e.url and e.url not in crawled and e.source in ("searxng", "openalex", "europepmc", "pubmed")
        and (not e.fulltext) and (not e.abstract or e.is_open_access)
    ][:budget]

    fetched: list[str] = []
    for e in candidates:
        try:
            page = await asyncio.wait_for(crawler.crawl(e.url), timeout=40)
        except Exception as exc:
            logger.debug("crawl failed for %s: %s", e.url, exc)
            continue
        text = (page.get("text") or "").strip()
        if len(text) < 200:
            continue
        e.fulltext = text[: cfg.max_fulltext_chars]
        e.provenance["crawl_engine"] = page.get("engine", "unknown")
        crawled.add(e.url)
        fetched.append(e.url)

    steps = _log_step(state, "crawl_fulltext",
                      f"crawled {len(fetched)} full texts (engine "
                      f"{clients['crawl'].__class__.__name__})",
                      items=len(fetched), t0=t0)
    return {"evidence": items, "crawled_urls": sorted(crawled),
            "crawl_count": state.get("crawl_count", 0) + len(fetched), "steps": steps}


# ── node: dedup + score + rerank ────────────────────────────────────────────

async def _node_dedup_score(state: ResearchState, cfg: ResearchConfig,
                            clients: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    items = _merge_now(state)
    query = state.get("active_query", state["query"])
    ranked, meta = score_and_rank(query, items, cfg)
    detail = (f"{len(ranked)} unique evidence ranked "
              f"(rerank={meta.get('model', 'n/a')})")
    steps = _log_step(state, "dedup_score", detail, items=len(ranked), t0=t0)
    return {"evidence": ranked, "rerank_meta": meta, "steps": steps}


async def _node_sufficiency(state: ResearchState, cfg: ResearchConfig,
                            clients: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    ok, msg = evidence_sufficiency(state.get("evidence", []), cfg)
    steps = _log_step(state, "sufficiency", f"ok={ok}: {msg}", t0=t0)
    return {"sufficiency": {"ok": ok, "message": msg}, "steps": steps}


def _make_sufficiency_router(cfg: ResearchConfig) -> Callable[[ResearchState], str]:
    """Conditional edge: reformulate while iteration budget remains, else synthesize."""
    def route(state: ResearchState) -> str:
        if state.get("sufficiency", {}).get("ok"):
            return "synthesize"
        if state.get("iteration", 0) < cfg.max_iterations:
            return "reformulate"
        return "synthesize"
    return route


async def _node_reformulate(state: ResearchState, cfg: ResearchConfig,
                            clients: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    query = state["query"]
    evidence = state.get("evidence", [])
    seen = [e.id for e in evidence][:8]
    newq = reformulate_query(query, seen)
    iteration = state.get("iteration", 0) + 1
    steps = _log_step(state, "reformulate",
                      f"iteration {iteration}: evidence insufficient "
                      f"({state.get('sufficiency', {}).get('message', '')}); "
                      f"reformulated query (excluded {len(seen)} seen ids)", t0=t0)
    return {"active_query": newq, "iteration": iteration,
            "reformulations": [*state.get("reformulations", []), newq],
            "steps": steps}


# ── node: synthesis ─────────────────────────────────────────────────────────

async def _node_synthesize(state: ResearchState, cfg: ResearchConfig,
                           clients: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    plan: SearchPlan = state.get("plan") or SearchPlan()
    evidence = state.get("evidence", [])[: cfg.top_k_evidence]
    ev_dicts = []
    used_chars = 0
    for e in evidence:
        text = (e.passage or e.abstract or "")[:900]
        if e.fulltext:
            text = text or (e.fulltext or "")[:400]
        budget_left = cfg.max_evidence_prompt_chars - used_chars
        if budget_left <= 0:
            break
        text = text[: budget_left]
        used_chars += len(text)
        ev_dicts.append({
            "id": e.id, "title": e.title, "journal": e.journal, "year": e.year,
            "doi": e.doi, "url": e.url, "pmid": e.pmid, "abstract": e.abstract[:600],
            "passage": text, "source": e.source,
        })
    answer, used_strong, usage = await asyncio.to_thread(
        synthesize, state["query"], ev_dicts, cfg, plan)
    detail = (f"synthesis over {len(ev_dicts)} evidence items"
              + (" [STRONG LLM]" if used_strong else " [cheap/fallback LLM]"))
    steps = _log_step(state, "synthesize", detail, items=len(ev_dicts), t0=t0)
    return {"answer_md": answer, "used_strong_llm": used_strong, "llm_usage": usage,
            "steps": steps}


# ── node: claim verification ────────────────────────────────────────────────

async def _node_verify(state: ResearchState, cfg: ResearchConfig,
                       clients: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    n_evidence = len(state.get("evidence", []))
    verification = verify_claims(state.get("answer_md", ""), n_evidence)
    if n_evidence == 0:
        verification["note"] = "no evidence retrieved; answer is an explicit insufficiency statement"
    steps = _log_step(state, "verify_claims",
                      f"{len(verification['claims'])} claims, "
                      f"{verification['unsupported_count']} unsupported, "
                      f"citation_map_ok={verification['citation_map_ok']}",
                      t0=t0)
    return {"verification": verification, "steps": steps}


# ── node: finalize report ───────────────────────────────────────────────────

def _node_finalize(state: ResearchState, cfg: ResearchConfig,
                   clients: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    evidence = state.get("evidence", [])
    steps = _log_step(state, "finalize",
                      f"report: {len(evidence)} evidence, {len(state.get('steps', []))} steps",
                      t0=t0)
    from synglue_agent.research.schemas import ResearchReport, SourceSearched

    report = ResearchReport(
        query=state["query"],
        answer_md=state.get("answer_md", ""),
        evidence=evidence[:50],
        sources_searched=[SourceSearched(**s) for s in state.get("sources_searched", [])],
        verification=dict(state.get("verification", {})),
        steps=steps,
        iterations_used=state.get("iteration", 0) + 1,
        reformulations=state.get("reformulations", []),
        llm_usage=state.get("llm_usage", {}),
        used_strong_llm=bool(state.get("used_strong_llm")),
        warnings=state.get("warnings", []),
        config_snapshot=state.get("config_snapshot", cfg.snapshot()),
        reproducible={
            "evidence_ids": [e.id for e in evidence],
            "sub_queries": [str(s) for s in (state.get("plan") or SearchPlan()).sub_queries],
            "n_raw_records": len(state.get("raw_records", [])),
            "graph": "analyze->search_scientific->enrich_graph->web_search->crawl_fulltext->dedup_score->sufficiency->synthesize->verify_claims->finalize",
        },
    )
    return {"final_report": report.model_dump(), "steps": steps}


# ── graph build ─────────────────────────────────────────────────────────────

def build_graph(config: ResearchConfig | None = None, clients: dict[str, Any] | None = None):
    cfg = config or ResearchConfig.from_env()
    clients = clients or make_clients(cfg)

    async def node_analyze(state):
        return await _node_analyze(state, cfg, clients)

    async def node_search_scientific(state):
        return await _node_search_scientific(state, cfg, clients)

    async def node_enrich(state):
        return await _node_enrich(state, cfg, clients)

    async def node_web(state):
        return await _node_web_search(state, cfg, clients)

    async def node_crawl(state):
        return await _node_crawl(state, cfg, clients)

    async def node_dedup_score(state):
        return await _node_dedup_score(state, cfg, clients)

    async def node_suff(state):
        return await _node_sufficiency(state, cfg, clients)

    async def node_reformulate(state):
        return await _node_reformulate(state, cfg, clients)

    async def node_synthesize(state):
        return await _node_synthesize(state, cfg, clients)

    async def node_verify(state):
        return await _node_verify(state, cfg, clients)

    def node_finalize(state):
        return _node_finalize(state, cfg, clients)

    g = StateGraph(ResearchState)
    g.add_node("analyze", node_analyze)
    g.add_node("search_scientific", node_search_scientific)
    g.add_node("enrich_graph", node_enrich)
    g.add_node("web_search", node_web)
    g.add_node("crawl_fulltext", node_crawl)
    g.add_node("dedup_score", node_dedup_score)
    g.add_node("sufficiency", node_suff)
    g.add_node("reformulate", node_reformulate)
    g.add_node("synthesize", node_synthesize)
    g.add_node("verify_claims", node_verify)
    g.add_node("finalize", node_finalize)

    g.add_edge(START, "analyze")
    g.add_edge("analyze", "search_scientific")
    g.add_edge("search_scientific", "enrich_graph")
    g.add_edge("enrich_graph", "web_search")
    g.add_edge("web_search", "crawl_fulltext")
    g.add_edge("crawl_fulltext", "dedup_score")
    g.add_edge("dedup_score", "sufficiency")
    g.add_conditional_edges("sufficiency", _make_sufficiency_router(cfg),
                            {"synthesize": "synthesize", "reformulate": "reformulate"})
    g.add_edge("reformulate", "search_scientific")
    g.add_edge("synthesize", "verify_claims")
    g.add_edge("verify_claims", "finalize")
    g.add_edge("finalize", END)
    return g.compile(), cfg, clients


async def run_research_graph(query: str, config: ResearchConfig | None = None,
                             clients: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the compiled graph; returns the final state (final_report filled)."""
    graph, cfg, _clients = build_graph(config, clients)
    initial: ResearchState = {
        "query": query,
        "active_query": query,
        "iteration": 0,
        "max_iterations": cfg.max_iterations,
        "raw_records": [],
        "evidence": [],
        "crawled_urls": [],
        "crawl_count": 0,
        "sources_searched": [],
        "steps": [],
        "errors": [],
        "reformulations": [],
        "rerank_meta": {},
        "sufficiency": {"ok": False, "message": ""},
        "answer_md": "",
        "used_strong_llm": False,
        "llm_usage": {},
        "verification": {},
        "warnings": [],
        "config_snapshot": cfg.snapshot(),
    }
    final = await graph.ainvoke(initial)
    return final
