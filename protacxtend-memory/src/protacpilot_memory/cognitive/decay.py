"""Memory strength, controlled forgetting, and use-dependent strengthening.

    M(t) = M0 · exp(−λ·Δt)          λ = ln2 / half_life(class)
    M_new = M_old + η·(1 − M_old)   only when retrieval was *useful*

Decay only lowers retrieval priority / marks review. It never deletes
scientific provenance (Master Prompt §25, §26).
"""

from __future__ import annotations

import math
from typing import Any

from ..config import DecayConfig, MemoryConfig
from ..store.store import MemoryStore
from ..util import days_between, now_iso


class DecayModel:
    def __init__(self, store: MemoryStore, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config
        self.cfg: DecayConfig = self.config.decay

    # ── class selection ──────────────────────────────────────────────────────
    @staticmethod
    def decay_key(trace: dict[str, Any]) -> str:
        memory_type = trace.get("memory_type")
        if memory_type == "semantic":
            provisional = trace.get("provisional", 1)
            confidence = trace.get("confidence") or trace.get("sem_confidence") or 0.0
            independent = trace.get("n_independent_sources") or 0
            if not provisional and confidence >= 0.6 and independent >= 2:
                return "semantic_validated"
            return "semantic_provisional" if provisional else "semantic"
        if memory_type == "negative":
            return "negative"
        if memory_type == "procedural":
            return "procedural"
        if memory_type == "prospective":
            return "prospective"
        if memory_type == "episodic":
            event_type = trace.get("event_type") or ""
            if event_type == "hypothesis":
                return "hypothesis"
            if event_type == "paper_observation":
                return "observation"
            return "episodic"
        return "episodic"

    def half_life_days(self, key: str) -> float:
        return float(self.cfg.half_life_days.get(key, 365.0))

    def decay_rate(self, key: str) -> float:
        half_life = self.half_life_days(key)
        if half_life <= 0:
            return 0.0
        return math.log(2.0) / half_life

    # ── strength ─────────────────────────────────────────────────────────────
    def effective_strength(self, trace: dict[str, Any], now_iso_str: str | None = None) -> float:
        m0 = float(trace.get("memory_strength") or 0.0)
        anchor = trace.get("last_seen_at") or trace.get("updated_at") or trace.get("created_at")
        from ..util import parse_iso

        end = parse_iso(now_iso_str) if now_iso_str else None
        elapsed = days_between(anchor, end)
        key = self.decay_key(trace)
        return max(0.0, m0 * math.exp(-self.decay_rate(key) * elapsed))

    def strength_ratio(self, trace: dict[str, Any], now_iso_str: str | None = None) -> float:
        m0 = float(trace.get("memory_strength") or 0.0)
        if m0 <= 0:
            return 0.0
        return min(1.0, self.effective_strength(trace, now_iso_str) / m0)

    # ── operations ───────────────────────────────────────────────────────────
    def strengthen(self, trace_id: str, *, useful: bool = True, eta: float | None = None) -> float:
        trace = self.store.require_trace(trace_id)
        current = self.effective_strength(trace)
        if not useful:
            return current
        rate = self.cfg.strengthen_eta if eta is None else eta
        strengthened = current + rate * (1.0 - current)
        strengthened = max(0.0, min(1.0, strengthened))
        self.store.update_trace(
            trace_id,
            memory_strength=strengthened,
            last_seen_at=now_iso(),
            successful_retrieval_count=int(trace.get("successful_retrieval_count") or 0) + 1,
        )
        self.store.log_event(trace_id, "STRENGTHENED", {"from": current, "to": strengthened, "eta": rate})
        return strengthened

    def weaken(self, trace_id: str, *, factor: float = 0.7, reason: str | None = None) -> float:
        trace = self.store.require_trace(trace_id)
        current = self.effective_strength(trace)
        weakened = max(0.0, min(1.0, current * factor))
        self.store.update_trace(trace_id, memory_strength=weakened, last_seen_at=now_iso())
        self.store.log_event(trace_id, "WEAKENED", {"from": current, "to": weakened, "reason": reason})
        return weakened

    def mark_review_candidates(self, project_id: str | None = None) -> list[str]:
        """Flag memories whose effective strength fell below the review fraction."""
        threshold = self.cfg.review_fraction
        flagged: list[str] = []
        for trace in self.store.list(project_id=project_id, limit=100000, include_deleted=False):
            if trace.get("status") in {"archived", "superseded", "retracted", "needs_review"}:
                continue
            if self.strength_ratio(trace) < threshold:
                self.store.mark_review(trace["id"], reason=f"strength ratio below {threshold}")
                self.store.log_event(trace["id"], "DECAYED", {"ratio": self.strength_ratio(trace)})
                flagged.append(trace["id"])
        return flagged

    def apply_decay_sweep(self, project_id: str | None = None) -> dict[str, Any]:
        """Compute decay for reporting and mark review candidates (no deletion)."""
        traces = self.store.list(project_id=project_id, limit=100000, include_deleted=False)
        flagged = self.mark_review_candidates(project_id)
        return {
            "checked": len(traces),
            "flagged_for_review": flagged,
            "checked_at": now_iso(),
        }
