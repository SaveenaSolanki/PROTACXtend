"""snapshot.py — versioned, source-attributed local evidence snapshots.

When a live service is unavailable (offline mode, HTTP error, timeout) the
retrieval tracer serves a local snapshot instead of fabricating results.
Every snapshot record carries: schema version, fetched_at, the live source
(kind + URL), the query that produced it, and the raw records. Trace rows
served from a snapshot are labelled ``snapshot=True`` with the snapshot
version, so downstream consumers (and reviewers) can distinguish live from
snapshot evidence at a glance.

Layout:
    data/evidence_snapshots/<schema_version>/<tool>/<sha1(query)>.json
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "evidence-snapshot-v1"
ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_ROOT = ROOT / "data" / "evidence_snapshots" / SCHEMA_VERSION


def _slug(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]


def snapshot_path(tool: str, query: str) -> Path:
    return SNAPSHOT_ROOT / tool / f"{_slug(query)}.json"


def save_snapshot(tool: str, query: str, records: list[dict[str, Any]],
                  source_meta: dict[str, Any], *, fetched_at: Optional[str] = None) -> Path:
    """Persist raw records + attribution for a live retrieval call."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "tool": tool,
        "query": query,
        "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(),
        "source": source_meta,
        "n_records": len(records),
        "records": records,
    }
    path = snapshot_path(tool, query)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)
    return path


def load_snapshot(tool: str, query: str) -> Optional[dict[str, Any]]:
    """Return the snapshot payload (or None) without raising."""
    path = snapshot_path(tool, query)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - corrupt snapshot must not crash
        return None


def snapshot_status(snap: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Attribution block attached to every snapshot-served trace row."""
    if snap is None:
        return {}
    src = snap.get("source") or {}
    return {
        "snapshot": True,
        "snapshot_schema_version": snap.get("schema_version"),
        "snapshot_tool": snap.get("tool"),
        "snapshot_fetched_at": snap.get("fetched_at"),
        "snapshot_live_source": src.get("kind", ""),
        "snapshot_live_url": src.get("url", ""),
        "snapshot_query": snap.get("query", ""),
    }