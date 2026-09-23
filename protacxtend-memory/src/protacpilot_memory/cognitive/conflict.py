"""Contradiction engine: classify apparent conflicts (Master Prompt §21).

Distinguishes a true contradiction from contextual / scope / measurement / assay
differences and model disagreement. Verdicts are persisted so resolved
pseudo-conflicts are not repeatedly reconsidered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..domain.protac.context import ProtacContext, context_from_any
from ..domain.protac.ontology import (
    CONFLICT_ASSAY_DIFFERENCE,
    CONFLICT_COMPATIBLE,
    CONFLICT_CONTEXTUAL_DIFFERENCE,
    CONFLICT_MEASUREMENT_DIFFERENCE,
    CONFLICT_MODEL_DISAGREEMENT,
    CONFLICT_SCOPE_DIFFERENCE,
    CONFLICT_TRUE_CONTRADICTION,
)
from ..store.store import MemoryStore
from ..util import new_id, now_iso

# fields whose difference implies a scope difference rather than a contradiction
_SCOPE_FIELDS = ("target", "target_domain", "e3")
_CONTEXT_FIELDS = ("cell",)
_ASSAY_FIELDS = ("assay",)
_MEASUREMENT_FIELDS = ("time",)


@dataclass
class ConflictVerdict:
    memory_a: str
    memory_b: str
    verdict: str
    rationale: str
    context_diff: dict[str, tuple[str, str]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "memory_a": self.memory_a,
            "memory_b": self.memory_b,
            "verdict": self.verdict,
            "rationale": self.rationale,
            "context_diff": {k: list(v) for k, v in self.context_diff.items()},
        }


class ConflictEngine:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    # ── classification ───────────────────────────────────────────────────────
    def classify(self, memory_a_id: str, memory_b_id: str) -> ConflictVerdict:
        cached = self._cached(memory_a_id, memory_b_id)
        if cached is not None:
            return cached

        ctx_a = self._context_of(memory_a_id)
        ctx_b = self._context_of(memory_b_id)
        diff = ctx_a.diff(ctx_b)
        metric_opposition = self._metric_opposition(memory_a_id, memory_b_id)
        evidence_mismatch = self._evidence_kind_mismatch(memory_a_id, memory_b_id)

        verdict, rationale = self._decide(diff, metric_opposition, evidence_mismatch)

        record = ConflictVerdict(
            memory_a=memory_a_id, memory_b=memory_b_id,
            verdict=verdict, rationale=rationale, context_diff=diff,
        )
        self._persist(record)
        if verdict == CONFLICT_TRUE_CONTRADICTION:
            self.store.log_event(memory_a_id, "CONFLICT_DETECTED", record.as_dict())
            self.store.log_event(memory_b_id, "CONFLICT_DETECTED", record.as_dict())
        return record

    def _decide(
        self,
        diff: dict[str, tuple[str, str]],
        metric_opposition: bool,
        evidence_mismatch: bool,
    ) -> tuple[str, str]:
        scope_changes = [f for f in _SCOPE_FIELDS if f in diff]
        if scope_changes:
            return (
                CONFLICT_SCOPE_DIFFERENCE,
                f"different scientific scope ({', '.join(scope_changes)}); not a direct contradiction",
            )
        if any(f in diff for f in _CONTEXT_FIELDS):
            return (
                CONFLICT_CONTEXTUAL_DIFFERENCE,
                "different cellular context; results may both be valid",
            )
        if any(f in diff for f in _ASSAY_FIELDS):
            return (
                CONFLICT_ASSAY_DIFFERENCE,
                "different assay context; results are not directly comparable",
            )
        if any(f in diff for f in _MEASUREMENT_FIELDS):
            return (
                CONFLICT_MEASUREMENT_DIFFERENCE,
                "different measurement time/condition",
            )
        if evidence_mismatch and not metric_opposition:
            return (
                CONFLICT_MODEL_DISAGREEMENT,
                "evidence types disagree (e.g. model vs experiment) without matched context",
            )
        if metric_opposition:
            return (
                CONFLICT_TRUE_CONTRADICTION,
                "matched context with opposed observed outcomes",
            )
        return (CONFLICT_COMPATIBLE, "no conflicting coordinate or opposed outcome detected")

    # ── helpers ──────────────────────────────────────────────────────────────
    def _context_of(self, memory_id: str) -> ProtacContext:
        episode = self.store.get_episode(memory_id)
        if episode is not None:
            return context_from_any(episode.get("context_json") or {})
        semantic = self.store.get_semantic(memory_id)
        if semantic is not None:
            return ProtacContext.from_scope(semantic.get("sem_scope_json") or semantic.get("scope_json") or {})
        trace = self.store.require_trace(memory_id)
        return context_from_any(trace.get("scope_json") or {})

    def _observations(self, memory_id: str) -> dict[str, float]:
        episode = self.store.get_episode(memory_id)
        if episode is not None:
            observed = episode.get("observed_json") or {}
            return {k: float(v) for k, v in observed.items()
                    if isinstance(v, (int, float)) and not isinstance(v, bool)}
        # semantic: mean of supporting episodes' observations
        values: dict[str, list[float]] = {}
        semantic = self.store.get_semantic(memory_id)
        if semantic is not None:
            for rel in self.store.relations_for(memory_id):
                if rel["relation_type"] not in {"generalizes", "supports", "replicates"}:
                    continue
                other = rel["source_memory_id"] if rel["target_memory_id"] == memory_id else rel["target_memory_id"]
                ep = self.store.get_episode(other)
                if ep is None:
                    continue
                for k, v in (ep.get("observed_json") or {}).items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        values.setdefault(k, []).append(float(v))
        return {k: sum(v) / len(v) for k, v in values.items() if v}

    def _metric_opposition(self, a: str, b: str) -> bool:
        obs_a = self._observations(a)
        obs_b = self._observations(b)
        for metric in set(obs_a) & set(obs_b):
            va, vb = obs_a[metric], obs_b[metric]
            if abs(va - vb) < 1e-9:
                continue
            # Normalised metrics: treat opposite sides of 0.5 as opposition.
            if 0.0 <= va <= 1.0 and 0.0 <= vb <= 1.0:
                if (va - 0.5) * (vb - 0.5) < 0:
                    return True
            else:
                mean = (va + vb) / 2
                if mean != 0 and abs(va - vb) / abs(mean) > 0.5:
                    return True
        return False

    def _evidence_kind_mismatch(self, a: str, b: str) -> bool:
        kinds_a = {r["evidence_type"] for r in self.store.links_for_memory(a)}
        kinds_b = {r["evidence_type"] for r in self.store.links_for_memory(b)}
        if not kinds_a or not kinds_b:
            return False
        experimental = {"internal_experiment", "external_experiment"}
        model = {"ml_prediction", "docking", "simulation", "md_simulation", "llm_inference"}
        return bool((kinds_a & experimental and kinds_b & model) or (kinds_b & experimental and kinds_a & model))

    def _cached(self, a: str, b: str) -> ConflictVerdict | None:
        row = self.store.db.query_one(
            "SELECT * FROM conflict_verdicts WHERE (memory_a = ? AND memory_b = ?) "
            "OR (memory_a = ? AND memory_b = ?) ORDER BY created_at DESC LIMIT 1",
            (a, b, b, a),
        )
        if row is None:
            return None
        from ..util import loads

        return ConflictVerdict(
            memory_a=row["memory_a"], memory_b=row["memory_b"], verdict=row["verdict"],
            rationale=row["rationale"], context_diff=loads(row["context_diff_json"], {}),
        )

    def _persist(self, record: ConflictVerdict) -> None:
        import json

        self.store.db.execute(
            "INSERT OR IGNORE INTO conflict_verdicts"
            "(id, memory_a, memory_b, verdict, rationale, context_diff_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id("cv"), record.memory_a, record.memory_b, record.verdict,
             record.rationale, json.dumps({k: list(v) for k, v in record.context_diff.items()}),
             now_iso()),
        )
