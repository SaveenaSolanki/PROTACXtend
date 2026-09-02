"""protacpilot scientific deep-research framework.

Low-cost, production-ready evidence retrieval with LangGraph routing:

    scientific APIs (Europe PMC/PubMed/OpenAlex) -> citation graph (OpenAlex/
    Crossref) -> free web search (SearXNG) -> full-text crawl (Crawl4AI/clean
    extractor) -> dedup -> local rerank (cross-encoder/embeddings or lexical)
    -> evidence verification -> cheap/strong LLM synthesis.

Public API:

    from synglue_agent.research import deep_research
    report = await deep_research("PROTACs for BRD4 degradation ...")
"""

from synglue_agent.research.api import (
    answer_to_markdown,
    deep_research,
    deep_research_sync,
)
from synglue_agent.research.config import ResearchConfig
from synglue_agent.research.schemas import ResearchReport

__all__ = [
    "deep_research",
    "deep_research_sync",
    "answer_to_markdown",
    "ResearchConfig",
    "ResearchReport",
]
