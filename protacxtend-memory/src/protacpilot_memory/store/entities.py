"""Entity store: canonical entities, aliases, and memory↔entity links."""

from __future__ import annotations

from typing import Any

from ..domain.protac.normalization import (
    EntityRef,
    entity_key,
    make_entity_ref,
    normalize_entity_name,
)
from ..util import dumps, loads, now_iso
from .base import BaseStore


class EntityStore(BaseStore):
    # ── entities ─────────────────────────────────────────────────────────────
    def upsert_entity(
        self,
        entity_type: str,
        name: str,
        canonical_id: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> str | None:
        canonical = normalize_entity_name(entity_type, name)
        if canonical is None:
            return None
        ident = entity_key(entity_type, canonical, canonical_id)
        ts = now_iso()
        self.db.execute(
            """
            INSERT INTO entities(id, entity_type, canonical_name, canonical_id,
                                 properties_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                properties_json = excluded.properties_json,
                updated_at = excluded.updated_at
            """,
            (ident, entity_type, canonical, canonical_id, dumps(properties or {}), ts, ts),
        )
        return ident

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM entities WHERE id = ?", (entity_id,))
        if row is None:
            return None
        return dict(row) | {"properties_json": loads(row["properties_json"], {})}

    def find_entities(self, entity_type: str | None = None, name: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM entities WHERE 1=1"
        params: list[Any] = []
        if entity_type:
            sql += " AND entity_type = ?"
            params.append(entity_type)
        if name:
            canonical = normalize_entity_name(entity_type or "", name) or name
            sql += " AND (canonical_name = ? OR canonical_id = ?)"
            params.extend([canonical, name])
        return [dict(r) | {"properties_json": loads(r["properties_json"], {})}
                for r in self.db.query(sql, params)]

    def list_entities(self, entity_type: str | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        if entity_type:
            rows = self.db.query(
                "SELECT * FROM entities WHERE entity_type = ? ORDER BY canonical_name LIMIT ?",
                (entity_type, limit),
            )
        else:
            rows = self.db.query(
                "SELECT * FROM entities ORDER BY entity_type, canonical_name LIMIT ?", (limit,)
            )
        return [dict(r) for r in rows]

    def resolve(self, entity_type: str, name: str) -> EntityRef | None:
        """Resolve a raw string to a canonical EntityRef (alias-aware)."""
        canonical = normalize_entity_name(entity_type, name)
        if canonical is None:
            return None
        # Prefer an alias mapping to an existing entity.
        row = self.db.query_one(
            "SELECT entity_id FROM entity_aliases WHERE alias IN (?, ?) LIMIT 1",
            (name, canonical),
        )
        if row is not None:
            entity = self.get_entity(row["entity_id"])
            if entity is not None:
                return EntityRef(
                    entity_type=entity["entity_type"],
                    name=entity["canonical_name"],
                    canonical_id=entity["canonical_id"],
                )
        return make_entity_ref(entity_type, canonical)

    def add_alias(self, entity_id: str, alias: str, alias_type: str = "synonym", source: str | None = None) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO entity_aliases(entity_id, alias, alias_type, source) "
            "VALUES (?, ?, ?, ?)",
            (entity_id, alias.strip(), alias_type, source),
        )

    def aliases_for(self, entity_id: str) -> list[str]:
        return [r["alias"] for r in self.db.query(
            "SELECT alias FROM entity_aliases WHERE entity_id = ? ORDER BY alias", (entity_id,)
        )]

    def duplicate_entities(self) -> list[dict[str, Any]]:
        """Entities that share a canonical_id — potential duplicates (audit)."""
        rows = self.db.query(
            """
            SELECT canonical_id, COUNT(*) AS n, GROUP_CONCAT(id) AS ids
            FROM entities
            WHERE canonical_id IS NOT NULL AND canonical_id != ''
            GROUP BY canonical_id HAVING COUNT(*) > 1
            """
        )
        return [dict(r) for r in rows]

    # ── links ────────────────────────────────────────────────────────────────
    def link_memory_entity(
        self, memory_id: str, ref: EntityRef, role: str | None = None, confidence: float | None = None
    ) -> str | None:
        entity_id = self.upsert_entity(
            ref.entity_type, ref.name, canonical_id=ref.canonical_id
        )
        if entity_id is None:
            return None
        for alias in ref.aliases:
            self.add_alias(entity_id, alias)
        self.db.execute(
            "INSERT OR REPLACE INTO memory_entities(memory_id, entity_id, role, confidence) "
            "VALUES (?, ?, ?, ?)",
            (memory_id, entity_id, role or ref.role or "mentioned",
             float(confidence if confidence is not None else ref.confidence)),
        )
        return entity_id

    def entities_for_memory(self, memory_id: str) -> list[dict[str, Any]]:
        rows = self.db.query(
            """
            SELECT e.*, me.role AS role, me.confidence AS link_confidence
            FROM memory_entities me JOIN entities e ON e.id = me.entity_id
            WHERE me.memory_id = ?
            ORDER BY me.role, e.canonical_name
            """,
            (memory_id,),
        )
        return [dict(r) for r in rows]

    def memory_ids_for_entity(self, entity_id: str) -> list[str]:
        return [r["memory_id"] for r in self.db.query(
            "SELECT memory_id FROM memory_entities WHERE entity_id = ?", (entity_id,)
        )]

    def memories_for_entity_names(self, names: list[str]) -> list[str]:
        if not names:
            return []
        placeholders = ", ".join("?" for _ in names)
        rows = self.db.query(
            f"""
            SELECT DISTINCT me.memory_id
            FROM memory_entities me JOIN entities e ON e.id = me.entity_id
            WHERE e.canonical_name IN ({placeholders}) OR e.canonical_id IN ({placeholders})
            """,
            tuple(names) + tuple(names),
        )
        return [r["memory_id"] for r in rows]
