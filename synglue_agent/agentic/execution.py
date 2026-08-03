"""Execution layer for deterministic tools and existing workflow modules."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

from synglue_agent.backend.schemas import model_to_dict
from synglue_agent.schemas.tool_schema import NextAction, ToolResult


class AgenticToolRegistry:
    """Common registry for deterministic tools used by the agentic layer."""

    def __init__(self):
        self._tools: dict[str, Callable[[dict[str, Any]], Any]] = {
            "synglue_agent.backend.main.run_workflow_from_request": self._run_workflow,
            "run_deterministic_design_workflow": self._run_workflow,
        }

    def get(self, name: str) -> Callable[[dict[str, Any]], Any]:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name}")
        return self._tools[name]

    def _run_workflow(self, payload: dict[str, Any]) -> Any:
        from synglue_agent.backend.main import run_workflow_from_request

        return run_workflow_from_request(str(payload.get("request", "")))


class ExecutionAgent:
    """Call selected tools, validate failures, and return structured results."""

    name = "ExecutionAgent"

    def __init__(self, registry: AgenticToolRegistry | None = None):
        self.registry = registry or AgenticToolRegistry()

    def run(self, action: NextAction) -> ToolResult:
        started = time.time()
        input_hash = self._hash(action.input_payload)
        try:
            tool = self.registry.get(action.selected_tool)
            output = tool(action.input_payload)
            warnings = list(getattr(output, "warnings", []) or [])
            return ToolResult(
                tool_name=action.selected_tool,
                input_hash=input_hash,
                output=output,
                status="success",
                warnings=warnings,
                runtime_seconds=round(time.time() - started, 6),
                provenance={
                    "action_name": action.action_name,
                    "reason_for_action": action.reason_for_action,
                    "safety_checks": action.safety_checks,
                },
            )
        except Exception as exc:
            return ToolResult(
                tool_name=action.selected_tool,
                input_hash=input_hash,
                output=None,
                status="failed",
                error_message=str(exc),
                runtime_seconds=round(time.time() - started, 6),
                provenance={"action_name": action.action_name, "fallback_action": action.fallback_action},
            )

    def result_as_dict(self, result: ToolResult) -> dict[str, Any]:
        payload = model_to_dict(result)
        payload["output"] = model_to_dict(result.output)
        return payload

    def _hash(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]
