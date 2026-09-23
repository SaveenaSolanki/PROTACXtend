"""Relation-graph store: typed, confidence-weighted memory relations."""

from __future__ import annotations

from collections import deque
from typing import Any

from ..util import dumps, loads, now_iso
from .base import BaseStore

# Relations that propagate "evidence-like" support when traversing.
SUPPORT_RELATIONS = {"supports", "refines", "replicates", "generalizes", "derived_from", "caused_decision"}
OPPOSING_RELATIONS = {"contradicts", "failed_to_replicate", "exception_to"}
STRUCTURAL_RELATIONS = {"same_context", "related_context", "predicted", "observed", "supersedes"}


class RelationStore(BaseStore):
    def add_relation(
        self,
        source_memory_id: str,
        target_memory_id: str,
        relation_type: str,
        *,
        confidence: float = 0.5,
        created_by: str = "system",
        rationale: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        self.db.execute(
            """
            INSERT INTO memory_relations
                (source_memory_id, target_memory_id, relation_type, confidence,
                 created_by, created_at, rationale, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_memory_id, target_memory_id, relation_type)
            DO UPDATE SET confidence = excluded.confidence,
                          rationale = excluded.rationale,
                          created_by = excluded.created_by
            """,
            (
                source_memory_id, target_memory_id, relation_type, float(confidence),
                created_by, now_iso(), rationale, dumps(metadata or {}),
            ),
        )
        row = self.db.query_one(
            "SELECT id FROM memory_relations WHERE source_memory_id = ? AND "
            "target_memory_id = ? AND relation_type = ?",
            (source_memory_id, target_memory_id, relation_type),
        )
        return int(row["id"]) if row else 0

    def relations_for(self, memory_id: str, direction: str = "both") -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if direction in ("out", "both"):
            clauses.append("source_memory_id = ?")
            params.append(memory_id)
        if direction in ("in", "both"):
            clauses.append("target_memory_id = ?")
            params.append(memory_id)
        where = " OR ".join(clauses) if clauses else "1=0"
        rows = self.db.query(
            f"SELECT * FROM memory_relations WHERE {where} ORDER BY created_at DESC", params
        )
        return [dict(r) | {"metadata_json": loads(r["metadata_json"], {})} for r in rows]

    def relation_exists(self, source: str, target: str, relation_type: str) -> bool:
        row = self.db.query_one(
            "SELECT 1 FROM memory_relations WHERE source_memory_id = ? AND "
            "target_memory_id = ? AND relation_type = ?",
            (source, target, relation_type),
        )
        return row is not None

    def neighbors(self, memory_id: str, depth: int = 1, relation_types: list[str] | None = None) -> list[dict[str, Any]]:
        """Breadth-first associative expansion. Foundation of pattern completion."""
        seen = {memory_id}
        frontier = deque([(memory_id, 0)])
        out: list[dict[str, Any]] = []
        while frontier:
            current, dist = frontier.popleft()
            if dist >= depth:
                continue
            for rel in self.relations_for(current):
                target = rel["target_memory_id"] if rel["source_memory_id"] == current else rel["source_memory_id"]
                if relation_types and rel["relation_type"] not in relation_types:
                    continue
                if target in seen:
                    continue
                seen.add(target)
                out.append({
                    "memory_id": target,
                    "via": rel["relation_type"],
                    "direction": "out" if rel["source_memory_id"] == current else "in",
                    "confidence": rel["confidence"],
                    "distance": dist + 1,
                })
                frontier.append((target, dist + 1))
        return out

    def supersede(self, old_memory_id: str, new_memory_id: str, rationale: str | None = None) -> None:
        self.add_relation(
            new_memory_id, old_memory_id, "supersedes",
            confidence=1.0, created_by="reconsolidation", rationale=rationale,
        )

    def contradictions_for(self, memory_id: str) -> list[dict[str, Any]]:
        return [r for r in self.relations_for(memory_id) if r["relation_type"] == "contradicts"]

    def unresolved_contradictions(self) -> list[dict[str, Any]]:
        rows = self.db.query(
            """
            SELECT r.*, o.status AS old_status, n.status AS new_status,
                   o.title AS source_title, n.title AS target_title
            FROM memory_relations r
            LEFT JOIN memory_traces o ON o.id = r.source_memory_id
            LEFT JOIN memory_traces n ON n.id = r.target_memory_id
            WHERE r.relation_type = 'contradicts'
              AND o.deleted_at IS NULL AND n.deleted_at IS NULL
              AND (o.status NOT IN ('superseded','retracted','archived')
                   OR n.status NOT IN ('superseded','retracted','archived'))
            ORDER BY r.created_at DESC
            """
        )
        return [dict(r) for r in rows]
