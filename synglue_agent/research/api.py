"""Unified deep-research API.

``await deep_research(query)`` returns a :class:`ResearchReport` with the
answer, evidence, claims/citations, sources searched and a full search trace.

Sync convenience: ``deep_research_sync(query)``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from synglue_agent.research.config import ResearchConfig
from synglue_agent.research.graph import run_research_graph
from synglue_agent.research.schemas import ResearchReport

logger = logging.getLogger("protacpilot.research.api")


def _slug(query: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", (query or "").lower()).strip("_")[:60]
    return s or "research"


async def deep_research(query: str, *, config: ResearchConfig | None = None,
                        clients: dict[str, Any] | None = None,
                        persist_trace: bool | None = None,
                        trace_dir: Path | None = None) -> ResearchReport:
    """Run the LangGraph research pipeline and return a structured report.

    Args:
        query: the research question.
        config: ResearchConfig (env defaults when None).
        clients: optional pre-built client registry (used by tests).
        persist_trace: write the reproducible trace JSON when True.
        trace_dir: override trace directory.
    """
    cfg = config or ResearchConfig.from_env()
    final = await run_research_graph(query, config=cfg, clients=clients)
    payload = final.get("final_report")
    if payload is None:
        # finalize node should always run; rebuild minimal report defensively
        payload = {
            "query": query,
            "answer_md": final.get("answer_md", ""),
            "evidence": [e.model_dump() for e in final.get("evidence", [])],
            "steps": final.get("steps", []),
            "config_snapshot": cfg.snapshot(),
        }
    report = ResearchReport.model_validate(payload)

    do_persist = cfg.trace_persist if persist_trace is None else persist_trace
    if do_persist:
        persist_path = (trace_dir or cfg.trace_dir)
        try:
            persist_path.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = persist_path / f"{_slug(query)}__{stamp}.json"
            path.write_text(json.dumps(report.model_dump(), indent=2, default=str),
                            encoding="utf-8")
            repro = dict(report.reproducible or {})
            repro["trace_path"] = str(path)
            report.reproducible = repro
            logger.info("research trace written: %s", path)
        except Exception as exc:
            logger.warning("trace persistence failed: %s", exc)
    return report


def deep_research_sync(query: str, **kwargs) -> ResearchReport:
    """Synchronous wrapper around :func:`deep_research`."""
    return asyncio.run(deep_research(query, **kwargs))


def answer_to_markdown(report: ResearchReport) -> str:
    """Render the full report as Markdown (answer + references + sources)."""
    lines = [f"# Research: {report.query}", "", report.answer_md or "*no answer*", ""]
    if report.evidence:
        lines += ["## Evidence sources", ""]
        for i, e in enumerate(report.evidence, start=1):
            ref = e.doi or e.url or e.pmid
            journal = f" ({e.journal})" if e.journal else ""
            year = f", {e.year}" if e.year else ""
            lines.append(f"{i}. **{e.title}**{journal}{year} — "
                         f"[{ref}]({ref}) · source={e.source} · "
                         f"scores=rel {e.relevance_score:.2f}/auth {e.authority_score:.2f}")
    if report.verification.claims:
        unsupported = report.verification.unsupported_count
        lines += ["", f"## Claim verification: {len(report.verification.claims)} claims, "
                      f"{unsupported} unsupported"]
    if report.sources_searched:
        lines += ["", "## Sources searched", ""]
        for s in report.sources_searched:
            state = f"{s.hits} hits" if s.available else ("error" if s.error else "skipped")
            lines.append(f"- **{s.label}** ({s.name}): {state}"
                         + (f" — {s.error[:120]}" if s.error else ""))
    if report.steps:
        lines += ["", "## Search trace", ""]
        for step in report.steps:
            lines.append(f"- `{step.node}` ({step.duration_ms:.0f} ms, {step.items} items): "
                         f"{step.detail[:200]}")
    return "\n".join(lines)
