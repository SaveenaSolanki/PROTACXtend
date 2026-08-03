"""Structured memory schemas for agentic design runs."""

from __future__ import annotations

from typing import Any, Optional

from synglue_agent.backend.schemas import BaseModel, Field


class DesignMemoryRecord(BaseModel):
    run_id: str = ""
    timestamp: str = ""
    user_request: str = ""
    target: str = ""
    e3_ligase: str = ""
    warheads_used: list[str] = Field(default_factory=list)
    linkers_used: list[str] = Field(default_factory=list)
    exit_vectors_used: list[str] = Field(default_factory=list)
    candidates_generated: int = 0
    candidates_valid: int = 0
    candidates_failed: int = 0
    top_candidates: list[dict[str, Any]] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    model_versions: dict[str, str] = Field(default_factory=dict)
    tool_versions: dict[str, str] = Field(default_factory=dict)
    user_feedback: Optional[str] = None
    reusable_lessons: list[str] = Field(default_factory=list)

