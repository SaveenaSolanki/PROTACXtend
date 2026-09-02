"""Offline tests for the scientific deep-research framework.

Covers: dedup/merge, scoring, lexical rerank, claim verification, deterministic
synthesis, config/env plumbing, and a full LangGraph run with stub clients
(no network, no LLM). Live scientific-API tests are marked ``network``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.research.config import ResearchConfig
from synglue_agent.research.reasoning import deterministic_synthesis, plan_deterministic
from synglue_agent.research.retrieval import (
    canonical_url,
    dedup_and_merge,
    dedup_id,
    evidence_sufficiency,
    find_citation_indices,
    normalize_title,
    reformulate_query,
    score_and_rank,
    verify_claims,
)
from synglue_agent.research.schemas import EvidenceItem
from synglue_agent.research.sources import is_biomedical_query

Q = "PROTAC-mediated degradation of BRD4 in cancer"


def _rec(source, title, doi="", pmid="", pmcid="", url="", year=2022, abstract="",
         extra=None, cited=None):
    return {
        "source": source, "title": title, "abstract": abstract or "A study of PROTAC BRD4 degradation.",
        "doi": doi, "pmid": pmid, "pmcid": pmcid, "url": url,
        "authors": ["A. Author", "B. Author"], "year": year,
        "journal": "J. Test Chem", "venue_type": "journal_article",
        "is_open_access": True, "is_primary": True, "cited_by_count": cited,
        "references": [], "publication_date": "", "extra": extra or {},
    }


# ── normalization / dedup ───────────────────────────────────────────────────

class TestDedup:
    def test_normalize_title(self):
        assert normalize_title("  BRD4: A   Novel? Target!! ") == "brd4 a novel target"
        assert normalize_title("") == ""

    def test_canonical_url(self):
        assert canonical_url("https://pubmed.ncbi.nlm.nih.gov/12345/") == "pubmed:12345"
        assert canonical_url("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234/") == "pmc:PMC1234"
        assert canonical_url("https://EXAMPLE.com/a/b/?x=1") == "example.com/a/b"

    def test_dedup_priority(self):
        r = _rec("europepmc", "T", doi="10.1/x", pmid="12", url="https://x.io/a")
        assert dedup_id(r) == "doi:10.1/x"
        r2 = dict(r)
        r2["doi"] = ""
        assert dedup_id(r2) == "pmid:12"
        r3 = dict(r2)
        r3["pmid"] = ""
        assert dedup_id(r3).startswith("url:")

    def test_merge_same_doi_across_sources(self):
        records = [
            _rec("europepmc", "One PROTAC paper", doi="10.1000/abc",
                 abstract="Short abstract here."),
            _rec("pubmed", "One PROTAC paper", doi="10.1000/ABC", pmid="999",
                 abstract="A much longer abstract about PROTAC BRD4 degradation in cells."),
            _rec("openalex", "Totally different paper", doi="10.1000/xyz"),
        ]
        items, log = dedup_and_merge(records)
        assert len(items) == 2
        doi_item = next(i for i in items if i.doi.lower() == "10.1000/abc")
        assert doi_item.pmid == "999"
        assert len(doi_item.abstract) >= len("Short abstract here.")
        assert "pubmed" in doi_item.provenance["merged_from"]


# ── scoring ─────────────────────────────────────────────────────────────────

class TestScoring:
    def test_recency_and_authority_monotonic(self):
        cfg = ResearchConfig()
        old = EvidenceItem(id="a", title="old", year=2005, cited_by_count=5)
        new = EvidenceItem(id="b", title="new", year=2023, cited_by_count=100)
        import synglue_agent.research.retrieval as rt
        old = rt.score_item(old, cfg, 2024)
        new = rt.score_item(new, cfg, 2024)
        assert new.recency_score > old.recency_score
        assert new.authority_score > old.authority_score

    def test_primary_source_boost(self):
        cfg = ResearchConfig()
        import synglue_agent.research.retrieval as rt
        prim = rt.score_item(EvidenceItem(id="a", title="p", venue_type="journal_article",
                                          is_primary=True), cfg, 2024)
        web = rt.score_item(EvidenceItem(id="b", title="w", venue_type="web",
                                         is_primary=False), cfg, 2024)
        assert prim.primary_score > web.primary_score


# ── rerank / sufficiency ────────────────────────────────────────────────────

class TestRerankAndSufficiency:
    def test_lexical_rerank_orders_relevant_first(self):
        cfg = ResearchConfig()
        items = [
            EvidenceItem(id="1", title="Unrelated topic", passage="quantum chromodynamics gauge theory"),
            EvidenceItem(id="2", title="BRD4 PROTAC degrader paper", passage="PROTAC BRD4 degradation cancer cells"),
            EvidenceItem(id="3", title="Another PROTAC study", passage="PROTAC BRD4 degradation in vivo"),
        ]
        ranked, meta = score_and_rank("PROTAC BRD4 degradation cancer", items, cfg)
        assert meta["model"] == "lexical_bm25" or "lexical" in meta["model"]
        assert ranked[0].id == "2"
        assert ranked[0].relevance_score >= ranked[1].relevance_score

    def test_sufficiency_threshold(self):
        cfg = ResearchConfig()
        cfg.min_evidence = 3
        cfg.min_top_relevance = 0.0
        ok, msg = evidence_sufficiency([], cfg)
        assert not ok
        items = [EvidenceItem(id=f"e{i}", title=f"PROTAC BRD4 paper {i}",
                              passage="PROTAC BRD4 degradation", source="europepmc",
                              relevance_score=0.9) for i in range(3)]
        ok, _ = evidence_sufficiency(items, cfg)
        assert ok

    def test_reformulate_excludes_seen_dois(self):
        out = reformulate_query(Q, ["doi:10.1000/abc", "doi:10.1000/def"])
        assert "10.1000/abc" in out and "10.1000/def" in out


# ── verification (no fabrication) ───────────────────────────────────────────

class TestVerification:
    def test_find_citations(self):
        assert find_citation_indices("claim here [1, 3] and [2].") == [1, 3, 2]

    def test_valid_and_invalid_citations(self):
        v = verify_claims("BRD4 PROTACs degrade the protein [1].\n"
                          "Another claim cites nothing useful [9].\n"
                          "A claim with no citation here.", n_evidence=3)
        assert v["citation_map_ok"] is False      # [9] out of range
        assert v["unsupported_count"] >= 1        # no-citation claim flagged
        statuses = {c["status"] for c in v["claims"]}
        assert "supported" in statuses and "unsupported" in statuses

    def test_all_claims_supported_when_cited(self):
        v = verify_claims("Degraders engage the E3 ligase [1].\nThey degrade BRD4 [1,2].",
                          n_evidence=2)
        assert v["citation_map_ok"] is True
        assert v["unsupported_count"] == 0


# ── reasoning fallbacks ─────────────────────────────────────────────────────

class TestReasoningFallbacks:
    def test_deterministic_plan(self):
        plan = plan_deterministic(Q, web_available=False)
        assert plan.sub_queries == [Q]
        assert plan.domain == "biomedical"
        assert plan.include_web is False
        assert plan.complexity in ("simple", "moderate", "hard")

    def test_domain_detection(self):
        assert is_biomedical_query("PROTAC BRD4 degradation clinical trial")
        assert not is_biomedical_query("best laptop 2026")

    def test_deterministic_synthesis_never_fabricates(self):
        ev = [EvidenceItem(id="doi:10.1000/abc", title="BRD4 degrader paper",
                           passage="We show PROTAC-mediated BRD4 degradation.",
                           journal="Nature", year=2022).model_dump()]
        answer = deterministic_synthesis(Q, ev)
        assert "[1]" in answer
        assert "## Bottom line" in answer
        assert "retrieved-source quotes" in answer.lower()


# ── full graph run with stub clients ────────────────────────────────────────

class _StubSource:
    def __init__(self, records): self.records = records
    async def search(self, query, page_size=8):
        return [dict(r) for r in self.records], ""
    async def cited_by(self, oid, limit=4): return []
    async def work_by_openalex_id(self, oid): return None
    async def work_by_doi(self, doi): return None


def _stub_clients():
    return {
        "europepmc": _StubSource([
            _rec("europepmc", "BRD4 PROTAC degradation study 1", doi="10.1000/one",
                 pmid="101", pmcid="PMC101", cited=42, year=2023),
            _rec("europepmc", "BRD4 PROTAC degradation study 2", doi="10.1000/two",
                 pmid="102", cited=10, year=2024),
        ]),
        "pubmed": _StubSource([
            _rec("pubmed", "BRD4 PROTAC degradation study 1", doi="10.1000/ONE",
                 pmid="101", year=2023),                       # duplicate by DOI
            _rec("pubmed", "Review of PROTAC degraders for BRD4", pmid="900",
                 year=2024, cited=77),
        ]),
        "openalex": _StubSource([
            _rec("openalex", "PROTAC BRD4 degrader mechanisms", doi="10.1000/three",
                 pmid="103", year=2022, cited=120,
                 extra={"openalex_id": "https://openalex.org/W1"}),
        ]),
        "crossref": _StubSource([]),
    }


def _test_config():
    cfg = ResearchConfig.from_env()
    cfg.llm_always_off = True
    cfg.min_evidence = 3
    cfg.min_top_relevance = 0.0
    cfg.max_iterations = 1
    cfg.results_per_source = 8
    cfg.concurrency_per_source = 1
    return cfg


class TestGraphRun:
    def test_full_graph_offline(self):
        from synglue_agent.research.graph import run_research_graph
        cfg = _test_config()
        final = asyncio.run(run_research_graph(Q, config=cfg, clients=_stub_clients()))
        report = final["final_report"]
        assert report is not None
        assert report["query"] == Q
        # dedup collapsed europepmc+pubmed duplicates to 4 unique
        ids = [e["id"] for e in report["evidence"]]
        assert len(ids) == len(set(ids)) >= 3
        assert any(e["doi"] == "10.1000/one" for e in report["evidence"])
        # deterministic digest answer + verified citations
        assert "[1]" in report["answer_md"]
        assert report["verification"]["citation_map_ok"] is True
        # sources searched & steps present
        names = {s["name"] for s in report["sources_searched"]}
        assert {"europepmc", "pubmed", "openalex"} <= names
        nodes = {s["node"] for s in report["steps"]}
        assert {"analyze", "search_scientific", "enrich_graph", "web_search",
                "dedup_score", "sufficiency", "synthesize", "verify_claims",
                "finalize"} <= nodes
        assert report["llm_usage"] is not None

    def test_insufficient_evidence_triggers_reformulation(self):
        from synglue_agent.research.graph import run_research_graph
        cfg = _test_config()
        cfg.min_evidence = 50          # impossible -> forces reformulation loop
        final = asyncio.run(run_research_graph(Q, config=cfg, clients=_stub_clients()))
        report = final["final_report"]
        assert report["iterations_used"] == 2      # initial + 1 reformulation
        assert len(report["reformulations"]) == 1
        # reformulated query excludes seen DOIs from round one
        assert "10.1000" in report["reformulations"][0]


# ── caching unit (no network) ───────────────────────────────────────────────

class TestCache:
    def test_disk_cache_roundtrip(self, tmp_path):
        from synglue_agent.research.httpbase import AsyncApiClient
        c = AsyncApiClient("https://example.invalid", cache_dir=tmp_path,
                           ttl_s=3600, cache_enabled=True)
        key = c._cache_key("GET", "u", "{}", "{}")
        assert c._cache_get(key) is None
        c._cache_set(key, {"a": [1, 2]})
        assert c._cache_get(key) == {"a": [1, 2]}


# ── live scientific API (opt-in) ────────────────────────────────────────────

@pytest.mark.network
class TestLiveApis:
    def test_europepmc_live_search(self):
        async def _run():
            import tempfile

            from synglue_agent.research.sources import EuropePMCClient
            cfg = ResearchConfig()
            with tempfile.TemporaryDirectory() as td:
                client = EuropePMCClient(cfg.europepmc_base, cache_dir=Path(td),
                                         ttl_s=60, user_agent=cfg.user_agent,
                                         timeout_s=20, max_retries=3, rate_delay_s=1.0)
                records, err = await client.search("PROTAC BRD4", page_size=3)
                await client.aclose()
            return records, err
        records, err = asyncio.run(_run())
        assert not err
        assert len(records) >= 1
        assert records[0]["source"] == "europepmc"
        assert records[0]["title"]
