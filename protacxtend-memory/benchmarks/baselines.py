"""Four-way memory-backend harness for Benchmark H (Master Prompt §46/§36).

This module defines a *shared* experimental interface so four memory conditions
receive identical tasks, identical historical events, and identical queries:

    NoMemoryBackend        — no historical retention (control)
    TranscriptRAGBackend   — conversation/transcript chunks + lexical retrieval
    CuratedMemoryBackend   — Engram-like curated observations with topic upsert
    CognitiveMemoryBackend — the full PROTACpilot cognitive memory stack

Fairness rules
--------------
* Every backend consumes the same ordered ``BenchEvent`` stream.
* Each backend uses its *native* retrieval mechanism. The two lexical baselines
  share one deterministic BM25 implementation (``bm25_scores``) so they are not
  differentially advantaged; the cognitive backend uses its own hybrid FTS5 +
  entity + context pipeline.
* No backend sees another backend's database; each owns an isolated store.
* Nothing here calls an LLM. Answers are produced downstream by a deterministic
  reader over the retrieved context, identical across backends.

Naming: ``CuratedMemoryBackend`` is a *compatible experimental baseline* loosely
inspired by upstream Engram's curated-observation philosophy. It is **not** the
Engram software, and results must not be reported as an Engram evaluation.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from protacpilot_memory import CognitiveMemory
from protacpilot_memory.config import MemoryConfig

# Documented token approximation: ~4 characters per token. We deliberately do
# not claim tokenizer-exact counts; the *same* function is used for every
# backend so the comparison is internally consistent.
TOKEN_DIVISOR = 4.0


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return int(math.ceil(len(text) / TOKEN_DIVISOR))


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def bm25_scores(query: str, docs: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Deterministic BM25 over a document list (used by both lexical baselines)."""
    q = tokenize(query)
    if not q or not docs:
        return [0.0] * len(docs)
    tokenized = [tokenize(d) for d in docs]
    n = len(tokenized)
    avgdl = sum(len(d) for d in tokenized) / n or 1.0
    df: dict[str, int] = {}
    for d in tokenized:
        for term in set(d):
            df[term] = df.get(term, 0) + 1
    scores: list[float] = []
    for d in tokenized:
        dl = len(d) or 1
        tf: dict[str, int] = {}
        for term in d:
            tf[term] = tf.get(term, 0) + 1
        score = 0.0
        for term in q:
            if term not in tf:
                continue
            idf = math.log(1.0 + (n - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
            denom = tf[term] + k1 * (1.0 - b + b * dl / avgdl)
            score += idf * (tf[term] * (k1 + 1.0)) / denom
        scores.append(score)
    return scores


# ── shared records ───────────────────────────────────────────────────────────
@dataclass
class BenchEvent:
    """One historical event fed identically to every backend."""

    event_id: str
    session: int
    kind: str                       # episodic | negative | semantic | prospective
    event_type: str
    title: str
    content: str
    context: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    observed: dict[str, Any] = field(default_factory=dict)
    interpretation: str | None = None
    is_negative: bool = False
    decision_impact: float = 0.5
    goal_relevance: float = 0.5
    topic_key: str | None = None
    prediction: dict[str, Any] | None = None
    outcome: dict[str, Any] | None = None
    related_prediction_event: str | None = None
    task: str | None = None

    def render(self) -> str:
        parts = [f"Session {self.session}", self.title, self.content]
        if self.interpretation:
            parts.append(self.interpretation)
        for key, value in self.observed.items():
            parts.append(f"{key}={value}")
        for ev in self.evidence:
            ident = ev.get("experiment_id") or ev.get("doi") or ev.get("pmid") or ev.get("accession")
            if ident:
                parts.append(f"evidence {ev.get('evidence_type', 'source')} {ident}")
        return " | ".join(str(p) for p in parts if p not in (None, ""))


@dataclass
class RetrievedItem:
    id: str
    title: str
    text: str
    kind: str
    score: float = 0.0
    session: int | None = None
    source_events: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    #: scientific context of the memory, when the backend retains one
    context: dict[str, Any] = field(default_factory=dict)


def render_items(items: Iterable[RetrievedItem]) -> str:
    return "\n".join(f"[{it.kind}] {it.title}: {it.text}" for it in items)


# ── backend interface ────────────────────────────────────────────────────────
class MemoryBackend:
    name = "abstract"

    def reset(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def ingest(self, event: BenchEvent) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def retrieve(
        self, query: str, *, context: dict[str, Any] | None = None, k: int = 5
    ) -> list[RetrievedItem]:  # pragma: no cover - interface
        raise NotImplementedError

    def finalize(self) -> None:
        """Post-ingestion cognitive processing (no-op for non-cognitive backends)."""

    def session_context(self, *, k: int = 8) -> dict[str, Any]:
        return {"items": [], "text": ""}

    def assemble(self, query: str, *, context: dict[str, Any] | None = None, k: int = 5) -> str:
        return render_items(self.retrieve(query, context=context, k=k))

    def stats(self) -> dict[str, Any]:
        return {"backend": self.name}


# ── A. no memory ─────────────────────────────────────────────────────────────
class NoMemoryBackend(MemoryBackend):
    name = "no_memory"

    def reset(self) -> None:
        self._seen = 0

    def ingest(self, event: BenchEvent) -> None:
        # Receives the stream but deliberately retains nothing.
        self._seen += 1

    def retrieve(self, query: str, *, context: dict[str, Any] | None = None, k: int = 5) -> list[RetrievedItem]:
        return []

    def session_context(self, *, k: int = 8) -> dict[str, Any]:
        return {"items": [], "text": ""}

    def stats(self) -> dict[str, Any]:
        return {"backend": self.name, "stored": 0, "seen": self._seen}


# ── B. naive transcript RAG ──────────────────────────────────────────────────
class TranscriptRAGBackend(MemoryBackend):
    """conversation -> chunks -> lexical retrieval (no structure, no cognition)."""

    name = "transcript_rag"

    def reset(self) -> None:
        self._chunks: list[dict[str, Any]] = []

    def ingest(self, event: BenchEvent) -> None:
        self._chunks.append({
            "id": event.event_id,
            "title": event.title,
            "text": event.render(),
            "session": event.session,
            "kind": event.kind,
            "context": dict(event.context or {}),
        })

    def retrieve(self, query: str, *, context: dict[str, Any] | None = None, k: int = 5) -> list[RetrievedItem]:
        if not self._chunks:
            return []
        docs = [c["text"] for c in self._chunks]
        scores = bm25_scores(query, docs)
        order = sorted(range(len(docs)), key=lambda i: (-scores[i], self._chunks[i]["id"]))
        out: list[RetrievedItem] = []
        for i in order:
            if len(out) >= k:
                break
            if scores[i] <= 0:
                continue
            c = self._chunks[i]
            out.append(RetrievedItem(
                id=c["id"], title=c["title"], text=c["text"], kind=c["kind"],
                score=scores[i], session=c["session"], source_events=[c["id"]],
                metadata={"backend": self.name}, context=dict(c.get("context") or {}),
            ))
        return out

    def session_context(self, *, k: int = 8) -> dict[str, Any]:
        recent = self._chunks[-k:]
        items = [
            RetrievedItem(id=c["id"], title=c["title"], text=c["text"], kind=c["kind"],
                          session=c["session"], source_events=[c["id"]],
                          context=dict(c.get("context") or {}))
            for c in recent
        ]
        return {"items": items, "text": render_items(items)}

    def stats(self) -> dict[str, Any]:
        return {"backend": self.name, "chunks": len(self._chunks)}


# ── C. standard retrieval/RAG (chunked, no structure) ───────────────────────
class StandardRAGBackend(MemoryBackend):
    """Standard retrieval-augmented generation memory.

    Each event is split into sentence-level chunks and retrieved with BM25
    (top-k). This is the conventional RAG pipeline: no topic identity, no
    consolidation, no negative-memory class, no provenance or context weighting.
    It is deliberately distinct from ``TranscriptRAGBackend`` (whole-turn
    conversation history) so the five conditions in the brief are represented.
    """

    name = "rag_memory"

    def reset(self) -> None:
        self._chunks: list[dict[str, Any]] = []

    def ingest(self, event: BenchEvent) -> None:
        text = event.render()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        if not sentences:
            sentences = [text]
        for index, sentence in enumerate(sentences):
            self._chunks.append({
                "id": f"{event.event_id}#{index}",
                "event_id": event.event_id,
                "title": event.title,
                "text": sentence,
                "session": event.session,
                "kind": event.kind,
                "context": dict(event.context or {}),
            })

    def retrieve(self, query: str, *, context: dict[str, Any] | None = None, k: int = 5) -> list[RetrievedItem]:
        if not self._chunks:
            return []
        docs = [c["text"] for c in self._chunks]
        scores = bm25_scores(query, docs)
        order = sorted(range(len(docs)), key=lambda i: (-scores[i], self._chunks[i]["id"]))
        out: list[RetrievedItem] = []
        for i in order:
            if len(out) >= k:
                break
            if scores[i] <= 0:
                continue
            c = self._chunks[i]
            out.append(RetrievedItem(
                id=c["id"], title=c["title"], text=c["text"], kind=c["kind"],
                score=scores[i], session=c["session"], source_events=[c["event_id"]],
                metadata={"backend": self.name, "chunk": True},
                context=dict(c.get("context") or {}),
            ))
        return out

    def session_context(self, *, k: int = 8) -> dict[str, Any]:
        recent = self._chunks[-k:]
        items = [
            RetrievedItem(id=c["id"], title=c["title"], text=c["text"], kind=c["kind"],
                          session=c["session"], source_events=[c["event_id"]],
                          context=dict(c.get("context") or {}))
            for c in recent
        ]
        return {"items": items, "text": render_items(items)}

    def stats(self) -> dict[str, Any]:
        return {"backend": self.name, "chunks": len(self._chunks)}


# ── D. Engram-like curated memory baseline ───────────────────────────────────
class CuratedMemoryBackend(MemoryBackend):
    """Curated observations + sessions + lexical retrieval + topic upsert.

    Deliberately omits: consolidation, prediction-error prioritisation,
    reconsolidation, adaptive decay, and any negative-memory-specific
    mechanism. Negative events are stored as ordinary observations.
    """

    name = "curated_memory"
    TITLE_BOOST = 0.5   # additive boost from a title-only BM25 pass

    def reset(self) -> None:
        self._obs: dict[str, dict[str, Any]] = {}
        self._topic_index: dict[str, str] = {}
        self._order: list[str] = []

    def ingest(self, event: BenchEvent) -> None:
        key = event.topic_key
        if key and key in self._topic_index:
            oid = self._topic_index[key]
            obs = self._obs[oid]
            obs["title"] = event.title
            obs["text"] = event.render()
            obs["session"] = event.session
            obs["revision_count"] += 1
            if event.event_id not in obs["source_events"]:
                obs["source_events"].append(event.event_id)
            return
        oid = event.event_id
        self._obs[oid] = {
            "id": oid, "title": event.title, "text": event.render(),
            "session": event.session, "kind": event.kind,
            "source_events": [event.event_id], "topic_key": key,
            "revision_count": 1, "context": dict(event.context or {}),
        }
        self._order.append(oid)
        if key:
            self._topic_index[key] = oid

    def retrieve(self, query: str, *, context: dict[str, Any] | None = None, k: int = 5) -> list[RetrievedItem]:
        if not self._obs:
            return []
        ids = list(self._obs)
        base = bm25_scores(query, [self._obs[i]["text"] for i in ids])
        title = bm25_scores(query, [self._obs[i]["title"] for i in ids])
        scores = [base[j] + self.TITLE_BOOST * title[j] for j in range(len(ids))]
        order = sorted(range(len(ids)), key=lambda j: (-scores[j], ids[j]))
        out: list[RetrievedItem] = []
        for j in order:
            if len(out) >= k:
                break
            if scores[j] <= 0:
                continue
            obs = self._obs[ids[j]]
            out.append(RetrievedItem(
                id=obs["id"], title=obs["title"], text=obs["text"], kind=obs["kind"],
                score=scores[j], session=obs["session"],
                source_events=list(obs["source_events"]),
                metadata={"backend": self.name, "revision_count": obs["revision_count"],
                          "topic_key": obs["topic_key"]},
                context=dict(obs.get("context") or {}),
            ))
        return out

    def session_context(self, *, k: int = 8) -> dict[str, Any]:
        recent = self._order[-k:]
        items = [
            RetrievedItem(id=self._obs[i]["id"], title=self._obs[i]["title"],
                          text=self._obs[i]["text"], kind=self._obs[i]["kind"],
                          session=self._obs[i]["session"],
                          source_events=list(self._obs[i]["source_events"]),
                          context=dict(self._obs[i].get("context") or {}))
            for i in recent
        ]
        return {"items": items, "text": render_items(items)}

    def stats(self) -> dict[str, Any]:
        return {"backend": self.name, "observations": len(self._obs),
                "topics": len(self._topic_index)}


# ── D. PROTACpilot cognitive memory ──────────────────────────────────────────
class CognitiveMemoryBackend(MemoryBackend):
    name = "cognitive_memory"

    def __init__(self, config: MemoryConfig | None = None, flags: dict[str, Any] | None = None) -> None:
        self._config = config
        self._flags = dict(flags or {})
        self.reset()

    def reset(self) -> None:
        mem = getattr(self, "_mem", None)
        if mem is not None:
            mem.close()
        self._mem = CognitiveMemory.in_memory(self._config)
        self._project = self._mem.ensure_project("bench-h")
        self._sessions: dict[int, str] = {}
        self._native_to_events: dict[str, list[str]] = {}
        self._context_by_native: dict[str, dict[str, Any]] = {}
        self._event_ids: set[str] = set()
        self._pending_predictions: dict[str, str] = {}

    # -- helpers ---------------------------------------------------------
    def _session(self, index: int) -> str:
        if index not in self._sessions:
            self._sessions[index] = self._mem.start_session(
                self._project, goal="design a permeable, degrading BRD4/VHL PROTAC"
            )
        return self._sessions[index]

    def _record_native(self, native_id: str | None, event_id: str) -> None:
        if not native_id:
            return
        self._native_to_events.setdefault(native_id, [])
        if event_id not in self._native_to_events[native_id]:
            self._native_to_events[native_id].append(event_id)

    def _context_for_trace(self, trace: dict[str, Any]) -> dict[str, Any]:
        direct = self._context_by_native.get(str(trace.get("id")))
        if direct:
            return direct
        metadata = trace.get("metadata_json") or {}
        for episode_id in metadata.get("episode_ids", []) or []:
            ctx = self._context_by_native.get(str(episode_id))
            if ctx:
                return ctx
        return {}

    def _source_events(self, trace: dict[str, Any]) -> list[str]:
        native = trace.get("id")
        if native in self._native_to_events:
            return sorted(set(self._native_to_events[native]))
        source_id = trace.get("source_id")
        if source_id in self._event_ids:
            return [source_id]
        events: list[str] = []
        metadata = trace.get("metadata_json") or {}
        for episode_id in metadata.get("episode_ids", []) or []:
            events.extend(self._native_to_events.get(episode_id, []))
        return sorted(set(events))

    def _evidence_text(self, memory_id: str) -> str:
        """Render this memory's provenance so retrieval can surface it (Layer 2)."""
        try:
            links = self._mem.store.links_for_memory(memory_id)
        except Exception:  # pragma: no cover
            return ""
        idents: list[str] = []
        for link in links:
            ident = (link.get("experiment_id") or link.get("doi") or link.get("pmid")
                     or link.get("accession") or link.get("pdb"))
            if ident:
                idents.append(f"evidence {link.get('evidence_type')} {ident}")
        return " ".join(idents)

    # -- ingest ----------------------------------------------------------
    def ingest(self, event: BenchEvent) -> None:
        self._event_ids.add(event.event_id)
        session_id = self._session(event.session)

        if event.prediction is not None:
            prediction_id = self._mem.predict(
                project_id=self._project, session_id=session_id,
                context=event.context, **event.prediction,
            )
            self._pending_predictions[event.event_id] = prediction_id
            return

        if event.outcome is not None:
            prediction_id = self._pending_predictions.get(event.related_prediction_event or "")
            if prediction_id is None:
                return
            result = self._mem.record_outcome(
                prediction_id, project_id=self._project, session_id=session_id,
                title=event.title, interpretation=event.interpretation,
                is_negative=False if self._flags.get("disable_negative") else event.is_negative,
                goal_relevance=event.goal_relevance,
                **event.outcome,
            )
            episode_id = (result.get("episode") or {}).get("episode_id")
            self._record_native(episode_id, event.event_id)
            if episode_id:
                self._context_by_native[episode_id] = dict(event.context or {})
            return

        if event.kind == "prospective" or event.task:
            if self._flags.get("disable_prospective"):
                return
            prospective_id = self._mem.future(
                title=event.title, content=event.content,
                project_id=self._project, session_id=session_id,
                related_memory_id=None, priority=0.8,
            )
            self._record_native(prospective_id, event.event_id)
            return

        is_negative = bool(event.is_negative) and not self._flags.get("disable_negative")
        result = self._mem.save_episode(
            title=event.title, content=event.content, event_type=event.event_type,
            project_id=self._project, session_id=session_id,
            context=event.context, evidence=event.evidence,
            observed=event.observed, interpretation=event.interpretation,
            is_negative=is_negative, decision_impact=event.decision_impact,
            goal_relevance=event.goal_relevance,
            source={"source_ref": event.event_id, "source_type": "benchmark"},
        )
        self._record_native(result.get("episode_id"), event.event_id)
        if result.get("episode_id"):
            self._context_by_native[result["episode_id"]] = dict(event.context or {})

    def finalize(self) -> None:
        if not self._flags.get("skip_consolidation"):
            self._mem.consolidate(self._project)
        if not self._flags.get("skip_reconsolidation"):
            try:
                self._mem.reconsolidation.run(self._project)
            except Exception:  # pragma: no cover - reconsolidation is best-effort here
                pass

    # -- retrieval -------------------------------------------------------
    def retrieve(self, query: str, *, context: dict[str, Any] | None = None, k: int = 5) -> list[RetrievedItem]:
        memory_types = None
        if self._flags.get("exclude_semantic"):
            memory_types = ["episodic", "negative", "prospective", "procedural"]
        response = self._mem.search(
            query, project_id=self._project, context=context,
            memory_types=memory_types, limit=k,
        )
        out: list[RetrievedItem] = []
        for hit in response.hits:
            trace = hit.memory
            provenance = self._evidence_text(hit.id)
            body = str(trace.get("content") or "")
            out.append(RetrievedItem(
                id=hit.id,
                title=str(trace.get("title") or ""),
                text=f"{body} {provenance}".strip(),
                kind=str(trace.get("memory_type") or "memory"),
                score=float(hit.score),
                session=None,
                source_events=self._source_events(trace),
                metadata={
                    "backend": self.name,
                    "why_retrieved": hit.why_retrieved,
                    "components": hit.components,
                    "status": trace.get("status"),
                    "confidence": trace.get("confidence"),
                },
                context=self._context_for_trace(trace),
            ))
        return out

    def session_context(self, *, k: int = 8) -> dict[str, Any]:
        overview = self._mem.context(self._project)
        text = self._mem.retriever.render_context(self._project)
        return {**overview, "text": text}

    def stats(self) -> dict[str, Any]:
        base = {"backend": self.name, "project": self._project}
        try:
            base.update(self._mem.stats())
        except Exception:  # pragma: no cover
            pass
        return base


BACKENDS = {
    "no_memory": NoMemoryBackend,
    "transcript_rag": TranscriptRAGBackend,
    "rag_memory": StandardRAGBackend,
    "curated_memory": CuratedMemoryBackend,
    "cognitive_memory": CognitiveMemoryBackend,
}


def build_backends() -> dict[str, MemoryBackend]:
    """Construct one isolated instance of every backend."""
    return {name: cls() for name, cls in BACKENDS.items()}


__all__ = [
    "BenchEvent",
    "RetrievedItem",
    "MemoryBackend",
    "NoMemoryBackend",
    "TranscriptRAGBackend",
    "StandardRAGBackend",
    "CuratedMemoryBackend",
    "CognitiveMemoryBackend",
    "BACKENDS",
    "build_backends",
    "bm25_scores",
    "estimate_tokens",
    "render_items",
    "tokenize",
]
