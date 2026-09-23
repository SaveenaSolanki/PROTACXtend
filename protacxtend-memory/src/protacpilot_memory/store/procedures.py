"""Procedural memory store: reusable workflows (not scientific claims)."""

from __future__ import annotations

from typing import Any

from ..util import dumps, loads
from .base import BaseStore


class ProcedureStore(BaseStore):
    def add_procedure(
        self,
        *,
        workflow_name: str,
        steps: list[str] | list[dict[str, Any]],
        title: str | None = None,
        content: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        domain: str | None = None,
        preconditions: str | None = None,
        status: str = "active",
        search_context: str | None = None,
        search_entities: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        trace_id = self.insert_trace(
            memory_type="procedural",
            title=title or workflow_name,
            content=content or "\n".join(
                s if isinstance(s, str) else str(s.get("step", s)) for s in steps
            ),
            project_id=project_id,
            session_id=session_id,
            status=status,
            source_type="procedure",
            search_context=search_context,
            search_entities=search_entities,
            metadata_json=metadata,
        )
        self.db.execute(
            """
            INSERT INTO procedural_memories
                (trace_id, workflow_name, steps_json, domain, preconditions)
            VALUES (?, ?, ?, ?, ?)
            """,
            (trace_id, workflow_name, dumps(steps), domain, preconditions),
        )
        return trace_id

    def get_procedure(self, trace_id: str) -> dict[str, Any] | None:
        row = self.db.query_one(
            """
            SELECT t.*, p.workflow_name, p.steps_json, p.domain, p.preconditions,
                   p.success_count, p.failure_count
            FROM memory_traces t JOIN procedural_memories p ON p.trace_id = t.id
            WHERE t.id = ?
            """,
            (trace_id,),
        )
        if row is None:
            return None
        data = dict(row)
        data["steps_json"] = loads(data.get("steps_json"), [])
        data["metadata_json"] = loads(data.get("metadata_json"), {})
        return data

    def procedures(self, project_id: str | None = None, domain: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        sql = (
            "SELECT t.*, p.workflow_name, p.steps_json, p.domain, p.success_count, p.failure_count "
            "FROM memory_traces t JOIN procedural_memories p ON p.trace_id = t.id "
            "WHERE t.deleted_at IS NULL"
        )
        params: list[Any] = []
        if project_id:
            sql += " AND t.project_id = ?"
            params.append(project_id)
        if domain:
            sql += " AND p.domain = ?"
            params.append(domain)
        sql += " ORDER BY p.success_count DESC, t.updated_at DESC LIMIT ?"
        params.append(limit)
        out = []
        for r in self.db.query(sql, params):
            d = dict(r)
            d["steps_json"] = loads(d.get("steps_json"), [])
            out.append(d)
        return out

    def find_by_workflow(self, workflow_name: str, project_id: str | None = None) -> dict[str, Any] | None:
        sql = (
            "SELECT t.id FROM memory_traces t JOIN procedural_memories p ON p.trace_id = t.id "
            "WHERE p.workflow_name = ? AND t.deleted_at IS NULL"
        )
        params: list[Any] = [workflow_name]
        if project_id:
            sql += " AND t.project_id = ?"
            params.append(project_id)
        sql += " LIMIT 1"
        row = self.db.query_one(sql, params)
        return self.get_procedure(row["id"]) if row else None

    def record_run(self, trace_id: str, success: bool) -> None:
        column = "success_count" if success else "failure_count"
        self.db.execute(
            f"UPDATE procedural_memories SET {column} = {column} + 1 WHERE trace_id = ?",
            (trace_id,),
        )
