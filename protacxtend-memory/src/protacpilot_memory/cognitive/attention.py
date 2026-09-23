"""Attentional gate / encoding-priority score (Master Prompt §9).

E = Σ w_i · component_i, components normalised to [0,1]. Every decision records
*why* an experience was encoded. This is deterministic application logic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from ..config import EncodingThresholds, EncodingWeights, MemoryConfig
from ..domain.protac.context import ProtacContext, context_from_any
from ..domain.protac.entities import entity_search_text
from ..domain.protac.evidence import EvidenceRef
from ..domain.protac.normalization import EntityRef
from ..store.store import MemoryStore
from ..util import clamp01, content_hash, jaccard, tokenize
from .prediction_error import surprise_from_error

# Deterministic decision-impact priors by event type (engineering priors).
_EVENT_IMPACT: dict[str, float] = {
    "failure": 0.90,
    "user_correction": 0.90,
    "design_choice": 0.80,
    "degradation_assay": 0.80,
    "outcome": 0.80,
    "experiment": 0.70,
    "synthesis_decision": 0.70,
    "permeability_assay": 0.65,
    "hypothesis": 0.55,
    "docking_experiment": 0.55,
    "md_result": 0.50,
    "paper_observation": 0.40,
    "prediction": 0.40,
    "procedure_run": 0.20,
}

DECISION_IGNORE = "ignore"
DECISION_TEMPORARY = "temporary"
DECISION_ENCODE = "encode"
DECISION_PRIORITY = "priority"

# Two experiences are duplicates only when their normalised content AND their
# scientific fingerprint are identical. Similarity never collapses distinct
# experiments (pattern separation, Master Prompt §12).
_DEDUPE_SIMILARITY = 0.999
_RELATED_SIMILARITY = 0.50


@dataclass
class AttentionInput:
    title: str
    content: str
    event_type: str = "experiment"
    context: ProtacContext = field(default_factory=ProtacContext)
    entities: list[EntityRef] = field(default_factory=list)
    evidence: list[EvidenceRef] = field(default_factory=list)
    project_id: str | None = None
    session_id: str | None = None
    goal: str | None = None
    working: list[dict[str, Any]] = field(default_factory=list)
    goal_relevance: float | None = None
    decision_impact: float | None = None
    prediction_error: float | None = None
    prediction_confidence: float | None = None
    is_negative: bool = False
    source_type: str | None = None
    exclude_memory_id: str | None = None


@dataclass
class EncodingDecision:
    score: float
    components: dict[str, float]
    decision: str
    reason: str
    fingerprint: str
    related: list[dict[str, Any]] = field(default_factory=list)
    candidate_semantics: list[dict[str, Any]] = field(default_factory=list)
    duplicate_of: str | None = None
    novelty_basis: float = 1.0
    recurrence_count: int = 0

    def breakdown(self) -> dict[str, Any]:
        return {
            **self.components,
            "encoding_score": self.score,
            "decision": self.decision,
            "reason": self.reason,
        }


class AttentionGate:
    def __init__(self, store: MemoryStore, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config
        self.weights: EncodingWeights = self.config.encoding
        self.thresholds: EncodingThresholds = self.config.thresholds

    # ── public ───────────────────────────────────────────────────────────────
    def evaluate(self, inp: AttentionInput) -> EncodingDecision:
        ctx = context_from_any(inp.context)
        fingerprint = ctx.fingerprint(inp.source_type)

        candidates = self._gather_candidates(inp)
        max_sim, related, recurrence = self._similarity_profile(inp, ctx, candidates)
        novelty = clamp01(1.0 - max_sim)
        duplicate_of = self._exact_duplicate(inp, decision_fingerprint=fingerprint, candidates=candidates)

        components = {
            "goal_relevance": clamp01(self._goal_relevance(inp)),
            "novelty": novelty,
            "surprise": clamp01(self._surprise(inp)),
            "evidence_strength": clamp01(self._evidence_strength(inp)),
            "recurrence": recurrence,
            "decision_impact": clamp01(self._decision_impact(inp)),
        }
        score = clamp01(
            self.weights.goal_relevance * components["goal_relevance"]
            + self.weights.novelty * components["novelty"]
            + self.weights.surprise * components["surprise"]
            + self.weights.evidence_strength * components["evidence_strength"]
            + self.weights.recurrence * components["recurrence"]
            + self.weights.decision_impact * components["decision_impact"]
        )
        decision = self._decide(score, duplicate_of)
        reason = self._reason(inp, components, score, decision, duplicate_of)

        return EncodingDecision(
            score=score,
            components=components,
            decision=decision,
            reason=reason,
            fingerprint=fingerprint,
            related=related[:5],
            candidate_semantics=self._candidate_semantics(inp, ctx),
            duplicate_of=duplicate_of,
            novelty_basis=max_sim,
            recurrence_count=recurrence,
        )

    # ── components ───────────────────────────────────────────────────────────
    def _goal_relevance(self, inp: AttentionInput) -> float:
        if inp.goal_relevance is not None:
            return clamp01(inp.goal_relevance)
        goal_text = inp.goal or ""
        for item in inp.working or []:
            if item.get("key") in {"objective", "goal", "current_hypothesis"}:
                goal_text += " " + str(item.get("content", ""))
        if not goal_text.strip():
            return 0.0
        event_tokens = set(tokenize(f"{inp.title} {inp.content}"))
        event_tokens |= {e.name for e in inp.entities}
        goal_tokens = set(tokenize(goal_text))
        overlap = jaccard(event_tokens, goal_tokens)
        # Working-memory context match provides a modest floor.
        context_bonus = 0.0
        for item in inp.working or []:
            content = str(item.get("content", ""))
            if content and content.lower() in f"{inp.title} {inp.content}".lower():
                context_bonus = max(context_bonus, 0.3)
        return clamp01(max(overlap, context_bonus))

    def _surprise(self, inp: AttentionInput) -> float:
        if inp.prediction_error is None:
            return 0.0
        return surprise_from_error(inp.prediction_error, inp.prediction_confidence or 0.5)

    def _evidence_strength(self, inp: AttentionInput) -> float:
        if not inp.evidence:
            return 0.0
        return max(e.effective_quality for e in inp.evidence)

    def _decision_impact(self, inp: AttentionInput) -> float:
        if inp.decision_impact is not None:
            return clamp01(inp.decision_impact)
        base = _EVENT_IMPACT.get(inp.event_type, 0.4)
        if inp.is_negative:
            base = max(base, 0.85)
        return base

    # ── candidate profiling ──────────────────────────────────────────────────
    def _gather_candidates(self, inp: AttentionInput) -> list[dict[str, Any]]:
        episodes = self.store.episodes(
            project_id=inp.project_id, include_negative=True, limit=300
        )
        return [e for e in episodes if e["id"] != inp.exclude_memory_id]

    def _exact_duplicate(
        self, inp: AttentionInput, *, decision_fingerprint: str, candidates: list[dict[str, Any]]
    ) -> str | None:
        incoming = content_hash(f"{inp.title}\n{inp.content}")
        for cand in candidates:
            if cand.get("normalized_hash") != incoming:
                continue
            if cand.get("context_fingerprint") and cand["context_fingerprint"] != decision_fingerprint:
                continue
            return cand["id"]
        return None

    def _similarity_profile(
        self, inp: AttentionInput, ctx: ProtacContext, candidates: list[dict[str, Any]]
    ) -> tuple[float, list[dict[str, Any]], float]:
        if not candidates:
            return 0.0, [], 0.0
        query_tokens = set(tokenize(f"{inp.title} {inp.content}"))
        query_entities = {e.name for e in inp.entities}
        entity_map = self._entity_map([c["id"] for c in candidates])

        scored: list[dict[str, Any]] = []
        for cand in candidates:
            cand_ctx = context_from_any(cand.get("context_json") or {})
            ctx_match = ctx.match_score(cand_ctx)
            cand_entities = entity_map.get(cand["id"], set())
            ent_match = jaccard(query_entities, cand_entities)
            cand_tokens = set(tokenize(f"{cand.get('title','')} {cand.get('content','')}"))
            tok_match = jaccard(query_tokens, cand_tokens)
            sim = 0.45 * ent_match + 0.35 * ctx_match + 0.20 * tok_match
            if cand.get("context_fingerprint") and cand["context_fingerprint"] == ctx.fingerprint(inp.source_type):
                # Same scientific coordinates → related, but never "identical":
                # distinct runs of the same experiment remain distinct episodes
                # (true duplicates are caught by the content-hash check instead).
                sim = min(sim, 0.75)
            scored.append({
                "memory_id": cand["id"],
                "similarity": clamp01(sim),
                "context_match": ctx_match,
                "entity_match": ent_match,
                "token_match": tok_match,
                "title": cand.get("title"),
            })
        scored.sort(key=lambda s: s["similarity"], reverse=True)
        max_sim = scored[0]["similarity"] if scored else 0.0
        related = [s for s in scored if s["similarity"] >= _RELATED_SIMILARITY]
        recurrence = 0.0
        if len(related) > 0:
            recurrence = min(1.0, math.log1p(len(related)) / math.log1p(5.0))
        return max_sim, related, recurrence

    def _entity_map(self, memory_ids: list[str]) -> dict[str, set[str]]:
        if not memory_ids:
            return {}
        out: dict[str, set[str]] = {}
        placeholders = ", ".join("?" for _ in memory_ids)
        rows = self.store.db.query(
            f"""
            SELECT me.memory_id, e.canonical_name
            FROM memory_entities me JOIN entities e ON e.id = me.entity_id
            WHERE me.memory_id IN ({placeholders})
            """,
            memory_ids,
        )
        for row in rows:
            out.setdefault(row["memory_id"], set()).add(row["canonical_name"])
        return out

    def _candidate_semantics(self, inp: AttentionInput, ctx: ProtacContext) -> list[dict[str, Any]]:
        semantics = self.store.active_semantics(inp.project_id, limit=50)
        if not semantics:
            return []
        names = {e.name for e in inp.entities} | {e.canonical_id for e in inp.entities if e.canonical_id}
        out = []
        for sem in semantics:
            scope = sem.get("sem_scope_json") or sem.get("scope_json") or {}
            scope_values = {str(v) for v in scope.values() if v}
            overlap = len(names & scope_values)
            if overlap or self._text_mentions(sem, inp):
                out.append({
                    "memory_id": sem["id"],
                    "title": sem.get("title"),
                    "claim": sem.get("claim"),
                    "confidence": sem.get("sem_confidence"),
                    "overlap": overlap,
                })
        return out[:5]

    @staticmethod
    def _text_mentions(sem: dict[str, Any], inp: AttentionInput) -> bool:
        haystack = f"{sem.get('title','')} {sem.get('claim','')}".lower()
        needles = tokenize(inp.title) + tokenize(inp.content)
        return sum(1 for n in set(needles) if n in haystack) >= 3

    # ── decision policy ──────────────────────────────────────────────────────
    def _decide(self, score: float, duplicate_of: str | None) -> str:
        if duplicate_of is not None:
            return DECISION_TEMPORARY
        t = self.thresholds
        if score < t.t_ignore:
            return DECISION_IGNORE
        if score < t.t_episode:
            return DECISION_TEMPORARY
        if score < t.t_priority:
            return DECISION_ENCODE
        return DECISION_PRIORITY

    def _reason(
        self,
        inp: AttentionInput,
        components: dict[str, float],
        score: float,
        decision: str,
        duplicate_of: str | None,
    ) -> str:
        if duplicate_of:
            return f"duplicate of {duplicate_of}; not re-encoded"
        top = sorted(components.items(), key=lambda kv: kv[1], reverse=True)[:2]
        parts = [f"{name}={value:.2f}" for name, value in top]
        extra = ""
        if inp.prediction_error is not None and inp.prediction_error >= 0.5:
            extra = "experiment strongly contradicted model prediction; "
        elif inp.is_negative:
            extra = "recorded as a negative/failure memory; "
        return f"{extra}{decision} (E={score:.2f}; " + ", ".join(parts) + ")"
