"""Transparent component-based reranking (Master Prompt §13, §38).

    R = Σ w_i · component_i   (all components in [0,1])

Every component is logged so retrieval is fully explainable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..cognitive.decay import DecayModel
from ..config import MemoryConfig
from ..domain.protac.context import ProtacContext, context_from_any
from ..store.store import MemoryStore
from ..util import clamp01, days_between, jaccard, loads

_TEMPORAL_HALF_LIFE_DAYS = 180.0
_WHY_THRESHOLD = 0.15


@dataclass
class RankedMemory:
    memory: dict[str, Any]
    score: float
    components: dict[str, float]
    why_retrieved: list[str] = field(default_factory=list)
    matched_entities: list[str] = field(default_factory=list)
    matched_context: dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.memory["id"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "memory_type": self.memory.get("memory_type"),
            "title": self.memory.get("title"),
            "score": self.score,
            "components": self.components,
            "why_retrieved": self.why_retrieved,
            "matched_entities": self.matched_entities,
            "matched_context": self.matched_context,
            "status": self.memory.get("status"),
            "confidence": self.memory.get("confidence"),
        }


class Reranker:
    def __init__(self, store: MemoryStore, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config
        self.weights = self.config.retrieval
        self.decay = DecayModel(store, self.config)

    def rank(
        self,
        candidates: list[dict[str, Any]],
        *,
        query: str,
        query_context: ProtacContext | None = None,
        query_entities: list[str] | None = None,
        lexical: dict[str, float] | None = None,
        semantic: dict[str, float] | None = None,
        graph: dict[str, float] | None = None,
        limit: int = 20,
    ) -> list[RankedMemory]:
        if not candidates:
            return []
        qctx = context_from_any(query_context)
        q_entities = set(query_entities or [])
        lexical = lexical or {}
        semantic = semantic or {}
        graph = graph or {}
        entity_map = self._entity_map([c["id"] for c in candidates])
        context_map = self._context_map([c["id"] for c in candidates])
        weights = self.weights
        weight_sum = (
            weights.lexical + weights.semantic + weights.entity + weights.graph
            + weights.context + weights.evidence + weights.confidence
            + weights.strength + weights.goal + weights.temporal
        ) or 1.0

        ranked: list[RankedMemory] = []
        for cand in candidates:
            mid = cand["id"]
            mem_entities = entity_map.get(mid, set())
            components = {
                "lexical": clamp01(lexical.get(mid, 0.0)),
                "semantic": clamp01(semantic.get(mid, 0.0)),
                "entity": clamp01(jaccard(q_entities, mem_entities)),
                "graph": clamp01(graph.get(mid, 0.0)),
                "context": 0.0,
                "evidence": clamp01(float(cand.get("evidence_strength") or 0.0)),
                "confidence": clamp01(float(cand.get("confidence") or 0.0)),
                "strength": clamp01(self.decay.effective_strength(cand)),
                "goal": clamp01(float(cand.get("goal_relevance") or 0.0)),
                "temporal": self._temporal(cand),
            }
            matched_context: dict[str, str] = {}
            cand_ctx = self._context_of(cand, context_map.get(mid))
            if cand_ctx is not None and qctx is not None:
                components["context"] = clamp01(qctx.match_score(cand_ctx))
                matched_context = {
                    k: v[0] for k, v in qctx.diff(cand_ctx).items() if v[0]
                }
            score = (
                weights.lexical * components["lexical"]
                + weights.semantic * components["semantic"]
                + weights.entity * components["entity"]
                + weights.graph * components["graph"]
                + weights.context * components["context"]
                + weights.evidence * components["evidence"]
                + weights.confidence * components["confidence"]
                + weights.strength * components["strength"]
                + weights.goal * components["goal"]
                + weights.temporal * components["temporal"]
            ) / weight_sum
            matched_entities = sorted(q_entities & mem_entities)
            ranked.append(RankedMemory(
                memory=cand,
                score=clamp01(score),
                components=components,
                why_retrieved=self._why(components),
                matched_entities=matched_entities,
                matched_context=matched_context,
            ))
        ranked.sort(key=lambda r: (-r.score, r.id))
        return ranked[:limit]

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _temporal(cand: dict[str, Any]) -> float:
        import math

        age = days_between(cand.get("created_at"))
        return clamp01(math.exp(-age / _TEMPORAL_HALF_LIFE_DAYS))

    @staticmethod
    def _context_of(cand: dict[str, Any], context_data: dict[str, Any] | None = None) -> ProtacContext | None:
        raw = cand.get("context_json") or context_data
        if raw:
            return context_from_any(raw if isinstance(raw, dict) else {})
        if cand.get("scope_json"):
            return ProtacContext.from_dict(cand["scope_json"] if isinstance(cand["scope_json"], dict) else {})
        return None

    def _context_map(self, memory_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Load episode context from the ``episodic_memories`` satellite table.

        The PROTAC context is stored on the satellite, not on ``memory_traces``;
        without this lookup the context-match reranking component is silently 0.
        """
        if not memory_ids:
            return {}
        out: dict[str, dict[str, Any]] = {}
        placeholders = ", ".join("?" for _ in memory_ids)
        rows = self.store.db.query(
            f"SELECT trace_id, context_json FROM episodic_memories "
            f"WHERE trace_id IN ({placeholders}) AND context_json IS NOT NULL",
            memory_ids,
        )
        for row in rows:
            parsed = loads(row["context_json"], {})
            if parsed:
                out[row["trace_id"]] = parsed
        return out

    def _entity_map(self, memory_ids: list[str]) -> dict[str, set[str]]:
        if not memory_ids:
            return {}
        out: dict[str, set[str]] = {}
        placeholders = ", ".join("?" for _ in memory_ids)
        rows = self.store.db.query(
            f"""
            SELECT me.memory_id, e.canonical_name
            FROM memory_entities me JOIN entities e ON e.id = me.entity_id
            WHERE me.memory_id IN ({placeholders})
            """,
            memory_ids,
        )
        for row in rows:
            out.setdefault(row["memory_id"], set()).add(row["canonical_name"])
        return out

    @staticmethod
    def _why(components: dict[str, float]) -> list[str]:
        labels = {
            "lexical": "lexical match",
            "semantic": "semantic similarity",
            "entity": "entity overlap",
            "graph": "graph neighbour",
            "context": "context match",
            "evidence": "evidence strength",
            "confidence": "confidence",
            "strength": "memory strength",
            "goal": "goal relevance",
            "temporal": "recency",
        }
        return [
            labels[name] for name, value in sorted(components.items(), key=lambda kv: kv[1], reverse=True)
            if value >= _WHY_THRESHOLD
        ]
