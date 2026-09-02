"""Pydantic schemas for the deep-research framework (typed, serialisable)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ── retrieval records ───────────────────────────────────────────────────────

DOMAIN = Literal["biomedical", "general"]
COMPLEXITY = Literal["simple", "moderate", "hard"]


class SourceSearched(BaseModel):
    name: str                              # europepmc | pubmed | openalex | crossref | searxng | crawl4ai
    label: str = ""
    queried: bool = False
    available: bool = False
    hits: int = 0
    error: str = ""
    note: str = ""


class EvidenceItem(BaseModel):
    """One deduplicated source document with its score vector."""

    id: str                                # stable dedup id (doi|pmid|url|title-hash)
    title: str = ""
    abstract: str = ""
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    url: str = ""
    source: str = "api"                    # europepmc | pubmed | openalex | crossref | searxng | web
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    journal: str = ""
    venue_type: str = "journal_article"    # journal_article|preprint|report|patent|book|web|news
    is_open_access: bool = False
    is_primary: bool = True                # primary literature vs secondary commentary/web
    cited_by_count: int | None = None
    references: list[str] = Field(default_factory=list)   # DOIs/ids cited by this work
    fulltext: str | None = None         # populated by the crawl stage (truncated)
    passage: str = ""                      # best passage/title+abstract used for reranking
    relevance_score: float = 0.0
    authority_score: float = 0.0
    recency_score: float = 0.0
    primary_score: float = 0.0
    total_score: float = 0.0
    rerank_model: str = "lexical"          # cross_encoder | embeddings | lexical
    provenance: dict[str, Any] = Field(default_factory=dict)

    def model_dump_slim(self) -> dict[str, Any]:
        d = self.model_dump()
        for k in ("passage", "fulltext", "abstract"):
            d[k] = None
        return d


# ── LLM-plan / claims schemas ──────────────────────────────────────────────

class SearchPlan(BaseModel):
    sub_queries: list[str] = Field(default_factory=list)
    domain: DOMAIN = "biomedical"
    complexity: COMPLEXITY = "moderate"
    focus: str = ""
    include_web: bool = False
    notes: str = ""


class ClaimOut(BaseModel):
    claim_id: str = ""
    text: str
    citation_indices: list[int] = Field(default_factory=list)
    status: Literal["supported", "unsupported", "needs_review"] = "needs_review"
    note: str = ""


class AnswerOut(BaseModel):
    answer_md: str
    claims: list[ClaimOut] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# ── trace / report ─────────────────────────────────────────────────────────

class StepLog(BaseModel):
    node: str
    detail: str = ""
    duration_ms: float = 0.0
    items: int = 0
    error: str = ""


class VerificationResult(BaseModel):
    claims: list[ClaimOut] = Field(default_factory=list)
    citation_map_ok: bool = True
    unsupported_count: int = 0
    note: str = ""


class ResearchReport(BaseModel):
    query: str
    answer_md: str = ""
    answer_plain: str = ""
    claims: list[ClaimOut] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    sources_searched: list[SourceSearched] = Field(default_factory=list)
    verification: VerificationResult = Field(default_factory=VerificationResult)
    steps: list[StepLog] = Field(default_factory=list)
    iterations_used: int = 1
    reformulations: list[str] = Field(default_factory=list)
    llm_usage: dict[str, Any] = Field(default_factory=dict)
    used_strong_llm: bool = False
    warnings: list[str] = Field(default_factory=list)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    reproducible: dict[str, Any] = Field(default_factory=dict)
