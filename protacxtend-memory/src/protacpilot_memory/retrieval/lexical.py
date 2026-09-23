"""Lexical retrieval: FTS5 / BM25 candidate generation."""

from __future__ import annotations

from typing import Any

from ..domain.protac.ontology import SILENCED_STATUSES
from ..store.store import MemoryStore


class LexicalRetriever:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def candidates(
        self,
        query: str,
        *,
        project_id: str | None = None,
        memory_types: list[str] | None = None,
        statuses: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, float]:
        rows = self.store.search_fts(
            query,
            project_id=project_id,
            memory_types=memory_types,
            statuses=statuses,
            exclude_statuses=None if statuses else sorted(SILENCED_STATUSES),
            limit=limit,
        )
        if not rows:
            return {}
        scores: dict[str, float] = {}
        relevance = {r["id"]: max(0.0, -float(r["bm25_rank"])) for r in rows}
        best = max(relevance.values()) if relevance else 0.0
        worst = min(relevance.values()) if relevance else 0.0
        for memory_id, rel in relevance.items():
            if best <= 0.0:
                scores[memory_id] = 0.0
            elif best == worst:
                scores[memory_id] = 1.0
            else:
                scores[memory_id] = (rel - worst) / (best - worst)
        return scores
