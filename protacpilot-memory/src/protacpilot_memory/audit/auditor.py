"""Memory auditor: mandatory integrity & quality reporting (Master Prompt §37)."""

from __future__ import annotations

from typing import Any

from ..config import MemoryConfig
from ..store.store import MemoryStore
from ..util import now_iso


class MemoryAuditor:
    def __init__(self, store: MemoryStore, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config

    def run(self, project_id: str | None = None) -> dict[str, Any]:
        findings: dict[str, list[dict[str, Any]]] = {
            "orphan_memories": self.orphan_memories(project_id),
            "semantic_without_evidence": self.semantic_without_evidence(project_id),
            "high_confidence_weak_support": self.high_confidence_weak_support(project_id),
            "unresolved_conflicts": self.store.unresolved_contradictions(),
            "duplicate_entities": self.store.duplicate_entities(),
            "stale_knowledge": self.stale_knowledge(project_id),
            "retrieved_but_never_useful": self.retrieved_but_never_useful(project_id),
            "llm_only_claims": self.llm_only_claims(project_id),
            "scope_inconsistencies": self.scope_inconsistencies(project_id),
            "broken_provenance_links": self.broken_provenance_links(),
            "prospective_never_resolved": self.store.never_resolved(older_than_days=90.0),
            "predictions_awaiting_outcome": self.store.unresolved_predictions(project_id),
        }
        summary = {name: len(items) for name, items in findings.items()}
        severity = self._severity(summary)
        return {
            "audited_at": now_iso(),
            "project_id": project_id,
            "summary": summary,
            "severity": severity,
            "findings": findings,
        }

    # ── individual checks ────────────────────────────────────────────────────
    def orphan_memories(self, project_id: str | None = None) -> list[dict[str, Any]]:
        sql = """
            SELECT t.id, t.memory_type, t.title FROM memory_traces t
            WHERE t.deleted_at IS NULL
              AND t.memory_type NOT IN ('procedural', 'prospective')
              AND NOT EXISTS (SELECT 1 FROM memory_entities me WHERE me.memory_id = t.id)
              AND NOT EXISTS (SELECT 1 FROM memory_evidence ev WHERE ev.memory_id = t.id)
              AND NOT EXISTS (SELECT 1 FROM memory_relations r
                              WHERE r.source_memory_id = t.id OR r.target_memory_id = t.id)
        """
        params: list[Any] = []
        if project_id:
            sql += " AND t.project_id = ?"
            params.append(project_id)
        sql += " LIMIT 100"
        return [dict(r) for r in self.store.db.query(sql, params)]

    def semantic_without_evidence(self, project_id: str | None = None) -> list[dict[str, Any]]:
        sql = """
            SELECT t.id, t.title FROM memory_traces t
            WHERE t.memory_type = 'semantic' AND t.deleted_at IS NULL
              AND NOT EXISTS (SELECT 1 FROM memory_evidence ev WHERE ev.memory_id = t.id)
        """
        params: list[Any] = []
        if project_id:
            sql += " AND t.project_id = ?"
            params.append(project_id)
        return [dict(r) for r in self.store.db.query(sql, params)]

    def high_confidence_weak_support(self, project_id: str | None = None) -> list[dict[str, Any]]:
        sql = """
            SELECT t.id, t.title, t.confidence, s.n_supporting, s.n_independent_sources
            FROM memory_traces t JOIN semantic_memories s ON s.trace_id = t.id
            WHERE t.deleted_at IS NULL AND t.confidence >= 0.7
              AND (s.n_supporting < 3 OR s.n_independent_sources < 2)
        """
        params: list[Any] = []
        if project_id:
            sql += " AND t.project_id = ?"
            params.append(project_id)
        return [dict(r) for r in self.store.db.query(sql, params)]

    def stale_knowledge(self, project_id: str | None = None) -> list[dict[str, Any]]:
        from ..cognitive.decay import DecayModel

        decay = DecayModel(self.store, self.config)
        out = []
        for trace in self.store.list(project_id=project_id, limit=5000):
            if trace.get("memory_type") not in {"semantic", "procedural"}:
                continue
            if trace.get("status") in {"archived", "superseded", "retracted"}:
                continue
            ratio = decay.strength_ratio(trace)
            if ratio < decay.cfg.review_fraction or trace.get("status") == "needs_review":
                out.append({
                    "id": trace["id"], "title": trace.get("title"),
                    "strength_ratio": round(ratio, 3), "status": trace.get("status"),
                })
        return out

    def retrieved_but_never_useful(self, project_id: str | None = None) -> list[dict[str, Any]]:
        sql = """
            SELECT t.id, t.title, t.retrieval_count, t.successful_retrieval_count
            FROM memory_traces t
            WHERE t.deleted_at IS NULL AND t.retrieval_count >= 5
              AND t.successful_retrieval_count = 0
        """
        params: list[Any] = []
        if project_id:
            sql += " AND t.project_id = ?"
            params.append(project_id)
        return [dict(r) for r in self.store.db.query(sql, params)]

    def llm_only_claims(self, project_id: str | None = None) -> list[dict[str, Any]]:
        out = []
        for sem in self.store.semantics(project_id=project_id, limit=1000):
            links = self.store.links_for_memory(sem["id"])
            types = {link["evidence_type"] for link in links}
            if types and types <= {"llm_inference"}:
                out.append({"id": sem["id"], "title": sem.get("title"), "evidence_types": sorted(types)})
        return out

    def scope_inconsistencies(self, project_id: str | None = None) -> list[dict[str, Any]]:
        out = []
        for sem in self.store.semantics(project_id=project_id, limit=1000):
            scope = sem.get("sem_scope_json") or {}
            if not (scope.get("target_scope") or scope.get("e3_scope")):
                out.append({"id": sem["id"], "title": sem.get("title"), "scope": scope})
        return out

    def broken_provenance_links(self) -> list[dict[str, Any]]:
        rows = self.store.db.query(
            """
            SELECT me.memory_id, me.evidence_id FROM memory_evidence me
            LEFT JOIN evidence_items e ON e.id = me.evidence_id
            WHERE e.id IS NULL
            """
        )
        broken = [dict(r) for r in rows]
        rel_rows = self.store.db.query(
            """
            SELECT r.id, r.source_memory_id, r.target_memory_id FROM memory_relations r
            LEFT JOIN memory_traces s ON s.id = r.source_memory_id
            LEFT JOIN memory_traces t ON t.id = r.target_memory_id
            WHERE s.id IS NULL OR t.id IS NULL
            """
        )
        broken.extend(dict(r) for r in rel_rows)
        return broken

    # ── severity ─────────────────────────────────────────────────────────────
    @staticmethod
    def _severity(summary: dict[str, int]) -> str:
        critical = summary.get("broken_provenance_links", 0) + summary.get("semantic_without_evidence", 0)
        warning = summary.get("unresolved_conflicts", 0) + summary.get("high_confidence_weak_support", 0)
        if critical > 0:
            return "critical"
        if warning > 0:
            return "warning"
        if any(v > 0 for v in summary.values()):
            return "info"
        return "ok"
