"""Semantic memory store: generalized, scope-aware, versioned claims."""

from __future__ import annotations

from typing import Any

from ..util import dumps, loads, now_iso
from .base import BaseStore


class SemanticStore(BaseStore):
    def add_semantic(
        self,
        *,
        claim: str,
        title: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        status: str = "active",
        scope: str | None = None,
        scope_json: dict[str, Any] | None = None,
        topic_key: str | None = None,
        confidence: float = 0.0,
        n_supporting: int = 0,
        n_contradicting: int = 0,
        n_independent_sources: int = 0,
        n_experimental: int = 0,
        n_computational: int = 0,
        n_literature: int = 0,
        replication_count: int = 0,
        source_quality: float = 0.0,
        context_consistency: float = 0.0,
        prediction_accuracy: float = 0.0,
        version: int = 1,
        supersedes_id: str | None = None,
        consolidation_event_id: str | None = None,
        provisional: bool = True,
        evidence_strength: float = 0.0,
        search_context: str | None = None,
        search_entities: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        trace_id = self.insert_trace(
            memory_type="semantic",
            title=title or claim[:120],
            content=claim,
            project_id=project_id,
            session_id=session_id,
            status=status,
            scope=scope,
            scope_json=scope_json,
            topic_key=topic_key,
            confidence=confidence,
            evidence_strength=evidence_strength,
            supersedes_id=supersedes_id,
            version=version,
            source_type="generalization",
            search_context=search_context,
            search_entities=search_entities,
            metadata_json=metadata,
        )
        self.db.execute(
            """
            INSERT INTO semantic_memories
                (trace_id, claim, topic_key, scope_json, confidence, n_supporting,
                 n_contradicting, n_independent_sources, n_experimental,
                 n_computational, n_literature, replication_count, source_quality,
                 context_consistency, prediction_accuracy, version, supersedes_id,
                 consolidation_event_id, provisional)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id, claim, topic_key, dumps(scope_json or {}), confidence,
                n_supporting, n_contradicting, n_independent_sources, n_experimental,
                n_computational, n_literature, replication_count, source_quality,
                context_consistency, prediction_accuracy, version, supersedes_id,
                consolidation_event_id, int(bool(provisional)),
            ),
        )
        return trace_id

    def get_semantic(self, trace_id: str) -> dict[str, Any] | None:
        row = self.db.query_one(
            """
            SELECT t.*, s.claim, s.topic_key AS sem_topic_key, s.scope_json AS sem_scope_json,
                   s.confidence AS sem_confidence, s.n_supporting, s.n_contradicting,
                   s.n_independent_sources, s.n_experimental, s.n_computational,
                   s.n_literature, s.replication_count, s.source_quality,
                   s.context_consistency, s.prediction_accuracy, s.version AS sem_version,
                   s.supersedes_id AS sem_supersedes_id, s.provisional,
                   s.consolidation_event_id, s.confidence_features_json
            FROM memory_traces t JOIN semantic_memories s ON s.trace_id = t.id
            WHERE t.id = ?
            """,
            (trace_id,),
        )
        if row is None:
            return None
        data = dict(row)
        for key in ("scope_json", "metadata_json", "sem_scope_json", "confidence_features_json"):
            data[key] = loads(data.get(key), {})
        return data

    def semantics(
        self,
        *,
        project_id: str | None = None,
        topic_key: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        sql = (
            "SELECT t.*, s.claim, s.n_supporting, s.n_contradicting, s.n_independent_sources, "
            "s.confidence AS sem_confidence, s.provisional, s.version AS sem_version, "
            "s.scope_json AS sem_scope_json "
            "FROM memory_traces t JOIN semantic_memories s ON s.trace_id = t.id "
            "WHERE t.deleted_at IS NULL"
        )
        params: list[Any] = []
        if project_id:
            sql += " AND t.project_id = ?"
            params.append(project_id)
        if topic_key:
            sql += " AND s.topic_key = ?"
            params.append(topic_key)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            sql += f" AND t.status IN ({placeholders})"
            params.extend(statuses)
        sql += " ORDER BY s.confidence DESC, t.updated_at DESC LIMIT ?"
        params.append(limit)
        out = []
        for r in self.db.query(sql, params):
            d = dict(r)
            d["sem_scope_json"] = loads(d.get("sem_scope_json"), {})
            out.append(d)
        return out

    def active_semantics(self, project_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return self.semantics(
            project_id=project_id,
            statuses=["active", "consolidated", "needs_review", "contradicted"],
            limit=limit,
        )

    def find_by_topic(self, topic_key: str, project_id: str | None = None) -> dict[str, Any] | None:
        results = self.semantics(project_id=project_id, topic_key=topic_key, limit=1)
        return results[0] if results else None

    def update_metrics(self, trace_id: str, **metrics: Any) -> None:
        allowed = {
            "confidence", "n_supporting", "n_contradicting", "n_independent_sources",
            "n_experimental", "n_computational", "n_literature", "replication_count",
            "source_quality", "context_consistency", "prediction_accuracy", "version",
            "supersedes_id", "provisional", "confidence_features_json",
        }
        updates = {k: v for k, v in metrics.items() if k in allowed}
        if not updates:
            return
        if "confidence_features_json" in updates and isinstance(updates["confidence_features_json"], (dict, list)):
            updates["confidence_features_json"] = dumps(updates["confidence_features_json"])
        if "provisional" in updates:
            updates["provisional"] = int(bool(updates["provisional"]))
        assignments = ", ".join(f"{k} = ?" for k in updates)
        self.db.execute(
            f"UPDATE semantic_memories SET {assignments} WHERE trace_id = ?",
            tuple(updates.values()) + (trace_id,),
        )
        if "confidence" in updates:
            self.update_trace(trace_id, confidence=updates["confidence"])
        if "version" in updates:
            self.update_trace(trace_id, version=updates["version"])

    def update_claim(
        self,
        trace_id: str,
        claim: str,
        *,
        scope_json: dict[str, Any] | None = None,
        reason: str = "reconsolidation",
    ) -> int:
        """Advance a semantic memory to a new version, preserving the old one."""
        current = self.require_trace(trace_id)
        old_version = int(current.get("version") or 1)
        self.snapshot_version(trace_id, reason=reason)
        new_version = old_version + 1
        self.db.execute(
            "UPDATE semantic_memories SET claim = ?" + (", scope_json = ?" if scope_json is not None else "")
            + " WHERE trace_id = ?",
            tuple([claim] + ([dumps(scope_json)] if scope_json is not None else []) + [trace_id]),
        )
        self.update_trace(trace_id, content=claim, title=claim[:120], version=new_version)
        return new_version
