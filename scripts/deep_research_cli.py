#!/usr/bin/env python3
"""Scientific deep-research CLI (publication-quality evidence review).

Retrieval: Europe PMC/PubMed/OpenAlex/Crossref/SearXNG/Crawl4AI via LangGraph,
with local reranking, DOI/PMID/title/URL dedup, Crossref metadata validation,
claim-level verification and cheap/strong LLM synthesis.

The default terminal output is a concise scientific evidence review in this
order: query -> bottom-line answer -> overall evidence confidence -> key
findings -> best supporting evidence table -> mechanistic interpretation ->
conflicting/weak/excluded evidence -> knowledge gaps -> validated references ->
compact provenance. Execution traces stay hidden unless --trace is given; use
--json for the complete machine-readable report (all retrieved sources are
kept there and in the appendix of the markdown report).

Examples:
  python scripts/deep_research_cli.py "PROTAC BRD4 degradation cancer" --no-llm
  python scripts/deep_research_cli.py "..." --trace --json > report.json
  SEARXNG_URL=http://127.0.0.1:8888 python scripts/deep_research_cli.py "..."
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", help="research question (or use --query)")
    ap.add_argument("--query", dest="query_opt", help="research question")
    ap.add_argument("--trace", action="store_true",
                    help="append the detailed execution trace to the terminal report")
    ap.add_argument("--json", action="store_true",
                    help="print the complete machine-readable report (incl. trace + full sources)")
    ap.add_argument("--no-llm", action="store_true", help="force deterministic digest (RESEARCH_LLM_OFF=1)")
    ap.add_argument("--no-trace", action="store_true", help="do not persist the trace JSON")
    ap.add_argument("--max-iterations", type=int, default=None, help="reformulation budget")
    ap.add_argument("--top-k", type=int, default=None, help="evidence items used in synthesis")
    ap.add_argument("--out", default="", help="write the Markdown review to this file")
    args = ap.parse_args()

    query = (args.query_opt or args.query or "").strip()
    if not query:
        ap.error("provide a query (positional or --query)")
    if args.no_llm:
        import os
        os.environ["RESEARCH_LLM_OFF"] = "1"

    from protacxtend.research import ResearchConfig, deep_research
    from protacxtend.research.reporting import render_publication_report

    cfg = ResearchConfig.from_env()
    if args.max_iterations is not None:
        cfg.max_iterations = args.max_iterations
    if args.top_k is not None:
        cfg.top_k_evidence = args.top_k

    report = asyncio.run(deep_research(query, config=cfg, persist_trace=not args.no_trace))

    if args.json:
        payload = report.model_dump()
        # machine-readable analyses that support the rendered review
        from protacxtend.research.reporting import (
            evidence_score,
            excluded_evidence,
            grade_claims,
            metadata_conflicts,
            overall_confidence,
            parse_narrative,
            reference_rows,
            source_role,
        )
        payload["_analyses"] = {
            "narrative": parse_narrative(report.answer_md),
            "graded_claims": grade_claims(dict(report.verification), report.evidence),
            "overall_confidence": overall_confidence(dict(report.verification),
                                                     grade_claims(dict(report.verification),
                                                                  report.evidence), report.evidence),
            "references": reference_rows(report),
            "metadata_conflicts": metadata_conflicts(report),
            "excluded_evidence": excluded_evidence(report.query, report.evidence),
            "evidence_scores": {e.id: evidence_score(e, report.query) for e in report.evidence},
            "source_roles": {e.id: source_role(e) for e in report.evidence},
        }
        print(json.dumps(payload, indent=2, default=str))
        return 0

    print(render_publication_report(report, cfg, include_trace=args.trace))
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_publication_report(report, cfg, include_trace=args.trace),
                            encoding="utf-8")
        print(f"\n[written] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
