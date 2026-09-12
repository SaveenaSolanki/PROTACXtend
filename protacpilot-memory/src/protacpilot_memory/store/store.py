"""MemoryStore: the single authoritative local cognitive store.

Composes the typed stores behind one façade. All higher-level cognitive engines
depend only on this class plus ``Database``/``MemoryConfig``.
"""

from __future__ import annotations

from typing import Any

from ..config import MemoryConfig
from ..db import Database
from ..util import fts_query, loads
from .base import BaseStore, row_to_trace
from .entities import EntityStore
from .episodes import EpisodeStore
from .evidence import EvidenceStore
from .predictions import PredictionStore
from .procedures import ProcedureStore
from .prospective import ProspectiveStore
from .relations import RelationStore
from .semantics import SemanticStore
from .sessions import SessionStore
from .traces import TraceStore


class MemoryStore(
    SessionStore,
    TraceStore,
    EpisodeStore,
    SemanticStore,
    PredictionStore,
    ProcedureStore,
    ProspectiveStore,
    EntityStore,
    EvidenceStore,
    RelationStore,
):
    def __init__(self, db: Database, config: MemoryConfig | None = None) -> None:
        super().__init__(db, config or MemoryConfig())

    # ── low-level lexical search (BM25 with bounded column boosts) ───────────
    def search_fts(
        self,
        query: str,
        *,
        project_id: str | None = None,
        memory_types: list[str] | None = None,
        statuses: list[str] | None = None,
        exclude_types: list[str] | None = None,
        exclude_statuses: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        match = fts_query(query)
        if not match:
            return []
        sql = (
            "SELECT t.*, bm25(memory_fts, 5.0, 1.0, 2.0, 1.5, 2.5) AS bm25_rank "
            "FROM memory_fts JOIN memory_traces t ON t.rowid = memory_fts.rowid "
            "WHERE memory_fts MATCH ? AND t.deleted_at IS NULL"
        )
        params: list[Any] = [match]
        if project_id:
            sql += " AND t.project_id = ?"
            params.append(project_id)
        if memory_types:
            placeholders = ", ".join("?" for _ in memory_types)
            sql += f" AND t.memory_type IN ({placeholders})"
            params.extend(memory_types)
        if exclude_types:
            placeholders = ", ".join("?" for _ in exclude_types)
            sql += f" AND t.memory_type NOT IN ({placeholders})"
            params.extend(exclude_types)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            sql += f" AND t.status IN ({placeholders})"
            params.extend(statuses)
        if exclude_statuses:
            placeholders = ", ".join("?" for _ in exclude_statuses)
            sql += f" AND t.status NOT IN ({placeholders})"
            params.extend(exclude_statuses)
        sql += " ORDER BY bm25_rank ASC LIMIT ?"
        params.append(limit)
        rows = self.db.query(sql, params)
        out = []
        for row in rows:
            data = row_to_trace(row) or {}
            data["bm25_rank"] = row["bm25_rank"]
            out.append(data)
        return out

    def search_entities_text(self, query: str, limit: int = 50) -> list[str]:
        """Return memory ids whose denormalised entity text matches the query."""
        match = fts_query(query)
        if not match:
            return []
        rows = self.db.query(
            "SELECT t.id FROM memory_fts JOIN memory_traces t ON t.rowid = memory_fts.rowid "
            "WHERE memory_fts MATCH ? AND t.deleted_at IS NULL LIMIT ?",
            (match, limit),
        )
        return [r["id"] for r in rows]

    def project_memory_ids(self, project_id: str | None) -> list[str]:
        if project_id:
            rows = self.db.query(
                "SELECT id FROM memory_traces WHERE project_id = ? AND deleted_at IS NULL",
                (project_id,),
            )
        else:
            rows = self.db.query("SELECT id FROM memory_traces WHERE deleted_at IS NULL")
        return [r["id"] for r in rows]

    def stats(self) -> dict[str, Any]:
        by_type = {
            r["memory_type"]: r["n"]
            for r in self.db.query(
                "SELECT memory_type, COUNT(*) AS n FROM memory_traces "
                "WHERE deleted_at IS NULL GROUP BY memory_type"
            )
        }
        by_status = {
            r["status"]: r["n"]
            for r in self.db.query(
                "SELECT status, COUNT(*) AS n FROM memory_traces "
                "WHERE deleted_at IS NULL GROUP BY status"
            )
        }
        return {
            "total_memories": self.count("memory_traces", "deleted_at IS NULL"),
            "soft_deleted": self.count("memory_traces", "deleted_at IS NOT NULL"),
            "by_type": by_type,
            "by_status": by_status,
            "episodes": self.count("episodic_memories"),
            "negative_episodes": self.count("episodic_memories", "is_negative = 1"),
            "semantic_memories": self.count("semantic_memories"),
            "procedures": self.count("procedural_memories"),
            "prospective": self.count("prospective_memories"),
            "entities": self.count("entities"),
            "aliases": self.count("entity_aliases"),
            "relations": self.count("memory_relations"),
            "evidence_items": self.count("evidence_items"),
            "predictions": self.count("prediction_events"),
            "unresolved_predictions": self.count("prediction_events", "resolved = 0"),
            "outcomes": self.count("outcome_events"),
            "projects": self.count("projects"),
            "sessions": self.count("sessions"),
            "db_size_bytes": self.db.size_bytes(),
        }

    def doctor(self) -> dict[str, Any]:
        return {
            "db_path": self.db.path,
            "integrity": self.db.integrity_check(),
            "fts5_ok": self.db.fts_ok(),
            "migrations": [dict(r) for r in self.db.applied_migrations()],
            "stats": self.stats(),
        }


__all__ = ["MemoryStore", "BaseStore", "row_to_trace"]
