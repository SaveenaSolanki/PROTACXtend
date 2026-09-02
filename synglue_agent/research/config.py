"""Scientific deep-research configuration (env-driven, replaceable per module).

Every knobs can be overridden with environment variables; a ``ResearchConfig``
instance can also be constructed in code and passed to ``deep_research``. All
endpoints/keys are optional: disabled sources are reported honestly, never
silently skipped.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env(*names: str, default: str = "") -> str:
    for name in names:
        val = os.environ.get(name)
        if val:
            return val
    return default


@dataclass
class ResearchConfig:
    # ── budgets ───────────────────────────────────────────────────────────
    max_sub_queries: int = 3                 # split query into ≤N parallel searches
    max_iterations: int = 2                  # reformulation loops (0 = single pass)
    results_per_source: int = 8              # raw hits per source per sub-query
    top_k_evidence: int = 8                  # reranked evidence sent to the LLM
    min_evidence: int = 3                    # sufficiency: minimum unique evidence docs
    min_top_relevance: float = 0.05          # sufficiency: best relevance must exceed this
    enrich_top_works: int = 4                # citation-graph enrichment on top-N API works
    enrich_ref_cap: int = 10                 # max OpenAlex/Crossref references pulled per work
    web_results_per_query: int = 6           # SearXNG hits per sub-query
    crawl_limit: int = 2                     # full-text crawls per run
    max_fulltext_chars: int = 24_000         # context cap for a crawled full text
    max_abstract_chars: int = 3_000
    max_evidence_prompt_chars: int = 18_000  # total evidence text budget for the LLM

    # ── caching / network ─────────────────────────────────────────────────
    cache_dir: Path = PROJECT_ROOT / "data" / "research" / "cache"
    cache_ttl_s: int = 7 * 86400
    request_timeout_s: float = 25.0
    connect_timeout_s: float = 10.0
    max_retries: int = 3
    retry_backoff_base_s: float = 1.2
    ncbi_request_delay_s: float = 0.34       # NCBI: ≤3/s without an API key
    concurrency_per_source: int = 3
    respect_robots: bool = True              # crawl gate for web pages

    # ── scientific API endpoints ───────────────────────────────────────────
    europepmc_base: str = "https://www.ebi.ac.uk/europepmc/webservices/rest"
    ncbi_eutils_base: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    ncbi_api_key: str = ""
    openalex_base: str = "https://api.openalex.org"
    openalex_mailto: str = "protacpilot@example.org"
    crossref_base: str = "https://api.crossref.org"
    crossref_mailto: str = "protacpilot@example.org"

    # ── free web search + crawling ─────────────────────────────────────────
    searxng_url: str = ""                    # e.g. http://127.0.0.1:8888 (self-hosted)
    searxng_key: str = ""                    # optional header X-Searx-API-Key / bearer
    searxng_disabled: bool = False
    crawl4ai_disabled: bool = False

    # ── local embeddings / reranker (honest tiers) ─────────────────────────
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    require_neural_rerank: bool = False      # False -> lexical tier fallback is allowed

    # ── LLM tiers (cheap local / optional strong) ──────────────────────────
    cheap_provider: str = _env("PROTACPILOT_LLM_PROVIDER", "RESEARCH_LLM_PROVIDER", default="ollama")
    cheap_model: str = _env("PROTACPILOT_LLM_MODEL", "RESEARCH_LLM_MODEL", default="gpt-oss:20b")
    cheap_base_url: str = _env("PROTACPILOT_LLM_BASE_URL", "RESEARCH_LLM_BASE_URL", default="http://127.0.0.1:11435")
    cheap_api_key: str = _env("PROTACPILOT_LLM_API_KEY", "RESEARCH_LLM_API_KEY", default="")
    cheap_timeout_s: int = int(_env("RESEARCH_LLM_TIMEOUT_S", default="300"))

    strong_provider: str = _env("RESEARCH_STRONG_LLM_PROVIDER", default="")
    strong_model: str = _env("RESEARCH_STRONG_LLM_MODEL", default="")
    strong_base_url: str = _env("RESEARCH_STRONG_LLM_BASE_URL", default="")
    strong_api_key: str = _env("RESEARCH_STRONG_LLM_API_KEY", default="")
    use_strong_llm: bool = _env("RESEARCH_USE_STRONG_LLM", default="1") == "1"
    llm_always_off: bool = _env("RESEARCH_LLM_OFF", default="0") == "1"

    # ── scoring weights (relevance/authority/recency/primary) ─────────────
    w_relevance: float = 0.45
    w_authority: float = 0.20
    w_recency: float = 0.15
    w_primary: float = 0.20

    # ── provenance / reproducibility ───────────────────────────────────────
    user_agent: str = "protacpilot-deep-research/0.1 (scientific evidence retrieval; mailto:protacpilot@example.org)"
    trace_persist: bool = True
    trace_dir: Path = PROJECT_ROOT / "outputs" / "research_traces"

    def snapshot(self) -> dict:
        """Reproducible config snapshot (no secrets)."""
        data = dict(self.__dict__)
        data["cache_dir"] = str(self.cache_dir)
        data["trace_dir"] = str(self.trace_dir)
        for k in ("searxng_key", "ncbi_api_key", "cheap_api_key", "strong_api_key"):
            if data.get(k):
                data[k] = "***"
        data.pop("cheap_api_key", None)
        data.pop("strong_api_key", None)
        return data

    @staticmethod
    def from_env() -> ResearchConfig:
        c = ResearchConfig()
        c.max_sub_queries = int(_env("RESEARCH_MAX_SUBQUERIES", default=str(c.max_sub_queries)))
        c.max_iterations = int(_env("RESEARCH_MAX_ITERATIONS", default=str(c.max_iterations)))
        c.top_k_evidence = int(_env("RESEARCH_TOP_K", default=str(c.top_k_evidence)))
        c.min_evidence = int(_env("RESEARCH_MIN_EVIDENCE", default=str(c.min_evidence)))
        c.results_per_source = int(_env("RESEARCH_PER_SOURCE", default=str(c.results_per_source)))
        c.searxng_url = _env("SEARXNG_URL", default=c.searxng_url).strip().rstrip("/")
        c.searxng_key = _env("SEARXNG_KEY", default="")
        c.searxng_disabled = _env("SEARXNG_DISABLED", default="0") == "1"
        c.ncbi_api_key = _env("NCBI_API_KEY", default="")
        c.require_neural_rerank = _env("RESEARCH_REQUIRE_NEURAL_RERANK", default="0") == "1"
        c.use_strong_llm = _env("RESEARCH_USE_STRONG_LLM", default="1") == "1"
        c.llm_always_off = _env("RESEARCH_LLM_OFF", default="0") == "1"
        cache = _env("RESEARCH_CACHE_DIR", default="")
        if cache:
            c.cache_dir = Path(cache)
        trace = _env("RESEARCH_TRACE_DIR", default="")
        if trace:
            c.trace_dir = Path(trace)
        c.cache_ttl_s = int(_env("RESEARCH_CACHE_TTL_S", default=str(c.cache_ttl_s)))
        return c


def cheap_llm_provider_config(cfg: ResearchConfig | None = None) -> object:
    """ProviderConfig for the cheap/local LLM tier (reuses the project gateway)."""
    from synglue_agent.llm.providers import ProviderConfig

    c = cfg or ResearchConfig.from_env()
    return ProviderConfig(
        provider=c.cheap_provider,
        model=c.cheap_model,
        base_url=c.cheap_base_url,
        api_key=c.cheap_api_key,
        num_ctx=16_384,
        temperature=0.0,
        timeout_s=c.cheap_timeout_s,
    )


def strong_llm_provider_config(cfg: ResearchConfig | None = None):
    """ProviderConfig for the optional strong tier, or None when not configured."""
    from synglue_agent.llm.providers import ProviderConfig

    c = cfg or ResearchConfig.from_env()
    if not c.strong_provider:
        return None
    return ProviderConfig(
        provider=c.strong_provider,
        model=c.strong_model or "claude-3-7-sonnet-20250219",
        base_url=c.strong_base_url,
        api_key=c.strong_api_key,
        num_ctx=32_768,
        temperature=0.0,
        timeout_s=600,
    )
