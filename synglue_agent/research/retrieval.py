"""Evidence processing: normalization, dedup/merge, scoring, reranking and
claim-level citation verification. Deterministic unless neural models are
installed (cross-encoder/embeddings are optional honest tiers)."""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from synglue_agent.research.config import ResearchConfig
from synglue_agent.research.schemas import EvidenceItem

logger = logging.getLogger("protacpilot.research.retrieval")

_WS = re.compile(r"\s+")
_YEAR_RE = re.compile(r"(19|20)\d{2}")


# ── normalization / ids ─────────────────────────────────────────────────────

def normalize_title(title: str) -> str:
    t = _WS.sub(" ", (title or "").lower())
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def canonical_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", u)
    if m:
        return f"pubmed:{m.group(1)}"
    m = re.search(r"ncbi\.nlm\.nih\.gov/pmc/articles/(PMC\d+)", u, re.I)
    if m:
        return f"pmc:{m.group(1).upper()}"
    try:
        from urllib.parse import urlsplit
        parts = urlsplit(u)
        if parts.scheme not in ("http", "https"):
            return u.lower()
        host = (parts.netloc or "").lower()
        path = (parts.path or "").rstrip("/")
        return f"{host}{path}".lower()
    except Exception:
        return u.lower()


def dedup_id(record: dict[str, Any]) -> str:
    doi = str(record.get("doi") or "").strip().lower()
    pmid = str(record.get("pmid") or "").strip()
    pmcid = str(record.get("pmcid") or "").strip().upper()
    url = canonical_url(str(record.get("url") or ""))
    if doi:
        return f"doi:{doi}"
    if pmid:
        return f"pmid:{pmid}"
    if pmcid:
        return f"pmc:{pmcid}"
    if url:
        return f"url:{url}"
    title = normalize_title(str(record.get("title") or ""))
    if title:
        h = hashlib.sha1(title.encode("utf-8")).hexdigest()[:16]
        return f"title:{h}"
    return f"url:unknown:{abs(hash(str(record)))}"


def build_evidence(record: dict[str, Any]) -> EvidenceItem | None:
    """Raw adapter record -> EvidenceItem (id assigned by dedup key)."""
    title = str(record.get("title") or "").strip()
    if not title:
        return None
    abstract = str(record.get("abstract") or "")
    doi = str(record.get("doi") or "").strip()
    pmid = str(record.get("pmid") or "").strip()
    pmcid = str(record.get("pmcid") or "").strip().upper()
    year = record.get("year")
    try:
        year = int(year) if year is not None else None
    except (TypeError, ValueError):
        year = None
    if year is None:
        m = _YEAR_RE.search(str(record.get("publication_date") or ""))
        if m:
            year = int(m.group(0))
    passage = " ".join(x for x in (title, abstract) if x)[:config_max_abstract()]
    item = EvidenceItem(
        id=dedup_id(record),
        title=title,
        abstract=abstract[:config_max_abstract()],
        doi=doi,
        pmid=pmid,
        pmcid=pmcid,
        url=str(record.get("url") or ""),
        source=str(record.get("source") or "api"),
        authors=[str(a) for a in (record.get("authors") or [])][:25],
        year=year,
        journal=str(record.get("journal") or ""),
        venue_type=str(record.get("venue_type") or "journal_article"),
        is_open_access=bool(record.get("is_open_access")),
        is_primary=bool(record.get("is_primary", True)),
        cited_by_count=record.get("cited_by_count"),
        references=[str(x) for x in (record.get("references") or [])][:60],
        passage=passage,
        provenance={
            "first_found_by": str(record.get("source") or "api"),
            "merged_from": [],
            "extra": record.get("extra") or {},
        },
    )
    return item


def config_max_abstract() -> int:
    return 3_000  # see ResearchConfig.max_abstract_chars (avoid import cycle)


# ── dedup / merge ───────────────────────────────────────────────────────────

def dedup_and_merge(new_records: Sequence[dict[str, Any]],
                    existing: Sequence[EvidenceItem] | None = None,
                    ) -> tuple[list[EvidenceItem], dict[str, list[str]]]:
    """Merge raw records into existing evidence; returns (items, merge_log)."""
    by_id: dict[str, EvidenceItem] = {e.id: e for e in (existing or [])}
    merge_log: dict[str, list[str]] = {}

    for rec in new_records:
        item = build_evidence(rec)
        if item is None:
            continue
        cur = by_id.get(item.id)
        if cur is None:
            by_id[item.id] = item
            continue
        # merge: fill gaps, prefer richer abstract, union refs & sources
        merge_log.setdefault(item.id, []).append(rec.get("source", "?"))
        merged = _merge_item(cur, item)
        by_id[item.id] = merged

    items = sorted(by_id.values(), key=lambda e: e.id)
    return items, merge_log


def _merge_item(primary: EvidenceItem, other: EvidenceItem) -> EvidenceItem:
    src = [primary.source] if primary.source not in primary.provenance.get("merged_from", []) else list(primary.provenance.get("merged_from", []))
    merged_from = list(dict.fromkeys(src + [other.source]))
    provenance = dict(primary.provenance)
    provenance["merged_from"] = merged_from
    provenance["extra"] = {**(other.provenance.get("extra") or {}),
                           **(primary.provenance.get("extra") or {})}
    fields: dict[str, Any] = dict(primary)
    if len(str(other.abstract or "")) > len(str(primary.abstract or "")):
        fields["abstract"] = other.abstract
        fields["passage"] = " ".join(x for x in (other.title, other.abstract) if x)
    for key in ("doi", "pmid", "pmcid", "url"):
        if not fields.get(key):
            fields[key] = getattr(other, key)
    if not fields.get("journal"):
        fields["journal"] = other.journal
    if fields.get("cited_by_count") is None:
        fields["cited_by_count"] = other.cited_by_count
    elif other.cited_by_count is not None:
        fields["cited_by_count"] = max(fields["cited_by_count"], other.cited_by_count)
    if not fields.get("year"):
        fields["year"] = other.year
    fields["is_open_access"] = bool(fields.get("is_open_access") or other.is_open_access)
    fields["is_primary"] = bool(fields.get("is_primary", True) or other.is_primary)
    fields["references"] = list(dict.fromkeys(list(fields.get("references") or []) + other.references))
    if other.fulltext and not fields.get("fulltext"):
        fields["fulltext"] = other.fulltext
    fields["provenance"] = provenance
    return EvidenceItem(**fields)


# ── scoring ─────────────────────────────────────────────────────────────────

def score_item(item: EvidenceItem, config: ResearchConfig, now_year: int) -> EvidenceItem:
    """Deterministic authority / recency / primary-source sub-scores."""
    # authority: citations dominate, journal/OA/venue small boosts
    cites = item.cited_by_count or 0
    auth_cites = min(1.0, math.log1p(max(cites, 0)) / 9.0)
    auth = 0.6 * auth_cites + 0.2 * (1.0 if item.journal else 0.0) + 0.2 * (1.0 if item.is_open_access else 0.0)
    auth = max(0.0, min(1.0, auth))

    # recency: exponential decay, half-life ~6 years
    age = max(0, (now_year or 2026) - (item.year or 2000))
    recency = math.exp(-age / 8.0)

    # primary-source status
    vt = (item.venue_type or "").lower()
    if item.is_primary and vt in ("journal_article", "review", "journal", ""):
        primary = 1.0
    elif item.is_primary:
        primary = 0.8
    elif vt in ("preprint",):
        primary = 0.55
    elif vt in ("report", "book", "patent", "editorial", "letter"):
        primary = 0.4
    elif vt == "web":
        primary = 0.3
    else:
        primary = 0.45

    item.authority_score = round(auth, 4)
    item.recency_score = round(recency, 4)
    item.primary_score = round(primary, 4)
    item.total_score = round(
        config.w_relevance * item.relevance_score
        + config.w_authority * auth
        + config.w_recency * recency
        + config.w_primary * primary, 4)
    return item


# ── reranking (neural optional, lexical default) ────────────────────────────

_neural_modules_available = None


def neural_rerank_available() -> bool:
    global _neural_modules_available
    if _neural_modules_available is None:
        _neural_modules_available = (importlib.util.find_spec("sentence_transformers") is not None
                                     and importlib.util.find_spec("torch") is not None)
    return _neural_modules_available


def _lexical_relevance(query: str, items: Sequence[EvidenceItem]) -> dict[str, float]:
    q_tokens = set(_WS.sub(" ", query.lower()).split())
    if not q_tokens:
        return {}
    scores: dict[str, float] = {}
    for item in items:
        doc_tokens = set(_WS.sub(" ", (item.passage or "").lower()).split())
        if not doc_tokens:
            scores[item.id] = 0.0
            continue
        overlap = len(q_tokens & doc_tokens)
        scores[item.id] = overlap / max(len(q_tokens), 1) * min(1.0, len(doc_tokens) / 40.0)
    if scores and max(scores.values()) > 0:
        mx = max(scores.values())
        scores = {k: v / mx for k, v in scores.items()}
    return scores


def _minmax_normalize(values: Sequence[float]) -> list[float]:
    vals = list(values)
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def rerank_items(query: str, items: Sequence[EvidenceItem],
                 config: ResearchConfig) -> tuple[list[EvidenceItem], dict[str, Any]]:
    """Sort by relevance (cross-encoder + local embeddings when available,
    deterministic lexical BM25-style otherwise). Returns (items, meta)."""
    items = list(items)
    if not items:
        return [], {"model": "none", "note": "no evidence to rerank"}

    used = "lexical_bm25"
    status_note = "lexical rerank (BM25-style overlap) — no neural model loaded"
    relevance: dict[str, float] = {}

    if neural_rerank_available():
        try:
            from sentence_transformers import (  # type: ignore
                CrossEncoder,
                SentenceTransformer,
            )

            reranker: Any = None
            embedder: Any = None
            if config.reranker_model:
                reranker = CrossEncoder(config.reranker_model)
            if config.embed_model:
                embedder = SentenceTransformer(config.embed_model)
            pairs = [[query, (i.passage or i.title)[:1200]] for i in items]
            ce_raw: list[float] | None = None
            emb_sim: list[float] | None = None
            if reranker is not None:
                ce_raw = list(reranker.predict(pairs, batch_size=32, show_progress_bar=False))
            if embedder is not None:
                vecs = embedder.encode([query] + [(i.passage or i.title)[:1200] for i in items],
                                       normalize_embeddings=True)
                import numpy as np
                qv = np.asarray(vecs[0])
                dv = np.asarray(vecs[1:])
                emb_sim = [float(qv @ row) for row in dv]
            if ce_raw is not None or emb_sim is not None:
                ce_norm = _minmax_normalize(ce_raw) if ce_raw is not None else [0.5] * len(items)
                emb_norm = _minmax_normalize(emb_sim) if emb_sim is not None else [0.5] * len(items)
                for i, item in enumerate(items):
                    relevance[item.id] = 0.65 * ce_norm[i] + 0.35 * emb_norm[i]
                used = "cross_encoder" + ("+embeddings" if emb_sim is not None else "")
                status_note = f"neural rerank ({used})"
        except Exception as exc:
            logger.warning("neural rerank failed (%s) -> lexical fallback", exc)
            status_note = f"neural rerank attempted but unavailable ({exc}) -> lexical fallback"

    if not relevance:
        relevance = _lexical_relevance(query, items)
        status_note = "lexical rerank (BM25-style overlap)"

    for item in items:
        item.relevance_score = round(max(0.0, min(1.0, relevance.get(item.id, 0.0))), 4)
        item.rerank_model = used

    ranked = sorted(items, key=lambda e: e.total_score or e.relevance_score, reverse=True)
    return ranked, {"model": used, "note": status_note, "n_ranked": len(ranked)}


def score_and_rank(query: str, items: Sequence[EvidenceItem],
                   config: ResearchConfig, now_year: int | None = None) -> tuple[list[EvidenceItem], dict[str, Any]]:
    """Rerank then score; returns sorted list + rerank meta."""
    ranked, meta = rerank_items(query, items, config)
    now = now_year or _current_year()
    ranked = [score_item(e, config, now) for e in ranked]
    ranked.sort(key=lambda e: e.total_score, reverse=True)
    return ranked, meta


def _current_year() -> int:
    import datetime
    return datetime.date.today().year


# ── sufficiency / reformulation heuristics ──────────────────────────────────

def evidence_sufficiency(evidence: Sequence[EvidenceItem], config: ResearchConfig,
                         ) -> tuple[bool, str]:
    """True when enough unique evidence with acceptable top relevance exists."""
    unique = len({e.id for e in evidence})
    scientific = [e for e in evidence if e.source in ("europepmc", "pubmed", "openalex")]
    top_rel = max([e.relevance_score for e in evidence], default=0.0)
    if unique < config.min_evidence:
        return False, f"only {unique} unique evidence item(s); need >= {config.min_evidence}"
    if top_rel < config.min_top_relevance:
        return False, f"best relevance {top_rel:.3f} below threshold {config.min_top_relevance}"
    if not scientific and unique < config.min_evidence + 2:
        return False, "no primary scientific (Europe PMC/PubMed/OpenAlex) evidence found yet"
    return True, f"sufficient ({unique} unique, top relevance {top_rel:.3f})"


def reformulate_query(query: str, seen_ids: Sequence[str], top_terms: str | None = None) -> str:
    """Deterministic query broadening/exclusion for the next iteration."""
    seen = list(seen_ids)[:12]
    exclusion = " ".join(f"-doi:\"{s.replace('doi:', '')}\"" if s.startswith("doi:") else f"NOT {s}" for s in seen[:5])
    terms = f" AND ({top_terms})" if top_terms else ""
    return f"{query}{terms} {exclusion}".strip()


# ── claim-level verification ────────────────────────────────────────────────

_CITE_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def find_citation_indices(text: str) -> list[int]:
    out: list[int] = []
    for m in _CITE_RE.finditer(text or ""):
        for part in m.group(1).split(","):
            part = part.strip()
            if part.isdigit():
                out.append(int(part))
    return out


def split_claims(text: str) -> list[dict[str, Any]]:
    """Split answer text into claim units (bullets/paragraph lines).

    A unit is a bullet or line together with its citation tokens; deterministic
    digests quote whole sources, so sentence-level splitting is deliberately
    avoided (it would flag quote fragments as unsupported).
    """
    claims: list[dict[str, Any]] = []
    if not text:
        return claims
    for line in re.split(r"\n", text):
        line = line.strip().lstrip("-#*• \t")
        low = line.lower()
        # framework framing/limitation lines are not evidence claims
        if low.startswith(("limitations:", "llm synthesis", "no retrievable evidence",
                           "no answer is fabricated", "no generative", "evidence digest")):
            continue
        if len(line) < 30:
            continue
        claims.append({"text": line, "citations": find_citation_indices(line)})
    return claims


def verify_claims(answer_md: str, n_evidence: int) -> dict[str, Any]:
    """Structural verification: every citation index must point at provided
    evidence; claims without citations are flagged unsupported (fabrication
    guard — the framework never adds references that were not retrieved)."""
    claims_out: list[dict[str, Any]] = []
    unsupported = 0
    map_ok = True
    notes: list[str] = []
    for idx, claim in enumerate(split_claims(answer_md or "")):
        cits = claim["citations"]
        valid = [c for c in cits if 1 <= c <= n_evidence]
        invalid = [c for c in cits if not (1 <= c <= n_evidence)]
        if invalid:
            map_ok = False
            notes.append(f"claim {idx + 1} cites out-of-range index {invalid}")
        if not valid and n_evidence > 0:
            status = "unsupported"
            unsupported += 1
            note = "no citation to retrieved evidence"
        elif not valid:
            status = "needs_review"
            note = "no evidence available to cite"
        else:
            status = "supported"
            note = f"cites evidence {valid}"
        claims_out.append({
            "claim_id": f"claim_{idx + 1}",
            "text": claim["text"],
            "citation_indices": valid,
            "status": status,
            "note": note,
        })
    return {
        "claims": claims_out,
        "citation_map_ok": map_ok,
        "unsupported_count": unsupported,
        "note": "; ".join(notes) if notes else "all citation indices map to retrieved evidence",
    }
