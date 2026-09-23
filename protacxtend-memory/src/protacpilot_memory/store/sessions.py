"""Projects, sessions, and transient working memory (Master Prompt §3A, §54)."""

from __future__ import annotations

from typing import Any

from ..util import dumps, iso_in_days, loads, new_id, now_iso
from .base import BaseStore


class SessionStore(BaseStore):
    # ── projects ─────────────────────────────────────────────────────────────
    def ensure_project(self, name: str, description: str | None = None) -> str:
        project_id = new_id("proj")
        row = self.db.query_one("SELECT id FROM projects WHERE name = ?", (name,))
        if row is not None:
            if description:
                self.db.execute("UPDATE projects SET description = ? WHERE id = ?", (description, row["id"]))
            return row["id"]
        self.db.execute(
            "INSERT INTO projects(id, name, description, created_at, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (project_id, name, description, now_iso(), dumps({})),
        )
        return project_id

    def get_project(self, name: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM projects WHERE name = ?", (name,))
        return dict(row) if row else None

    def get_project_by_id(self, project_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM projects WHERE id = ?", (project_id,))
        return dict(row) if row else None

    def list_projects(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query("SELECT * FROM projects ORDER BY name")]

    def resolve_project(self, name: str | None = None, description: str | None = None) -> str:
        return self.ensure_project(name or self.config.project_name, description)

    # ── sessions ─────────────────────────────────────────────────────────────
    def start_session(self, project_id: str | None = None, goal: str | None = None) -> str:
        session_id = new_id("sess")
        self.db.execute(
            "INSERT INTO sessions(id, project_id, goal, status, started_at) VALUES (?, ?, ?, 'open', ?)",
            (session_id, project_id, goal, now_iso()),
        )
        return session_id

    def end_session(self, session_id: str, summary: str | None = None) -> None:
        self.db.execute(
            "UPDATE sessions SET status = 'closed', ended_at = ?, summary = COALESCE(?, summary) WHERE id = ?",
            (now_iso(), summary, session_id),
        )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
        return dict(row) if row else None

    def recent_session(self, project_id: str) -> dict[str, Any] | None:
        row = self.db.query_one(
            "SELECT * FROM sessions WHERE project_id = ? ORDER BY started_at DESC LIMIT 1",
            (project_id,),
        )
        return dict(row) if row else None

    def sessions_for(self, project_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            "SELECT * FROM sessions WHERE project_id = ? ORDER BY started_at DESC LIMIT ?",
            (project_id, limit),
        )]

    # ── working memory ───────────────────────────────────────────────────────
    def set_working(
        self,
        session_id: str,
        key: str,
        content: str,
        *,
        project_id: str | None = None,
        goal_relevance: float = 0.0,
        salience: float = 0.0,
        ttl_hours: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        ttl = self.config.decay.working_ttl_hours if ttl_hours is None else ttl_hours
        expires = iso_in_days(ttl / 24.0) if ttl else None
        existing = self.db.query_one(
            "SELECT id FROM working_memory WHERE session_id = ? AND key = ?", (session_id, key)
        )
        if existing is not None:
            self.db.execute(
                "UPDATE working_memory SET content = ?, goal_relevance = ?, salience = ?, "
                "expires_at = ?, metadata_json = ? WHERE id = ?",
                (content, goal_relevance, salience, expires, dumps(metadata or {}), existing["id"]),
            )
            return existing["id"]
        working_id = new_id("wm")
        self.db.execute(
            """
            INSERT INTO working_memory
                (id, session_id, project_id, key, content, goal_relevance, salience,
                 created_at, expires_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (working_id, session_id, project_id, key, content, goal_relevance, salience,
             now_iso(), expires, dumps(metadata or {})),
        )
        return working_id

    def get_working(self, session_id: str, include_expired: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM working_memory WHERE session_id = ?"
        params: list[Any] = [session_id]
        if not include_expired:
            sql += " AND (expires_at IS NULL OR expires_at > ?)"
            params.append(now_iso())
        sql += " ORDER BY salience DESC, created_at DESC"
        return [dict(r) | {"metadata_json": loads(r["metadata_json"], {})}
                for r in self.db.query(sql, params)]

    def delete_working(self, session_id: str, key: str) -> None:
        self.db.execute("DELETE FROM working_memory WHERE session_id = ? AND key = ?", (session_id, key))

    def clear_working(self, session_id: str) -> None:
        self.db.execute("DELETE FROM working_memory WHERE session_id = ?", (session_id,))

    def expire_working(self) -> int:
        cursor = self.db.execute(
            "DELETE FROM working_memory WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now_iso(),),
        )
        return int(cursor.rowcount or 0)
