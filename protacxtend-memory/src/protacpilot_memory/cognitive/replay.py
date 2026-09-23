"""Prioritized memory replay (Master Prompt §19, §43).

Replay is not "ask the LLM to reread random memories". It selects memories by a
deterministic priority, retrieves neighbours, compares evidence, detects
recurring structure and conflicts, and writes an auditable replay event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import MemoryConfig, ReplayConfig
from ..store.store import MemoryStore
from ..util import clamp01, new_id, now_iso
from .decay import DecayModel


@dataclass
class ReplayCandidate:
    memory_id: str
    priority: float
    components: dict[str, float] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "priority": self.priority,
            "components": self.components,
            "memory_type": self.memory.get("memory_type"),
            "title": self.memory.get("title"),
        }


class ReplayEngine:
    def __init__(self, store: MemoryStore, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config
        self.cfg: ReplayConfig = self.config.replay
        self.decay = DecayModel(store, self.config)

    # ── priority ─────────────────────────────────────────────────────────────
    def priority(self, memory: dict[str, Any]) -> ReplayCandidate:
        mid = memory["id"]
        has_conflict = bool(self.store.contradictions_for(mid)) or self._true_conflict(mid)
        prospective = self._prospective_relevance(mid)
        forgetting_risk = clamp01(1.0 - self.decay.effective_strength(memory))
        components = {
            "prediction_error": clamp01(float(memory.get("surprise") or 0.0)),
            "uncertainty": clamp01(1.0 - float(memory.get("confidence") or 0.0)),
            "decision_importance": clamp01(
                max(float(memory.get("salience") or 0.0), float(memory.get("goal_relevance") or 0.0))
            ),
            "unresolved_conflict": 1.0 if has_conflict else 0.0,
            "forgetting_risk": forgetting_risk,
            "prospective_relevance": prospective,
        }
        score = clamp01(
            self.cfg.prediction_error * components["prediction_error"]
            + self.cfg.uncertainty * components["uncertainty"]
            + self.cfg.decision_importance * components["decision_importance"]
            + self.cfg.unresolved_conflict * components["unresolved_conflict"]
            + self.cfg.forgetting_risk * components["forgetting_risk"]
            + self.cfg.prospective_relevance * components["prospective_relevance"]
        )
        return ReplayCandidate(memory_id=mid, priority=score, components=components, memory=memory)

    def select(self, project_id: str | None = None, limit: int | None = None) -> list[ReplayCandidate]:
        limit = limit or self.cfg.batch_size
        memories = self.store.list(project_id=project_id, limit=5000, include_deleted=False)
        scored = [self.priority(m) for m in memories]
        scored = [c for c in scored if c.priority >= self.cfg.min_priority]
        scored.sort(key=lambda c: c.priority, reverse=True)
        return scored[:limit]

    # ── replay ───────────────────────────────────────────────────────────────
    def run(
        self,
        project_id: str | None = None,
        *,
        trigger: str = "manual",
        session_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        from .conflict import ConflictEngine
        from .consolidation import ConsolidationEngine

        candidates = self.select(project_id, limit)
        replayed: list[dict[str, Any]] = []
        conflicts_detected: list[dict[str, Any]] = []
        conflict_engine = ConflictEngine(self.store)

        for candidate in candidates:
            neighbors = self.store.neighbors(candidate.memory_id, depth=1)
            for neighbor in neighbors[:5]:
                if neighbor["via"] in {"supports", "contradicts", "related_context", "same_context"}:
                    other = neighbor["memory_id"]
                    verdict = conflict_engine.classify(candidate.memory_id, other)
                    if verdict.verdict == "true_contradiction":
                        conflicts_detected.append(verdict.as_dict())
                        if not self.store.relation_exists(candidate.memory_id, other, "contradicts"):
                            self.store.add_relation(
                                candidate.memory_id, other, "contradicts",
                                confidence=0.6, created_by="replay",
                                rationale=verdict.rationale,
                            )
            self.store.log_event(
                candidate.memory_id, "REPLAYED",
                {"trigger": trigger, "priority": candidate.priority, "components": candidate.components},
                session_id,
            )
            replayed.append(candidate.as_dict())

        consolidation = ConsolidationEngine(self.store, self.config)
        groups = consolidation.find_candidates(project_id)
        eligible_groups = [g.as_dict() for g in groups if g.eligible]
        stale = self._stale_semantics(project_id)

        event_id = new_id("REPLAY")
        findings = {
            "replayed": len(replayed),
            "conflicts_detected": conflicts_detected,
            "consolidation_candidates": eligible_groups,
            "stale_semantic_memories": stale,
        }
        import json

        self.store.db.execute(
            "INSERT INTO replay_events(id, created_at, trigger, session_id, project_id, "
            "candidate_ids_json, findings_json, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'completed')",
            (event_id, now_iso(), trigger, session_id, project_id,
             json.dumps([c.memory_id for c in candidates]), json.dumps(findings)),
        )
        return {"replay_event_id": event_id, "trigger": trigger, **findings}

    # ── helpers ──────────────────────────────────────────────────────────────
    def _true_conflict(self, memory_id: str) -> bool:
        row = self.store.db.query_one(
            "SELECT 1 FROM conflict_verdicts WHERE (memory_a = ? OR memory_b = ?) "
            "AND verdict = 'true_contradiction' LIMIT 1",
            (memory_id, memory_id),
        )
        return row is not None

    def _prospective_relevance(self, memory_id: str) -> float:
        row = self.store.db.query_one(
            "SELECT COUNT(*) AS n FROM tasks WHERE related_memory_id = ? AND status = 'open'",
            (memory_id,),
        )
        count = int(row["n"]) if row else 0
        return clamp01(count / 2.0)

    def _stale_semantics(self, project_id: str | None) -> list[dict[str, Any]]:
        out = []
        for sem in self.store.semantics(
            project_id=project_id, statuses=["active", "consolidated", "needs_review"], limit=200
        ):
            ratio = self.decay.strength_ratio(sem)
            if sem.get("status") == "needs_review" or ratio < self.decay.cfg.review_fraction:
                out.append({
                    "memory_id": sem["id"],
                    "title": sem.get("title"),
                    "strength_ratio": ratio,
                    "status": sem.get("status"),
                })
        return out
