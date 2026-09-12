"""Optional embedding retrieval (Master Prompt §35, §36).

Embeddings are **never mandatory** and **never decide identity**. When disabled
(the default) this retriever returns no candidates. A deterministic hashing
embedder is provided so the component is exercised without a model, but it is
clearly labelled as non-semantic.

Embedding failure must not break memory: every method degrades to an empty
result rather than raising.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

from ..config import MemoryConfig
from ..util import cosine, tokenize


class HashingEmbedder:
    """Dependency-free bag-of-tokens hashing embedder (deterministic)."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        toks = tokenize(text)
        for tok in toks:
            digest = hashlib.md5(tok.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class SemanticRetriever:
    """Cosine similarity over an optional embedding backend."""

    def __init__(self, config: MemoryConfig, embedder: Any | None = None) -> None:
        self.config = config
        self.enabled = bool(config.embeddings_enabled)
        self.embedder = embedder or HashingEmbedder(config.embedding_dim)
        self._cache: dict[str, list[float]] = {}

    def _embed(self, text: str) -> list[float] | None:
        if not self.enabled:
            return None
        key = hashlib.md5(text.encode("utf-8")).hexdigest()
        if key in self._cache:
            return self._cache[key]
        try:
            vec = self.embedder.embed(text)
        except Exception:  # noqa: BLE001 - optional backend must never break memory
            return None
        self._cache[key] = vec
        return vec

    def candidates(self, query: str, documents: dict[str, str], *, limit: int = 50) -> dict[str, float]:
        if not self.enabled or not documents:
            return {}
        query_vec = self._embed(query)
        if query_vec is None:
            return {}
        scored: list[tuple[str, float]] = []
        for doc_id, text in documents.items():
            vec = self._embed(text)
            if vec is None:
                continue
            scored.append((doc_id, cosine(query_vec, vec)))
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return {doc_id: max(0.0, score) for doc_id, score in scored[:limit]}

    def label(self) -> str:
        if not self.enabled:
            return "disabled"
        if isinstance(self.embedder, HashingEmbedder):
            return "hashing-fallback (non-semantic)"
        return "embedding-backend"
