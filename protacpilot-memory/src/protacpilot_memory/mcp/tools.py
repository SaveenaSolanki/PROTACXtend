"""MCP-compatible tool registry: agent-agnostic `cog_*` affordances (Master Prompt §31)."""

from __future__ import annotations

from typing import Any, Callable

from ..api import CognitiveMemory


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": True,
    }


_STR = {"type": "string"}
_NUM = {"type": "number"}
_INT = {"type": "integer"}
_BOOL = {"type": "boolean"}
_OBJ = {"type": "object"}


class CogToolRegistry:
    """Registry mapping readable `cog_*` tools onto CognitiveMemory methods."""

    def __init__(self, memory: CognitiveMemory) -> None:
        self.memory = memory

    # ── tool catalogue ───────────────────────────────────────────────────────
    def catalogue(self) -> list[dict[str, Any]]:
        return [
            self._tool("cog_current_project", "Resolve the current project (never errors).", _schema({
                "name": _STR,
            }), lambda a: self.memory.current_project(a.get("name"))),
            self._tool("cog_encode", "Encode a scientific experience as an episodic memory (attentional gate applies).", _schema({
                "title": _STR, "content": _STR, "event_type": _STR, "project_id": _STR,
                "session_id": _STR, "context": _OBJ, "observed": _OBJ, "interpretation": _STR,
                "is_negative": _BOOL, "decision_impact": _NUM, "goal_relevance": _NUM,
                "evidence": {"type": "array"}, "source_type": _STR,
            }, ["title", "content"]), lambda a: self.memory.encode(**a)),
            self._tool("cog_save_episode", "Alias of cog_encode for structured episodes.", _schema({
                "title": _STR, "content": _STR, "event_type": _STR, "project_id": _STR,
                "session_id": _STR, "context": _OBJ, "observed": _OBJ, "interpretation": _STR,
                "is_negative": _BOOL, "evidence": {"type": "array"},
            }, ["title", "content"]), lambda a: self.memory.save_episode(**a)),
            self._tool("cog_search", "Hybrid memory search (compact, explainable results).", _schema({
                "query": _STR, "project_id": _STR, "context": _OBJ,
                "memory_types": {"type": "array"}, "limit": _INT, "session_id": _STR,
            }, ["query"]), lambda a: self.memory.search_dict(**a)),
            self._tool("cog_recall", "Search then return the top memory's neighbourhood.", _schema({
                "query": _STR, "project_id": _STR, "context": _OBJ, "limit": _INT,
            }, ["query"]), lambda a: self.memory.recall(**a)),
            self._tool("cog_get", "Get the full scientific memory packet for one memory.", _schema({
                "memory_id": _STR, "why": {"type": "array"},
            }, ["memory_id"]), lambda a: self.memory.get(a["memory_id"], a.get("why"))),
            self._tool("cog_timeline", "Chronological neighbourhood of a memory.", _schema({
                "memory_id": _STR, "window": _INT,
            }, ["memory_id"]), lambda a: self.memory.timeline(a["memory_id"], int(a.get("window", 5)))),
            self._tool("cog_neighbors", "Associative neighbours of a memory.", _schema({
                "memory_id": _STR, "depth": _INT,
            }, ["memory_id"]), lambda a: self.memory.neighbors(a["memory_id"], int(a.get("depth", 1)))),
            self._tool("cog_evidence", "Raw provenance / evidence layer for a memory.", _schema({
                "memory_id": _STR,
            }, ["memory_id"]), lambda a: self.memory.evidence(a["memory_id"])),
            self._tool("cog_context", "Session-start cognitive context (token-budgeted).", _schema({
                "project_id": _STR, "session_id": _STR,
            }), lambda a: self.memory.context(a.get("project_id"), a.get("session_id"))),
            self._tool("cog_predict", "Store a prediction BEFORE the outcome exists.", _schema({
                "prediction_type": _STR, "project_id": _STR, "session_id": _STR,
                "candidate_id": _STR, "metric": _STR, "predicted_value": _NUM,
                "predicted_class": _STR, "predicted_probability": _NUM, "confidence": _NUM,
                "scale": _NUM, "context": _OBJ, "assumptions": {"type": "array"},
            }), lambda a: {"prediction_id": self.memory.predict(**a)}),
            self._tool("cog_record_outcome", "Record an outcome; compute prediction error; encode an episode.", _schema({
                "prediction_id": _STR, "observed_value": _NUM, "observed_class": _STR,
                "observed_probability": _NUM, "outcome_type": _STR, "evidence_type": _STR,
                "source_ref": _STR, "experiment_id": _STR, "notes": _STR,
                "project_id": _STR, "session_id": _STR, "encode": _BOOL,
                "title": _STR, "interpretation": _STR, "is_negative": _BOOL,
            }, ["prediction_id"]), lambda a: self.memory.record_outcome(**a)),
            self._tool("cog_consolidate", "Run gated consolidation of repeated episodes into scoped semantics.", _schema({
                "project_id": _STR, "session_id": _STR,
            }), lambda a: self.memory.consolidate(a.get("project_id"), a.get("session_id"))),
            self._tool("cog_replay", "Run prioritized memory replay.", _schema({
                "project_id": _STR, "trigger": _STR, "session_id": _STR,
            }), lambda a: self.memory.replay(a.get("project_id"), trigger=a.get("trigger", "manual"), session_id=a.get("session_id"))),
            self._tool("cog_compare", "Persist a typed relation between two memories.", _schema({
                "memory_a": _STR, "memory_b": _STR, "relation_type": _STR,
                "confidence": _NUM, "rationale": _STR,
            }, ["memory_a", "memory_b", "relation_type"]), lambda a: self.memory.compare(**a)),
            self._tool("cog_judge_conflict", "Deterministically classify an apparent conflict.", _schema({
                "memory_a": _STR, "memory_b": _STR,
            }, ["memory_a", "memory_b"]), lambda a: self.memory.judge_conflict(a["memory_a"], a["memory_b"])),
            self._tool("cog_reconsolidate", "Versioned belief update for a semantic memory.", _schema({
                "semantic_id": _STR, "trigger": _STR, "session_id": _STR,
            }, ["semantic_id"]), lambda a: self.memory.reconsolidate(a["semantic_id"], trigger=a.get("trigger", "manual"), session_id=a.get("session_id"))),
            self._tool("cog_strengthen", "Use-dependent strengthening of a memory.", _schema({
                "memory_id": _STR,
            }, ["memory_id"]), lambda a: self.memory.strengthen(a["memory_id"])),
            self._tool("cog_weaken", "Explicit weakening of a memory.", _schema({
                "memory_id": _STR, "factor": _NUM,
            }, ["memory_id"]), lambda a: self.memory.weaken(a["memory_id"], float(a.get("factor", 0.7)))),
            self._tool("cog_archive", "Soft-delete / archive a memory (provenance preserved).", _schema({
                "memory_id": _STR, "reason": _STR,
            }, ["memory_id"]), lambda a: self.memory.archive(a["memory_id"], a.get("reason"))),
            self._tool("cog_feedback", "Record whether a retrieved memory was useful (strengthens if so).", _schema({
                "memory_id": _STR, "useful": _BOOL, "used_for": _STR, "session_id": _STR,
            }, ["memory_id", "useful"]), lambda a: self.memory.feedback(a["memory_id"], useful=bool(a["useful"]), used_for=a.get("used_for"), session_id=a.get("session_id"))),
            self._tool("cog_future", "Create a prospective memory / future intention.", _schema({
                "title": _STR, "project_id": _STR, "session_id": _STR, "content": _STR,
                "trigger": _STR, "due_at": _STR, "related_memory_id": _STR, "priority": _NUM,
            }, ["title"]), lambda a: {"prospective_id": self.memory.future(**a)}),
            self._tool("cog_task_add", "Add an actionable task.", _schema({
                "title": _STR, "project_id": _STR, "session_id": _STR, "description": _STR,
                "due_at": _STR, "related_memory_id": _STR, "priority": _NUM,
            }, ["title"]), lambda a: {"task_id": self.memory.task_add(**a)}),
            self._tool("cog_task_resolve", "Resolve a task.", _schema({
                "task_id": _STR, "status": _STR, "note": _STR,
            }, ["task_id"]), lambda a: self.memory.task_resolve(a["task_id"], a.get("status", "done"), a.get("note"))),
            self._tool("cog_pattern_complete", "Cue-driven associative reconstruction.", _schema({
                "cue": _STR, "project_id": _STR, "depth": _INT,
            }, ["cue"]), lambda a: self.memory.pattern_complete(a["cue"], project_id=a.get("project_id"), depth=int(a.get("depth", 2)))),
            self._tool("cog_procedure_save", "Create or version a reusable scientific workflow (procedural memory).", _schema({
                "name": _STR, "steps": {"type": "array"}, "objective": _STR,
                "prerequisites": _STR, "inputs": {"type": "array"}, "outputs": {"type": "array"},
                "tool_dependencies": {"type": "array"}, "version": _INT, "evidence": {"type": "array"},
                "domain": _STR, "project_id": _STR, "session_id": _STR, "replace": _BOOL,
            }, ["name", "steps"]), lambda a: self.memory.procedure_save(**a)),
            self._tool("cog_procedure_search", "Search reusable workflows (hybrid retrieval).", _schema({
                "query": _STR, "project_id": _STR, "domain": _STR, "limit": _INT,
            }), lambda a: self.memory.procedure_search(a.get("query"), project_id=a.get("project_id"), domain=a.get("domain"), limit=int(a.get("limit", 5)))),
            self._tool("cog_procedure_get", "Get a workflow definition by memory id.", _schema({
                "memory_id": _STR,
            }, ["memory_id"]), lambda a: self.memory.procedure_get(a["memory_id"])),
            self._tool("cog_procedure_record_run", "Record a workflow run outcome (success/failure statistics).", _schema({
                "memory_id": _STR, "success": _BOOL, "note": _STR, "session_id": _STR,
            }, ["memory_id", "success"]), lambda a: self.memory.procedure_record_run(a["memory_id"], success=bool(a["success"]), note=a.get("note"), session_id=a.get("session_id"))),
            self._tool("cog_counterfactual", "Analyze an important failure (separate artifact).", _schema({
                "prediction_id": _STR, "outcome_id": _STR, "episode_id": _STR,
                "project_id": _STR, "session_id": _STR, "alternative_assumption": _STR,
            }, ["prediction_id"]), lambda a: self.memory.counterfactual(**a)),
            self._tool("cog_end_session", "Run the end-of-session cognitive process.", _schema({
                "session_id": _STR, "summary": _STR, "next_steps": {"type": "array"},
            }, ["session_id"]), lambda a: self.memory.end_session(a["session_id"], summary=a.get("summary"), next_steps=a.get("next_steps"))),
            self._tool("cog_stats", "Cognitive memory statistics.", _schema({}), lambda a: self.memory.stats()),
            self._tool("cog_doctor", "Store health diagnostics.", _schema({}), lambda a: self.memory.doctor()),
            self._tool("cog_audit", "Run the mandatory memory audit.", _schema({
                "project_id": _STR,
            }), lambda a: self.memory.audit(a.get("project_id"))),
        ]

    def names(self) -> list[str]:
        return [tool["name"] for tool in self.catalogue()]

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
            for t in self.catalogue()
        ]

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        for tool in self.catalogue():
            if tool["name"] == name:
                try:
                    return tool["handler"](dict(arguments or {}))
                except TypeError:
                    # Allow extra/unknown keys by filtering to the handler signature.
                    raise
        raise KeyError(f"unknown tool: {name}")

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _tool(name: str, description: str, input_schema: dict[str, Any], handler: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
        return {"name": name, "description": description, "inputSchema": input_schema, "handler": handler}
