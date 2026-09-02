"""Source adapters: Europe PMC, PubMed (NCBI), OpenAlex, Crossref, SearXNG,
and web full-text crawling (Crawl4AI with a clean-HTML fallback).

Every adapter follows the retrieval-priority contract:
  scientific APIs -> citation graph -> free web search -> crawling.
Each ``search()`` returns ``(records, error)`` where records use a common
schema documented in ``COMMON_KEYS``; errors are strings (never exceptions),
so a broken source can never crash the research graph.
"""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from synglue_agent.research.config import ResearchConfig
from synglue_agent.research.httpbase import AsyncApiClient, ClientError

logger = logging.getLogger("protacpilot.research.sources")

# Common raw-record schema produced by all adapters (retrieval.py builds
# EvidenceItem from these).
COMMON_KEYS = [
    "source", "title", "abstract", "doi", "pmid", "pmcid", "url",
    "authors", "year", "journal", "venue_type", "is_open_access", "is_primary",
    "cited_by_count", "references", "publication_date", "extra",
]

# Domain routing order used by the plan.
SCIENTIFIC_FIRST = ["europepmc", "pubmed", "openalex"]   # per requirement: EPMC/PubMed first
GRAPH_SOURCES = ["openalex", "crossref"]
WEB_SOURCES = ["searxng"]
CRAWL_SOURCE = "crawl4ai"

BIOMEDICAL_KEYWORDS = (
    "protein|gene|drug|disease|cell|patient|clinical|trial|kinase|degrad|protac|"
    "biomarker|therap|antibody|receptor|enzyme|mutation|tumor|tumour|cancer|"
    "inhibitor|compound|smiles|ligand|pharmacolog|toxicolog|genom|proteom|biolog|"
    "chemistry|chemical|dna|rna|immuno|viral|bacteria|infection|metabol|syndrome|"
    "assay|efficacy|safety|pharmacokin|dosage|e3 ligase|warhead"
)


def is_biomedical_query(text: str) -> bool:
    low = (text or "").lower()
    return bool(re.search(BIOMEDICAL_KEYWORDS, low))


# ── SearXNG (self-hosted free web search) ────────────────────────────────

class SearXNGClient(AsyncApiClient):
    name = "searxng"

    def available(self) -> bool:
        return bool(self.base_url)

    async def search(self, query: str, n_results: int = 6) -> tuple[list[dict[str, Any]], str]:
        if not self.available():
            return [], "searxng not configured (set SEARXNG_URL to a self-hosted instance)"
        try:
            data = await self.get_json("/search", params={
                "q": query, "format": "json", "categories": "general",
                "language": "en-US", "safesearch": "0", "pageno": "1"})
            results = (data or {}).get("results") or []
            records = []
            for r in results[:n_results]:
                url = r.get("url", "")
                if not url:
                    continue
                year = None
                pd = r.get("publishedDate")
                if pd:
                    m = re.search(r"(19|20)\d{2}", str(pd))
                    if m:
                        year = int(m.group(0))
                title = r.get("title", "") or ""
                snippet = r.get("content", "") or ""
                engine = ",".join(r.get("engines") or [r.get("engine") or "searxng"])
                records.append({
                    "source": "searxng",
                    "title": title,
                    "abstract": snippet,
                    "doi": "", "pmid": "", "pmcid": "",
                    "url": url,
                    "authors": [],
                    "year": year,
                    "journal": "",
                    "venue_type": "web",
                    "is_open_access": False,
                    "is_primary": False,
                    "cited_by_count": None,
                    "references": [],
                    "publication_date": str(pd or ""),
                    "extra": {"engine": engine, "score": r.get("score"),
                              "category": r.get("category", "")},
                })
            return records, ""
        except Exception as exc:
            return [], f"searxng search failed: {exc}"


# ── Web full-text crawling (Crawl4AI + clean-HTML fallback) ────────────────

class WebCrawlClient(AsyncApiClient):
    """Full-text extractor. Uses Crawl4AI when installed, otherwise an honest
    clean-HTML extractor (httpx + BeautifulSoup). Robots.txt is honoured when
    ``respect_robots`` is enabled."""

    name = "web_crawl"

    def __init__(self, *, crawl4ai_disabled: bool = False, max_chars: int = 24_000,
                 respect_robots: bool = True, **kw):
        super().__init__(base_url="", **kw)
        self.crawl4ai_disabled = crawl4ai_disabled
        self.max_chars = max_chars
        self.respect_robots = respect_robots
        self._robots_cache: dict[str, list[str]] = {}

    # robots.txt (simple prefix honouring)
    async def _robots_disallow(self, url: str) -> bool:
        if not self.respect_robots:
            return False
        try:
            parsed = urllib.parse.urlparse(url)
            domain = f"{parsed.scheme}://{parsed.netloc}"
            if domain not in self._robots_cache:
                try:
                    resp = await self._http.get(f"{domain}/robots.txt",
                                                timeout=8, follow_redirects=True)
                    rules = []
                    if resp.status_code == 200:
                        user_agent_ok = True
                        for line in resp.text.splitlines():
                            line = line.strip()
                            low = line.lower()
                            if low.startswith("user-agent") and "*" not in low:
                                user_agent_ok = False
                            elif low.startswith("user-agent") and "*" in low:
                                user_agent_ok = True
                            elif low.startswith("disallow") and user_agent_ok:
                                val = line.split(":", 1)[1].strip() if ":" in line else ""
                                if val:
                                    rules.append(val)
                    self._robots_cache[domain] = rules
                except Exception:
                    self._robots_cache[domain] = []
            path = parsed.path or "/"
            for rule in self._robots_cache.get(domain, []):
                if rule.endswith("/") and path.startswith(rule):
                    return True
                if path == rule or path.startswith(rule.rstrip("/") + "/"):
                    return True
        except Exception:
            return False
        return False

    async def crawl(self, url: str) -> dict[str, Any]:
        """Return {"title", "text", "engine", "url"} or raise ClientError."""
        if await self._robots_disallow(url):
            raise ClientError("crawl blocked by robots.txt", kind="robots")
        if not self.crawl4ai_disabled:
            try:
                from crawl4ai import AsyncWebCrawler  # type: ignore[import-not-found]
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url=url)
                    markdown = getattr(result, "markdown", "") or ""
                    text = getattr(result, "cleaned_html", "") or markdown
                    if text:
                        return {"title": getattr(result, "title", "") or "",
                                "text": text[: self.max_chars],
                                "engine": "crawl4ai", "url": url}
            except Exception as exc:
                logger.debug("crawl4ai unavailable (%s); using clean-HTML extractor", exc)
        title, text = await _clean_html_extract(self._http, url, self.headers)
        return {"title": title, "text": text[: self.max_chars],
                "engine": "clean_web_extractor", "url": url}


async def _clean_html_extract(http: httpx.AsyncClient, url: str,
                              headers: dict[str, str]) -> tuple[str, str]:
    """Fetch a page and extract readable text (honest fallback engine)."""
    resp = await http.get(url, headers={**headers, "Accept": "text/html"},
                          follow_redirects=True, timeout=20)
    if resp.status_code >= 400:
        raise ClientError(f"HTTP {resp.status_code}", kind="http", status=resp.status_code)
    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "aside",
                     "form", "svg", "header", "iframe"]):
        tag.decompose()
    title = (soup.title.get_text(strip=True) if soup.title else "") or ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True) or title
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return title, text[:120_000]


# ── client factory used by the graph ────────────────────────────────────────

def make_clients(config: ResearchConfig, cache_dir=None) -> dict[str, Any]:
    """Build the client registry honouring source availability flags."""
    common = dict(
        cache_dir=cache_dir or config.cache_dir,
        ttl_s=config.cache_ttl_s,
        user_agent=config.user_agent,
        timeout_s=config.request_timeout_s,
        connect_timeout_s=config.connect_timeout_s,
        max_retries=config.max_retries,
        backoff_base_s=config.retry_backoff_base_s,
        semaphore=asyncio.Semaphore(config.concurrency_per_source),
    )
    clients: dict[str, Any] = {}
    clients["europepmc"] = EuropePMCClient(config.europepmc_base, **common)
    clients["pubmed"] = PubMedClient(
        config.ncbi_eutils_base,
        headers={"X-API-Key": config.ncbi_api_key} if config.ncbi_api_key else None,
        rate_delay_s=0.0 if config.ncbi_api_key else config.ncbi_request_delay_s,
        **common)
    clients["openalex"] = OpenAlexClient(config.openalex_base, **common)
    clients["crossref"] = CrossrefClient(config.crossref_base, **common)
    if config.searxng_url and not config.searxng_disabled:
        clients["searxng"] = SearXNGClient(
            config.searxng_url,
            headers={"X-Searx-API-Key": config.searxng_key} if config.searxng_key else None,
            **common)
    clients["crawl"] = WebCrawlClient(
        crawl4ai_disabled=config.crawl4ai_disabled,
        max_chars=config.max_fulltext_chars,
        respect_robots=config.respect_robots,
        **common)
    return clients


def build_client(config: ResearchConfig, name: str, cache_dir=None) -> AsyncApiClient:
    """Create a cached client for one source (helper used by tests)."""
    return make_clients(config, cache_dir=cache_dir)[name]


# ── Europe PMC ──────────────────────────────────────────────────────────────

class EuropePMCClient(AsyncApiClient):
    name = "europepmc"

    async def search(self, query: str, page_size: int = 8, cursor: str = "") -> tuple[list[dict[str, Any]], str]:
        try:
            params: dict[str, Any] = {"query": query, "format": "json",
                                      "pageSize": page_size, "resultType": "core"}
            if cursor:
                params["cursorMark"] = cursor
            data = await self.get_json("/search", params=params)
            results = ((data or {}).get("resultList") or {}).get("result") or []
            records = []
            for r in results:
                ji = r.get("journalInfo") or {}
                year = r.get("pubYear")
                authors = []
                for a in (r.get("authorList") or {}).get("author", []) or []:
                    full = " ".join(x for x in [a.get("firstName"), a.get("lastName")] if x)
                    if full:
                        authors.append(full)
                source = r.get("source") or ""
                pmcid = r.get("pmcid") or ""
                url = ""
                if pmcid:
                    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
                elif r.get("pmid"):
                    url = f"https://pubmed.ncbi.nlm.nih.gov/{r.get('pmid')}/"
                records.append({
                    "source": "europepmc",
                    "title": r.get("title", ""),
                    "abstract": r.get("abstractText", ""),
                    "doi": r.get("doi", ""),
                    "pmid": str(r.get("pmid", "") or ""),
                    "pmcid": pmcid,
                    "url": url,
                    "authors": authors,
                    "year": int(year) if str(year).isdigit() else None,
                    "journal": ((ji.get("journal") or {}).get("title") or ""),
                    "venue_type": "journal_article",
                    "is_open_access": str(r.get("isOpenAccess", "N")).upper() == "Y",
                    "is_primary": source in ("MED", "PMC"),
                    "cited_by_count": r.get("citedByCount"),
                    "references": [],
                    "publication_date": r.get("firstPublicationDate", ""),
                    "extra": {"epmc_source": source, "epmc_id": r.get("id", ""),
                              "has_references": r.get("hasReferences") == "Y",
                              "license": r.get("license", ""),
                              "mesh": [m.get("descriptorName", "") for m in (r.get("meshHeadingList") or {}).get("meshHeading", [])][:8]},
                })
            return records, ""
        except Exception as exc:
            return [], f"europepmc search failed: {exc}"

    async def fulltext_xml(self, source: str, article_id: str) -> str:
        """OA full-text XML (PMC/MED); may be gated for non-OA MED records."""
        try:
            xml = await self.get_text(f"/{source}/{article_id}/fullTextXML",
                                      headers={"Accept": "application/xml"})
            return _xml_to_text(xml)
        except Exception as exc:
            raise ClientError(f"fulltext unavailable ({source}/{article_id}): {exc}") from exc


def _xml_to_text(xml: str, max_chars: int = 60_000) -> str:
    """XML -> plain text (whole record or just the <body> when present)."""
    if not xml or "<" not in xml:
        return ""
    try:
        root = ET.fromstring(xml)
    except Exception:
        return re.sub(r"<[^>]+>", " ", xml)[:max_chars]
    body = root.find(".//body")
    subtree = body if body is not None else root
    parts = [t for t in subtree.itertext() if t and t.strip()]
    return " ".join(parts)[:max_chars]


# ── PubMed / NCBI E-utilities ───────────────────────────────────────────────

class PubMedClient(AsyncApiClient):
    name = "pubmed"

    async def search(self, query: str, page_size: int = 8, retmax: int | None = None) -> tuple[list[dict[str, Any]], str]:
        try:
            data = await self.get_json("/esearch.fcgi", params={
                "db": "pubmed", "term": query, "retmode": "json",
                "retmax": retmax or page_size, "sort": "relevance",
                **({"api_key": self.headers.get("X-API-Key")} if self.headers.get("X-API-Key") else {})})
            ids = (((data or {}).get("esearchresult") or {}).get("idlist")) or []
            if not ids:
                return [], ""
            return await self.fetch_records(ids)
        except Exception as exc:
            return [], f"pubmed search failed: {exc}"

    async def fetch_records(self, pmids: list[str]) -> tuple[list[dict[str, Any]], str]:
        try:
            ids = ",".join(pmids[:25])
            xml = await self.get_text("/efetch.fcgi", params={
                "db": "pubmed", "id": ids, "retmode": "xml", "rettype": "abstract"})
            return _parse_pubmed_xml(xml, pmids), ""
        except Exception as exc:
            return [], f"pubmed efetch failed: {exc}"


def _parse_pubmed_xml(xml: str, requested_pmids: list[str]) -> list[dict[str, Any]]:
    if not xml:
        return []
    try:
        root = ET.fromstring(xml)
    except Exception:
        return []
    records: list[dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        rec = _parse_pubmed_article(article)
        if rec:
            records.append(rec)
    return records


def _parse_pubmed_article(article: ET.Element) -> dict[str, Any] | None:
    pmid = (article.findtext(".//PMID") or "").strip()
    title = " ".join((article.findtext(".//ArticleTitle") or "").split())
    abstract_parts = []
    for ab in article.findall(".//Abstract/AbstractText"):
        label = ab.get("Label")
        txt = " ".join("".join(ab.itertext()).split())
        abstract_parts.append(f"{label}: {txt}" if label and txt else txt)
    abstract = " ".join(abstract_parts)
    journal = article.findtext(".//Journal/Title") or ""
    year_raw = article.findtext(".//JournalIssue/PubDate/Year") or article.findtext(".//ArticleDate/Year") or ""
    authors = []
    for au in article.findall(".//AuthorList/Author"):
        collective = au.findtext("CollectiveName")
        if collective:
            authors.append(collective)
            continue
        last = au.findtext("LastName") or ""
        init = au.findtext("Initials") or ""
        if last:
            authors.append(f"{last} {init}".strip())
    doi = ""
    pmcid = ""
    for aid in article.findall(".//ArticleIdList/ArticleId"):
        typ = aid.get("IdType", "")
        if typ == "doi":
            doi = (aid.text or "").strip()
        elif typ == "pmc":
            pmcid = (aid.text or "").strip()
    pub_type = "journal_article"
    pub_types = [pt.text for pt in article.findall(".//PublicationTypeList/PublicationType")]
    if pub_types:
        joined = " ".join(pub_types).lower()
        if "review" in joined and "systematic review" not in joined:
            pub_type = "review"
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    year = int(year_raw) if year_raw.isdigit() else None
    return {
        "source": "pubmed",
        "title": title,
        "abstract": abstract,
        "doi": doi,
        "pmid": pmid,
        "pmcid": pmcid,
        "url": url,
        "authors": authors,
        "year": year,
        "journal": journal,
        "venue_type": pub_type,
        "is_open_access": bool(pmcid),
        "is_primary": True,
        "cited_by_count": None,
        "references": [],
        "publication_date": "",
        "extra": {"pub_types": pub_types[:5]},
    }


# ── OpenAlex ────────────────────────────────────────────────────────────────

class OpenAlexClient(AsyncApiClient):
    name = "openalex"

    async def search(self, query: str, page_size: int = 8, per_page: int | None = None) -> tuple[list[dict[str, Any]], str]:
        try:
            data = await self.get_json("/works", params={
                "search": query, "per-page": per_page or page_size,
                "mailto": self.headers.get("mailto", "")})
            works = ((data or {}).get("results")) or []
            records = []
            for w in works[: per_page or page_size]:
                rec = self._work_to_record(w)
                if rec:
                    records.append(rec)
            return records, ""
        except Exception as exc:
            return [], f"openalex search failed: {exc}"

    def _work_to_record(self, w: dict[str, Any]) -> dict[str, Any] | None:
        try:
            title = w.get("title") or ""
            if not title:
                return None
            doi = (w.get("doi") or "").replace("https://doi.org/", "")
            loc = w.get("primary_location") or {}
            src = loc.get("source") or {}
            journal = src.get("display_name") or ""
            host = (loc.get("landing_page_url") or "") or w.get("id") or ""
            authors = [a.get("author", {}).get("display_name", "") for a in (w.get("authorships") or []) if a.get("author", {}).get("display_name")]
            abstract = _reconstruct_abstract(w.get("abstract_inverted_index"))
            oa = w.get("open_access") or {}
            wtype = (w.get("type") or "article").lower()
            venue_type = {"preprint": "preprint", "editorial": "editorial", "letter": "letter",
                          "paratext": "paratext", "book-chapter": "book", "book": "book",
                          "dissertation": "report", "grant": "report", "dataset": "report",
                          "other": "report"}.get(wtype, "journal_article")
            is_primary = wtype not in ("preprint", "editorial", "letter", "paratext", "other")
            year = w.get("publication_year")
            cited = w.get("cited_by_count")
            refs_openalex = (w.get("referenced_works") or [])[:20]
            refs = [r.replace("https://openalex.org/W", "") for r in refs_openalex]
            ids = w.get("ids") or {}
            return {
                "source": "openalex",
                "title": title,
                "abstract": abstract or "",
                "doi": doi,
                "pmid": (ids.get("pmid") or "").replace("https://pubmed.ncbi.nlm.nih.gov/", ""),
                "pmcid": (ids.get("pmc") or "").replace("https://www.ncbi.nlm.nih.gov/pmc/articles/", ""),
                "url": host,
                "authors": authors,
                "year": year,
                "journal": journal,
                "venue_type": venue_type,
                "is_open_access": bool(oa.get("is_oa")),
                "is_primary": is_primary,
                "cited_by_count": cited,
                "references": refs,           # OpenAlex ids (not DOIs)
                "publication_date": w.get("publication_date", ""),
                "extra": {"openalex_id": w.get("id", ""), "type": wtype,
                          "cited_by_api": w.get("cited_by_api_url", ""),
                          "countries": [i.get("country_code") for i in (w.get("authorships") or [])
                                        for inst in [i.get("institutions") or []]
                                        for c in inst if (c.get("country_code") or "").lower() not in ("", "us")][:3]},
            }
        except Exception:
            return None

    async def cited_by(self, openalex_id: str, limit: int = 10) -> list[dict[str, Any]]:
        if not openalex_id.startswith("https://openalex.org/"):
            openalex_id = f"https://openalex.org/W{openalex_id.lstrip('W')}"
        data = await self.get_json("/works", params={
            "filter": f"cites:{openalex_id}", "per-page": limit,
            "mailto": self.headers.get("mailto", "")})
        out = []
        for w in ((data or {}).get("results") or [])[:limit]:
            rec = self._work_to_record(w)
            if rec:
                rec["extra"] = {**(rec.get("extra") or {}), "relation": "cited_by"}
                out.append(rec)
        return out

    async def work_by_openalex_id(self, openalex_id: str) -> dict[str, Any] | None:
        try:
            w = await self.get_json(f"/works/{openalex_id.lstrip('W')}",
                                    params={"mailto": self.headers.get("mailto", "")})
            return self._work_to_record(w) if isinstance(w, dict) else None
        except Exception:
            return None


def _reconstruct_abstract(inverted: dict[str, Any] | None) -> str:
    if not inverted:
        return ""
    positions: list[tuple[int, str]] = []
    for token, idxs in inverted.items():
        for i in idxs:
            positions.append((int(i), token))
    if not positions:
        return ""
    positions.sort()
    return " ".join(t for _, t in positions)


# ── Crossref ────────────────────────────────────────────────────────────────

class CrossrefClient(AsyncApiClient):
    name = "crossref"

    async def work_by_doi(self, doi: str) -> dict[str, Any] | None:
        try:
            data = await self.get_json(f"/works/{urllib.parse.quote(doi)}",
                                       params={"mailto": self.headers.get("mailto", "")})
            m = (data or {}).get("message")
            if not m:
                return None
            year = None
            for key in ("published-print", "published-online", "issued"):
                dp = (m.get(key) or {}).get("date-parts")
                if dp and dp[0]:
                    year = int(dp[0][0])
                    break
            refs = []
            for r in (m.get("reference") or [])[:40]:
                d = r.get("DOI")
                if d:
                    refs.append(d.lower())
            authors = []
            for a in (m.get("author") or [])[:20]:
                nm = " ".join(x for x in [a.get("given"), a.get("family")] if x)
                if nm:
                    authors.append(nm)
            title = (m.get("title") or [""])[0] or ""
            return {
                "source": "crossref",
                "title": title,
                "abstract": (m.get("abstract") or ""),
                "doi": (m.get("DOI") or "").lower(),
                "pmid": "",
                "pmcid": "",
                "url": m.get("URL", ""),
                "authors": authors,
                "year": year,
                "journal": (m.get("container-title") or [""])[0] if m.get("container-title") else "",
                "venue_type": m.get("type", "journal_article"),
                "is_open_access": bool(m.get("license") or []),
                "is_primary": m.get("type") in ("journal-article", "review-article", "proceedings-article", "book-chapter", "book"),
                "cited_by_count": m.get("is-referenced-by-count"),
                "references": refs,            # DOIs
                "publication_date": "",
                "extra": {"crossref_type": m.get("type"), "issn": (m.get("ISSN") or [])[:4],
                          "license": [x.get("URL") for x in (m.get("license") or [])][:2],
                          "relation": "doi_validation"},
            }
        except Exception as exc:
            raise ClientError(f"crossref DOI lookup failed for {doi}: {exc}") from exc
