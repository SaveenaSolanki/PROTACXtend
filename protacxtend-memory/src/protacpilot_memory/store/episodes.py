"""Episodic memory store: high-resolution individual experiences."""

from __future__ import annotations

from typing import Any

from ..util import dumps, loads
from .base import BaseStore


class EpisodeStore(BaseStore):
    def add_episode(
        self,
        *,
        title: str,
        content: str,
        event_type: str,
        project_id: str | None = None,
        session_id: str | None = None,
        status: str = "active",
        scope: str | None = None,
        scope_json: dict[str, Any] | None = None,
        topic_key: str | None = None,
        context_fingerprint: str | None = None,
        observed: dict[str, Any] | None = None,
        interpretation: str | None = None,
        context: dict[str, Any] | None = None,
        source: dict[str, Any] | None = None,
        prediction_id: str | None = None,
        outcome_id: str | None = None,
        is_negative: bool = False,
        salience: float = 0.0,
        novelty: float = 0.0,
        goal_relevance: float = 0.0,
        surprise: float = 0.0,
        evidence_strength: float = 0.0,
        confidence: float = 0.0,
        memory_strength: float = 1.0,
        encoding_score: float | None = None,
        encoding_breakdown: dict[str, Any] | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        search_context: str | None = None,
        search_entities: str | None = None,
        review_after: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        memory_type = "negative" if is_negative else "episodic"
        trace_id = self.insert_trace(
            memory_type=memory_type,
            title=title,
            content=content,
            project_id=project_id,
            session_id=session_id,
            status=status,
            scope=scope,
            scope_json=scope_json,
            topic_key=topic_key,
            context_fingerprint=context_fingerprint,
            salience=salience,
            novelty=novelty,
            goal_relevance=goal_relevance,
            surprise=surprise,
            evidence_strength=evidence_strength,
            confidence=confidence,
            memory_strength=memory_strength,
            encoding_score=encoding_score,
            encoding_breakdown_json=encoding_breakdown,
            source_type=source_type,
            source_id=source_id,
            search_context=search_context,
            search_entities=search_entities,
            review_after=review_after,
            metadata_json=metadata,
        )
        self.db.execute(
            """
            INSERT INTO episodic_memories
                (trace_id, event_type, prediction_id, outcome_id, observed_json,
                 interpretation, context_json, source_json, context_fingerprint,
                 is_negative, encoding_score, encoding_breakdown_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id, event_type, prediction_id, outcome_id,
                dumps(observed or {}), interpretation, dumps(context or {}),
                dumps(source or {}), context_fingerprint, int(bool(is_negative)),
                encoding_score, dumps(encoding_breakdown or {}),
            ),
        )
        return trace_id

    def get_episode(self, trace_id: str) -> dict[str, Any] | None:
        row = self.db.query_one(
            """
            SELECT t.*, e.event_type, e.prediction_id, e.outcome_id, e.observed_json,
                   e.interpretation, e.context_json, e.source_json, e.context_fingerprint,
                   e.is_negative, e.encoding_breakdown_json
            FROM memory_traces t JOIN episodic_memories e ON e.trace_id = t.id
            WHERE t.id = ?
            """,
            (trace_id,),
        )
        if row is None:
            return None
        data = dict(row)
        for key in ("scope_json", "metadata_json", "observed_json", "context_json",
                    "source_json", "encoding_breakdown_json"):
            data[key] = loads(data.get(key), {})
        return data

    def episodes(
        self,
        *,
        project_id: str | None = None,
        event_type: str | None = None,
        fingerprint: str | None = None,
        include_negative: bool = True,
        statuses: list[str] | None = None,
        limit: int = 500,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = (
            "SELECT t.*, e.event_type, e.is_negative, e.observed_json, e.interpretation, "
            "e.prediction_id, e.outcome_id, e.context_fingerprint, e.context_json "
            "FROM memory_traces t JOIN episodic_memories e ON e.trace_id = t.id "
            "WHERE t.deleted_at IS NULL"
        )
        params: list[Any] = []
        if project_id:
            sql += " AND t.project_id = ?"
            params.append(project_id)
        if session_id:
            sql += " AND t.session_id = ?"
            params.append(session_id)
        if event_type:
            sql += " AND e.event_type = ?"
            params.append(event_type)
        if fingerprint:
            sql += " AND e.context_fingerprint = ?"
            params.append(fingerprint)
        if not include_negative:
            sql += " AND e.is_negative = 0"
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            sql += f" AND t.status IN ({placeholders})"
            params.extend(statuses)
        sql += " ORDER BY t.created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) | {"observed_json": loads(r["observed_json"], {}),
                           "context_json": loads(r["context_json"], {})}
                for r in self.db.query(sql, params)]

    def negative_for_fingerprint(self, fingerprint: str, project_id: str | None = None) -> list[dict[str, Any]]:
        return self.episodes(fingerprint=fingerprint, project_id=project_id, include_negative=True)

    def episode_for_prediction(self, prediction_id: str) -> dict[str, Any] | None:
        row = self.db.query_one(
            "SELECT trace_id FROM episodic_memories WHERE prediction_id = ? LIMIT 1",
            (prediction_id,),
        )
        return self.get_episode(row["trace_id"]) if row else None

    def link_outcome(self, trace_id: str, outcome_id: str) -> None:
        self.db.execute(
            "UPDATE episodic_memories SET outcome_id = ? WHERE trace_id = ?", (outcome_id, trace_id)
        )
