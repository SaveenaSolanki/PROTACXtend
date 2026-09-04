"""Cheap/strong LLM reasoning for planning and synthesis.

Every LLM call has a deterministic fallback so the framework always produces
an evidence-grounded answer even with no model available (RESEARCH_LLM_OFF=1
or a dead endpoint). Cost discipline:

  * query planning/routing        -> cheap tier only
  * final synthesis               -> cheap tier; the strong tier is reserved
    for ``complexity == hard`` plans when RESEARCH_STRONG_LLM_* is configured
  * never call the LLM per-document or per-source
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, ValidationError

from protacxtend.llm.json_repair import parse_json_robust
from protacxtend.llm.providers import LLMProvider, ProviderConfig, get_provider
from protacxtend.research.config import (
    ResearchConfig,
    cheap_llm_provider_config,
    strong_llm_provider_config,
)
from protacxtend.research.schemas import SearchPlan
from protacxtend.research.sources import is_biomedical_query  # noqa: F401 (re-export)

logger = logging.getLogger("protacpilot.research.reasoning")

_HARD_HINTS = re.compile(
    r"\b(vs\.?|versus|compare|comparison|controvers|conflict|debate|risk.?benefit|"
    r"meta.?analysis|systematic review|latest|state of the art|evidence.?based|"
    r"guideline|mechanism of action|adverse|efficacy|dose|regulatory|safety)\b",
    re.I,
)


def ask_structured(schema: type[BaseModel], system: str, user: str,
                   config: ProviderConfig) -> tuple[BaseModel | None, str]:
    """Provider-agnostic structured chat (JSON repair + validation + one retry)."""
    if config is None:
        return None, "no provider config"
    try:
        provider: LLMProvider = get_provider(config.provider)
        schema_json = schema.model_json_schema()
        raw = provider.chat_raw(system, user, schema_json, config)
        payload = parse_json_robust(raw)
        obj = schema.model_validate(payload)
        return obj, ""
    except Exception as exc:
        try:
            raw2 = provider.chat_raw(system + "\nReturn ONLY valid JSON matching the schema.",
                                     user, schema.model_json_schema(), config)
            obj2 = schema.model_validate(parse_json_robust(raw2))
            return obj2, ""
        except Exception as exc2:
            return None, f"{type(exc).__name__}: {str(exc2)[:180]}"


def ask_text(system: str, user: str, config: ProviderConfig,
             max_chars: int = 6_000) -> tuple[str, str]:
    """Free-text chat (final synthesis); returns (text, error)."""
    if config is None:
        return "", "no provider config"
    try:
        provider = get_provider(config.provider)
        raw = provider.chat_raw(system, user, {}, config)
        return (raw or "")[:max_chars], ""
    except Exception as exc:
        return "", f"{type(exc).__name__}: {str(exc)[:180]}"


# ── deterministic planning fallback ─────────────────────────────────────────

def _estimate_complexity(query: str) -> str:
    n_words = len(re.findall(r"\S+", query or ""))
    if _HARD_HINTS.search(query or "") or n_words > 28:
        return "hard"
    if n_words > 14:
        return "moderate"
    return "simple"


def plan_deterministic(query: str, web_available: bool) -> SearchPlan:
    dom = "biomedical" if is_biomedical_query(query) else "general"
    return SearchPlan(
        sub_queries=[query],
        domain=dom,
        complexity=_estimate_complexity(query),
        focus=query,
        include_web=web_available and dom == "general",
        notes="deterministic plan (LLM unavailable/disabled)",
    )


def plan_query(query: str, cfg: ResearchConfig, web_available: bool) -> tuple[SearchPlan, bool, str]:
    """Cheap-LLM query decomposition + domain/complexity routing."""
    dom_hint = "biomedical" if is_biomedical_query(query) else "general"
    system = (
        "You are a scientific search planner. Split the user question into at most 3 "
        "parallel, searchable sub-queries (plain phrases, no operators). "
        "domain is 'biomedical' when it concerns biology/chemistry/medicine/pharma "
        f"(user query looks {dom_hint}); complexity is simple|moderate|hard. "
        "include_web=true only when general web sources are required. "
        "Return JSON only."
    )
    if cfg.llm_always_off:
        return plan_deterministic(query, web_available), False, "LLM disabled (RESEARCH_LLM_OFF=1)"
    obj, err = ask_structured(SearchPlan, system, query, cheap_llm_provider_config(cfg))
    if obj is None:
        plan = plan_deterministic(query, web_available)
        plan.notes = f"deterministic plan (LLM failed: {err[:120]})"
        return plan, False, err
    if not obj.sub_queries:
        obj.sub_queries = [query]
    # clamp to budget & respect config include_web off
    obj.sub_queries = obj.sub_queries[: cfg.max_sub_queries]
    if not web_available:
        obj.include_web = False
    return obj, True, ""


# ── synthesis ───────────────────────────────────────────────────────────────

def choose_synthesis_config(cfg: ResearchConfig, plan: SearchPlan) -> tuple[ProviderConfig, bool]:
    """Return (config, used_strong). Strong only for hard plans when enabled."""
    strong = strong_llm_provider_config(cfg)
    if strong is not None and cfg.use_strong_llm and plan.complexity == "hard":
        return strong, True
    return cheap_llm_provider_config(cfg), False


def synthesis_prompt(query: str, evidence: list[dict[str, Any]]) -> tuple[str, str]:
    numbered = []
    for i, e in enumerate(evidence, start=1):
        ref = e.get("doi") or e.get("url") or e.get("pmid") or e.get("id")
        journal = e.get("journal") or ""
        year = e.get("year") or ""
        header = (f"[{i}] {e.get('title','')} ({journal} {year}) ref: {ref}\n")
        text = (e.get("passage") or e.get("abstract") or e.get("fulltext") or "")[:900]
        numbered.append(header + text)
    system = (
        "You are a careful scientific evidence synthesizer writing a concise "
        "evidence review. Rules:\n"
        "1. Answer ONLY from the numbered evidence below.\n"
        "2. Never invent a citation, DOI, PMID or result. Every factual claim "
        "must end with citation tokens like [1] or [2,4] referencing evidence "
        "numbers from the provided list.\n"
        "3. If the evidence cannot answer part of the question, say so explicitly.\n"
        "4. Use EXACTLY these Markdown section headers, in this order:\n"
        "   ## Bottom line\n"
        "   ## Key findings\n"
        "   ## Mechanism (interpretation)\n"
        "   ## Conflicts and weak evidence\n"
        "   ## Knowledge gaps and limitations\n"
        "5. Bottom line: 1-2 short paragraphs, at most ~200 words. Key findings: "
        "one bullet per claim; EVERY bullet carries its own [n] tokens. Mechanism: "
        "explicit model interpretation grounded in evidence with [n]. Conflicts: "
        "surface disagreements or weak spots among the evidence. Gaps: what the "
        "evidence cannot answer.\n"
        "6. Output plain Markdown. No preamble before the first header.\n\n"
        "Evidence:\n" + "\n\n".join(numbered)
    )
    user = f"Question: {query}\n\nSynthesize an evidence-grounded answer with citations."
    return system, user


def deterministic_synthesis(query: str, evidence: list[dict[str, Any]]) -> str:
    """No-LLM fallback: honest, sectioned evidence digest. Quotes are short and
    explicitly labelled as retrieved-source quotes — never framework claims."""
    if not evidence:
        return ("## Bottom line\n\nNo retrievable evidence was found (all sources "
                "unavailable or empty). No answer is fabricated when evidence is "
                "insufficient.\n\n## Knowledge gaps and limitations\n\n- All configured "
                "sources returned no usable records for this query.\n")
    top = evidence[0]
    meta = ", ".join(x for x in (top.get("journal"), str(top.get("year", ""))) if x)
    lines = ["## Bottom line", "",
             "A generative synthesis was **not** performed (no LLM configured or "
             "unavailable), so no model-derived bottom line is claimed here. The "
             "highest-ranked retrieved source is "
             f"\"{top.get('title', '')}\" ({meta}). "
             "The key-finding bullets below are direct short quotes from retrieved "
             "sources — treat them as retrieved evidence, not framework interpretation.",
             "", "## Key findings (retrieved-source quotes)", ""]
    for i, e in enumerate(evidence, start=1):
        meta_i = ", ".join(x for x in (e.get("journal"), str(e.get("year", ""))) if x)
        title = e.get("title", "") or ""
        text = (e.get("passage") or e.get("abstract") or "")
        # first sentence; drop a leading duplication of the title
        m = re.search(r"(?<=[.!?])\s+", text[:800])
        sentence = (text[: m.start() + 1] if m else text[:300])
        sentence = " ".join(sentence.split()).strip()
        t = " ".join(title.split()).strip()
        if sentence.lower().startswith(t.lower()) and len(t) > 10:
            sentence = sentence[len(t):].strip()
        sentence = sentence.strip(":;-, \"")
        if len(sentence) < 25:
            sentence = "See the reference record for full content."
        lines.append(f"* **{title[:160]}** ({meta_i}) [{i}]: \"{sentence[:260]}\"")
    lines += ["", "## Conflicts and weak evidence", "",
              "No claim-level conflicts were evaluated without an LLM; see the "
              "verification report for unsupported claims and the excluded-evidence "
              "appendix for tangential sources.",
              "", "## Knowledge gaps and limitations", "",
              "* Retrieval was limited to the configured sources and query "
              "formulation.\n"
              "* No generative synthesis was performed; quotes must be verified "
              "against the primary sources before any claim is relied upon.\n"
              "* Numbers, effect sizes and conclusions should be traced to the "
              "referenced DOI/PMID records."]
    return "\n".join(lines)


def synthesize(query: str, evidence: list[dict[str, Any]], cfg: ResearchConfig,
               plan: SearchPlan) -> tuple[str, bool, dict[str, Any]]:
    """Synthesize the answer. (answer_md, used_strong, usage)"""
    usage: dict[str, Any] = {"cheap_calls": 0, "strong_calls": 0, "est_tokens_in": 0,
                             "est_tokens_out": 0}
    if cfg.llm_always_off or not evidence:
        if not evidence:
            return deterministic_synthesis(query, []), False, usage
        return deterministic_synthesis(query, evidence), False, usage

    chosen, used_strong = choose_synthesis_config(cfg, plan)
    system, user = synthesis_prompt(query, evidence)
    out, err = ask_text(system, user, chosen)
    if not out.strip():
        logger.warning("LLM synthesis failed (%s) -> deterministic digest", err)
        return deterministic_synthesis(query, evidence), used_strong, usage

    if used_strong:
        usage["strong_calls"] = 1
    else:
        usage["cheap_calls"] = 1
    usage["est_tokens_in"] = len(system.split()) + len(user.split())
    usage["est_tokens_out"] = len(out.split())
    usage["provider"] = f"{chosen.provider}/{chosen.model}"
    return out.strip(), used_strong, usage
