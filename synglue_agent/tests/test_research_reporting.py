"""Offline tests for the publication-quality research report layer."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.research.config import ResearchConfig
from synglue_agent.research.reporting import (
    evidence_score,
    excluded_evidence,
    findings_claims,
    grade_claims,
    metadata_conflicts,
    overall_confidence,
    parse_narrative,
    reference_rows,
    render_publication_report,
    source_role,
)
from synglue_agent.research.schemas import (
    EvidenceItem,
    ResearchReport,
    SourceSearched,
    StepLog,
    VerificationResult,
)

QUERY = "PROTAC-mediated degradation of BRD4 in cancer"


def _evidence(i: int, *, role_hint: str = "", year: int = 2022, doi: str = "",
              pmid: str = "", url: str = "", abstract: str = "study abstract PROTAC BRD4 degradation cells",
              total: float = 0.7, source: str = "europepmc") -> EvidenceItem:
    title = f"BRD4 PROTAC degradation study {i} {role_hint}"
    extra: dict = {}
    if doi:
        extra["doi_validated"] = True
    return EvidenceItem(
        id=f"doi:10.1000/mod{i}" if doi else f"pmid:{i}",
        title=title, abstract=abstract,
        doi=doi or "", pmid=pmid or "", pmcid="", url=url or "",
        source=source, authors=["A. Author"], year=year, journal="J Test",
        venue_type="journal_article", is_open_access=True, is_primary=True,
        cited_by_count=50, references=[], passage=f"{title}. {abstract}",
        relevance_score=0.8, authority_score=0.6, recency_score=0.7,
        primary_score=1.0, total_score=total, provenance={"first_found_by": source,
                                                          "merged_from": [], "extra": extra},
    )


def _report(answer_md: str, evidence: list[EvidenceItem],
            verification_note: str = "") -> ResearchReport:
    return ResearchReport(
        query=QUERY, answer_md=answer_md, evidence=evidence,
        sources_searched=[SourceSearched(name="europepmc", hits=4, available=True)],
        steps=[StepLog(node="analyze", detail="x")],
        verification=VerificationResult(claims=[], note=verification_note),
        llm_usage={}, config_snapshot=ResearchConfig().snapshot(),
    )


class TestEvidenceScore:
    def test_components_and_label(self):
        e = _evidence(1)
        es = evidence_score(e, QUERY)
        assert set(es["components"]) == {"relevance", "primary_source", "directness",
                                         "authority", "citation_support", "fulltext_availability"}
        assert es["label"] in {"Excellent", "Strong", "Good", "Moderate", "Low"}
        assert 0.0 <= es["total"] <= 1.0

    def test_tangential_scores_lower(self):
        good = _evidence(1, abstract="BRD4 PROTAC degrades the bromodomain protein in cancer cells")
        bad = _evidence(2, abstract="quantum chromodynamics and lattice gauge theory computing")
        assert evidence_score(good, QUERY)["total"] > evidence_score(bad, QUERY)["total"]


class TestSourceRoles:
    def test_role_separation(self):
        mech = _evidence(1, role_hint="ternary complex crystal structure mechanism")
        assert source_role(mech) == "mechanistic"
        review = _evidence(2, role_hint="review")
        review.venue_type = "review"
        assert source_role(review) == "review"
        web = _evidence(3)
        web.source = "searxng"
        web.venue_type = "web"
        web.is_primary = False
        assert source_role(web) == "web"


class TestNarrativeAndFindings:
    DIGEST = (
        "## Bottom line\n\nNo generative synthesis was performed.\n\n"
        "## Key findings (retrieved-source quotes)\n\n"
        "* **BRD4 degrader paper** [1]: \"quote one.\"\n"
        "* **Second paper** [9]: \"quote out of range.\"\n"
        "* A claim without citations here.\n\n"
        "## Conflicts and weak evidence\n\nNo conflicts.\n\n"
        "## Knowledge gaps and limitations\n\nLimited.\n"
    )

    def test_parse_narrative_prefix_headers(self):
        n = parse_narrative(self.DIGEST)
        assert n["bottom_line"].startswith("No generative synthesis")
        assert "[1]" in n["findings"] and "quote one" in n["findings"]
        assert n["gaps"] == "Limited."

    def test_findings_claims_scoped_and_graded(self):
        ev = [_evidence(1), _evidence(2)]
        claims = findings_claims(self.DIGEST, ev)
        # framing lines are excluded; only 3 bullets become claims
        assert len(claims) == 3
        grades = {c["text"][:20]: c["grade"] for c in claims}
        assert any(g in ("Moderate", "Strong") for g in grades.values())  # [1] valid
        unsupported = [c for c in claims if c["grade"] == "Unsupported"]
        assert len(unsupported) >= 1  # [9] out-of-range and no-citation lines


class TestReferencesAndConflicts:
    def test_conflicted_metadata_rejected(self):
        ev = [_evidence(1, doi="10.1000/ok"),
              _evidence(2, doi="10.1000/conflict")]
        ev[1].provenance["extra"]["crossref_title_conflict"] = True
        ev[1].provenance["extra"]["crossref_title"] = "Completely different paper title"
        report = _report("## Bottom line\n\nx\n", ev)
        conflicts = metadata_conflicts(report)
        assert any(c["doi"] == "10.1000/conflict" for c in conflicts)
        rows = reference_rows(report)
        assert all(r["doi"] != "10.1000/conflict" for r in rows)
        assert any(r["doi"] == "10.1000/ok" and r["validation"] == "Crossref-validated" for r in rows)

    def test_deduplicated_references(self):
        a = _evidence(1, doi="10.1000/dup")
        b = _evidence(2, doi="10.1000/dup")
        b.title = a.title
        rows = reference_rows(_report("## Bottom line\n\nx\n", [a, b]))
        assert sum(1 for r in rows if r["doi"] == "10.1000/dup") == 1


class TestExclusions:
    def test_tangential_excluded_with_reasons(self):
        strong = _evidence(1, abstract="BRD4 PROTAC degradation cancer clinical", total=0.9)
        tangential = _evidence(2, source="searxng", url="https://x.io/post",
                               abstract="general blog about kitchen gadgets and travel", total=0.05)
        tangential.title = "Blog: ten gadgets for 2026"
        tangential.passage = tangential.title + ". " + tangential.abstract
        tangential.relevance_score = 0.0
        tangential.is_primary = False
        tangential.venue_type = "web"
        excl = excluded_evidence(QUERY, [strong, tangential], keep=12)
        assert any(e["title"] == tangential.title and any("low topical" in r for r in e["reasons"])
                   for e in excl)


class TestRenderingOrder:
    def test_publication_section_order(self):
        ev = [_evidence(1, doi="10.1000/one"), _evidence(2, doi="10.1000/two")]
        md = _report(
            "## Bottom line\n\nBottom line text here.\n\n"
            "## Key findings\n\n* A solid finding [1,2].\n\n"
            "## Mechanism (interpretation)\n\nMechanism text.\n\n"
            "## Conflicts and weak evidence\n\nNone.\n\n"
            "## Knowledge gaps and limitations\n\nGaps here.\n", ev)
        text = render_publication_report(md)
        sections = [
            "Research question", "Bottom-line answer", "Overall evidence confidence",
            "Key findings", "Best supporting evidence", "Scientific / mechanistic interpretation",
            "Conflicting, weak, or excluded evidence", "Knowledge gaps and limitations",
            "References", "Research provenance", "Appendix — complete retrieved sources",
        ]
        positions = [text.find(s) for s in sections]
        assert all(p >= 0 for p in positions), positions
        assert positions == sorted(positions), "sections out of order"

    def test_trace_only_when_requested(self):
        ev = [_evidence(1)]
        md = _report("## Bottom line\n\nx\n", ev)
        assert "Execution trace" not in render_publication_report(md)
        assert "Execution trace" in render_publication_report(md, include_trace=True)
