"""Vector/index backend selection and lightweight retrieval helpers."""

from __future__ import annotations

import importlib.util
import math
import re
from collections import Counter
from typing import Any, Iterable


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z0-9_]+", (text or "").lower()) if token]


def detect_vector_backend() -> dict[str, Any]:
    faiss_available = importlib.util.find_spec("faiss") is not None
    qdrant_available = importlib.util.find_spec("qdrant_client") is not None
    if faiss_available:
        return {"backend": "faiss", "available": True, "label": "faiss_vector"}
    if qdrant_available:
        return {"backend": "qdrant", "available": True, "label": "qdrant_vector"}
    return {"backend": "bm25_text_fallback", "available": True, "label": "bm25_text_fallback"}


def bm25_search(
    query: str,
    documents: Iterable[dict[str, Any]],
    text_key: str = "text",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    docs = list(documents)
    if not docs:
        return []
    tokens_query = _tokenize(query)
    if not tokens_query:
        return []
    doc_tokens = [_tokenize(str(item.get(text_key, ""))) for item in docs]
    avg_len = sum(len(tokens) for tokens in doc_tokens) / max(len(doc_tokens), 1)
    idf: dict[str, float] = {}
    for token in set(tokens_query):
        contains = sum(1 for tokens in doc_tokens if token in tokens)
        idf[token] = math.log((len(doc_tokens) - contains + 0.5) / (contains + 0.5) + 1.0)

    k1 = 1.5
    b = 0.75
    scored = []
    for idx, item in enumerate(docs):
        tokens = doc_tokens[idx]
        counts = Counter(tokens)
        score = 0.0
        for token in tokens_query:
            freq = counts.get(token, 0)
            if freq == 0:
                continue
            denom = freq + k1 * (1.0 - b + b * (len(tokens) / max(avg_len, 1e-9)))
            score += idf.get(token, 0.0) * ((freq * (k1 + 1.0)) / max(denom, 1e-9))
        if score > 0:
            row = dict(item)
            row["score"] = round(float(score), 6)
            scored.append(row)
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(int(top_k), 1)]

