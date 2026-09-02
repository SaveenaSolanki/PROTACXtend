# Scientific Deep-Research Framework (LangGraph)

Low-cost, production-ready evidence retrieval and synthesis for biomedical and
general questions. Built on **LangGraph** routing with modular, replaceable,
async source adapters; scientific APIs are always searched first.

```
synglue_agent/research/
├── api.py        unified public API: deep_research / deep_research_sync
├── config.py     ResearchConfig — every knob env-configurable
├── schemas.py    pydantic contracts (evidence, claims, report, trace)
├── httpbase.py   async client: retries, rate limits, disk cache, errors
├── sources.py    Europe PMC · PubMed(NCBI) · OpenAlex · Crossref ·
│                 SearXNG · Crawl4AI(+clean-HTML fallback)
├── retrieval.py  dedup/merge · authority/recency/primary scoring ·
│                 cross-encoder/embeddings or lexical rerank ·
│                 claim-level citation verification
├── reasoning.py  cheap/strong LLM wrappers + deterministic fallbacks
├── graph.py      LangGraph state machine + nodes
└── __init__.py   deep_research(...) public entry points
scripts/deep_research_cli.py      command-line runner
```

## Retrieval priority (implemented order)

1. **Scientific APIs** — Europe PMC + PubMed searched first for biomedical
   questions (OpenAlex always searched).
2. **Metadata/citation graph** — OpenAlex related/cited-by/references +
   Crossref DOI validation & metadata.
3. **Free web search** — self-hosted SearXNG (JSON API) when `SEARXNG_URL` is set.
4. **Full-text crawling** — Crawl4AI when installed, else a robots-honouring
   clean-HTML extractor (honest engine labels).
5. **Deduplication** — by DOI → PMID → PMCID → canonical URL → normalized title.
6. **Reranking** — local cross-encoder + embeddings when `sentence_transformers`
   is installed; deterministic lexical BM25 otherwise (honest `rerank_model`).
7. **Evidence verification** — claim-level citation checks; out-of-range or
   missing citations are flagged, never fabricated.
8. **LLM synthesis** — cheap/local model by default; a strong model is used only
   when the plan is `hard` and `RESEARCH_STRONG_LLM_*` is configured.

Insufficient evidence automatically reformulates the query (excluding seen DOIs)
and re-searches while the iteration budget remains.

## Unified API

```python
import asyncio
from synglue_agent.research import deep_research, answer_to_markdown

async def main():
    report = await deep_research(
        "What is the clinical evidence for PROTAC-mediated degradation of BRD4?")
    print(answer_to_markdown(report))
    # report.evidence / report.claims / report.verification /
    # report.sources_searched / report.steps  (search trace)

asyncio.run(main())

# sync:
from synglue_agent.research import deep_research_sync
report = deep_research_sync("PROTAC BRD4 cancer evidence")
```

CLI:

```bash
# deterministic digest, zero LLM/API cost beyond free scientific APIs
python scripts/deep_research_cli.py "PROTAC BRD4 degradation cancer" --no-llm

# with a local/cheap LLM (default: project gateway, PROTACPILOT_LLM_* envs)
python scripts/deep_research_cli.py "..." --out outputs/research_answers/answer.md

# enable web + crawling
SEARXNG_URL=http://127.0.0.1:8888 python scripts/deep_research_cli.py "..."
```

## Configuration (env)

| Variable | Purpose | Default |
|---|---|---|
| `PROTACPILOT_LLM_PROVIDER/MODEL/BASE_URL/API_KEY` | cheap/local LLM tier | ollama · gpt-oss:20b |
| `RESEARCH_STRONG_LLM_PROVIDER/MODEL/BASE_URL/API_KEY` | optional strong tier (hard plans only) | off |
| `RESEARCH_LLM_OFF=1` | disable all LLM calls (deterministic digest) | 0 |
| `SEARXNG_URL` / `SEARXNG_KEY` / `SEARXNG_DISABLED` | self-hosted SearXNG | off |
| `NCBI_API_KEY` | PubMed E-utilities key (higher rate limit) | — |
| `RESEARCH_CACHE_DIR` / `RESEARCH_TRACE_DIR` | cache + trace locations | `data/research/cache`, `outputs/research_traces` |
| `RESEARCH_MAX_ITERATIONS` · `RESEARCH_TOP_K` · `RESEARCH_MIN_EVIDENCE` · `RESEARCH_PER_SOURCE` | budgets | 2 · 8 · 3 · 8 |
| `RESEARCH_REQUIRE_NEURAL_RERANK=1` | refuse lexical rerank fallback | 0 |
| `RERANKER_MODEL`/`RESEARCH_EMBED_MODEL` | local model ids (optional) | cross-encoder MiniLM-L6 / MiniLM-L6 |

## Honesty guarantees

* A source that fails is reported in `sources_searched.error` — never silently
  treated as "no results".
* The answer may only cite evidence actually retrieved; `verify_claims` flags
  claims with no/missing/out-of-range citations (`unsupported`).
* With no LLM available the framework returns a deterministic, quoted evidence
  digest instead of a generated answer.
* Every run persists a reproducible trace (steps with durations, sub-queries,
  config snapshot without secrets, evidence ids) under `outputs/research_traces/`.

## Cost profile

* Scientific APIs are free; SearXNG is self-hosted; crawling is capped.
* LLM calls: 1 planning call (cheap) + 1 synthesis call; the strong model is
  reserved for `hard` plans only when explicitly configured.
* Disk cache (7-day TTL) avoids repeated API hits.
