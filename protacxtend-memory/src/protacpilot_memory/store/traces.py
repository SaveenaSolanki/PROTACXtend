"""Universal trace store: lifecycle, soft delete, versions, retrieval log."""

from __future__ import annotations

from typing import Any

from ..errors import ValidationError
from ..util import loads, now_iso
from .base import BaseStore, row_to_trace


class TraceStore(BaseStore):
    def get(self, trace_id: str) -> dict[str, Any] | None:
        return self.get_trace(trace_id)

    def list(
        self,
        *,
        project_id: str | None = None,
        memory_type: str | None = None,
        status: str | None = None,
        session_id: str | None = None,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM memory_traces WHERE 1=1"
        params: list[Any] = []
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type)
        if status:
            sql += " AND status = ?"
            params.append(status)
        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return [row_to_trace(r) for r in self.db.query(sql, params)]  # type: ignore[misc]

    def recent(
        self, project_id: str | None = None, limit: int = 10, memory_types: list[str] | None = None
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM memory_traces WHERE deleted_at IS NULL"
        params: list[Any] = []
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        if memory_types:
            placeholders = ", ".join("?" for _ in memory_types)
            sql += f" AND memory_type IN ({placeholders})"
            params.extend(memory_types)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [row_to_trace(r) for r in self.db.query(sql, params)]  # type: ignore[misc]

    def high_salience(self, project_id: str, limit: int = 10, memory_types: list[str] | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM memory_traces WHERE deleted_at IS NULL AND status IN ('active','consolidated','candidate','needs_review')"
        params: list[Any] = []
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        if memory_types:
            placeholders = ", ".join("?" for _ in memory_types)
            sql += f" AND memory_type IN ({placeholders})"
            params.extend(memory_types)
        sql += " ORDER BY (salience + surprise) DESC, created_at DESC LIMIT ?"
        params.append(limit)
        return [row_to_trace(r) for r in self.db.query(sql, params)]  # type: ignore[misc]

    # ── lifecycle ────────────────────────────────────────────────────────────
    def archive(self, trace_id: str, session_id: str | None = None, reason: str | None = None) -> None:
        from ..domain.protac.ontology import STATUS_ARCHIVED

        self.set_status(
            trace_id, STATUS_ARCHIVED, reason=reason, session_id=session_id,
            event_type="ARCHIVED", event_detail={"reason": reason},
        )

    def supersede(self, trace_id: str, superseded_by: str, reason: str | None = None) -> None:
        from ..domain.protac.ontology import STATUS_SUPERSEDED

        self.set_status(
            trace_id, STATUS_SUPERSEDED, reason=reason,
            event_type="SUPERSEDED",
            event_detail={"superseded_by": superseded_by, "reason": reason},
        )

    def mark_review(self, trace_id: str, reason: str | None = None) -> None:
        from ..domain.protac.ontology import STATUS_NEEDS_REVIEW

        self.set_status(
            trace_id, STATUS_NEEDS_REVIEW, reason=reason,
            event_type="REVIEW_MARKED",
        )

    # ── traversal helpers ────────────────────────────────────────────────────
    def by_topic(self, topic_key: str, project_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM memory_traces WHERE topic_key = ? AND deleted_at IS NULL"
        params: list[Any] = [topic_key]
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY updated_at DESC"
        return [row_to_trace(r) for r in self.db.query(sql, params)]  # type: ignore[misc]

    def by_fingerprint(self, fingerprint: str, project_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM memory_traces WHERE context_fingerprint = ? AND deleted_at IS NULL"
        params: list[Any] = [fingerprint]
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY created_at DESC"
        return [row_to_trace(r) for r in self.db.query(sql, params)]  # type: ignore[misc]

    def timeline(self, memory_id: str, window: int = 5) -> dict[str, Any]:
        """Chronological neighbourhood around a memory (progressive disclosure L2)."""
        anchor = self.require_trace(memory_id)
        session_id = anchor.get("session_id")
        project_id = anchor.get("project_id")
        if session_id:
            rows = self.db.query(
                "SELECT * FROM memory_traces WHERE session_id = ? AND deleted_at IS NULL "
                "ORDER BY created_at ASC",
                (session_id,),
            )
        else:
            rows = self.db.query(
                "SELECT * FROM memory_traces WHERE project_id IS ? AND deleted_at IS NULL "
                "ORDER BY created_at ASC",
                (project_id,),
            )
        traces = [row_to_trace(r) for r in rows]  # type: ignore[misc]
        index = next((i for i, t in enumerate(traces) if t["id"] == memory_id), 0)
        return {
            "anchor": anchor,
            "before": traces[max(0, index - window):index],
            "after": traces[index + 1:index + 1 + window],
        }

    def retrieval_stats(self, trace_id: str) -> dict[str, Any]:
        trace = self.require_trace(trace_id)
        useful = self.count(
            "memory_access_log", "memory_id = ? AND was_useful = 1", (trace_id,)
        )
        useless = self.count(
            "memory_access_log", "memory_id = ? AND was_useful = 0", (trace_id,)
        )
        return {
            "retrieval_count": trace.get("retrieval_count", 0),
            "successful_retrieval_count": trace.get("successful_retrieval_count", 0),
            "feedback_useful": useful,
            "feedback_useless": useless,
        }

    def validate_type(self, memory_type: str) -> None:
        from ..domain.protac.ontology import MEMORY_TYPES

        if memory_type not in MEMORY_TYPES:
            raise ValidationError(f"unknown memory_type: {memory_type}")
