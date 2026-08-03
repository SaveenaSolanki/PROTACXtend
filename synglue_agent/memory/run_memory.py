"""Run memory storage and retrieval for prior SynGlue executions."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from synglue_agent.backend.config import MEMORY_DIR
from synglue_agent.memory.vector_store import bm25_search, detect_vector_backend


RUN_MEMORY_DIR = MEMORY_DIR / "run_store"
RUN_JSONL_PATH = RUN_MEMORY_DIR / "runs.jsonl"
RUN_SQLITE_PATH = RUN_MEMORY_DIR / "runs.sqlite3"


def _ensure_store() -> None:
    RUN_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(RUN_SQLITE_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                query TEXT,
                target TEXT,
                e3 TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        con.commit()


def _target_from_payload(query: str, candidates: list[dict[str, Any]]) -> str | None:
    if candidates:
        target = candidates[0].get("target")
        if target:
            return str(target)
    upper = (query or "").upper()
    for token in upper.split():
        if token.isalnum() and len(token) >= 3 and token not in {"PROTAC", "CRBN", "VHL"}:
            return token
    return None


def _e3_from_payload(candidates: list[dict[str, Any]]) -> str | None:
    if not candidates:
        return None
    value = candidates[0].get("e3_ligase")
    return str(value) if value else None


def store_run_result(run_id: str, query: str, candidates: list[dict[str, Any]], report: str) -> dict[str, Any]:
    _ensure_store()
    payload = {
        "run_id": run_id,
        "query": query,
        "candidates": candidates or [],
        "report": report or "",
    }
    target = _target_from_payload(query, payload["candidates"])
    e3 = _e3_from_payload(payload["candidates"])

    with RUN_JSONL_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")

    with sqlite3.connect(RUN_SQLITE_PATH) as con:
        con.execute(
            "INSERT OR REPLACE INTO runs (run_id, query, target, e3, payload_json) VALUES (?, ?, ?, ?, ?)",
            (run_id, query, target, e3, json.dumps(payload, ensure_ascii=True)),
        )
        con.commit()

    backend = detect_vector_backend()
    return {
        "success": True,
        "error": None,
        "backend": backend["label"],
        "stored": {"run_id": run_id, "target": target, "e3": e3},
        "source": str(RUN_JSONL_PATH),
    }


def _load_all_runs() -> list[dict[str, Any]]:
    _ensure_store()
    if not RUN_JSONL_PATH.exists():
        return []
    rows = []
    with RUN_JSONL_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def retrieve_target_memory(target: str) -> dict[str, Any]:
    runs = _load_all_runs()
    if not runs:
        return {"success": True, "empty": True, "error": None, "results": [], "backend": "jsonl_sqlite"}
    needle = (target or "").strip().lower()
    hits = []
    for run in runs:
        candidates = run.get("candidates", [])
        target_names = {str(item.get("target", "")).lower() for item in candidates}
        if needle and needle not in target_names and needle not in (run.get("query", "").lower()):
            continue
        hits.append(
            {
                "source": "run_memory",
                "run_id": run.get("run_id"),
                "query": run.get("query"),
                "candidate_count": len(candidates),
                "report_snippet": (run.get("report", "") or "")[:280],
            }
        )
    return {"success": True, "empty": not bool(hits), "error": None, "results": hits, "backend": "jsonl_sqlite"}


def retrieve_failed_linker_memory(target: str | None = None, e3: str | None = None) -> dict[str, Any]:
    runs = _load_all_runs()
    if not runs:
        return {"success": True, "empty": True, "error": None, "results": [], "backend": "jsonl_sqlite"}
    target_q = (target or "").strip().lower()
    e3_q = (e3 or "").strip().lower()
    hits = []
    for run in runs:
        for candidate in run.get("candidates", []):
            warnings = candidate.get("warning_flags", []) or []
            if not any("linker" in str(flag).lower() or "assembly" in str(flag).lower() for flag in warnings):
                continue
            if target_q and target_q != str(candidate.get("target", "")).lower():
                continue
            if e3_q and e3_q != str(candidate.get("e3_ligase", "")).lower():
                continue
            hits.append(
                {
                    "source": "run_memory",
                    "run_id": run.get("run_id"),
                    "candidate_id": candidate.get("candidate_id"),
                    "target": candidate.get("target"),
                    "e3": candidate.get("e3_ligase"),
                    "linker_name": candidate.get("linker_name"),
                    "warnings": warnings,
                }
            )
    return {"success": True, "empty": not bool(hits), "error": None, "results": hits, "backend": "jsonl_sqlite"}


def retrieve_successful_patterns(target: str | None = None, e3: str | None = None) -> dict[str, Any]:
    runs = _load_all_runs()
    if not runs:
        return {"success": True, "empty": True, "error": None, "results": [], "backend": "jsonl_sqlite"}
    target_q = (target or "").strip().lower()
    e3_q = (e3 or "").strip().lower()
    rows = []
    for run in runs:
        for candidate in run.get("candidates", []):
            if target_q and target_q != str(candidate.get("target", "")).lower():
                continue
            if e3_q and e3_q != str(candidate.get("e3_ligase", "")).lower():
                continue
            score = candidate.get("synthetic_feasibility_score")
            if score is None:
                continue
            try:
                if float(score) < 0.6:
                    continue
            except Exception:
                continue
            rows.append(
                {
                    "source": "run_memory",
                    "run_id": run.get("run_id"),
                    "candidate_id": candidate.get("candidate_id"),
                    "target": candidate.get("target"),
                    "e3": candidate.get("e3_ligase"),
                    "linker_class": candidate.get("linker_class"),
                    "synthetic_feasibility_score": score,
                }
            )
    return {"success": True, "empty": not bool(rows), "error": None, "results": rows, "backend": "jsonl_sqlite"}


def run_text_search(query: str, top_k: int = 5) -> dict[str, Any]:
    runs = _load_all_runs()
    if not runs:
        return {"success": True, "empty": True, "error": None, "results": [], "backend": "bm25_text_fallback"}
    docs = [{"run_id": row.get("run_id"), "text": f"{row.get('query', '')}\n{row.get('report', '')}", "source": "run_memory"} for row in runs]
    hits = bm25_search(query, docs, text_key="text", top_k=top_k)
    return {"success": True, "empty": not bool(hits), "error": None, "results": hits, "backend": detect_vector_backend()["label"]}

