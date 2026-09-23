"""Prospective memory + tasks (Master Prompt §29)."""

from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from ..util import dumps, loads, new_id, now_iso
from .base import BaseStore


class ProspectiveStore(BaseStore):
    # ── tasks ────────────────────────────────────────────────────────────────
    def add_task(
        self,
        *,
        title: str,
        project_id: str | None = None,
        session_id: str | None = None,
        description: str | None = None,
        due_at: str | None = None,
        related_memory_id: str | None = None,
        priority: float = 0.5,
        status: str = "open",
    ) -> str:
        task_id = new_id("task")
        self.db.execute(
            """
            INSERT INTO tasks(id, project_id, session_id, title, description, status,
                              due_at, related_memory_id, priority, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, project_id, session_id, title, description, status, due_at,
             related_memory_id, float(priority), now_iso()),
        )
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return dict(row) if row else None

    def open_tasks(self, project_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        sql = "SELECT * FROM tasks WHERE status = 'open'"
        params: list[Any] = []
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY priority DESC, COALESCE(due_at, '9999') ASC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.db.query(sql, params)]

    def resolve_task(self, task_id: str, status: str = "done", note: str | None = None) -> None:
        task = self.get_task(task_id)
        if task is None:
            raise NotFoundError("task", task_id)
        self.db.execute(
            "UPDATE tasks SET status = ?, resolved_at = ? WHERE id = ?",
            (status, now_iso(), task_id),
        )
        self.db.execute(
            "UPDATE prospective_memories SET status = ? WHERE task_id = ?", (status, task_id)
        )
        related = task.get("related_memory_id")
        if related:
            self.log_event(related, "STATE_CHANGED", {"task_resolved": task_id, "status": status, "note": note})

    # ── prospective memories ─────────────────────────────────────────────────
    def add_prospective(
        self,
        *,
        title: str,
        content: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        task_id: str | None = None,
        trigger: str | None = None,
        due_at: str | None = None,
        related_memory_id: str | None = None,
        status: str = "open",
        priority: float = 0.5,
        salience: float = 0.0,
        search_context: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        trace_id = self.insert_trace(
            memory_type="prospective",
            title=title,
            content=content or title,
            project_id=project_id,
            session_id=session_id,
            status="active",
            source_type="prospective",
            salience=salience,
            search_context=search_context,
            metadata_json=metadata,
        )
        if task_id is None:
            task_id = self.add_task(
                title=title, project_id=project_id, session_id=session_id,
                description=content, due_at=due_at, related_memory_id=related_memory_id,
                priority=priority, status=status,
            )
        self.db.execute(
            """
            INSERT INTO prospective_memories
                (trace_id, task_id, trigger, due_at, related_memory_id, status, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (trace_id, task_id, trigger, due_at, related_memory_id, status, float(priority)),
        )
        return trace_id

    def get_prospective(self, trace_id: str) -> dict[str, Any] | None:
        row = self.db.query_one(
            """
            SELECT t.*, p.task_id, p.trigger, p.due_at, p.related_memory_id,
                   p.status AS prosp_status, p.priority
            FROM memory_traces t JOIN prospective_memories p ON p.trace_id = t.id
            WHERE t.id = ?
            """,
            (trace_id,),
        )
        if row is None:
            return None
        data = dict(row)
        data["metadata_json"] = loads(data.get("metadata_json"), {})
        return data

    def prospective_open(self, project_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        sql = (
            "SELECT t.*, p.task_id, p.trigger, p.due_at, p.related_memory_id, "
            "p.status AS prosp_status, p.priority "
            "FROM memory_traces t JOIN prospective_memories p ON p.trace_id = t.id "
            "WHERE t.deleted_at IS NULL AND p.status = 'open'"
        )
        params: list[Any] = []
        if project_id:
            sql += " AND t.project_id = ?"
            params.append(project_id)
        sql += " ORDER BY p.priority DESC, COALESCE(p.due_at, '9999') ASC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.db.query(sql, params)]

    def never_resolved(self, older_than_days: float = 90.0) -> list[dict[str, Any]]:
        """Prospective tasks created long ago and still open (audit)."""
        from ..util import iso_in_days

        cutoff = iso_in_days(-older_than_days)
        rows = self.db.query(
            "SELECT * FROM tasks WHERE status = 'open' AND created_at < ? ORDER BY created_at ASC",
            (cutoff,),
        )
        return [dict(r) for r in rows]
