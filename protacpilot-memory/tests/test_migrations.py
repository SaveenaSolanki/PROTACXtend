"""Migration safety and database edge cases."""

from __future__ import annotations

import pytest
from protacpilot_memory.db import Database, split_sql_statements
from protacpilot_memory.errors import MigrationError


def test_fresh_init_is_idempotent(tmp_path):
    db = Database(tmp_path / "m.db")
    versions = [r["version"] for r in db.applied_migrations()]
    assert versions == [1, 2, 3, 4]
    db.close()

    reopened = Database(tmp_path / "m.db")
    assert [r["version"] for r in reopened.applied_migrations()] == [1, 2, 3, 4]
    assert reopened.integrity_check() == "ok"
    assert reopened.fts_ok() is True
    reopened.close()


def test_additive_migrations_add_columns(tmp_path):
    db = Database(tmp_path / "m.db")
    sem_cols = {r[1] for r in db.query("PRAGMA table_info(semantic_memories)")}
    assert "confidence_features_json" in sem_cols
    trace_cols = {r[1] for r in db.query("PRAGMA table_info(memory_traces)")}
    assert {"calibration_error", "normalized_hash", "duplicate_count", "last_seen_at"} <= trace_cols
    db.close()


def test_checksum_guard_rejects_changed_migration(tmp_path):
    migrations = tmp_path / "mig"
    migrations.mkdir()
    path = migrations / "0001_a.sql"
    path.write_text("CREATE TABLE t(a INTEGER);")
    db = Database(tmp_path / "x.db", auto_migrate=False)
    db.migrate(migrations)
    path.write_text("CREATE TABLE t(a INTEGER, b INTEGER);")
    with pytest.raises(MigrationError):
        db.migrate(migrations)
    db.close()


def test_split_sql_handles_triggers():
    script = (
        "CREATE TABLE a(x);\n"
        "CREATE TRIGGER tr AFTER INSERT ON a BEGIN\n"
        "  INSERT INTO a(x) VALUES (1);\n"
        "END;\n"
    )
    statements = split_sql_statements(script)
    assert len(statements) == 2
    assert statements[1].upper().startswith("CREATE TRIGGER")


def test_foreign_keys_and_soft_delete_columns_exist(tmp_path):
    db = Database(tmp_path / "m.db")
    tables = {r[0] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    for expected in {
        "memory_traces", "episodic_memories", "semantic_memories", "working_memory",
        "entities", "entity_aliases", "memory_relations", "evidence_items",
        "memory_evidence", "prediction_events", "outcome_events", "memory_access_log",
        "consolidation_events", "reconsolidation_events", "memory_versions",
        "memory_events", "tasks", "prospective_memories", "procedural_memories",
        "conflict_verdicts", "replay_events", "counterfactual_analyses",
    }:
        assert expected in tables
    db.close()
