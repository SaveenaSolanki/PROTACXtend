"""Associative graph retrieval: expand seeds through the relation network."""

from __future__ import annotations

from typing import Any

from ..store.store import MemoryStore
from ..util import clamp01

_RELATION_WEIGHT = {
    "supports": 0.9,
    "refines": 0.9,
    "replicates": 0.9,
    "generalizes": 0.8,
    "derived_from": 0.8,
    "caused_decision": 0.8,
    "contradicts": 0.8,
    "failed_to_replicate": 0.8,
    "exception_to": 0.7,
    "predicted": 0.7,
    "observed": 0.7,
    "same_context": 0.6,
    "related_context": 0.5,
    "supersedes": 0.4,
}


class GraphRetriever:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def expand(
        self, seed_ids: list[str], *, depth: int = 1, limit: int = 50
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        for seed in seed_ids:
            for neighbor in self.store.neighbors(seed, depth=depth):
                weight = _RELATION_WEIGHT.get(neighbor["via"], 0.5)
                conf = clamp01(neighbor.get("confidence") or 0.5)
                decay = 0.5 ** max(0, neighbor["distance"] - 1)
                score = weight * (0.5 + 0.5 * conf) * decay
                mid = neighbor["memory_id"]
                scores[mid] = max(scores.get(mid, 0.0), clamp01(score))
        ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return dict(ordered[:limit])

    def related_memories(self, memory_id: str, depth: int = 1) -> list[dict[str, Any]]:
        out = []
        for neighbor in self.store.neighbors(memory_id, depth=depth):
            trace = self.store.get_trace(neighbor["memory_id"])
            if trace is None:
                continue
            out.append({**neighbor, "memory": trace})
        return out
