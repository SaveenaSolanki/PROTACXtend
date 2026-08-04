"""
Production job queue (item 2) — Redis-backed with SQLite fallback.
==================================================================

For long-running jobs (P4ward 2-4h, retrosynthesis, benchmarks) that must
not block the API/UI. A worker process consumes jobs; results land in the
queue for retrieval by run_id.

Backends:
  - redis:  durable, multi-worker (requires redis server; PROTACPILOT_REDIS_URL)
  - sqlite: embedded fallback (single worker; works everywhere)

Job lifecycle: queued → running → done | failed | needs_human
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger("protacpilot.queue")

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE = ROOT / "data" / "queue" / "jobs.sqlite"
REDIS_URL = os.environ.get("PROTACPILOT_REDIS_URL", "")

JobStatus = Literal["queued", "running", "done", "failed", "needs_human"]


def _redis_available() -> bool:
    if not REDIS_URL:
        return False
    try:
        import redis
        r = redis.Redis.from_url(REDIS_URL, socket_timeout=3)
        return bool(r.ping())
    except Exception:
        return False


class JobQueue:
    """Unified job queue (redis if available, sqlite otherwise)."""

    def __init__(self, backend: str = "auto", db_path: Optional[str] = None):
        self.backend = backend
        if backend == "auto":
            self.backend = "redis" if _redis_available() else "sqlite"
        self._redis = None
        self._db_path = db_path or str(DEFAULT_SQLITE)
        if self.backend == "redis":
            import redis
            self._redis = redis.Redis.from_url(REDIS_URL, socket_timeout=5)
        else:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT, status TEXT, payload TEXT, result TEXT,
                    created REAL, updated REAL, error TEXT)"""
            )
            self._conn.commit()

    # ── submit ────────────────────────────────────────────────────────
    def submit(self, job_type: str, payload: Dict[str, Any],
               job_id: Optional[str] = None) -> str:
        job_id = job_id or f"job_{uuid.uuid4().hex[:10]}"
        now = time.time()
        if self.backend == "redis":
            self._redis.hset(
                f"protacpilot:job:{job_id}",
                mapping={"job_type": job_type, "status": "queued",
                         "payload": json.dumps(payload),
                         "created": str(now), "updated": str(now), "result": "", "error": ""},
            )
            self._redis.rpush("protacpilot:queue", job_id)
        else:
            self._conn.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)",
                (job_id, job_type, "queued", json.dumps(payload), "", now, now, ""),
            )
            self._conn.commit()
        logger.info("job queued: %s (%s)", job_id, job_type)
        return job_id

    # ── claim (worker) ────────────────────────────────────────────────
    def claim(self) -> Optional[Dict[str, Any]]:
        """Pop the oldest queued job and mark running (worker-side)."""
        if self.backend == "redis":
            job_id = self._redis.lpop("protacpilot:queue")
            if not job_id:
                return None
            job_id = job_id.decode() if isinstance(job_id, bytes) else job_id
            self._redis.hset(f"protacpilot:job:{job_id}", "status", "running")
            return self.get(job_id)
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1"
        ).fetchall()
        if not rows:
            return None
        job = self._row_to_job(rows[0])
        self._conn.execute("UPDATE jobs SET status='running', updated=? WHERE job_id=?",
                           (time.time(), job["job_id"]))
        self._conn.commit()
        return job

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        if self.backend == "redis":
            d = self._redis.hgetall(f"protacpilot:job:{job_id}")
            if not d:
                return None
            return {
                "job_id": job_id,
                "job_type": d[b"job_type"].decode(),
                "status": d[b"status"].decode(),
                "payload": json.loads(d[b"payload"]),
                "result": json.loads(d[b"result"]) if d.get(b"result") else None,
                "error": d.get(b"error", b"").decode(),
            }
        rows = self._conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchall()
        return self._row_to_job(rows[0]) if rows else None

    def complete(self, job_id: str, result: Dict[str, Any]) -> None:
        self._update(job_id, "done", result=result)

    def fail(self, job_id: str, error: str) -> None:
        self._update(job_id, "failed", error=error)

    def needs_human(self, job_id: str, payload: Dict[str, Any]) -> None:
        self._update(job_id, "needs_human", result=payload)

    def _update(self, job_id: str, status: JobStatus, result=None, error="") -> None:
        now = time.time()
        if self.backend == "redis":
            self._redis.hset(
                f"protacpilot:job:{job_id}",
                mapping={"status": status,
                         "result": json.dumps(result) if result else "",
                         "error": error, "updated": str(now)},
            )
        else:
            self._conn.execute(
                "UPDATE jobs SET status=?, result=?, error=?, updated=? WHERE job_id=?",
                (status, json.dumps(result) if result else "", error, now, job_id),
            )
            self._conn.commit()

    def list(self, status: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        if self.backend == "redis":
            keys = self._redis.keys("protacpilot:job:*")
            jobs = [self.get(k.split(":")[-1]) for k in keys]
            jobs = [j for j in jobs if j]
            if status:
                jobs = [j for j in jobs if j["status"] == status]
            return jobs[-limit:]
        rows = self._conn.execute(
            "SELECT * FROM jobs ORDER BY created DESC LIMIT ?", (limit,)
        ).fetchall()
        jobs = [self._row_to_job(r) for r in rows]
        if status:
            jobs = [j for j in jobs if j["status"] == status]
        return jobs

    def _row_to_job(self, row) -> Dict[str, Any]:
        (job_id, job_type, status, payload, result, created, updated, error) = row
        return {
            "job_id": job_id, "job_type": job_type, "status": status,
            "payload": json.loads(payload) if payload else {},
            "result": json.loads(result) if result else None,
            "error": error or "",
            "created": created, "updated": updated,
        }


# ── Worker loop ───────────────────────────────────────────────────────

def run_worker(handler, poll_interval: float = 2.0, max_jobs: Optional[int] = None):
    """Consume jobs and dispatch to handler(job) → (result | needs_human payload).

    handler returns: (job_result_dict, None) for done
                     (None, human_payload) for needs_human
                     raises → failed
    """
    q = JobQueue()
    processed = 0
    logger.info("worker started (backend=%s)", q.backend)
    while max_jobs is None or processed < max_jobs:
        job = q.claim()
        if job is None:
            time.sleep(poll_interval)
            continue
        try:
            result, human = handler(job)
            if human is not None:
                q.needs_human(job["job_id"], human)
                logger.info("job %s → needs_human", job["job_id"])
            else:
                q.complete(job["job_id"], result)
                logger.info("job %s → done", job["job_id"])
        except Exception as exc:
            q.fail(job["job_id"], str(exc))
            logger.error("job %s failed: %s", job["job_id"], exc)
        processed += 1
    logger.info("worker stopped after %d jobs", processed)
