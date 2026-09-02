"""Publication-quality research report composition (deterministic analysis).

Turns a ResearchReport into a concise scientific evidence review:

  * interpretable Evidence Score (relevance / primary-source status / directness
    / authority / citation support / full-text availability)
  * source role separation (primary studies, mechanistic/structural studies,
    reviews, web/other)
  * claim grading: Strong | Moderate | Weak | Unsupported
  * tangential-source detection + exclusions with reasons
  * title<->DOI metadata-conflict flagging (from Crossref validation)
  * the exact default output order required for the CLI report

Everything here is deterministic and derived only from retrieved data —
it never fabricates citations, DOIs, PMIDs or results.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional

from synglue_agent.research.config import ResearchConfig
from synglue_agent.research.retrieval import find_citation_indices
from synglue_agent.research.schemas import EvidenceItem, ResearchReport

logger = logging.getLogger("protacpilot.research.reporting")

_STOP = set("""a an the and or but of in on at to for with by from as is are was were be been
being this that these those it its about between among into onto during before after under
over within without across also may can could would should does did do not no yes vs versus
using used via include includes including such more most less than then their there here
which who whom what when where how why if then other some any all both each few new
known use study studies show shows found report reports suggest suggests evidence data
result results effect effects role roles mechanism mechanisms model models protein proteins
cell cells target targets ligand ligands e3 po1 po2 protac chimeric degradation degraders
degrade degrades""".split())


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in _STOP and len(t) > 2}


# ── interpretable evidence score ────────────────────────────────────────────

def evidence_score(item: EvidenceItem, query: str) -> dict[str, Any]:
    """Interpretable Evidence Score with explicit component labels."""
    q_tokens = _tokens(query)
    doc_text = f"{item.title} {item.title} {item.abstract or item.passage}"  # title weighted 2x
    d_tokens = _tokens(doc_text)
    directness = 0.0
    if q_tokens:
        overlap = len(q_tokens & d_tokens)
        directness = overlap / max(len(q_tokens), 1)
    directness = max(0.0, min(1.0, directness))

    primary = 1.0 if (item.is_primary and item.venue_type in ("journal_article", "review", "journal", "")) else (0.8 if item.is_primary else (0.5 if item.venue_type == "preprint" else 0.3))
    authority = min(1.0, math.log1p(item.cited_by_count or 0) / 9.0) * 0.7 + (0.3 if item.journal else 0.0)
    citation_support = min(1.0, math.log1p(item.cited_by_count or 0) / 9.0) if item.cited_by_count is not None else 0.3
    fulltext = 1.0 if item.fulltext else (0.7 if item.is_open_access else (0.5 if item.abstract else 0.2))

    score = (
        0.30 * (item.relevance_score or 0.0)
        + 0.20 * primary
        + 0.20 * directness
        + 0.15 * authority
        + 0.10 * citation_support
        + 0.05 * fulltext
    )
    label = ("Excellent" if score >= 0.75 else "Strong" if score >= 0.6
             else "Good" if score >= 0.45 else "Moderate" if score >= 0.3 else "Low")
    return {
        "total": round(score, 3),
        "label": label,
        "components": {
            "relevance": round(item.relevance_score or 0.0, 3),
            "primary_source": round(primary, 3),
            "directness": round(directness, 3),
            "authority": round(authority, 3),
            "citation_support": round(citation_support, 3),
            "fulltext_availability": round(fulltext, 3),
        },
    }


# ── source role separation ──────────────────────────────────────────────────

_MECHANISTIC_HINTS = re.compile(
    r"\b(ternary|binary|crystal|cryo-?em|structure|structural|mechanism|cooperativ|"
    r"molecular dynamics|binding|affinity|biophys|equilibrium|hook|occupancy|stoichiometr|"
    r"ubiquitin|processive|kinase|kinetic|thermodynam|dose-?response|bivalent|linker length|"
    r"conformational|allosteric)\b", re.I)


def source_role(item: EvidenceItem) -> str:
    """Classify a source: primary | mechanistic | review | preprint | web | other."""
    vt = (item.venue_type or "").lower()
    text = f"{item.title} {item.abstract or ''}"
    if item.source in ("searxng", "web") or vt in ("web", "news"):
        return "web"
    if vt == "preprint" or (item.source == "openalex" and not item.is_primary and "preprint" in text.lower()):
        return "preprint"
    if vt in ("review", "review-article") or re.search(r"\breview\b", item.title, re.I):
        return "review"
    if item.is_primary and _MECHANISTIC_HINTS.search(text):
        return "mechanistic"
    if item.is_primary:
        return "primary"
    return "other"


# ── claim grading ───────────────────────────────────────────────────────────

def grade_claims(verification: dict[str, Any], evidence: list[EvidenceItem]) -> list[dict[str, Any]]:
    """Classify every claim as Strong|Moderate|Weak|Unsupported using the
    quality of the evidence actually cited by that claim."""
    claims = []
    raw_claims = verification.get("claims", []) if isinstance(verification, dict) else getattr(verification, "claims", [])
    for claim in raw_claims:
        c = claim.model_dump() if hasattr(claim, "model_dump") else dict(claim)
        indices = [i for i in c.get("citation_indices", []) if 1 <= i <= len(evidence)]
        if not indices:
            claims.append({**c, "grade": "Unsupported"})
            continue
        cited = [evidence[i - 1] for i in indices]
        mean_q = sum(e.total_score for e in cited) / max(len(cited), 1)
        has_primary = any(e.is_primary and e.venue_type in ("journal_article", "review") for e in cited)
        has_review_only = all(source_role(e) == "review" for e in cited)
        if len(cited) >= 2 and mean_q >= 0.55 and has_primary:
            grade = "Strong"
        elif len(cited) >= 1 and mean_q >= 0.45 and has_primary:
            grade = "Moderate"
        elif len(cited) >= 1 and not has_review_only:
            grade = "Weak"
        else:
            grade = "Weak" if cited else "Unsupported"
        claims.append({**c, "grade": grade, "mean_evidence_total": round(mean_q, 3)})
    return claims


def overall_confidence(verification: dict[str, Any], graded: list[dict[str, Any]],
                       evidence: list[EvidenceItem]) -> dict[str, Any]:
    """Aggregate evidence confidence label + one-line basis."""
    claims = [c for c in graded if c.get("grade") != "Unsupported"]
    if claims:
        strong = sum(1 for c in claims if c["grade"] == "Strong")
        moderate = sum(1 for c in claims if c["grade"] == "Moderate")
        share = (strong + 0.6 * moderate) / len(claims)
    else:
        share = 0.0
    top_q = max((e.total_score for e in evidence), default=0.0)
    n_sci = sum(1 for e in evidence if e.source in ("europepmc", "pubmed", "openalex"))
    basis = []
    if claims:
        basis.append(f"{strong}/{len(claims)} Strong claims, {moderate} Moderate")
    basis.append(f"top evidence score {top_q:.2f}, {n_sci} scientific sources")
    if share >= 0.7 and top_q >= 0.6:
        label = "High"
    elif share >= 0.45 and top_q >= 0.35:
        label = "Moderate"
    else:
        label = "Low"
    return {"label": label, "basis": "; ".join(basis) or "insufficient evidence"}


# ── tangential / exclusion detection ────────────────────────────────────────

def excluded_evidence(query: str, evidence: list[EvidenceItem],
                      keep: int = 12) -> list[dict[str, Any]]:
    """Detect tangential/weak sources and return exclusions with reasons.

    The top ``keep`` by Evidence Score stay; everything below a defensible
    floor (low relevance AND no primary status AND no full text) is listed as
    excluded, each with an explicit reason.
    """
    scored = []
    for e in evidence:
        es = evidence_score(e, query)
        scored.append((e, es))
    scored.sort(key=lambda x: x[1]["total"], reverse=True)
    exclusions = []
    for idx, (e, es) in enumerate(scored):
        if idx < keep and es["total"] >= 0.30:
            continue
        reasons = []
        if es["components"]["relevance"] < 0.35:
            reasons.append("low topical relevance to the question")
        if not e.is_primary:
            reasons.append("not a primary scientific source")
        if not (e.abstract or e.fulltext):
            reasons.append("no abstract/full text to support claims")
        if e.source == "searxng" and not es["components"]["directness"]:
            reasons.append("web hit without direct topical match")
        if not reasons:
            reasons.append("ranked below the top evidence cut-off")
        exclusions.append({
            "evidence_id": e.id,
            "title": e.title,
            "doi": e.doi, "pmid": e.pmid, "url": e.url,
            "evidence_score": es,
            "role": source_role(e),
            "reasons": reasons,
        })
    return exclusions


# ── reference/DOI conflict handling ─────────────────────────────────────────

def display_ref_id(e: EvidenceItem) -> tuple[str, str]:
    """User-visible persistent id. A DOI is only DISPLAYED when it has been
    Crossref/title-validated; otherwise the record is shown by PMID / URL /
    evidence id (never an unvalidated DOI)."""
    extra = e.provenance.get("extra") or {}
    if e.doi and extra.get("doi_validated") and not extra.get("crossref_title_conflict"):
        return f"doi:{e.doi}", "doi"
    if e.pmid:
        return f"PMID:{e.pmid}", "pmid"
    if e.url:
        return e.url, "url"
    return e.id, "id"


def metadata_conflicts(report: ResearchReport) -> list[dict[str, Any]]:
    """Flag sources whose title<->DOI agreement could not be confirmed (or was
    contradicted) by Crossref validation. Unvalidated DOIs are never displayed
    in references/tables (see display_ref_id)."""
    out = []
    for e in report.evidence:
        extra = e.provenance.get("extra") or {}
        conflict = extra.get("crossref_title_conflict")
        validated = extra.get("doi_validated")
        if conflict:
            out.append({"evidence_id": e.id, "title": e.title, "doi": e.doi,
                        "issue": "Crossref metadata title mismatch (rejected from reference table)",
                        "crossref_title": extra.get("crossref_title", "")})
        elif e.doi and not validated:
            lbl, _kind = display_ref_id(e)
            out.append({"evidence_id": e.id, "title": e.title, "doi": e.doi,
                        "issue": f"DOI not Crossref/title-validated; displayed as {lbl} instead",
                        "displayed_as": lbl, "status": "registry_supplied_deferred"})
    return out


def reference_rows(report: ResearchReport) -> list[dict[str, Any]]:
    """Numbered references. Only Crossref/title-validated DOIs are displayed;
    otherwise PMID / URL / evidence-id is shown (never an unvalidated DOI).
    DOI-conflicted entries are rejected entirely (see metadata_conflicts)."""
    rows = []
    seen: set[str] = set()
    for i, e in enumerate(report.evidence, start=1):
        extra = e.provenance.get("extra") or {}
        if extra.get("crossref_title_conflict"):
            continue  # reject metadata-conflicted entries
        label, kind = display_ref_id(e)
        key = (e.doi or "").lower() or e.pmid or e.url or e.title.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        if kind == "doi":
            validation = "Crossref-validated"
        elif kind == "pmid":
            validation = "PMID"
        else:
            validation = "URL/evidence-id (DOI deferred until Crossref-validated)"
        rows.append({
            "index": i,
            "title": e.title,
            "authors": e.authors[:6],
            "year": e.year,
            "journal": e.journal,
            "doi": e.doi, "pmid": e.pmid, "url": e.url,
            "display_id": label,
            "validation": validation,
            "source": e.source,
            "role": source_role(e),
        })
    return rows


# ── findings-only claim grading (Key-findings section) ─────────────────────

def findings_claims(answer_md: str, evidence: list[EvidenceItem]) -> list[dict[str, Any]]:
    """Grade only the bullet claims under the 'Key findings' section — framing
    lines (bottom line, headers, gaps) are not treated as findings."""
    findings = parse_narrative(answer_md)["findings"]
    out: list[dict[str, Any]] = []
    for raw in findings.splitlines():
        line = raw.strip().lstrip("-#*• \t").replace("**", "").strip()
        if not line:
            continue
        idx = [c for c in find_citation_indices(line) if 1 <= c <= len(evidence)]
        cited = [evidence[i - 1] for i in idx]
        mean_q = sum(e.total_score for e in cited) / max(len(cited), 1)
        has_primary = any(e.is_primary and e.venue_type in ("journal_article", "review") for e in cited)
        if not idx:
            grade = "Unsupported"
        elif len(idx) >= 2 and mean_q >= 0.55 and has_primary:
            grade = "Strong"
        elif mean_q >= 0.45 and has_primary:
            grade = "Moderate"
        else:
            grade = "Weak"
        out.append({
            "claim_id": f"finding_{len(out) + 1}",
            "text": line,
            "citation_indices": idx,
            "status": "supported" if idx else "unsupported",
            "grade": grade,
            "mean_evidence_total": round(mean_q, 3),
        })
    return out

_NARRATIVE_HEADERS = [
    "## Bottom line",
    "## Key findings",
    "## Conflicts and weak evidence",
    "## Knowledge gaps and limitations",
    "## Mechanism",
    "## Mechanism (interpretation)",
    "## Confidence",
    "## Overall evidence confidence",
]


def parse_narrative(answer_md: str) -> dict[str, str]:
    """Split a sectioned answer into {bottom_line, findings, mechanism,
    conflicts, gaps}. Header matching is prefix-based so variants like
    '## Key findings (retrieved-source quotes)' are recognised."""
    parts: dict[str, str] = {}
    current = "preamble"
    buf: list[str] = []
    for line in (answer_md or "").splitlines():
        stripped = line.strip()
        matched = None
        for h in _NARRATIVE_HEADERS:
            if stripped == h or stripped.startswith(h + " "):
                matched = h
                break
        if matched:
            parts[current] = "\n".join(buf).strip()
            current = matched
            buf = []
        else:
            buf.append(line)
    parts[current] = "\n".join(buf).strip()

    def take(*names: str) -> str:
        for n in names:
            if parts.get(n):
                return parts[n]
        return ""

    preamble = parts.get("preamble", "")
    return {
        "bottom_line": take("## Bottom line") or preamble,
        "findings": take("## Key findings"),
        "mechanism": take("## Mechanism (interpretation)", "## Mechanism"),
        "conflicts": take("## Conflicts and weak evidence"),
        "gaps": take("## Knowledge gaps and limitations"),
    }


# ── publication report renderer (CLI default) ───────────────────────────────

def render_publication_report(report: ResearchReport, cfg: ResearchConfig | None = None,
                              *, include_trace: bool = False) -> str:
    """Compose the terminal report in the required order: query, bottom line,
    confidence, key findings, best-evidence table, mechanism, conflicts/weak
    evidence, gaps, references (DOI/PMID validated), compact provenance.
    Complete retrieved-source lists go to the appendix + --json only."""
    cfg = cfg or ResearchConfig.from_env()
    narrative = parse_narrative(report.answer_md)
    graded = findings_claims(report.answer_md, report.evidence)
    confidence = overall_confidence({}, graded, report.evidence)
    exclusions = excluded_evidence(report.query, report.evidence, keep=12)
    conflicts = metadata_conflicts(report)
    refs = reference_rows(report)

    synthesis_kind = "LLM synthesis" if (report.llm_usage.get("provider") or report.used_strong_llm) else "retrieved-evidence digest"
    out: list[str] = []

    # 1. Query
    out += ["# Research question", "", f"> {report.query}", ""]

    # 2. Bottom-line answer (model interpretation, clearly marked)
    out += ["## Bottom-line answer", f"*({synthesis_kind}; model interpretation is clearly separated from retrieved evidence)*", ""]
    bl = narrative["bottom_line"].strip()
    out.append(bl if bl else "*(No bottom line — insufficient evidence.)*")
    out.append("")

    # 3. Overall evidence confidence
    out += ["## Overall evidence confidence", "", f"**{confidence['label']}** — {confidence['basis']}", ""]

    # 4. Key findings as graded claims (only the Key-findings section)
    out += ["## Key findings", ""]
    if graded:
        is_retrieved = "retrieved-source quotes" in (narrative["findings"] or "") or not (report.llm_usage.get("provider") or report.used_strong_llm)
        tag = "retrieved-source quotes (no LLM synthesis)" if is_retrieved else "synthesized claims + verified citations"
        out.append(f"*({tag})*")
        out.append("")
        for c in graded:
            marker = {"Strong": "🟢", "Moderate": "🟡", "Weak": "🟠", "Unsupported": "🔴"}.get(c.get("grade", "Unsupported"), "•")
            out.append(f"- {marker} **{c.get('grade', 'Unsupported')}** — {c.get('text', '')}")
    else:
        out.append("_No claim-level findings were extracted._")
    out.append("")
    top = []
    for e in report.evidence[:30]:
        es = evidence_score(e, report.query)
        top.append((e, es))
    top.sort(key=lambda x: x[1]["total"], reverse=True)
    top = top[:12]
    out += ["## Best supporting evidence", "",
            "| # | Source (Year, Venue) | Role | Evidence Score | DOI/PMID |",
            "|---|---|---|---|---|"]
    if top:
        for e, es in top:
            venue = e.journal or e.venue_type
            label, kind = display_ref_id(e)
            ref_id = (f"[doi](https://doi.org/{e.doi})" if kind == "doi" else
                      f"PMID {e.pmid}" if kind == "pmid" else
                      f"[url]({label})" if kind == "url" else label)
            out.append(f"| {es['total']:.2f} | **{e.title[:90]}** ({e.year}, {venue[:36]}) | {source_role(e)} | {es['label']} | {ref_id[:64]} |")
    else:
        out.append("| — | _no evidence above threshold_ | — | — | — |")
    out.append("")

    # 6. Scientific / mechanistic interpretation (clearly model interpretation)
    out += ["## Scientific / mechanistic interpretation", "",
            "_Model interpretation_ — based only on the retrieved evidence above."]
    mech = narrative["mechanism"].strip()
    out.append(mech if mech else "_No mechanistic interpretation generated (no LLM); see retrieved primary sources._")
    out.append("")

    # 7. Conflicts / weak / excluded evidence
    out += ["## Conflicting, weak, or excluded evidence", ""]
    weak = [c for c in graded if c.get("grade") in ("Weak", "Unsupported")]
    if weak:
        out += ["**Weak or unsupported claims**"]
        for c in weak:
            out.append(f"- {c['grade']}: {c.get('text', '')[:200]}")
    nc = narrative["conflicts"].strip()
    if nc:
        out += ["", "**Model-noted conflicts**", "", nc]
    if conflicts:
        out += ["", "**Metadata conflicts (title↔DOI) — rejected from reference table**"]
        for c in conflicts:
            out.append(f"- {c['title'][:90]} doi:{c['doi']} — {c['issue']}")
    if exclusions:
        out += ["", "**Excluded / tangential sources (with reasons)**"]
        for x in exclusions[:8]:
            out.append(f"- {x['title'][:90]} — {'; '.join(x['reasons'])}")
    out += ["", "Retrieved evidence is never hidden; the complete source list is in the appendix "
               "and in the `--json` output."]
    out.append("")

    # 8. Knowledge gaps and limitations
    out += ["## Knowledge gaps and limitations", ""]
    gaps = narrative["gaps"].strip()
    out.append(gaps if gaps else "_No explicit gap analysis generated._")
    out += ["", f"- Retrieval completeness limited to: {', '.join(s.label for s in report.sources_searched)}.",
            f"- {len(report.evidence)} deduplicated evidence items after {report.iterations_used} search "
            f"{'iteration' if report.iterations_used == 1 else 'iterations'}."]
    if not report.llm_usage.get("provider") and not report.used_strong_llm:
        out.append("- No LLM synthesis ran — bottom line is intentionally absent.")
    out.append("")

    # 9. References with validated DOI/PMID
    out += ["## References", ""]
    if refs:
        for r in refs:
            authors = (", ".join(r["authors"][:3]) + (" et al." if len(r["authors"]) > 3 else "")) if r["authors"] else "n/a"
            year = r["year"] or "n.d."
            out.append(f"{r['index']}. {authors} ({year}). *{r['title']}*. {r['journal']}. {r['display_id']} ({r['validation']})")
    else:
        out.append("_No validated references available._")
    out.append("")

    # 10. Compact research provenance
    out += ["## Research provenance", ""]
    llm_note = f"{report.llm_usage.get('provider', 'none')}" if report.llm_usage.get("provider") else "no LLM (digest)"
    out.append(f"- **LLM tier:** {llm_note}{' [strong reserved/used]' if report.used_strong_llm else ''}")
    out.append(f"- **Sources queried:** {', '.join(f'{s.name} ({s.hits})' for s in report.sources_searched)}")
    out.append(f"- **Dedup:** {len(report.evidence)} unique evidence after DOI/PMID/URL/title dedup")
    out.append(f"- **Rerank model:** {report.evidence[0].rerank_model if report.evidence else 'n/a'}")
    trace_path = (report.reproducible or {}).get("trace_path", "")
    out.append(f"- **Trace:** `{trace_path}`" if trace_path else "- **Trace:** not persisted (use without --no-trace)")

    if include_trace:
        out += ["", "## Execution trace", ""]
        for st in report.steps:
            out.append(f"- `{st.node}` ({st.duration_ms:.0f} ms, {st.items} items): {st.detail[:220]}")
        out.append("")

    # Appendix: complete retrieved source list (one-liners, no raw fragments)
    out += ["", "## Appendix — complete retrieved sources", ""]
    for i, e in enumerate(report.evidence, start=1):
        id_part = e.doi or e.pmid or e.url or e.id
        out.append(f"{i}. {e.source}: {e.title[:120]} — {id_part[:80]} (score {e.total_score:.2f})")

    return "\n".join(out)
