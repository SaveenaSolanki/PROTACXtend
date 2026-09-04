"""
Persistent LangGraph checkpointer (production wiring).
=====================================================

Backend resolution order (env-driven):
  1. PROTACPILOT_CHECKPOINT_URL (postgres) → PostgresSaver  [production]
  2. PROTACPILOT_CHECKPOINT_DB (sqlite)    → SqliteSaver   [if langgraph version supports it]
  3. MemorySaver                                          [tests/CI/dev fallback]

Production requires a durable backend so interrupted runs (human gates) can
RESUME across processes/restarts. Verified: PostgresSaver round-trip works
with langgraph 1.2.10 (sqlite backend 3.1.1 is incompatible with the
checkpoint 4.x serialization — use postgres).

Usage:
    graph = build_agentic_graph(legacy_nodes=..., checkpointer=get_checkpointer())
    graph.invoke(state, config={"configurable": {"thread_id": run_id_thread(run_id)}})
    # after interrupt:
    graph.invoke(Command(resume=decision), config={"configurable": {"thread_id": run_id_thread(run_id)}})
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("protacpilot.checkpointer")

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_DB = ROOT / "data" / "checkpoints" / "protacpilot.sqlite"

_checkpoint_cache: Dict[str, Any] = {}


def get_checkpointer(db_url: Optional[str] = None, force_persistent: bool = False):
    """Persistent checkpointer (postgres → sqlite → memory), cached."""
    url = db_url or os.environ.get("PROTACPILOT_CHECKPOINT_URL", "")
    key = f"pg:{url}" if url else f"sqlite:{os.environ.get('PROTACPILOT_CHECKPOINT_DB', str(DEFAULT_SQLITE_DB))}"
    if key in _checkpoint_cache:
        return _checkpoint_cache[key]

    # 1. Postgres (production, checkpoint-4.x-native)
    if url:
        try:
            # Create the connection directly (from_conn_string's generator is
            # GC'd → closes the connection). The saver keeps this connection
            # alive for the process lifetime.
            from psycopg import Connection
            from psycopg.rows import dict_row
            conn = Connection.connect(
                url, autocommit=True, prepare_threshold=0, row_factory=dict_row,
            )
            from langgraph.checkpoint.postgres import PostgresSaver
            cp = PostgresSaver(conn)
            cp.setup()
            _checkpoint_cache[key] = cp
            logger.info("Postgres checkpointer ready: %s", url.split("@")[-1])
            return cp
        except Exception as exc:
            if force_persistent:
                raise RuntimeError(f"Postgres checkpointer unavailable: {exc}")
            logger.warning("Postgres checkpointer unavailable (%s) — falling back", exc)

    # 2. Sqlite (only works with langgraph checkpoint 3.x-era serialization)
    try:
        import sqlite3
        path = os.environ.get("PROTACPILOT_CHECKPOINT_DB", str(DEFAULT_SQLITE_DB))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver
        cp = SqliteSaver(conn)
        _checkpoint_cache[key] = cp
        logger.info("Sqlite checkpointer ready: %s", path)
        return cp
    except Exception as exc:
        logger.warning("Sqlite checkpointer unavailable (%s) — using MemorySaver", exc)

    # 3. Memory (dev/CI)
    from langgraph.checkpoint.memory import MemorySaver
    cp = MemorySaver()
    _checkpoint_cache["memory"] = cp
    logger.warning("Using in-memory checkpointer (non-persistent)")
    return cp


def run_id_thread(run_id: str) -> str:
    """Map a run_id to a LangGraph thread_id (namespaced)."""
    return f"protacpilot:{run_id}"


def compile_with_persistence(builder, checkpointer=None, **kwargs):
    """Compile a StateGraph with the persistent checkpointer wired in."""
    cp = checkpointer or get_checkpointer()
    return builder.compile(checkpointer=cp, **kwargs)


def resume_command(resume_value: Any):
    """Build the Command(resume=...) payload for interrupt/resume."""
    from langgraph.types import Command
    return Command(resume=resume_value)
