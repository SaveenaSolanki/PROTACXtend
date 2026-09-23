"""Bounded candidate generation before reranking (brief §4–§5).

The reranker only ever sees the candidate set this module produces. Two failure
modes motivated extracting it:

1. **Pollution** — unbounded entity-overlap expansion floods the reranker with
   weakly-relevant memories that can displace the gold memory at scale.
2. **Entity dominance** — simple entity overlap is a weak signal; it must not
   decide the candidate set on its own.

The strategy is deliberately conservative and transparent:

* lexical candidates (already bounded by BM25) are always retained;
* entity-expanded candidates are **project-scoped**, then ranked by PROTAC
  context compatibility (``ProtacContext.match_score``) and truncated to
  ``max_entity_candidates``;
* when ``context_gate`` is on, an entity-only candidate (i.e. one with no
  lexical support) whose fingerprint shares **no** known coordinate with the
  query context is dropped — it can still enter through lexical retrieval.

Nothing here is learned or probabilistic; every decision is deterministic and
recorded so the effect is auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import CandidateConfig, MemoryConfig
from ..domain.protac.context import ProtacContext, context_from_any
from ..util import loads

# Coordinates that confer *positive* compatibility. ``source_type`` is excluded
# because it describes provenance, not scientific identity.
_MATCH_COORDINATES = (
    "project", "target", "target_domain", "e3", "warhead", "linker", "compound",
    "cell", "organism", "assay", "experiment_type", "endpoint", "construct",
    "structural_context", "time",
)


@dataclass
class CandidateSet:
    """The bounded candidate material handed to the reranker."""

    lexical: dict[str, float] = field(default_factory=dict)
    entity: dict[str, float] = field(default_factory=dict)
    graph: dict[str, float] = field(default_factory=dict)
    #: entity-expanded candidates observed *before* bounding
    entity_total: int = 0
    #: entity-expanded candidates kept after bounding
    entity_kept: int = 0
    #: entity-only candidates dropped for sharing no known coordinate
    entity_gated: int = 0

    def ids(self) -> set[str]:
        return set(self.lexical) | set(self.entity) | set(self.graph)

    def counts(self) -> dict[str, int]:
        return {
            "lexical": len(self.lexical),
            "entity": len(self.entity),
            "entity_total": self.entity_total,
            "entity_kept": len(self.entity),
            "entity_gated": self.entity_gated,
            "graph": len(self.graph),
        }


#: SQLite builds cap host parameters (commonly 999, sometimes 32766). Chunking
#: every ``IN (...)`` query keeps large candidate sets safe at any N.
_PARAM_CHUNK = 900


def _chunks(values: list[str], size: int = _PARAM_CHUNK):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def contexts_for_memories(store: Any, memory_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Bulk-load the PROTAC context for episodic and semantic memories.

    Episodic context lives in the ``episodic_memories`` satellite; semantic
    claims carry a machine-readable ``scope_json``. Both are normalised to a
    context dict so ``ProtacContext`` can consume them.
    """
    if not memory_ids:
        return {}
    out: dict[str, dict[str, Any]] = {}

    for chunk in _chunks(list(memory_ids)):
        placeholders = ", ".join("?" for _ in chunk)
        rows = store.db.query(
            f"SELECT trace_id, context_json FROM episodic_memories "
            f"WHERE trace_id IN ({placeholders}) AND context_json IS NOT NULL",
            chunk,
        )
        for row in rows:
            parsed = loads(row["context_json"], {})
            if parsed:
                out[row["trace_id"]] = parsed

        rows = store.db.query(
            f"SELECT trace_id, scope_json FROM semantic_memories "
            f"WHERE trace_id IN ({placeholders}) AND scope_json IS NOT NULL",
            chunk,
        )
        for row in rows:
            if row["trace_id"] in out:
                continue
            parsed = loads(row["scope_json"], {})
            if parsed:
                out[row["trace_id"]] = parsed

        rows = store.db.query(
            f"SELECT id AS trace_id, metadata_json FROM memory_traces "
            f"WHERE id IN ({placeholders}) AND metadata_json IS NOT NULL",
            chunk,
        )
        for row in rows:
            if row["trace_id"] in out:
                continue
            parsed = loads(row["metadata_json"], {})
            ctx = parsed.get("context") if isinstance(parsed, dict) else None
            if ctx:
                out[row["trace_id"]] = ctx
    return out


def _known_match_coordinates(qctx: ProtacContext) -> int:
    coords = qctx.fingerprint_coordinates()
    return sum(1 for name in _MATCH_COORDINATES if coords.get(name))


class CandidateGenerator:
    """Produce a bounded, project-scoped, context-compatible candidate set."""

    def __init__(self, store: Any, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config
        self.settings: CandidateConfig = self.config.candidates

    # ── public API ───────────────────────────────────────────────────────────
    def build(
        self,
        *,
        lexical: dict[str, float],
        entity_names: set[str] | list[str],
        query_context: ProtacContext | dict[str, Any] | None,
        project_id: str | None,
        limit: int,
    ) -> CandidateSet:
        entity_names = sorted(set(entity_names or []))
        result = CandidateSet(lexical=dict(lexical))
        if not entity_names:
            return result

        names = entity_names
        entity_ids = self.store.memories_for_entity_names(names)
        result.entity_total = len(entity_ids)
        if not entity_ids:
            return result

        # project scoping — memories belong to a project, not the model
        if project_id:
            allowed = set(self.store.project_memory_ids(project_id))
            entity_ids = [mid for mid in entity_ids if mid in allowed]
        # never duplicate work already covered by lexical candidates
        entity_only = [mid for mid in entity_ids if mid not in result.lexical]
        if not entity_only:
            return result

        qctx = context_from_any(query_context)
        known = _known_match_coordinates(qctx)

        # Bound the *compatibility scan* itself: parse contexts for at most a
        # recency-ordered working pool, not for every entity match. Without this
        # the fix would shrink the reranker input but keep the scan O(entity
        # matches) in JSON parsing.
        pool_size = max(
            self.settings.max_entity_candidates * max(1, self.settings.entity_pool_factor),
            self.settings.max_entity_candidates,
        )
        if len(entity_only) > pool_size:
            entity_only = self._order_by_recency(entity_only)[:pool_size]

        contexts = contexts_for_memories(self.store, entity_only)

        scored: list[tuple[float, str]] = []
        gated = 0
        for mid in entity_only:
            ctx = ProtacContext.from_dict(contexts.get(mid, {})) if contexts.get(mid) else ProtacContext()
            compatibility = qctx.match_score(ctx) if known else 0.0
            if self.settings.context_gate and known and compatibility <= 0.0:
                # no shared known coordinate and no lexical support → weak overlap
                gated += 1
                continue
            scored.append((compatibility, mid))

        scored.sort(key=lambda item: (-item[0], item[1]))
        kept = scored[: max(0, self.settings.max_entity_candidates)]
        result.entity = {mid: compat for compat, mid in kept}
        result.entity_gated = gated
        return result

    def _order_by_recency(self, memory_ids: list[str]) -> list[str]:
        if not memory_ids:
            return []
        pairs: list[tuple[str, str]] = []
        for chunk in _chunks(list(memory_ids)):
            placeholders = ", ".join("?" for _ in chunk)
            rows = self.store.db.query(
                f"SELECT id, created_at FROM memory_traces WHERE id IN ({placeholders})",
                chunk,
            )
            pairs.extend((str(r["created_at"] or ""), r["id"]) for r in rows)
        pairs.sort(key=lambda item: (item[0], item[1]), reverse=True)
        ordered = [mid for _, mid in pairs]
        # Defensive: preserve any ids not returned (e.g. soft-deleted rows).
        seen = set(ordered)
        ordered.extend(mid for mid in memory_ids if mid not in seen)
        return ordered

    # ── "before" behaviour, for before/after benchmarking only ───────────────
    def build_unbounded(
        self,
        *,
        lexical: dict[str, float],
        entity_names: set[str] | list[str],
        project_id: str | None,
    ) -> CandidateSet:
        """Legacy pre-fix behaviour: entity overlap only, no project scope,
        no context compatibility, no truncation. Retained solely so the fix can
        be measured honestly; never used by production retrieval."""
        entity_names = sorted(set(entity_names or []))
        result = CandidateSet(lexical=dict(lexical))
        if not entity_names:
            return result
        entity_ids = self.store.memories_for_entity_names(entity_names)
        result.entity_total = len(entity_ids)
        result.entity = {mid: 0.0 for mid in entity_ids}
        return result
