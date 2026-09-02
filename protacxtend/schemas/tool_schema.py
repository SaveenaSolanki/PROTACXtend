"""Tool action/result schemas."""

from __future__ import annotations

from typing import Any

from protacxtend.backend.schemas import BaseModel, Field


class NextAction(BaseModel):
    action_name: str = ""
    selected_tool: str = ""
    input_payload: dict[str, Any] = Field(default_factory=dict)
    expected_output: str = ""
    reason_for_action: str = ""
    fallback_action: str = ""
    safety_checks: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class ToolResult(BaseModel):
    tool_name: str = ""
    input_hash: str = ""
    output: Any = None
    status: str = "not_run"
    error_message: str = ""
    warnings: list[str] = Field(default_factory=list)
    runtime_seconds: float = 0.0
    provenance: dict[str, Any] = Field(default_factory=dict)
    output_schema_version: str = "ToolResult.v1"

