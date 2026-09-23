"""Reconsolidation: versioned belief update (Master Prompt §20, §44).

Scientific knowledge is not append-only. When new evidence conflicts with an
active semantic memory, the engine evaluates all evidence and chooses one of
STRENGTHEN / WEAKEN / REFINE_SCOPE / BRANCH / SUPERSEDE / RETRACT / NO_CHANGE.
The previous version is always preserved in ``memory_versions``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..confidence import ConfidenceFeatures, compute_confidence
from ..config import MemoryConfig
from ..domain.protac.evidence import EvidenceBundle, EvidenceRef
from ..store.store import MemoryStore
from ..util import new_id, now_iso
from .conflict import ConflictEngine
from .decay import DecayModel
from .generalization import build_claim, common_scope, scope_text, summarize_pattern

OUTCOMES = {
    "STRENGTHEN", "WEAKEN", "REFINE_SCOPE", "BRANCH", "SUPERSEDE", "RETRACT", "NO_CHANGE",
}


@dataclass
class ReconsolidationResult:
    semantic_id: str
    outcome: str
    old_claim: str
    new_claim: str
    confidence_before: float
    confidence_after: float
    version_before: int
    version_after: int
    rationale: str
    evidence: dict[str, Any] = field(default_factory=dict)
    child_semantic_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "semantic_id": self.semantic_id,
            "outcome": self.outcome,
            "old_claim": self.old_claim,
            "new_claim": self.new_claim,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "version_before": self.version_before,
            "version_after": self.version_after,
            "rationale": self.rationale,
            "evidence": self.evidence,
            "child_semantic_id": self.child_semantic_id,
        }


class ReconsolidationEngine:
    def __init__(self, store: MemoryStore, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config
        self.decay = DecayModel(store, self.config)
        self.conflict = ConflictEngine(store)

    # ── conflict detection ───────────────────────────────────────────────────
    def detect_conflicts(self, project_id: str | None = None) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []
        for sem in self.store.active_semantics(project_id, limit=200):
            scope = sem.get("sem_scope_json") or {}
            target = scope.get("target_scope")
            e3 = scope.get("e3_scope")
            for ep in self.store.episodes(project_id=project_id, include_negative=True, limit=1000):
                if ep["id"] == sem["id"]:
                    continue
                ctx = ep.get("context_json") or {}
                if target and ctx.get("target_gene") not in (None, target):
                    continue
                if e3 and ctx.get("e3_ligase") not in (None, e3):
                    continue
                verdict = self.conflict.classify(sem["id"], ep["id"])
                if verdict.verdict == "true_contradiction":
                    if not self.store.relation_exists(ep["id"], sem["id"], "contradicts"):
                        self.store.add_relation(
                            ep["id"], sem["id"], "contradicts",
                            confidence=0.6, created_by="reconsolidation",
                            rationale=verdict.rationale,
                        )
                    conflicts.append(verdict.as_dict())
        return conflicts

    # ── evaluation ───────────────────────────────────────────────────────────
    def collect_bundle(self, semantic_id: str) -> EvidenceBundle:
        bundle = self.store.bundle_for_memory(semantic_id)
        seen_support = {self._evidence_key(r) for r in bundle.supports}
        seen_contra = {self._evidence_key(r) for r in bundle.contradicts}
        for rel in self.store.relations_for(semantic_id):
            other = rel["source_memory_id"] if rel["target_memory_id"] == semantic_id else rel["target_memory_id"]
            opposing = rel["relation_type"] in {"contradicts", "failed_to_replicate", "exception_to"}
            supporting = rel["relation_type"] in {"supports", "replicates"}
            if not (opposing or supporting):
                continue
            target_bundle = bundle.contradicts if opposing else bundle.supports
            seen = seen_contra if opposing else seen_support
            for link in self.store.links_for_memory(other):
                ref = EvidenceRef(
                    evidence_type=link["evidence_type"],
                    title=link.get("title"),
                    experiment_id=link.get("experiment_id"),
                    doi=link.get("doi"), pmid=link.get("pmid"),
                    accession=link.get("accession"),
                    quality=link.get("quality"),
                )
                key = self._evidence_key(ref)
                if key in seen:
                    continue
                seen.add(key)
                target_bundle.append(ref)
        return bundle

    @staticmethod
    def _evidence_key(ref: EvidenceRef) -> tuple:
        return (ref.evidence_type, ref.experiment_id, ref.doi, ref.pmid, ref.accession, ref.title)

    def choose_outcome(self, semantic: dict[str, Any], bundle: EvidenceBundle) -> tuple[str, str]:
        support_w = bundle.aggregate_weight
        oppose_w = bundle.aggregate_opposing_weight
        ratio = bundle.contradiction_ratio
        n_sup = bundle.n_supporting
        prev_sup = int(semantic.get("n_supporting") or 0)
        max_ratio = self.config.consolidation.max_contradiction_ratio

        if oppose_w <= 1e-9:
            if n_sup > prev_sup:
                return "STRENGTHEN", "new supporting evidence with no contradiction"
            return "NO_CHANGE", "no new evidence changes the belief"

        if oppose_w > support_w * 1.5:
            if support_w <= 1e-9:
                return "RETRACT", "contradicting evidence dominates and no support remains"
            return "SUPERSEDE", "contradicting evidence outweighs the existing support"

        if oppose_w >= support_w * 0.8 and ratio >= 0.5:
            return "BRANCH", "contradiction is strong and context-separable; branch instead of collapsing"

        if ratio > max_ratio:
            contradiction_contexts = self._contradiction_contexts(semantic["id"])
            if self._context_differs(contradiction_contexts):
                return "REFINE_SCOPE", "contradictions concentrate in a different context; narrow the scope"
            return "WEAKEN", f"contradiction ratio {ratio:.2f} exceeds threshold"

        return "NO_CHANGE", "evidence remains compatible"

    # ── reconsolidate ────────────────────────────────────────────────────────
    def reconsolidate(
        self,
        semantic_id: str,
        *,
        trigger: str = "new_evidence",
        session_id: str | None = None,
    ) -> ReconsolidationResult:
        semantic = self.store.get_semantic(semantic_id)
        if semantic is None:
            from ..errors import NotFoundError

            raise NotFoundError("semantic memory", semantic_id)
        bundle = self.collect_bundle(semantic_id)
        outcome, rationale = self.choose_outcome(semantic, bundle)

        old_claim = str(semantic.get("claim") or semantic.get("content"))
        old_confidence = float(semantic.get("confidence") or semantic.get("sem_confidence") or 0.0)
        version_before = int(semantic.get("version") or semantic.get("sem_version") or 1)
        new_claim = old_claim
        child_id: str | None = None
        confidence_after = old_confidence

        if outcome != "NO_CHANGE":
            self.store.snapshot_version(semantic_id, reason=f"reconsolidation:{outcome}")

        if outcome == "STRENGTHEN":
            confidence_after = self._apply_confidence(semantic, bundle, prev_support=int(semantic.get("n_supporting") or 0))
            self._update_metrics(semantic_id, bundle, confidence_after)
            self.store.log_event(semantic_id, "RECONSOLIDATED",
                                 {"outcome": outcome, "confidence": confidence_after}, session_id)

        elif outcome == "WEAKEN":
            confidence_after = max(0.0, old_confidence * 0.7)
            self.decay.weaken(semantic_id, factor=0.7, reason=rationale)
            self._update_metrics(semantic_id, bundle, confidence_after)
            self.store.log_event(semantic_id, "RECONSOLIDATED",
                                 {"outcome": outcome, "confidence": confidence_after}, session_id)

        elif outcome == "REFINE_SCOPE":
            refined = self._refined_scope(semantic_id, bundle)
            new_claim = self._scope_qualified_claim(old_claim, refined)
            self.store.update_claim(semantic_id, new_claim, scope_json=refined, reason="refine_scope")
            self.store.update_metrics(semantic_id, scope_json=refined, provisional=True)
            confidence_after = self._apply_confidence(semantic, bundle, prev_support=int(semantic.get("n_supporting") or 0))
            self._update_metrics(semantic_id, bundle, confidence_after)
            self.store.log_event(semantic_id, "RECONSOLIDATED",
                                 {"outcome": outcome, "scope": refined}, session_id)

        elif outcome == "BRANCH":
            child_id, new_claim = self._branch(semantic, bundle, session_id)
            confidence_after = old_confidence

        elif outcome == "SUPERSEDE":
            new_claim = self._superseding_claim(old_claim, semantic_id, bundle)
            self.store.update_claim(semantic_id, new_claim, reason="supersede")
            confidence_after = self._apply_confidence(semantic, bundle, prev_support=0)
            self._update_metrics(semantic_id, bundle, confidence_after)
            self.store.log_event(semantic_id, "SUPERSEDED",
                                 {"old_claim": old_claim, "new_claim": new_claim}, session_id)

        elif outcome == "RETRACT":
            self.store.set_status(semantic_id, "retracted", reason=rationale, session_id=session_id)
            confidence_after = 0.0
            self.store.update_metrics(semantic_id, confidence=0.0, provisional=True)
            self.store.log_event(semantic_id, "RECONSOLIDATED",
                                 {"outcome": outcome, "confidence": 0.0}, session_id)

        version_after = int(self.store.require_trace(semantic_id).get("version") or version_before)

        event = {
            "id": new_id("RECON"),
            "created_at": now_iso(),
            "semantic_memory_id": semantic_id,
            "trigger": trigger,
            "new_evidence_json": bundle.feature_dict(),
            "old_claim": old_claim,
            "new_claim": new_claim,
            "outcome": outcome,
            "confidence_before": old_confidence,
            "confidence_after": confidence_after,
            "rationale": rationale,
            "version_before": version_before,
            "version_after": version_after,
        }
        self._persist_event(event)

        return ReconsolidationResult(
            semantic_id=semantic_id,
            outcome=outcome,
            old_claim=old_claim,
            new_claim=new_claim,
            confidence_before=old_confidence,
            confidence_after=confidence_after,
            version_before=version_before,
            version_after=version_after,
            rationale=rationale,
            evidence=bundle.feature_dict(),
            child_semantic_id=child_id,
        )

    def run(self, project_id: str | None = None, *, session_id: str | None = None) -> dict[str, Any]:
        conflicts = self.detect_conflicts(project_id)
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for conflict in conflicts:
            a, b = conflict["memory_a"], conflict["memory_b"]
            semantic_id = a if self.store.get_semantic(a) else b
            if semantic_id in seen:
                continue
            seen.add(semantic_id)
            result = self.reconsolidate(semantic_id, trigger="conflict_detected", session_id=session_id)
            if result.outcome != "NO_CHANGE":
                results.append(result.as_dict())
        return {"conflicts_detected": len(conflicts), "reconsolidations": results}

    # ── outcome helpers ──────────────────────────────────────────────────────
    def _apply_confidence(self, semantic: dict[str, Any], bundle: EvidenceBundle, prev_support: int) -> float:
        features = ConfidenceFeatures(
            n_supporting=bundle.n_supporting,
            n_contradicting=bundle.n_contradicting,
            n_independent_sources=bundle.independent_sources(),
            replication_count=max(0, bundle.n_supporting - 1),
            mean_quality=bundle.mean_quality,
            context_consistency=1.0 - bundle.contradiction_ratio,
            contradiction_ratio=bundle.contradiction_ratio,
        )
        return compute_confidence(features, self.config.confidence).confidence

    def _update_metrics(self, semantic_id: str, bundle: EvidenceBundle, confidence: float) -> None:
        self.store.update_metrics(
            semantic_id,
            n_supporting=bundle.n_supporting,
            n_contradicting=bundle.n_contradicting,
            n_independent_sources=bundle.independent_sources(),
            confidence=confidence,
            source_quality=bundle.mean_quality,
            context_consistency=1.0 - bundle.contradiction_ratio,
            provisional=bundle.contradiction_ratio <= self.config.consolidation.max_contradiction_ratio,
        )

    def _refined_scope(self, semantic_id: str, bundle: EvidenceBundle) -> dict[str, Any]:
        ids = self._supporting_episode_ids(semantic_id)
        episodes = [self.store.get_episode(i) for i in ids]
        episodes = [e for e in episodes if e]
        if not episodes:
            return self.store.get_semantic(semantic_id).get("sem_scope_json") or {}
        return common_scope(episodes)

    def _scope_qualified_claim(self, claim: str, scope: dict[str, Any]) -> str:
        base = claim.split(" This claim is provisional")[0]
        return f"{base} (Scope refined to: {scope_text(scope)}.) This claim is provisional and bounded to the stated scope."

    def _superseding_claim(self, old_claim: str, semantic_id: str, bundle: EvidenceBundle) -> str:
        oppose = bundle.aggregate_opposing_weight
        support = bundle.aggregate_weight
        return (
            f"Revised claim (supersedes: \"{old_claim[:120]}\"). "
            f"Available matched evidence now weighs {support:.2f} supporting vs "
            f"{oppose:.2f} contradicting; the previous generalization is no longer "
            f"supported at its original confidence."
        )

    def _branch(self, semantic: dict[str, Any], bundle: EvidenceBundle, session_id: str | None) -> tuple[str, str]:
        contradiction_ids = self._contradiction_episode_ids(semantic["id"])
        episodes = [self.store.get_episode(i) for i in contradiction_ids]
        episodes = [e for e in episodes if e]
        scope = common_scope(episodes) if episodes else (semantic.get("sem_scope_json") or {})
        summary = summarize_pattern(episodes) if episodes else summarize_pattern([])
        if episodes:
            claim = build_claim(episodes, scope, summary, bundle)
        else:
            claim = f"Contextual exception to: {semantic.get('claim')}"
        child_id = self.store.add_semantic(
            claim=claim,
            title=f"Exception: {semantic.get('title')}",
            project_id=semantic.get("project_id"),
            status="active",
            scope=scope_text(scope),
            scope_json=scope,
            topic_key=(semantic.get("topic_key") or "") + ":exception",
            confidence=max(0.2, float(semantic.get("confidence") or 0.3) * 0.8),
            n_supporting=bundle.n_contradicting,
            n_contradicting=0,
            n_independent_sources=bundle.independent_sources("contradicts"),
            provisional=True,
            search_context=claim,
            metadata={"parent": semantic["id"]},
        )
        self.store.add_relation(child_id, semantic["id"], "exception_to",
                                confidence=0.7, created_by="reconsolidation",
                                rationale="context-separable contradictory evidence")
        for i in contradiction_ids:
            self.store.add_relation(child_id, i, "derived_from",
                                    confidence=0.7, created_by="reconsolidation")
        self.store.log_event(child_id, "CONSOLIDATED", {"branched_from": semantic["id"]}, session_id)
        return child_id, claim

    def _contradiction_contexts(self, semantic_id: str) -> list[dict[str, Any]]:
        out = []
        for i in self._contradiction_episode_ids(semantic_id):
            ep = self.store.get_episode(i)
            if ep:
                out.append(ep.get("context_json") or {})
        return out

    def _context_differs(self, contexts: list[dict[str, Any]]) -> bool:
        if not contexts:
            return False
        keys = ("cell_line", "assay_type", "assay_time")
        for key in keys:
            values = {str(c.get(key)) for c in contexts if c.get(key)}
            if len(values) > 1:
                return True
        return False

    def _supporting_episode_ids(self, semantic_id: str) -> list[str]:
        ids = []
        for rel in self.store.relations_for(semantic_id):
            if rel["relation_type"] not in {"generalizes", "supports"}:
                continue
            other = rel["source_memory_id"] if rel["target_memory_id"] == semantic_id else rel["target_memory_id"]
            if self.store.get_episode(other):
                ids.append(other)
        return sorted(set(ids))

    def _contradiction_episode_ids(self, semantic_id: str) -> list[str]:
        ids = []
        for rel in self.store.relations_for(semantic_id):
            if rel["relation_type"] not in {"contradicts", "failed_to_replicate", "exception_to"}:
                continue
            other = rel["source_memory_id"] if rel["target_memory_id"] == semantic_id else rel["target_memory_id"]
            if self.store.get_episode(other):
                ids.append(other)
        return sorted(set(ids))

    def _persist_event(self, event: dict[str, Any]) -> None:
        import json

        self.store.db.execute(
            """
            INSERT INTO reconsolidation_events
                (id, created_at, semantic_memory_id, trigger, new_evidence_json,
                 old_claim, new_claim, outcome, confidence_before, confidence_after,
                 rationale, version_before, version_after)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["id"], event["created_at"], event["semantic_memory_id"],
                event["trigger"], json.dumps(event["new_evidence_json"]),
                event["old_claim"], event["new_claim"], event["outcome"],
                event["confidence_before"], event["confidence_after"],
                event["rationale"], event["version_before"], event["version_after"],
            ),
        )
