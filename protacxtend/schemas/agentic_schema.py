"""Schemas for the seven-layer PROTACXtend agentic architecture."""

from __future__ import annotations

from typing import Any, Optional

from protacxtend.backend.schemas import BaseModel, Field
from protacxtend.schemas.candidate_schema import CandidateProvenance
from protacxtend.schemas.memory_schema import DesignMemoryRecord
from protacxtend.schemas.tool_schema import NextAction, ToolResult


class PerceptionState(BaseModel):
    raw_request: str = ""
    normalized_request: str = ""
    detected_entities: dict[str, Any] = Field(default_factory=dict)
    available_tools: dict[str, Any] = Field(default_factory=dict)
    available_models: dict[str, Any] = Field(default_factory=dict)
    available_local_data: dict[str, Any] = Field(default_factory=dict)
    retrieved_memory: list[dict[str, Any]] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    scientific_risk_flags: list[str] = Field(default_factory=list)
    perception_confidence: float = 0.0
    timestamp: str = ""


class ReasoningState(BaseModel):
    target_assessment: dict[str, Any] = Field(default_factory=dict)
    binder_assessment: dict[str, Any] = Field(default_factory=dict)
    e3_assessment: dict[str, Any] = Field(default_factory=dict)
    exit_vector_assessment: dict[str, Any] = Field(default_factory=dict)
    linker_strategy: dict[str, Any] = Field(default_factory=dict)
    scoring_strategy: dict[str, Any] = Field(default_factory=dict)
    ternary_strategy: dict[str, Any] = Field(default_factory=dict)
    admet_strategy: dict[str, Any] = Field(default_factory=dict)
    uncertainty_assessment: dict[str, Any] = Field(default_factory=dict)
    recommended_next_actions: list[str] = Field(default_factory=list)
    reasoning_trace: list[dict[str, Any]] = Field(default_factory=list)


class DesignGoal(BaseModel):
    target: str = ""
    e3_ligase: str = ""
    candidate_count: int = 0
    design_mode: str = "design"
    required_outputs: list[str] = Field(default_factory=list)
    optimization_objectives: list[str] = Field(default_factory=list)
    hard_constraints: dict[str, Any] = Field(default_factory=dict)
    soft_constraints: dict[str, Any] = Field(default_factory=dict)
    validation_depth: str = "medium"
    stop_criteria: list[str] = Field(default_factory=list)
    fallback_policy: dict[str, Any] = Field(default_factory=dict)
    success_criteria: list[str] = Field(default_factory=list)


class AgenticWorkflowResult(BaseModel):
    run_id: str = ""
    final_status: str = "not_started"
    perception: dict[str, Any] = Field(default_factory=dict)
    reasoning: dict[str, Any] = Field(default_factory=dict)
    design_goal: dict[str, Any] = Field(default_factory=dict)
    decision_trace: list[dict[str, Any]] = Field(default_factory=list)
    final_candidates: list[dict[str, Any]] = Field(default_factory=list)
    ranked_candidates: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    failed_steps: list[dict[str, Any]] = Field(default_factory=list)
    provenance_log: list[dict[str, Any]] = Field(default_factory=list)
    candidate_provenance: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    memory_updates: list[dict[str, Any]] = Field(default_factory=list)
    report_paths: dict[str, str] = Field(default_factory=dict)
    candidate_csv_path: str = ""
    candidate_json_path: str = ""
    markdown_report: str = ""


class AgenticRunState(BaseModel):
    run_id: str = ""
    request: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    perception: Optional[PerceptionState] = None
    reasoning: Optional[ReasoningState] = None
    design_goal: Optional[DesignGoal] = None
    decision_trace: list[NextAction] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    candidate_provenance: list[CandidateProvenance] = Field(default_factory=list)
    memory_updates: list[DesignMemoryRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    failed_steps: list[dict[str, Any]] = Field(default_factory=list)
