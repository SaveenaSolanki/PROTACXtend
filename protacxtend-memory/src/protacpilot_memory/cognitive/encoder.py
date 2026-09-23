"""Episodic encoder: turns a scientific experience into a structured episode.

The encoder is deterministic application logic. It decides whether to encode
(attentional gate), prevents identity collapse (context fingerprint + dedupe),
records provenance, and proposes related/contradiction candidates — but it does
not fabricate structured experimental fields (Master Prompt §11, §12, §51).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..confidence import ConfidenceFeatures, compute_confidence
from ..config import MemoryConfig
from ..domain.protac.context import ProtacContext, context_from_any
from ..domain.protac.entities import detect_entities, entity_search_text
from ..domain.protac.evidence import EvidenceRef
from ..domain.protac.normalization import EntityRef
from ..store.store import MemoryStore
from ..util import clamp01, iso_in_days, now_iso
from .attention import (
    DECISION_IGNORE,
    DECISION_PRIORITY,
    DECISION_TEMPORARY,
    AttentionGate,
    AttentionInput,
)
from .decay import DecayModel


@dataclass
class EpisodeInput:
    title: str
    content: str
    event_type: str = "experiment"
    project_id: str | None = None
    session_id: str | None = None
    context: ProtacContext | dict[str, Any] | None = None
    entities: list[EntityRef] | None = None
    evidence: list[EvidenceRef] = field(default_factory=list)
    source: dict[str, Any] = field(default_factory=dict)
    source_type: str | None = None
    prediction_id: str | None = None
    outcome_id: str | None = None
    observed: dict[str, Any] = field(default_factory=dict)
    interpretation: str | None = None
    is_negative: bool = False
    decision_impact: float | None = None
    goal_relevance: float | None = None
    prediction_error: float | None = None
    prediction_confidence: float | None = None
    goal: str | None = None
    working: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EncodeResult:
    episode_id: str | None
    decision: str
    encoding_score: float
    memory_state: str
    fingerprint: str
    duplicate_of: str | None = None
    related: list[dict[str, Any]] = field(default_factory=list)
    contradiction_candidates: list[dict[str, Any]] = field(default_factory=list)
    surprise: float = 0.0
    evidence_strength: float = 0.0
    confidence: float = 0.0
    breakdown: dict[str, Any] = field(default_factory=dict)
    entities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "decision": self.decision,
            "encoding_score": self.encoding_score,
            "memory_state": self.memory_state,
            "fingerprint": self.fingerprint,
            "duplicate_of": self.duplicate_of,
            "related": self.related,
            "contradiction_candidates": self.contradiction_candidates,
            "surprise": self.surprise,
            "evidence_strength": self.evidence_strength,
            "confidence": self.confidence,
            "breakdown": self.breakdown,
            "entities": self.entities,
        }


def build_search_context(
    title: str, content: str, context: ProtacContext, observed: dict[str, Any] | None = None
) -> str:
    coords = context.fingerprint_coordinates()
    coord_text = " ".join(v for v in coords.values() if v)
    data = context.to_dict()
    chem = " ".join(
        str(data.get(k)) for k in
        ("warhead_name", "e3_ligand_name", "linker_type", "linker_smiles",
         "canonical_smiles", "protac_smiles", "target_domain")
        if data.get(k)
    )
    obs = " ".join(f"{k} {v}" for k, v in (observed or {}).items())
    return " ".join(x for x in [title, content, coord_text, chem, obs] if x)


class EpisodeEncoder:
    def __init__(self, store: MemoryStore, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config
        self.gate = AttentionGate(store, self.config)
        self.decay = DecayModel(store, self.config)

    # ── main entry point ─────────────────────────────────────────────────────
    def encode(self, inp: EpisodeInput) -> EncodeResult:
        ctx = context_from_any(inp.context)
        entities = inp.entities if inp.entities is not None else detect_entities(ctx)
        goal = inp.goal
        working = inp.working
        if inp.session_id and (goal is None or working is None):
            session = self.store.get_session(inp.session_id)
            if session is not None:
                goal = goal or session.get("goal")
            if working is None:
                working = self.store.get_working(inp.session_id)

        attention_input = AttentionInput(
            title=inp.title,
            content=inp.content,
            event_type=inp.event_type,
            context=ctx,
            entities=entities,
            evidence=list(inp.evidence),
            project_id=inp.project_id,
            session_id=inp.session_id,
            goal=goal,
            working=working or [],
            goal_relevance=inp.goal_relevance,
            decision_impact=inp.decision_impact,
            prediction_error=inp.prediction_error,
            prediction_confidence=inp.prediction_confidence,
            is_negative=inp.is_negative,
            source_type=inp.source_type,
        )
        decision = self.gate.evaluate(attention_input)

        base = EncodeResult(
            episode_id=None,
            decision=decision.decision,
            encoding_score=decision.score,
            memory_state="discarded",
            fingerprint=decision.fingerprint,
            duplicate_of=decision.duplicate_of,
            related=decision.related,
            contradiction_candidates=decision.candidate_semantics,
            surprise=decision.components["surprise"],
            evidence_strength=decision.components["evidence_strength"],
            breakdown=decision.breakdown(),
            entities=[e.name for e in entities],
        )

        if decision.decision == DECISION_IGNORE:
            self.store.log_event(
                None, "ENCODING_REJECTED",
                {"title": inp.title, "reason": decision.reason, "score": decision.score},
                inp.session_id,
            )
            base.memory_state = "rejected"
            return base

        if decision.duplicate_of is not None:
            self._bump_duplicate(decision.duplicate_of)
            base.memory_state = "duplicate"
            base.episode_id = decision.duplicate_of
            self.store.log_event(
                decision.duplicate_of, "ENCODED",
                {"duplicate": True, "score": decision.score, "reason": decision.reason},
                inp.session_id,
            )
            return base

        if decision.decision == DECISION_TEMPORARY:
            if inp.session_id:
                self.store.set_working(
                    inp.session_id,
                    key=f"episode:{inp.title[:60]}",
                    content=inp.content,
                    project_id=inp.project_id,
                    goal_relevance=decision.components["goal_relevance"],
                    salience=decision.score,
                    metadata={"event_type": inp.event_type, "reason": decision.reason},
                )
                base.memory_state = "working_memory"
            else:
                base.memory_state = "rejected"
                self.store.log_event(
                    None, "ENCODING_REJECTED",
                    {"title": inp.title, "reason": "temporary and no session", "score": decision.score},
                )
            return base

        # ── encode as long-term episodic memory ─────────────────────────────
        evidence_bundle = self._evidence_bundle(inp.evidence)
        confidence = compute_confidence(
            ConfidenceFeatures(
                n_supporting=evidence_bundle.n_supporting,
                n_contradicting=evidence_bundle.n_contradicting,
                n_independent_sources=evidence_bundle.independent_sources(),
                replication_count=evidence_bundle.n_supporting,
                mean_quality=evidence_bundle.mean_quality,
                context_consistency=1.0,
            ),
            self.config.confidence,
        )

        search_context = build_search_context(inp.title, inp.content, ctx, inp.observed)
        search_entities = entity_search_text(entities)
        review_after = iso_in_days(self.decay.half_life_days(self._decay_key_for(inp)))

        episode_id = self.store.add_episode(
            title=inp.title,
            content=inp.content,
            event_type=inp.event_type,
            project_id=inp.project_id,
            session_id=inp.session_id,
            status="active",
            scope=self._scope_text(ctx),
            scope_json=ctx.scope(),
            topic_key=None,
            context_fingerprint=decision.fingerprint,
            observed=inp.observed,
            interpretation=inp.interpretation,
            context=ctx.to_dict(),
            source=inp.source,
            prediction_id=inp.prediction_id,
            outcome_id=inp.outcome_id,
            is_negative=inp.is_negative,
            salience=decision.score,
            novelty=decision.components["novelty"],
            goal_relevance=decision.components["goal_relevance"],
            surprise=decision.components["surprise"],
            evidence_strength=decision.components["evidence_strength"],
            confidence=confidence.confidence,
            memory_strength=1.0,
            encoding_score=decision.score,
            encoding_breakdown=decision.breakdown(),
            source_type=inp.source_type,
            source_id=inp.source.get("source_ref") if inp.source else None,
            search_context=search_context,
            search_entities=search_entities,
            review_after=review_after,
            metadata=inp.metadata,
        )

        # provenance + associative links
        for ref in entities:
            self.store.link_memory_entity(episode_id, ref)
        for ev in inp.evidence:
            evidence_id = self.store.add_evidence(ev, project_id=inp.project_id)
            self.store.link(episode_id, evidence_id, stance="supports", weight=ev.effective_quality,
                            independent_group=ev.group)

        self._link_related(episode_id, decision, ctx)
        self.store.log_event(
            episode_id, "ENCODED",
            {
                "event_type": inp.event_type,
                "encoding_score": decision.score,
                "decision": decision.decision,
                "reason": decision.reason,
                "breakdown": decision.breakdown(),
                "fingerprint": decision.fingerprint,
                "prediction_id": inp.prediction_id,
                "outcome_id": inp.outcome_id,
            },
            inp.session_id,
        )

        base.episode_id = episode_id
        base.memory_state = "episodic"
        base.confidence = confidence.confidence
        base.breakdown["confidence_breakdown"] = confidence.breakdown
        return base

    # ── outcome convenience ──────────────────────────────────────────────────
    def encode_outcome(
        self,
        outcome: dict[str, Any],
        *,
        project_id: str | None = None,
        session_id: str | None = None,
        context: ProtacContext | dict[str, Any] | None = None,
        evidence: list[EvidenceRef] | None = None,
        title: str | None = None,
        interpretation: str | None = None,
        is_negative: bool | None = None,
        goal_relevance: float | None = None,
    ) -> EncodeResult:
        prediction = self.store.get_prediction(outcome["prediction_id"]) or {}
        metric = prediction.get("metric") or "value"
        candidate = prediction.get("candidate_id") or "candidate"
        observed_value = outcome.get("observed_value")
        observed_text = (
            f"{metric}={observed_value}" if observed_value is not None else f"{metric}={outcome.get('observed_class')}"
        )
        predicted_text = (
            f"predicted {metric}={prediction.get('predicted_value')}"
            if prediction.get("predicted_value") is not None
            else f"predicted {prediction.get('predicted_class')}"
        )
        auto_title = title or f"Outcome for {candidate}: {observed_text} ({predicted_text})"
        negative = is_negative
        if negative is None:
            negative = bool(outcome.get("prediction_error", 0.0) and float(outcome["prediction_error"]) >= 0.5)
        content = (
            f"Prediction {prediction.get('id')}: {predicted_text}; "
            f"observed {observed_text}; prediction_error={outcome.get('prediction_error'):.3f} "
            f"({outcome.get('error_method')})."
        )
        ev = list(evidence or [])
        if outcome.get("evidence_id"):
            record = self.store.get_evidence(outcome["evidence_id"])
            if record is not None:
                ev.append(EvidenceRef(
                    evidence_type=record["evidence_type"],
                    title=record.get("title") or auto_title,
                    description=record.get("description"),
                    source_type=record.get("source_type"),
                    source_ref=record.get("source_ref"),
                    doi=record.get("doi"),
                    pmid=record.get("pmid"),
                    experiment_id=record.get("experiment_id"),
                    quality=record.get("quality"),
                ))
        return self.encode(EpisodeInput(
            title=auto_title,
            content=content,
            event_type="outcome",
            project_id=project_id,
            session_id=session_id,
            context=context or prediction.get("context_json") or {},
            evidence=ev,
            source={"source_ref": outcome.get("evidence_id"), "source_type": "outcome"},
            prediction_id=outcome["prediction_id"],
            outcome_id=outcome["id"],
            observed={
                "observed_value": observed_value,
                "observed_class": outcome.get("observed_class"),
                "prediction_error": outcome.get("prediction_error"),
            },
            interpretation=interpretation,
            is_negative=bool(negative),
            prediction_error=outcome.get("prediction_error"),
            prediction_confidence=prediction.get("confidence"),
            decision_impact=0.85,
            goal_relevance=goal_relevance,
            metadata={"error_method": outcome.get("error_method")},
        ))

    # ── helpers ──────────────────────────────────────────────────────────────
    def _bump_duplicate(self, memory_id: str) -> None:
        self.store.db.execute(
            "UPDATE memory_traces SET duplicate_count = duplicate_count + 1, "
            "last_seen_at = ? WHERE id = ?",
            (now_iso(), memory_id),
        )

    def _link_related(self, episode_id: str, decision: Any, ctx: ProtacContext) -> None:
        for rel in decision.related:
            relation = "same_context" if rel.get("context_match", 0.0) >= 0.8 else "related_context"
            self.store.add_relation(
                episode_id, rel["memory_id"], relation,
                confidence=rel["similarity"], created_by="encoder",
                rationale="context/entity similarity at encoding",
            )
        for sem in decision.candidate_semantics:
            if not self.store.relation_exists(episode_id, sem["memory_id"], "related_context"):
                self.store.add_relation(
                    episode_id, sem["memory_id"], "related_context",
                    confidence=0.4, created_by="encoder",
                    rationale="candidate semantic memory with overlapping scope",
                )

    @staticmethod
    def _scope_text(ctx: ProtacContext) -> str:
        parts = []
        if ctx.target_gene or ctx.target_uniprot:
            parts.append(f"target={ctx.target_gene or ctx.target_uniprot}")
        if ctx.e3_ligase:
            parts.append(f"e3={ctx.e3_ligase}")
        if ctx.cell_line:
            parts.append(f"cell={ctx.cell_line}")
        if ctx.assay_type:
            parts.append(f"assay={ctx.assay_type}")
        return "; ".join(parts)

    def _decay_key_for(self, inp: EpisodeInput) -> str:
        pseudo = {
            "memory_type": "negative" if inp.is_negative else "episodic",
            "event_type": inp.event_type,
        }
        return DecayModel.decay_key(pseudo)

    @staticmethod
    def _evidence_bundle(evidence: list[EvidenceRef]):
        from ..domain.protac.evidence import EvidenceBundle

        bundle = EvidenceBundle()
        bundle.supports = list(evidence)
        return bundle
