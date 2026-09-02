"""Literature indexing/search with honest backend fallback behavior."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from protacxtend.backend.config import MEMORY_DIR
from protacxtend.memory.vector_store import bm25_search, detect_vector_backend


LIT_DIR = MEMORY_DIR / "literature_store"
LIT_JSONL_PATH = LIT_DIR / "literature_chunks.jsonl"
LIT_SQLITE_PATH = LIT_DIR / "literature.sqlite3"


def _ensure_store() -> None:
    LIT_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(LIT_SQLITE_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS literature (
                document_id TEXT PRIMARY KEY,
                source TEXT,
                title TEXT,
                chunk_count INTEGER,
                payload_json TEXT NOT NULL
            )
            """
        )
        con.commit()


def _split_chunks(text: str, chunk_words: int = 180) -> list[str]:
    words = re.findall(r"\S+", text or "")
    if not words:
        return []
    chunks = []
    for i in range(0, len(words), chunk_words):
        chunks.append(" ".join(words[i : i + chunk_words]))
    return chunks


def index_literature_document(path_or_text: str) -> dict[str, Any]:
    _ensure_store()
    source = path_or_text
    path = Path(path_or_text)
    if path.exists() and path.is_file():
        text = path.read_text(encoding="utf-8", errors="ignore")
        source = str(path.resolve())
    else:
        text = path_or_text
    chunks = _split_chunks(text)
    if not chunks:
        return {
            "success": False,
            "error": "Document text is empty.",
            "document_id": None,
            "backend": detect_vector_backend()["label"],
        }
    document_id = hashlib.sha1((source + str(len(text))).encode("utf-8")).hexdigest()[:16]
    payload = {"document_id": document_id, "source": source, "chunks": chunks}
    with LIT_JSONL_PATH.open("a", encoding="utf-8") as handle:
        for idx, chunk in enumerate(chunks):
            handle.write(
                json.dumps(
                    {
                        "document_id": document_id,
                        "chunk_id": f"{document_id}:{idx}",
                        "source": source,
                        "text": chunk,
                    },
                    ensure_ascii=True,
                )
                + "\n"
            )
    with sqlite3.connect(LIT_SQLITE_PATH) as con:
        con.execute(
            "INSERT OR REPLACE INTO literature (document_id, source, title, chunk_count, payload_json) VALUES (?, ?, ?, ?, ?)",
            (document_id, source, source.split("/")[-1], len(chunks), json.dumps(payload, ensure_ascii=True)),
        )
        con.commit()
    return {"success": True, "error": None, "document_id": document_id, "chunk_count": len(chunks), "backend": detect_vector_backend()["label"]}


def _load_chunks() -> list[dict[str, Any]]:
    _ensure_store()
    if not LIT_JSONL_PATH.exists():
        return []
    rows = []
    with LIT_JSONL_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def search_literature(query: str, top_k: int = 5) -> dict[str, Any]:
    rows = _load_chunks()
    if not rows:
        return {"success": True, "empty": True, "error": None, "results": [], "backend": detect_vector_backend()["label"]}
    hits = bm25_search(query, rows, text_key="text", top_k=top_k)
    results = []
    for hit in hits:
        results.append(
            {
                "document_id": hit.get("document_id"),
                "chunk_id": hit.get("chunk_id"),
                "source": hit.get("source"),
                "text": hit.get("text"),
                "score": hit.get("score"),
            }
        )
    return {"success": True, "empty": not bool(results), "error": None, "results": results, "backend": detect_vector_backend()["label"]}


def summarize_retrieved_context(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"success": True, "empty": True, "summary": "No context retrieved from memory.", "citations": []}
    top = results[: min(len(results), 5)]
    snippets = []
    citations = []
    for item in top:
        text = (item.get("text") or "").strip().replace("\n", " ")
        snippets.append(text[:200])
        citations.append(
            {
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "source": item.get("source"),
            }
        )
    summary = " ".join(snippets)
    return {"success": True, "empty": False, "summary": summary, "citations": citations}

