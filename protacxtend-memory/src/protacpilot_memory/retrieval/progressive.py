"""Progressive disclosure: 4 layers, token-budget aware (Master Prompt §14, §32–34)."""

from __future__ import annotations

from typing import Any

from ..config import MemoryConfig
from ..store.store import MemoryStore
from ..util import loads


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class ProgressiveDisclosure:
    def __init__(self, store: MemoryStore, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config

    # ── Layer 1: compact search results ──────────────────────────────────────
    def compact(self, hit: Any) -> dict[str, Any]:
        mem = hit.memory if hasattr(hit, "memory") else hit
        semantic = self.store.get_semantic(mem["id"]) if mem.get("memory_type") == "semantic" else None
        line = {
            "id": mem["id"],
            "type": mem.get("memory_type"),
            "title": mem.get("title"),
            "status": mem.get("status"),
            "confidence": mem.get("confidence"),
            "why_retrieved": list(getattr(hit, "why_retrieved", []) or []),
            "score": getattr(hit, "score", None),
        }
        if semantic is not None:
            line["support"] = semantic.get("n_supporting")
            line["contradictions"] = semantic.get("n_contradicting")
            line["scope"] = self._scope_text(semantic)
        else:
            line["scope"] = mem.get("scope")
        line["preview"] = (mem.get("content") or "")[:240]
        return line

    def render_search_results(self, hits: list[Any], budget: int | None = None) -> str:
        budget = budget or self.config.token_budget
        used = 0
        lines: list[str] = []
        for hit in hits:
            compact = self.compact(hit)
            text = self._compact_text(compact)
            cost = estimate_tokens(text)
            if used + cost > budget and lines:
                lines.append(f"... ({len(hits) - len(lines)} more results omitted for token budget)")
                break
            lines.append(text)
            used += cost
        return "\n\n".join(lines)

    @staticmethod
    def _compact_text(compact: dict[str, Any]) -> str:
        why = " + ".join(compact.get("why_retrieved") or []) or "n/a"
        head = f"#{compact['id']}\nType: {compact['type']}\nTitle: {compact['title']}"
        if compact.get("confidence") is not None:
            head += f"\nConfidence: {compact['confidence']:.2f}"
        if compact.get("support") is not None:
            head += f"\nEvidence: {compact['support']} support / {compact['contradictions']} contradict"
        if compact.get("scope"):
            head += f"\nScope: {compact['scope']}"
        head += f"\nState: {compact.get('status')}\nWhy retrieved: {why}"
        return head

    # ── Layer 2: overview bundles ────────────────────────────────────────────
    def neighborhood(self, memory_id: str) -> dict[str, Any]:
        timeline = self.store.timeline(memory_id)
        relations = self.store.relations_for(memory_id)
        evidence = self.store.links_for_memory(memory_id)
        return {
            "anchor": self.compact(self.store.require_trace(memory_id)),
            "before": [self.compact(t) for t in timeline.get("before", [])],
            "after": [self.compact(t) for t in timeline.get("after", [])],
            "relations": [
                {k: r[k] for k in ("source_memory_id", "target_memory_id", "relation_type", "confidence")}
                for r in relations
            ],
            "evidence_overview": [
                {"id": e["id"], "type": e["evidence_type"], "stance": e["stance"], "quality": e["quality"]}
                for e in evidence
            ],
        }

    def context_overview(self, project_id: str | None, session_id: str | None = None) -> dict[str, Any]:
        """Session-start context (Master Prompt §33), token-budget aware."""
        contexts: dict[str, Any] = {
            "project": self.store.get_project_by_id(project_id) if project_id else None,
            "session": self.store.get_session(session_id) if session_id else None,
            "working_memory": self.store.get_working(session_id) if session_id else [],
            "recent_episodes": [self.compact(t) for t in self.store.high_salience(project_id, limit=8)],
            "active_semantics": [
                self.compact(s) for s in self.store.active_semantics(project_id, limit=10)
            ],
            "unresolved_contradictions": self.store.unresolved_contradictions()[:5],
            "open_tasks": self.store.open_tasks(project_id, limit=10),
            "recent_failures": [
                self.compact(t) for t in self.store.episodes(project_id=project_id, include_negative=True, limit=5)
                if t.get("is_negative")
            ],
            "procedures": [
                {"id": p["id"], "workflow": p.get("workflow_name"), "title": p.get("title")}
                for p in self.store.procedures(project_id, limit=5)
            ],
        }
        return self.trim_context(contexts, self.config.token_budget)

    def trim_context(self, contexts: dict[str, Any], budget: int) -> dict[str, Any]:
        """Drop lowest-priority sections until the estimated budget is met."""
        priority = [
            "project", "session", "working_memory", "open_tasks",
            "recent_failures", "unresolved_contradictions", "active_semantics",
            "recent_episodes", "procedures",
        ]
        import json

        def size() -> int:
            return estimate_tokens(json.dumps(contexts, default=str))

        for key in reversed(priority):
            if size() <= budget:
                break
            if key in contexts and contexts[key]:
                if isinstance(contexts[key], list):
                    contexts[key] = contexts[key][: max(1, len(contexts[key]) // 2)]
                else:
                    contexts[key] = None
        while size() > budget and contexts.get("recent_episodes"):
            contexts["recent_episodes"] = contexts["recent_episodes"][:-1]
        return contexts

    # ── Layer 3: full scientific memory packet ───────────────────────────────
    def render_packet(self, memory_id: str, why: list[str] | None = None) -> str:
        trace = self.store.require_trace(memory_id)
        if trace.get("memory_type") == "semantic":
            return self._semantic_packet(trace, why)
        return self._episodic_packet(trace, why)

    def _semantic_packet(self, trace: dict[str, Any], why: list[str] | None) -> str:
        sem = self.store.get_semantic(trace["id"]) or trace
        scope = self._scope_text(sem)
        lines = [
            f"[MEMORY {trace['id']}]",
            "CLAIM",
            str(sem.get("claim") or trace.get("content")),
            "SCOPE",
            scope or "(unspecified)",
            "CONFIDENCE",
            f"{(sem.get('sem_confidence') or trace.get('confidence') or 0.0):.2f}",
            "SUPPORT",
            f"{sem.get('n_supporting', 0)} episodes "
            f"({sem.get('n_independent_sources', 0)} independent sources)",
            "CONTRADICTIONS",
            f"{sem.get('n_contradicting', 0)} episodes",
            "EVIDENCE QUALITY",
            f"experimental={sem.get('n_experimental', 0)}, "
            f"computational={sem.get('n_computational', 0)}, "
            f"literature={sem.get('n_literature', 0)}",
            "STATUS",
            f"{trace.get('status')}{' (provisional)' if sem.get('provisional') else ''}",
            "LAST VALIDATED",
            str(trace.get("updated_at")),
        ]
        if why:
            lines += ["WHY RETRIEVED", " + ".join(why)]
        return "\n".join(lines)

    def _episodic_packet(self, trace: dict[str, Any], why: list[str] | None) -> str:
        ep = self.store.get_episode(trace["id"]) or trace
        observed = ep.get("observed_json") or {}
        lines = [
            f"[MEMORY {trace['id']}]",
            "TYPE",
            f"{trace.get('memory_type')} / {ep.get('event_type')}",
            "OBSERVATION",
            ", ".join(f"{k}={v}" for k, v in observed.items()) or "(none recorded)",
            "INTERPRETATION",
            str(ep.get("interpretation") or "(none — kept separate from observation)"),
            "CONTEXT",
            self._scope_text(ep) or "(unspecified)",
            "EVIDENCE",
            self._evidence_summary(trace["id"]),
            "STATUS",
            str(trace.get("status")),
            "CREATED",
            str(trace.get("created_at")),
        ]
        if why:
            lines += ["WHY RETRIEVED", " + ".join(why)]
        return "\n".join(lines)

    # ── Layer 4: raw source / artifacts ──────────────────────────────────────
    def raw_evidence(self, memory_id: str) -> dict[str, Any]:
        return {
            "memory_id": memory_id,
            "evidence_items": self.store.links_for_memory(memory_id),
            "events": self.store.events_for(memory_id),
        }

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _scope_text(mem: dict[str, Any]) -> str:
        scope = mem.get("sem_scope_json") or mem.get("scope_json") or {}
        if isinstance(scope, str):
            scope = loads(scope, {})
        parts = [str(v) for v in scope.values() if v]
        return " + ".join(parts) if parts else (mem.get("scope") or "")

    def _evidence_summary(self, memory_id: str) -> str:
        links = self.store.links_for_memory(memory_id)
        if not links:
            return "(none linked)"
        return ", ".join(
            f"{e['evidence_type']}:{e['stance']}" for e in links
        )
