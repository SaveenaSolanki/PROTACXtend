"""Consolidation engine: repeated episodes → scoped semantic knowledge.

Consolidation is a *gated, deterministic* process (Master Prompt §17, §43). One
episode never becomes a rule. The engine:
  1. groups episodes by shared scientific coordinates (target, E3);
  2. requires minimum episode count, independent sources, aggregate evidence;
  3. caps the contradiction ratio;
  4. only then proposes a scope-bounded provisional claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..confidence import ConfidenceFeatures, compute_confidence
from ..config import ConsolidationConfig, MemoryConfig
from ..domain.protac.evidence import EvidenceBundle, EvidenceRef
from ..store.store import MemoryStore
from ..util import new_id, now_iso
from .decay import DecayModel
from .generalization import (
    PatternSummary,
    build_claim,
    common_scope,
    scope_is_anchored,
    scope_text,
    summarize_pattern,
    topic_key_for,
)

_EPISODE_STATUSES = ["active", "candidate", "needs_review"]


@dataclass
class EpisodeGroup:
    key: tuple[str | None, str | None]
    episodes: list[dict[str, Any]]
    scope: dict[str, Any] = field(default_factory=dict)
    summary: PatternSummary = field(default_factory=PatternSummary)
    evidence: EvidenceBundle = field(default_factory=EvidenceBundle)
    contradiction_ratio: float = 0.0
    independent_sources: int = 0
    eligible: bool = False
    gate_reasons: list[str] = field(default_factory=list)
    topic_key: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "n_episodes": len(self.episodes),
            "episode_ids": [e["id"] for e in self.episodes],
            "scope": self.scope,
            "eligible": self.eligible,
            "gate_reasons": self.gate_reasons,
            "contradiction_ratio": self.contradiction_ratio,
            "independent_sources": self.independent_sources,
            "descriptors": self.summary.descriptors,
            "metrics": self.summary.metrics,
        }


class ConsolidationEngine:
    def __init__(self, store: MemoryStore, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config
        self.cfg: ConsolidationConfig = self.config.consolidation
        self.decay = DecayModel(store, self.config)

    # ── discovery ────────────────────────────────────────────────────────────
    def find_candidates(self, project_id: str | None = None) -> list[EpisodeGroup]:
        episodes = self.store.episodes(
            project_id=project_id, include_negative=self.cfg.include_negative,
            statuses=_EPISODE_STATUSES, limit=5000
        )
        groups: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
        for ep in episodes:
            ctx = ep.get("context_json") or {}
            target = (ctx.get("target_gene") or ctx.get("target_uniprot")) if isinstance(ctx, dict) else None
            e3 = ctx.get("e3_ligase") if isinstance(ctx, dict) else None
            if not target and not e3:
                continue
            groups.setdefault((target, e3), []).append(ep)

        candidates: list[EpisodeGroup] = []
        for key, members in groups.items():
            if len(members) < self.cfg.min_episodes:
                continue
            candidates.append(self.build_group(key, members))
        candidates.sort(key=lambda g: (g.eligible, len(g.episodes)), reverse=True)
        return candidates

    def build_group(self, key: tuple[str | None, str | None], episodes: list[dict[str, Any]]) -> EpisodeGroup:
        scope = common_scope(episodes)
        summary = summarize_pattern(episodes)
        bundle = self._aggregate_evidence(episodes)
        contradiction = self._contradiction_ratio(episodes, summary)
        independent = self._independent_sources(episodes, bundle)
        group = EpisodeGroup(
            key=key,
            episodes=episodes,
            scope=scope,
            summary=summary,
            evidence=bundle,
            contradiction_ratio=contradiction,
            independent_sources=independent,
            topic_key=topic_key_for(scope, summary),
        )
        group.eligible, group.gate_reasons = self._gate(group)
        return group

    # ── gates ────────────────────────────────────────────────────────────────
    def _gate(self, group: EpisodeGroup) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if len(group.episodes) < self.cfg.min_episodes:
            reasons.append(f"needs ≥{self.cfg.min_episodes} episodes")
        if group.independent_sources < self.cfg.min_independent_sources:
            reasons.append(f"needs ≥{self.cfg.min_independent_sources} independent sources")
        if group.evidence.aggregate_weight < self.cfg.min_aggregate_evidence:
            reasons.append("aggregate evidence below threshold")
        if group.contradiction_ratio > self.cfg.max_contradiction_ratio:
            reasons.append(
                f"contradiction ratio {group.contradiction_ratio:.2f} exceeds "
                f"{self.cfg.max_contradiction_ratio:.2f}"
            )
        if not scope_is_anchored(group.scope):
            reasons.append("scope is not anchored to a target or E3")
        if self.cfg.require_experimental_or_literature and not group.evidence.has_experimental_or_literature:
            reasons.append("no experimental or literature-level evidence")
        confidence = compute_confidence(self._confidence_features(group), self.config.confidence).confidence
        if confidence < self.cfg.min_confidence:
            reasons.append(f"confidence {confidence:.2f} below {self.cfg.min_confidence:.2f}")
        return (not reasons), reasons

    def _confidence_features(self, group: EpisodeGroup) -> ConfidenceFeatures:
        return ConfidenceFeatures(
            n_supporting=group.evidence.n_supporting,
            n_contradicting=group.evidence.n_contradicting,
            n_independent_sources=group.independent_sources,
            replication_count=max(0, group.evidence.n_supporting - 1),
            mean_quality=group.evidence.mean_quality,
            context_consistency=1.0 - group.contradiction_ratio,
            prediction_accuracy=0.0,
            contradiction_ratio=group.contradiction_ratio,
        )

    # ── evidence aggregation ─────────────────────────────────────────────────
    def _aggregate_evidence(self, episodes: list[dict[str, Any]]) -> EvidenceBundle:
        bundle = EvidenceBundle()
        for ep in episodes:
            for link in self.store.links_for_memory(ep["id"]):
                ref = EvidenceRef(
                    evidence_type=link["evidence_type"],
                    title=link.get("title"),
                    experiment_id=link.get("experiment_id"),
                    doi=link.get("doi"),
                    pmid=link.get("pmid"),
                    accession=link.get("accession"),
                    quality=link.get("quality"),
                )
                if link.get("stance") == "contradicts":
                    bundle.contradicts.append(ref)
                elif link.get("stance") == "context":
                    bundle.context.append(ref)
                else:
                    bundle.supports.append(ref)
        return bundle

    def _independent_sources(self, episodes: list[dict[str, Any]], bundle: EvidenceBundle) -> int:
        groups: set[str] = set()
        for ep in episodes:
            for link in self.store.links_for_memory(ep["id"]):
                if link.get("stance") == "context":
                    continue
                group = link.get("independent_group") or link.get("experiment_id") or link.get("doi") \
                    or link.get("pmid") or link.get("accession")
                if group:
                    groups.add(str(group))
        if not groups:
            # fall back to distinct evidence kinds (never distinct episodes)
            groups = {ref.evidence_type for ref in bundle.supports}
        return len(groups)

    def _contradiction_ratio(self, episodes: list[dict[str, Any]], summary: PatternSummary) -> float:
        ratios: list[float] = []
        for metric, stats in summary.metrics.items():
            values = []
            for ep in episodes:
                value = (ep.get("observed_json") or {}).get(metric)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    values.append(float(value))
            if len(values) < 3:
                continue
            spread = stats["max"] - stats["min"]
            if spread <= 1e-9:
                continue
            # Split around the mean to detect bimodal (opposed) outcomes.
            mean = stats["mean"]
            low = sum(1 for v in values if v < mean)
            high = len(values) - low
            minority = min(low, high) / len(values)
            # Only treat as opposition when the two sides are meaningfully separated.
            if spread > 0.2 * max(1.0, abs(mean)):
                ratios.append(minority)
        return max(ratios) if ratios else 0.0

    # ── consolidation ────────────────────────────────────────────────────────
    def consolidate(self, group: EpisodeGroup, *, session_id: str | None = None) -> dict[str, Any]:
        if not group.eligible:
            return {"action": "skipped", "reasons": group.gate_reasons, "group": group.as_dict()}

        confidence_result = compute_confidence(self._confidence_features(group), self.config.confidence)
        existing = self.store.find_by_topic(group.topic_key or "", project_id=self._project_of(group))
        if existing is not None and existing.get("status") in {"active", "consolidated", "needs_review"}:
            return self._update_existing(existing, group, confidence_result, session_id)
        return self._create_semantic(group, confidence_result, session_id)

    def _create_semantic(self, group: EpisodeGroup, confidence_result: Any, session_id: str | None) -> dict[str, Any]:
        claim = build_claim(group.episodes, group.scope, group.summary, group.evidence)
        project_id = self._project_of(group)
        event_id = new_id("CONS")
        half_life = (self.decay.half_life_days("semantic_provisional"))
        from ..util import iso_in_days

        semantic_id = self.store.add_semantic(
            claim=claim,
            title=self._title(group),
            project_id=project_id,
            session_id=session_id,
            status="active",
            scope=scope_text(group.scope),
            scope_json=group.scope,
            topic_key=group.topic_key,
            confidence=confidence_result.confidence,
            n_supporting=group.evidence.n_supporting,
            n_contradicting=group.evidence.n_contradicting,
            n_independent_sources=group.independent_sources,
            n_experimental=group.evidence.count_kind(
                {"internal_experiment", "external_experiment"}
            ),
            n_computational=group.evidence.count_kind(
                {"md_simulation", "docking", "simulation", "ml_prediction", "structural_observation"}
            ),
            n_literature=group.evidence.count_kind(
                {"peer_reviewed_publication", "curated_database"}
            ),
            replication_count=max(0, group.evidence.n_supporting - 1),
            source_quality=group.evidence.mean_quality,
            context_consistency=1.0 - group.contradiction_ratio,
            prediction_accuracy=0.0,
            version=1,
            consolidation_event_id=event_id,
            provisional=True,
            evidence_strength=group.evidence.aggregate_weight,
            search_context=f"{claim} {scope_text(group.scope)}",
            search_entities=" ".join(
                str(v) for v in group.scope.values() if v and not str(v).startswith("_")
            ),
            metadata={"episode_ids": [e["id"] for e in group.episodes]},
        )
        self.store.update_metrics(
            semantic_id, confidence_features_json=confidence_result.breakdown
        )

        # provenance: semantic derives from the episodes; evidence supports it
        for ep in group.episodes:
            self.store.add_relation(
                semantic_id, ep["id"], "generalizes",
                confidence=0.7, created_by="consolidation",
                rationale="episode is one basis of the generalized claim",
            )
            self.store.add_relation(
                ep["id"], semantic_id, "supports",
                confidence=min(1.0, float(ep.get("confidence") or 0.5) + 0.2),
                created_by="consolidation", rationale="episode supports the semantic claim",
            )
            for link in self.store.links_for_memory(ep["id"]):
                if link.get("stance") == "contradicts":
                    stance = "contradicts"
                else:
                    stance = "supports"
                self.store.link(semantic_id, link["id"], stance=stance, weight=link.get("quality") or 1.0,
                                independent_group=link.get("independent_group"))

        self.db_record_consolidation(event_id, group, semantic_id, "created", confidence_result)
        self.store.log_event(
            semantic_id, "CONSOLIDATED",
            {
                "episode_ids": [e["id"] for e in group.episodes],
                "confidence": confidence_result.confidence,
                "scope": group.scope,
                "contradiction_ratio": group.contradiction_ratio,
            },
            session_id,
        )
        # Provisional semantic memories get a slow decay class.
        self.store.update_trace(semantic_id, review_after=iso_in_days(half_life))
        return {
            "action": "created",
            "semantic_id": semantic_id,
            "claim": claim,
            "confidence": confidence_result.confidence,
            "scope": group.scope,
            "n_supporting": group.evidence.n_supporting,
            "n_contradicting": group.evidence.n_contradicting,
            "episode_ids": [e["id"] for e in group.episodes],
        }

    def _update_existing(
        self, existing: dict[str, Any], group: EpisodeGroup, confidence_result: Any, session_id: str | None
    ) -> dict[str, Any]:
        merged_supports = (existing.get("n_supporting") or 0) + group.evidence.n_supporting
        merged_contradicts = (existing.get("n_contradicting") or 0) + group.evidence.n_contradicting
        self.store.update_metrics(
            existing["id"],
            n_supporting=merged_supports,
            n_contradicting=merged_contradicts,
            n_independent_sources=(existing.get("n_independent_sources") or 0) + group.independent_sources,
            confidence=confidence_result.confidence,
            confidence_features_json=confidence_result.breakdown,
        )
        for ep in group.episodes:
            self.store.add_relation(
                ep["id"], existing["id"], "supports",
                confidence=0.6, created_by="consolidation",
                rationale="additional episode supporting an existing semantic claim",
            )
        self.store.log_event(
            existing["id"], "CONSOLIDATED",
            {"episode_ids": [e["id"] for e in group.episodes], "updated": True,
             "n_supporting": merged_supports},
            session_id,
        )
        return {
            "action": "updated",
            "semantic_id": existing["id"],
            "claim": existing.get("claim"),
            "confidence": confidence_result.confidence,
            "n_supporting": merged_supports,
            "n_contradicting": merged_contradicts,
            "episode_ids": [e["id"] for e in group.episodes],
        }

    def run(self, project_id: str | None = None, *, session_id: str | None = None) -> dict[str, Any]:
        candidates = self.find_candidates(project_id)
        created, updated, skipped = [], [], []
        for group in candidates:
            result = self.consolidate(group, session_id=session_id)
            if result["action"] == "created":
                created.append(result)
            elif result["action"] == "updated":
                updated.append(result)
            else:
                skipped.append(result)
        return {
            "groups_examined": len(candidates),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "run_at": now_iso(),
        }

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _project_of(group: EpisodeGroup) -> str | None:
        for ep in group.episodes:
            if ep.get("project_id"):
                return ep["project_id"]
        return None

    @staticmethod
    def _title(group: EpisodeGroup) -> str:
        target = group.scope.get("target_scope") or "multi-target"
        e3 = group.scope.get("e3_scope") or "multi-E3"
        if group.summary.descriptors:
            return f"{target}/{e3} trend: {', '.join(group.summary.descriptors[:4])}"
        return f"{target}/{e3} recurring observation"

    def db_record_consolidation(
        self, event_id: str, group: EpisodeGroup, semantic_id: str | None,
        decision: str, confidence_result: Any
    ) -> None:
        import json

        self.store.db.execute(
            """
            INSERT INTO consolidation_events
                (id, created_at, project_id, session_id, episode_ids_json, topic_key,
                 semantic_memory_id, decision, rationale, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id, now_iso(), self._project_of(group), None,
                json.dumps([e["id"] for e in group.episodes]), group.topic_key,
                semantic_id, decision,
                "; ".join(group.gate_reasons) or "all gates passed",
                json.dumps(confidence_result.breakdown),
            ),
        )
