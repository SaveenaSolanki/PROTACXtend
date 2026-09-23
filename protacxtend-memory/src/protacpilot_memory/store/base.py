"""Shared store primitives: universal memory trace + event ledger."""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from ..config import MemoryConfig
from ..db import Database
from ..util import content_hash, dumps, loads, new_id, now_iso

_ID_PREFIX = {
    "episodic": "EP",
    "negative": "NEG",
    "semantic": "SEM",
    "procedural": "PROC",
    "prospective": "PROSP",
    "working": "WM",
}

_JSON_FIELDS = ("scope_json", "encoding_breakdown_json", "metadata_json")

_TRACE_UPDATABLE = {
    "title", "content", "project_id", "session_id", "status", "scope",
    "scope_json", "topic_key", "context_fingerprint", "last_accessed_at",
    "salience", "novelty", "goal_relevance", "surprise", "evidence_strength",
    "confidence", "memory_strength", "review_after", "supersedes_id",
    "version", "source_type", "source_id", "encoding_score",
    "encoding_breakdown_json", "search_context", "search_entities",
    "metadata_json", "deleted_at", "normalized_hash", "duplicate_count",
    "last_seen_at", "retrieval_count", "successful_retrieval_count",
}


def row_to_trace(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for field in _JSON_FIELDS:
        if field in data:
            data[field] = loads(data[field], default={} if field != "metadata_json" else {})
    return data


class BaseStore:
    """Common behaviour for all typed stores."""

    def __init__(self, db: Database, config: MemoryConfig) -> None:
        self.db = db
        self.config = config

    # ── identifiers ──────────────────────────────────────────────────────────
    @staticmethod
    def new_trace_id(memory_type: str) -> str:
        return new_id(_ID_PREFIX.get(memory_type, "MEM"))

    # ── event ledger (event sourcing, Master Prompt §39) ─────────────────────
    def log_event(
        self,
        memory_id: str | None,
        event_type: str,
        detail: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> None:
        self.db.execute(
            "INSERT INTO memory_events(memory_id, event_type, detail_json, session_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (memory_id, event_type, dumps(detail or {}), session_id, now_iso()),
        )

    def events_for(self, memory_id: str) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT * FROM memory_events WHERE memory_id = ? ORDER BY id ASC", (memory_id,)
        )
        return [dict(r) | {"detail_json": loads(r["detail_json"], {})} for r in rows]

    # ── universal trace ──────────────────────────────────────────────────────
    def insert_trace(self, **fields: Any) -> str:
        memory_type = fields["memory_type"]
        trace_id = fields.get("id") or self.new_trace_id(memory_type)
        ts = fields.get("created_at") or now_iso()
        params: dict[str, Any] = {
            "id": trace_id,
            "memory_type": memory_type,
            "title": fields.get("title") or "",
            "content": fields.get("content") or "",
            "project_id": fields.get("project_id"),
            "session_id": fields.get("session_id"),
            "status": fields.get("status", "active"),
            "scope": fields.get("scope"),
            "scope_json": dumps(fields["scope_json"]) if isinstance(fields.get("scope_json"), (dict, list)) else fields.get("scope_json"),
            "topic_key": fields.get("topic_key"),
            "context_fingerprint": fields.get("context_fingerprint"),
            "created_at": ts,
            "updated_at": ts,
            "last_accessed_at": fields.get("last_accessed_at"),
            "deleted_at": fields.get("deleted_at"),
            "salience": float(fields.get("salience", 0.0) or 0.0),
            "novelty": float(fields.get("novelty", 0.0) or 0.0),
            "goal_relevance": float(fields.get("goal_relevance", 0.0) or 0.0),
            "surprise": float(fields.get("surprise", 0.0) or 0.0),
            "evidence_strength": float(fields.get("evidence_strength", 0.0) or 0.0),
            "confidence": float(fields.get("confidence", 0.0) or 0.0),
            "memory_strength": float(fields.get("memory_strength", 1.0)),
            "review_after": fields.get("review_after"),
            "supersedes_id": fields.get("supersedes_id"),
            "version": int(fields.get("version", 1)),
            "source_type": fields.get("source_type"),
            "source_id": fields.get("source_id"),
            "encoding_score": fields.get("encoding_score"),
            "encoding_breakdown_json": dumps(fields["encoding_breakdown_json"]) if isinstance(fields.get("encoding_breakdown_json"), (dict, list)) else fields.get("encoding_breakdown_json"),
            "search_context": fields.get("search_context"),
            "search_entities": fields.get("search_entities"),
            "metadata_json": dumps(fields.get("metadata_json") or {}),
            "normalized_hash": fields.get("normalized_hash") or content_hash(
                f"{fields.get('title') or ''}\n{fields.get('content') or ''}"
            ),
            "duplicate_count": int(fields.get("duplicate_count", 1)),
            "last_seen_at": fields.get("last_seen_at") or ts,
        }
        columns = ", ".join(params.keys())
        placeholders = ", ".join("?" for _ in params)
        self.db.execute(
            f"INSERT INTO memory_traces ({columns}) VALUES ({placeholders})",
            tuple(params.values()),
        )
        return trace_id

    def get_trace(self, trace_id: str, *, include_deleted: bool = False) -> dict[str, Any] | None:
        sql = "SELECT * FROM memory_traces WHERE id = ?"
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        return row_to_trace(self.db.query_one(sql, (trace_id,)))

    def require_trace(self, trace_id: str, *, include_deleted: bool = True) -> dict[str, Any]:
        trace = self.get_trace(trace_id, include_deleted=include_deleted)
        if trace is None:
            from ..errors import NotFoundError

            raise NotFoundError("memory", trace_id)
        return trace

    def update_trace(self, trace_id: str, **fields: Any) -> None:
        updates = {k: v for k, v in fields.items() if k in _TRACE_UPDATABLE}
        if not updates:
            return
        for key in ("scope_json", "encoding_breakdown_json", "metadata_json"):
            if key in updates and isinstance(updates[key], (dict, list)):
                updates[key] = dumps(updates[key])
        updates["updated_at"] = fields.get("updated_at") or now_iso()
        assignments = ", ".join(f"{k} = ?" for k in updates)
        self.db.execute(
            f"UPDATE memory_traces SET {assignments} WHERE id = ?",
            tuple(updates.values()) + (trace_id,),
        )

    def set_status(
        self,
        trace_id: str,
        status: str,
        reason: str | None = None,
        session_id: str | None = None,
        *,
        event_type: str = "STATE_CHANGED",
        event_detail: dict[str, Any] | None = None,
        force: bool = False,
    ) -> bool:
        """Validate and apply a lifecycle transition atomically.

        Returns ``True`` if the status changed, ``False`` for an idempotent
        self-transition. Raises ``InvalidMemoryTransition`` for an illegal or
        unknown target. The ``STATE_CHANGED`` (or caller-supplied) event is
        appended *only* after a successful mutation, inside the same
        transaction, so a rejected transition leaves no trace.
        """
        from ..cognitive.state_machine import is_known_status, validate_transition
        from ..domain.protac.ontology import MEMORY_STATUSES

        trace = self.require_trace(trace_id)
        current = trace.get("status") or "active"
        if status == current:
            return False
        if force:
            if not is_known_status(status):
                from ..errors import InvalidMemoryTransition

                raise InvalidMemoryTransition(trace_id, current, status, MEMORY_STATUSES)
        else:
            validate_transition(trace_id, current, status)
        return self._apply_status(
            trace_id, current, status, reason, session_id, event_type, event_detail
        )

    def _apply_status(
        self,
        trace_id: str,
        expected_current: str,
        status: str,
        reason: str | None,
        session_id: str | None,
        event_type: str,
        event_detail: dict[str, Any] | None,
    ) -> bool:
        """Atomically apply an already-validated transition.

        The conditional ``UPDATE ... WHERE status = expected_current`` is the
        optimistic-concurrency guard: if another writer changed the status
        between validation and mutation, the row is not updated and a
        ``ConflictError`` is raised *before* any event is logged.
        """
        from ..errors import ConflictError
        from ..util import now_iso

        detail: dict[str, Any] = {"from": expected_current, "to": status, "reason": reason}
        if event_detail:
            detail.update(event_detail)
        with self.db.transaction():
            cursor = self.db.execute(
                "UPDATE memory_traces SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
                (status, now_iso(), trace_id, expected_current),
            )
            if cursor.rowcount != 1:
                raise ConflictError(
                    f"concurrent status change for {trace_id}: expected "
                    f"{expected_current!r} but row no longer matches"
                )
            self.log_event(trace_id, event_type, detail, session_id)
        return True

    def force_status(
        self,
        trace_id: str,
        status: str,
        reason: str | None = None,
        session_id: str | None = None,
    ) -> bool:
        """Administrative override that bypasses the transition graph.

        Must never be used by normal cognitive logic. It still rejects unknown
        statuses and records the override (with ``forced: True``) in the event
        ledger for auditability.
        """
        return self.set_status(
            trace_id,
            status,
            reason=reason,
            session_id=session_id,
            event_type="STATE_CHANGED",
            event_detail={"forced": True},
            force=True,
        )

    def soft_delete(self, trace_id: str, session_id: str | None = None) -> None:
        self.db.execute(
            "UPDATE memory_traces SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (now_iso(), now_iso(), trace_id),
        )
        self.log_event(trace_id, "ARCHIVED", {"soft_delete": True}, session_id)

    def restore(self, trace_id: str) -> None:
        self.update_trace(trace_id, deleted_at=None)
        self.log_event(trace_id, "STATE_CHANGED", {"restored": True})

    def hard_delete(self, trace_id: str) -> None:
        """Explicit, non-automatic physical deletion (provenance loss)."""
        self.db.execute("DELETE FROM memory_traces WHERE id = ?", (trace_id,))

    # ── versioning (never overwrite scientific history) ──────────────────────
    def snapshot_version(self, trace_id: str, reason: str = "update") -> int:
        trace = self.require_trace(trace_id)
        version = int(trace.get("version") or 1)
        self.db.execute(
            """
            INSERT OR REPLACE INTO memory_versions
                (memory_id, version, content, confidence, status, scope_json,
                 snapshot_json, created_at, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                version,
                trace.get("content"),
                trace.get("confidence"),
                trace.get("status"),
                dumps(trace.get("scope_json") or {}),
                dumps(trace),
                now_iso(),
                reason,
            ),
        )
        return version

    def versions_for(self, trace_id: str) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT * FROM memory_versions WHERE memory_id = ? ORDER BY version DESC",
            (trace_id,),
        )
        return [dict(r) | {"snapshot_json": loads(r["snapshot_json"], {})} for r in rows]

    # ── retrieval accounting ─────────────────────────────────────────────────
    def log_access(
        self,
        memory_id: str,
        *,
        session_id: str | None,
        query: str | None,
        rank: int | None,
        score: float | None,
        components: dict[str, Any] | None,
        was_useful: bool | None = None,
        used_for: str | None = None,
    ) -> int:
        cursor = self.db.execute(
            """
            INSERT INTO memory_access_log
                (memory_id, session_id, query, retrieved_at, rank, score,
                 components_json, was_useful, used_for, feedback_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id, session_id, query, now_iso(), rank, score,
                dumps(components or {}),
                None if was_useful is None else int(bool(was_useful)),
                used_for, None if was_useful is None else now_iso(),
            ),
        )
        self.db.execute(
            "UPDATE memory_traces SET retrieval_count = retrieval_count + 1, "
            "last_accessed_at = ? WHERE id = ?",
            (now_iso(), memory_id),
        )
        return int(cursor.lastrowid or 0)

    def access_log_for(self, memory_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT * FROM memory_access_log WHERE memory_id = ? "
            "ORDER BY retrieved_at DESC LIMIT ?",
            (memory_id, limit),
        )
        return [dict(r) | {"components_json": loads(r["components_json"], {})} for r in rows]

    # ── convenience ──────────────────────────────────────────────────────────
    def count(self, table: str, where: str = "1=1", params: Sequence[Any] = ()) -> int:
        return int(self.db.scalar(f"SELECT COUNT(*) FROM {table} WHERE {where}", params, 0))

    def iter_rows(self, table: str, where: str = "1=1", params: Sequence[Any] = ()) -> Iterable[Any]:
        return iter(self.db.query(f"SELECT * FROM {table} WHERE {where}", params))
