"""Orchestrated hybrid retrieval + progressive disclosure (Master Prompt §13–15, §38)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import MemoryConfig
from ..domain.protac.context import ProtacContext, context_from_any
from ..domain.protac.normalization import entities_in_text
from ..retrieval.graph import GraphRetriever
from ..retrieval.lexical import LexicalRetriever
from ..retrieval.progressive import ProgressiveDisclosure
from ..retrieval.rerank import RankedMemory, Reranker
from ..retrieval.semantic import SemanticRetriever
from ..store.store import MemoryStore


@dataclass
class SearchResponse:
    query: str
    hits: list[RankedMemory] = field(default_factory=list)
    generator_counts: dict[str, int] = field(default_factory=dict)
    semantic_backend: str = "disabled"

    def ids(self) -> list[str]:
        return [h.id for h in self.hits]


class CognitiveRetriever:
    def __init__(self, store: MemoryStore, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config
        self.lexical = LexicalRetriever(store)
        self.semantic = SemanticRetriever(self.config)
        self.graph = GraphRetriever(store)
        self.reranker = Reranker(store, self.config)
        self.progressive = ProgressiveDisclosure(store, self.config)

    # ── search ───────────────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        *,
        project_id: str | None = None,
        context: ProtacContext | dict[str, Any] | None = None,
        entities: list[str] | None = None,
        memory_types: list[str] | None = None,
        limit: int | None = None,
        session_id: str | None = None,
        log: bool = True,
    ) -> SearchResponse:
        limit = limit or self.config.max_search_results
        qctx = context_from_any(context)
        query_entities = set(entities or [])
        query_entities |= {r.name for r in entities_in_text(query)}
        if qctx.target_gene:
            query_entities.add(qctx.target_gene)
        if qctx.e3_ligase:
            query_entities.add(qctx.e3_ligase)
        if qctx.cell_line:
            query_entities.add(qctx.cell_line)

        lexical = self.lexical.candidates(
            query, project_id=project_id, memory_types=memory_types, limit=max(30, limit * 3)
        )
        candidate_ids: set[str] = set(lexical.keys())

        # entity-overlap candidate generation
        if query_entities:
            for mid in self.store.memories_for_entity_names(sorted(query_entities)):
                candidate_ids.add(mid)

        # graph expansion from the strongest lexical/entity seeds
        seeds = list(candidate_ids)[:5]
        graph = self.graph.expand(seeds, depth=1, limit=max(20, limit * 2)) if seeds else {}
        candidate_ids |= set(graph.keys())

        candidates: list[dict[str, Any]] = []
        for mid in candidate_ids:
            trace = self.store.get_trace(mid)
            if trace is None:
                continue
            if memory_types and trace.get("memory_type") not in memory_types:
                continue
            candidates.append(trace)

        # Optional semantic similarity *among candidates only* (bounded cost).
        semantic_scores: dict[str, float] = {}
        if self.semantic.enabled and candidates:
            documents = {
                c["id"]: f"{c.get('title','')} {c.get('content','')}" for c in candidates
            }
            semantic_scores = self.semantic.candidates(query, documents, limit=len(documents))

        hits = self.reranker.rank(
            candidates,
            query=query,
            query_context=qctx,
            query_entities=sorted(query_entities),
            lexical=lexical,
            semantic=semantic_scores,
            graph=graph,
            limit=limit,
        )
        if log:
            for rank, hit in enumerate(hits):
                self.store.log_access(
                    hit.id,
                    session_id=session_id,
                    query=query,
                    rank=rank,
                    score=hit.score,
                    components={**hit.components, "why": hit.why_retrieved},
                )
        return SearchResponse(
            query=query,
            hits=hits,
            generator_counts={
                "lexical": len(lexical),
                "entity": len(candidate_ids),
                "graph": len(graph),
                "semantic": len(semantic_scores),
            },
            semantic_backend=self.semantic.label(),
        )

    # ── progressive layers ───────────────────────────────────────────────────
    def recall(self, query: str, *, project_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Layer 1 + Layer 2: search then a neighbourhood for the top hit."""
        response = self.search(query, project_id=project_id, **kwargs)
        overview = None
        if response.hits:
            overview = self.progressive.neighborhood(response.hits[0].id)
        return {
            "query": query,
            "results": [self.progressive.compact(h) for h in response.hits],
            "overview": overview,
            "semantic_backend": response.semantic_backend,
        }

    def get(self, memory_id: str, why: list[str] | None = None) -> dict[str, Any]:
        """Layer 3: full scientific memory packet."""
        return {
            "packet": self.progressive.render_packet(memory_id, why),
            "trace": self.store.require_trace(memory_id),
        }

    def evidence(self, memory_id: str) -> dict[str, Any]:
        """Layer 4: raw provenance / artifacts."""
        return self.progressive.raw_evidence(memory_id)

    def neighbors(self, memory_id: str, depth: int = 1) -> list[dict[str, Any]]:
        return self.graph.related_memories(memory_id, depth)

    def timeline(self, memory_id: str, window: int = 5) -> dict[str, Any]:
        return self.store.timeline(memory_id, window)

    # ── context assembly ─────────────────────────────────────────────────────
    def context(self, project_id: str | None, session_id: str | None = None) -> dict[str, Any]:
        return self.progressive.context_overview(project_id, session_id)

    def render_context(self, project_id: str | None, session_id: str | None = None) -> str:
        ctx = self.context(project_id, session_id)
        import json

        return json.dumps(ctx, indent=2, default=str)

    # ── feedback / use-dependent strengthening ───────────────────────────────
    def feedback(self, memory_id: str, *, useful: bool, used_for: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        self.store.log_access(
            memory_id,
            session_id=session_id,
            query=None,
            rank=None,
            score=None,
            components={"feedback": used_for or "manual"},
            was_useful=useful,
            used_for=used_for,
        )
        from .decay import DecayModel

        strength = DecayModel(self.store, self.config).strengthen(memory_id, useful=useful)
        return {"memory_id": memory_id, "useful": useful, "memory_strength": strength}
