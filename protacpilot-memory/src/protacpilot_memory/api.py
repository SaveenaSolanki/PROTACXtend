"""CognitiveMemory: the public façade for PROTACpilot Cognitive Memory.

Binds the store, cognitive engines and retrieval engines into one API that is
used by the Python host, the MCP server, the HTTP server, and the CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .audit.auditor import MemoryAuditor
from .cognitive.consolidation import ConsolidationEngine
from .cognitive.counterfactual import CounterfactualAnalyzer
from .cognitive.decay import DecayModel
from .cognitive.encoder import EpisodeEncoder, EpisodeInput
from .cognitive.pattern_completion import PatternCompleter
from .cognitive.reconsolidation import ReconsolidationEngine
from .cognitive.replay import ReplayEngine
from .cognitive.retriever import CognitiveRetriever, SearchResponse
from .config import MemoryConfig, load_config
from .db import Database
from .domain.protac.context import ProtacContext, context_from_any
from .domain.protac.evidence import EvidenceRef
from .domain.protac.normalization import make_entity_ref
from .store.store import MemoryStore
from .util import now_iso


class CognitiveMemory:
    def __init__(self, config: MemoryConfig | None = None, db: Database | None = None) -> None:
        self.config = config or load_config()
        self.db = db or Database(self.config.db_path)
        self.store = MemoryStore(self.db, self.config)
        self.encoder = EpisodeEncoder(self.store, self.config)
        self.retriever = CognitiveRetriever(self.store, self.config)
        self.decay = DecayModel(self.store, self.config)
        self.consolidation = ConsolidationEngine(self.store, self.config)
        self.replay_engine = ReplayEngine(self.store, self.config)
        self.reconsolidation = ReconsolidationEngine(self.store, self.config)
        self.pattern = PatternCompleter(self.store, self.retriever)
        self.counterfactual_analyzer = CounterfactualAnalyzer(self.store, self.config)
        self.auditor = MemoryAuditor(self.store, self.config)

    # ── construction / lifecycle ─────────────────────────────────────────────
    @classmethod
    def open(cls, path: str | Path | None = None, config: MemoryConfig | None = None) -> CognitiveMemory:
        cfg = config or load_config()
        if path is not None:
            cfg = cfg.with_overrides(db_path=Path(path))
        return cls(cfg)

    @classmethod
    def in_memory(cls, config: MemoryConfig | None = None) -> CognitiveMemory:
        cfg = (config or MemoryConfig()).with_overrides(db_path=Path(":memory:"))
        return cls(cfg, db=Database(":memory:"))

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> CognitiveMemory:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── project / session / working memory ───────────────────────────────────
    def ensure_project(self, name: str | None = None, description: str | None = None) -> str:
        return self.store.ensure_project(name or self.config.project_name, description)

    def current_project(self, name: str | None = None) -> dict[str, Any]:
        """Never errors (Master Prompt §31, upstream `mem_current_project`)."""
        resolved = name or self.config.project_name
        project = self.store.get_project(resolved)
        if project is None:
            project_id = self.ensure_project(resolved)
            project = self.store.get_project_by_id(project_id)
        return {"project": project, "detected_from": name or "config"}

    def start_session(self, project_id: str | None = None, goal: str | None = None) -> str:
        return self.store.start_session(project_id, goal)

    def remember_working(
        self, session_id: str, key: str, content: str, *, project_id: str | None = None,
        goal_relevance: float = 0.0, salience: float = 0.0, ttl_hours: float | None = None,
    ) -> str:
        return self.store.set_working(
            session_id, key, content, project_id=project_id,
            goal_relevance=goal_relevance, salience=salience, ttl_hours=ttl_hours,
        )

    def working(self, session_id: str) -> list[dict[str, Any]]:
        return self.store.get_working(session_id)

    def end_session(
        self, session_id: str, *, summary: str | None = None, next_steps: list[str] | None = None
    ) -> dict[str, Any]:
        """End-of-session cognitive process (Master Prompt §53)."""
        session = self.store.get_session(session_id) or {}
        project_id = session.get("project_id")
        session_episodes = self.store.episodes(project_id=project_id, session_id=session_id, limit=200)
        important = [
            {"id": e["id"], "title": e["title"], "salience": e["salience"], "surprise": e["surprise"]}
            for e in session_episodes
            if (e.get("salience") or 0) >= 0.6 or (e.get("surprise") or 0) >= 0.5
        ]
        failures = [
            {"id": e["id"], "title": e["title"]} for e in session_episodes if e.get("is_negative")
        ]
        awaiting = self.store.unresolved_predictions(project_id, limit=50)
        conflicts = self.store.unresolved_contradictions()
        groups = [g.as_dict() for g in self.consolidation.find_candidates(project_id) if g.eligible]

        created_prospective = []
        for step in next_steps or []:
            trace_id = self.future(title=step, project_id=project_id, session_id=session_id)
            created_prospective.append(trace_id)

        handoff_lines = [
            f"Session {session_id} ended at {now_iso()}.",
            f"Important episodes: {len(important)}; failures: {len(failures)}; "
            f"predictions awaiting outcome: {len(awaiting)}; unresolved conflicts: {len(conflicts)}; "
            f"consolidation candidates: {len(groups)}.",
        ]
        if important:
            handoff_lines.append("High-value episodes: " + "; ".join(e["title"] for e in important[:5]))
        if next_steps:
            handoff_lines.append("Next steps: " + "; ".join(next_steps))
        handoff = " ".join(handoff_lines)
        self.store.end_session(session_id, summary or handoff)
        return {
            "session_id": session_id,
            "important_episodes": important,
            "unresolved_failures": failures,
            "predictions_awaiting_outcome": awaiting,
            "unresolved_contradictions": conflicts,
            "consolidation_candidates": groups,
            "prospective_created": created_prospective,
            "handoff": handoff,
        }

    # ── encoding ─────────────────────────────────────────────────────────────
    def encode(self, **kwargs: Any) -> dict[str, Any]:
        return self.encoder.encode(EpisodeInput(**kwargs)).to_dict()

    def save_episode(
        self,
        title: str,
        content: str,
        *,
        event_type: str = "experiment",
        project_id: str | None = None,
        session_id: str | None = None,
        context: ProtacContext | dict[str, Any] | None = None,
        evidence: list[dict[str, Any]] | None = None,
        observed: dict[str, Any] | None = None,
        interpretation: str | None = None,
        is_negative: bool = False,
        decision_impact: float | None = None,
        goal_relevance: float | None = None,
        source: dict[str, Any] | None = None,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        return self.encoder.encode(EpisodeInput(
            title=title, content=content, event_type=event_type, project_id=project_id,
            session_id=session_id, context=context, evidence=_coerce_evidence(evidence),
            observed=observed or {}, interpretation=interpretation, is_negative=is_negative,
            decision_impact=decision_impact, goal_relevance=goal_relevance,
            source=source or {}, source_type=source_type,
        )).to_dict()

    # ── predictions / outcomes ───────────────────────────────────────────────
    def predict(
        self,
        *,
        prediction_type: str = "numeric",
        project_id: str | None = None,
        session_id: str | None = None,
        candidate_id: str | None = None,
        metric: str | None = None,
        predicted_value: float | None = None,
        predicted_class: str | None = None,
        predicted_probability: float | None = None,
        confidence: float = 0.5,
        scale: float | None = None,
        context: ProtacContext | dict[str, Any] | None = None,
        assumptions: list[str] | None = None,
    ) -> str:
        ctx = context_from_any(context)
        payload = ctx.to_dict()
        if assumptions:
            payload["assumptions"] = assumptions
        return self.store.create_prediction(
            prediction_type=prediction_type, project_id=project_id, session_id=session_id,
            candidate_id=candidate_id, metric=metric, predicted_value=predicted_value,
            predicted_class=predicted_class, predicted_probability=predicted_probability,
            confidence=confidence, scale=scale, context=payload,
        )

    def record_outcome(
        self,
        prediction_id: str,
        *,
        observed_value: float | None = None,
        observed_class: str | None = None,
        observed_probability: float | None = None,
        outcome_type: str | None = None,
        evidence_type: str = "internal_experiment",
        source_ref: str | None = None,
        experiment_id: str | None = None,
        notes: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        encode: bool = True,
        title: str | None = None,
        interpretation: str | None = None,
        is_negative: bool | None = None,
        goal_relevance: float | None = None,
    ) -> dict[str, Any]:
        prediction = self.store.require_prediction(prediction_id)
        evidence_id = None
        if encode or evidence_type:
            evidence_id = self.store.add_evidence(
                EvidenceRef(
                    evidence_type=evidence_type,
                    title=f"Outcome evidence for {prediction_id}",
                    source_type=outcome_type or "experiment",
                    source_ref=source_ref,
                    experiment_id=experiment_id,
                    timestamp=now_iso(),
                ),
                project_id=project_id or prediction.get("project_id"),
            )
        outcome = self.store.record_outcome(
            prediction_id, observed_value=observed_value, observed_class=observed_class,
            observed_probability=observed_probability, outcome_type=outcome_type,
            evidence_id=evidence_id, notes=notes,
        )
        if encode:
            ctx = context_from_any(prediction.get("context_json") or {})
            result = self.encoder.encode_outcome(
                outcome, project_id=project_id or prediction.get("project_id"),
                session_id=session_id or prediction.get("session_id"), context=ctx,
                title=title, interpretation=interpretation, is_negative=is_negative,
                goal_relevance=goal_relevance,
            )
            outcome["episode"] = result.to_dict()
        return outcome

    def unresolved_predictions(self, project_id: str | None = None) -> list[dict[str, Any]]:
        return self.store.unresolved_predictions(project_id)

    # ── retrieval ────────────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        *,
        project_id: str | None = None,
        context: ProtacContext | dict[str, Any] | None = None,
        memory_types: list[str] | None = None,
        limit: int | None = None,
        session_id: str | None = None,
    ) -> SearchResponse:
        return self.retriever.search(
            query, project_id=project_id, context=context, memory_types=memory_types,
            limit=limit, session_id=session_id,
        )

    def search_dict(self, query: str, **kwargs: Any) -> dict[str, Any]:
        response = self.search(query, **kwargs)
        return {
            "query": query,
            "semantic_backend": response.semantic_backend,
            "generator_counts": response.generator_counts,
            "results": [self.retriever.progressive.compact(h) for h in response.hits],
        }

    def recall(self, query: str, **kwargs: Any) -> dict[str, Any]:
        return self.retriever.recall(query, **kwargs)

    def get(self, memory_id: str, why: list[str] | None = None) -> dict[str, Any]:
        return self.retriever.get(memory_id, why)

    def packet(self, memory_id: str, why: list[str] | None = None) -> str:
        return self.retriever.progressive.render_packet(memory_id, why)

    def neighbors(self, memory_id: str, depth: int = 1) -> list[dict[str, Any]]:
        return self.retriever.neighbors(memory_id, depth)

    def timeline(self, memory_id: str, window: int = 5) -> dict[str, Any]:
        return self.retriever.timeline(memory_id, window)

    def evidence(self, memory_id: str) -> dict[str, Any]:
        return self.retriever.evidence(memory_id)

    def context(self, project_id: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        return self.retriever.context(project_id, session_id)

    # ── cognitive operations ─────────────────────────────────────────────────
    def consolidate(self, project_id: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        return self.consolidation.run(project_id, session_id=session_id)

    def replay(self, project_id: str | None = None, *, trigger: str = "manual", session_id: str | None = None) -> dict[str, Any]:
        return self.replay_engine.run(project_id, trigger=trigger, session_id=session_id)

    def reconsolidate(self, semantic_id: str, *, trigger: str = "manual", session_id: str | None = None) -> dict[str, Any]:
        return self.reconsolidation.reconsolidate(semantic_id, trigger=trigger, session_id=session_id).as_dict()

    def detect_conflicts(self, project_id: str | None = None) -> list[dict[str, Any]]:
        return self.reconsolidation.detect_conflicts(project_id)

    def judge_conflict(self, memory_a: str, memory_b: str) -> dict[str, Any]:
        return self.reconsolidation.conflict.classify(memory_a, memory_b).as_dict()

    def compare(
        self, memory_a: str, memory_b: str, relation_type: str, *,
        confidence: float = 0.5, rationale: str | None = None,
    ) -> dict[str, Any]:
        relation_id = self.store.add_relation(
            memory_a, memory_b, relation_type, confidence=confidence,
            created_by="agent", rationale=rationale,
        )
        return {"relation_id": relation_id, "source": memory_a, "target": memory_b,
                "relation_type": relation_type, "confidence": confidence}

    def strengthen(self, memory_id: str) -> dict[str, Any]:
        return {"memory_id": memory_id, "memory_strength": self.decay.strengthen(memory_id, useful=True)}

    def weaken(self, memory_id: str, factor: float = 0.7) -> dict[str, Any]:
        return {"memory_id": memory_id, "memory_strength": self.decay.weaken(memory_id, factor=factor)}

    def archive(self, memory_id: str, reason: str | None = None) -> dict[str, Any]:
        self.store.archive(memory_id, reason=reason)
        return {"memory_id": memory_id, "status": "archived"}

    def feedback(self, memory_id: str, *, useful: bool, used_for: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        return self.retriever.feedback(memory_id, useful=useful, used_for=used_for, session_id=session_id)

    def pattern_complete(self, cue: str, *, project_id: str | None = None, depth: int = 2) -> dict[str, Any]:
        return self.pattern.complete(cue, project_id=project_id, depth=depth)

    # ── procedural memory (reusable workflows, not scientific claims) ────────
    def procedure_save(
        self,
        *,
        name: str,
        steps: list[str] | list[dict[str, Any]],
        objective: str | None = None,
        prerequisites: str | None = None,
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
        tool_dependencies: list[str] | None = None,
        version: int = 1,
        evidence: list[dict[str, Any]] | None = None,
        domain: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Create or version a reusable workflow (procedural memory)."""
        if not steps:
            from .errors import ValidationError

            raise ValidationError("a procedure requires at least one step")
        ordered_steps = [
            {"order": i + 1, "step": s if isinstance(s, str) else s.get("step", str(s))}
            for i, s in enumerate(steps)
        ]
        superseded_id: str | None = None
        replace_target: dict[str, Any] | None = None
        if replace:
            replace_target = self.store.find_by_workflow(name, project_id)
            if replace_target is not None:
                previous_version = int((replace_target.get("metadata_json") or {}).get("version") or 1)
                version = max(version, previous_version + 1)
        search_context = " ".join(filter(None, [
            name, objective or "", prerequisites or "",
            " ".join(s["step"] for s in ordered_steps),
            " ".join(tool_dependencies or []),
        ]))
        metadata = {
            "objective": objective,
            "inputs": inputs or [],
            "outputs": outputs or [],
            "tool_dependencies": tool_dependencies or [],
            "version": version,
            "last_success_at": None,
            "last_run_at": None,
            "last_run_success": None,
        }
        trace_id = self.store.add_procedure(
            workflow_name=name, steps=ordered_steps, title=name,
            content=objective or name, project_id=project_id, session_id=session_id,
            domain=domain, preconditions=prerequisites, search_context=search_context,
            search_entities=" ".join(tool_dependencies or []), metadata=metadata,
        )
        self.store.update_trace(trace_id, version=version)
        if replace_target is not None:
            self.store.supersede(
                replace_target["id"], superseded_by=trace_id, reason="procedure replaced"
            )
            superseded_id = replace_target["id"]
        for ref in _coerce_evidence(evidence):
            ev_id = self.store.add_evidence(ref, project_id=project_id)
            self.store.link(trace_id, ev_id, stance="supports", weight=ref.effective_quality)
        self.store.log_event(trace_id, "ENCODED", {"memory_type": "procedural", "version": version}, session_id)
        record = self.procedure_get(trace_id)
        record["superseded_id"] = superseded_id
        return record

    def procedure_search(
        self, query: str | None = None, *, project_id: str | None = None,
        domain: str | None = None, limit: int = 5,
    ) -> dict[str, Any]:
        if not query:
            rows = self.store.procedures(project_id=project_id, domain=domain, limit=limit)
            return {"query": query, "results": [self._procedure_compact(r) for r in rows]}
        response = self.retriever.search(
            query, project_id=project_id, memory_types=["procedural"], limit=limit
        )
        results = []
        for hit in response.hits:
            record = self.store.get_procedure(hit.id)
            if record is None:
                continue
            if domain and record.get("domain") != domain:
                continue
            compact = self._procedure_compact(record)
            compact["score"] = hit.score
            compact["why_retrieved"] = hit.why_retrieved
            results.append(compact)
        return {"query": query, "results": results}

    def procedure_get(self, memory_id: str) -> dict[str, Any]:
        record = self.store.get_procedure(memory_id)
        if record is None:
            from .errors import NotFoundError

            raise NotFoundError("procedure", memory_id)
        record["trace_id"] = record.get("id", memory_id)
        record["evidence"] = self.store.links_for_memory(memory_id)
        return record

    def procedure_record_run(
        self, memory_id: str, *, success: bool, note: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        self.store.record_run(memory_id, success)
        trace = self.store.require_trace(memory_id)
        metadata = dict(trace.get("metadata_json") or {})
        metadata["last_run_at"] = now_iso()
        metadata["last_run_success"] = bool(success)
        if success:
            metadata["last_success_at"] = now_iso()
        self.store.update_trace(memory_id, metadata_json=metadata)
        self.store.log_event(
            memory_id, "RETRIEVED",
            {"procedure_run": True, "success": bool(success), "note": note}, session_id,
        )
        record = self.store.get_procedure(memory_id) or {}
        return {
            "memory_id": memory_id,
            "success": bool(success),
            "success_count": record.get("success_count", 0),
            "failure_count": record.get("failure_count", 0),
            "last_success_at": metadata.get("last_success_at"),
        }

    @staticmethod
    def _procedure_compact(record: dict[str, Any]) -> dict[str, Any]:
        from .util import loads

        metadata = record.get("metadata_json") or {}
        if isinstance(metadata, str):
            metadata = loads(metadata, {})
        return {
            "memory_id": record.get("id") or record.get("trace_id"),
            "name": record.get("workflow_name") or record.get("title"),
            "objective": metadata.get("objective"),
            "domain": record.get("domain"),
            "version": metadata.get("version"),
            "n_steps": len(record.get("steps_json") or []),
            "tool_dependencies": metadata.get("tool_dependencies", []),
            "success_count": record.get("success_count", 0),
            "failure_count": record.get("failure_count", 0),
            "last_success_at": metadata.get("last_success_at"),
            "status": record.get("status"),
        }

    def counterfactual(self, prediction_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.counterfactual_analyzer.analyze(prediction_id, **kwargs)

    # ── prospective memory ───────────────────────────────────────────────────
    def future(
        self, *, title: str, project_id: str | None = None, session_id: str | None = None,
        content: str | None = None, trigger: str | None = None, due_at: str | None = None,
        related_memory_id: str | None = None, priority: float = 0.5,
    ) -> str:
        return self.store.add_prospective(
            title=title, content=content, project_id=project_id, session_id=session_id,
            trigger=trigger, due_at=due_at, related_memory_id=related_memory_id, priority=priority,
        )

    def task_add(
        self, title: str, *, project_id: str | None = None, session_id: str | None = None,
        description: str | None = None, due_at: str | None = None,
        related_memory_id: str | None = None, priority: float = 0.5,
    ) -> str:
        return self.store.add_task(
            title=title, project_id=project_id, session_id=session_id,
            description=description, due_at=due_at, related_memory_id=related_memory_id,
            priority=priority,
        )

    def task_resolve(self, task_id: str, status: str = "done", note: str | None = None) -> dict[str, Any]:
        self.store.resolve_task(task_id, status=status, note=note)
        return {"task_id": task_id, "status": status}

    def open_tasks(self, project_id: str | None = None) -> list[dict[str, Any]]:
        return self.store.open_tasks(project_id)

    # ── diagnostics ──────────────────────────────────────────────────────────
    def audit(self, project_id: str | None = None) -> dict[str, Any]:
        return self.auditor.run(project_id)

    def stats(self) -> dict[str, Any]:
        return self.store.stats()

    def doctor(self) -> dict[str, Any]:
        return self.store.doctor()


def _coerce_evidence(evidence: list[dict[str, Any]] | None) -> list[EvidenceRef]:
    if not evidence:
        return []
    refs = []
    for item in evidence:
        if isinstance(item, EvidenceRef):
            refs.append(item)
        else:
            data = dict(item)
            data.pop("weight", None)
            refs.append(EvidenceRef(**{k: v for k, v in data.items()
                                       if k in EvidenceRef.__dataclass_fields__}))
    return refs
