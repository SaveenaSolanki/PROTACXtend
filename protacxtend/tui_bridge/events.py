"""Typed event contract for PROTACXtend TUI ↔ Python bridge.

Every event is a JSON object with a "type" field. The TypeScript TUI
renders events based on type; the Python backend emits them.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    """All event types in the protocol."""
    # System
    READY = "ready"
    ERROR = "error"

    # Run lifecycle
    RUN_START = "run_start"
    RUN_COMPLETE = "run_complete"

    # Agent lifecycle
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"

    # Tool calls
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

    # Scientific events
    EVIDENCE = "evidence"
    PREDICTION = "prediction"
    CANDIDATE = "candidate"
    WARNING = "warning"

    # Status
    STATUS = "status"
    PROGRESS = "progress"


# ── Agent registry for the TUI ────────────────────────────────────

AGENT_PIPELINE = [
    {"id": "supervisor",            "name": "Supervisor",            "stage": "KNOW"},
    {"id": "planner",               "name": "Design Planner",        "stage": "KNOW"},
    {"id": "safety",                "name": "Safety Precheck",       "stage": "KNOW"},
    {"id": "target_resolver",       "name": "Target Resolver",       "stage": "KNOW"},
    {"id": "binder_retrieval",      "name": "Binder Retrieval",      "stage": "KNOW"},
    {"id": "warhead_selection",     "name": "Warhead Selection",     "stage": "REASON"},
    {"id": "e3_selection",          "name": "E3 Ligand Selection",   "stage": "REASON"},
    {"id": "exit_vector_detection", "name": "Exit Vector Detection", "stage": "REASON"},
    {"id": "linker_generation",     "name": "Linker Generation",     "stage": "DESIGN"},
    {"id": "construction",          "name": "Molecular Construction", "stage": "DESIGN"},
    {"id": "validation",            "name": "Candidate Validation",  "stage": "DESIGN"},
    {"id": "ternary_feasibility",   "name": "Ternary Feasibility",   "stage": "DESIGN"},
    {"id": "degradation_prediction","name": "Degradation Prediction", "stage": "DESIGN"},
    {"id": "admet_prediction",      "name": "ADMET Prediction",      "stage": "DESIGN"},
    {"id": "novelty_check",         "name": "Novelty Check",         "stage": "DESIGN"},
    {"id": "applicability_domain",  "name": "Applicability Domain",  "stage": "DESIGN"},
    {"id": "evidence_sufficiency",  "name": "Evidence Sufficiency",  "stage": "REASON"},
    {"id": "repair_controller",     "name": "Repair Controller",     "stage": "REASON"},
    {"id": "ranking",               "name": "Initial Ranking",       "stage": "DISCOVER"},
    {"id": "diversity",             "name": "Diversity Clustering",  "stage": "DISCOVER"},
    {"id": "reflection",            "name": "Reflection Review",     "stage": "DISCOVER"},
    {"id": "evolution",             "name": "Evolution Refinement",  "stage": "DISCOVER"},
    {"id": "report",                "name": "Report Generation",     "stage": "DISCOVER"},
]

RESEARCH_WORKFLOWS = [
    {"cmd": "/design",    "desc": "Design and rank PROTAC candidates"},
    {"cmd": "/evidence",  "desc": "Retrieve PROTAC-DB, literature, affinity data"},
    {"cmd": "/structure", "desc": "Ternary feasibility, lysine reach, docking"},
    {"cmd": "/cellctx",   "desc": "Score target/E3 abundance per cell line"},
    {"cmd": "/rank",      "desc": "Multi-objective ranking with uncertainty"},
    {"cmd": "/learn",     "desc": "Active-learning feedback and next experiments"},
    {"cmd": "/report",    "desc": "Generate scientist-facing report"},
    {"cmd": "/validate",  "desc": "RDKit validation + ADMET proxy for SMILES"},
    {"cmd": "/contract",  "desc": "KNOW-REASON-DESIGN-DISCOVER contracts"},
    {"cmd": "/run",       "desc": "Execute full agentic workflow"},
    {"cmd": "/plan",      "desc": "Fast plan-only estimate (no execution)"},
    {"cmd": "/status",    "desc": "System and model status"},
    {"cmd": "/about",     "desc": "PROTACXtend information"},
]


def emit(event: dict[str, Any]) -> None:
    """Emit a JSONL event to stdout for the TUI to read."""
    event.setdefault("ts", time.time())
    line = json.dumps(event, default=str)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def emit_ready() -> None:
    """Signal that the Python backend is ready."""
    emit({"type": EventType.READY, "version": "0.1.0"})


def emit_run_start(request: str, run_id: str | None = None) -> str:
    """Signal run start. Returns the run_id."""
    rid = run_id or f"run_{uuid.uuid4().hex[:8]}"
    emit({
        "type": EventType.RUN_START,
        "run_id": rid,
        "request": request,
    })
    return rid


def emit_agent_start(agent_id: str) -> None:
    """Signal an agent is starting."""
    info = next((a for a in AGENT_PIPELINE if a["id"] == agent_id), None)
    emit({
        "type": EventType.AGENT_START,
        "agent_id": agent_id,
        "agent_name": info["name"] if info else agent_id,
        "stage": info["stage"] if info else "UNKNOWN",
    })


def emit_agent_complete(agent_id: str, status: str = "ok", detail: str = "") -> None:
    """Signal an agent completed."""
    emit({
        "type": EventType.AGENT_COMPLETE,
        "agent_id": agent_id,
        "status": status,
        "detail": detail,
    })


def emit_tool_call(tool: str, args: dict[str, Any] | None = None) -> None:
    """Signal a tool call."""
    emit({
        "type": EventType.TOOL_CALL,
        "tool": tool,
        "args": args or {},
    })


def emit_tool_result(tool: str, result: Any = None, status: str = "ok") -> None:
    """Signal a tool result."""
    emit({
        "type": EventType.TOOL_RESULT,
        "tool": tool,
        "result": result,
        "status": status,
    })


def emit_evidence(source: str, data: Any, summary: str = "") -> None:
    """Signal evidence from a tool/API."""
    emit({
        "type": EventType.EVIDENCE,
        "source": source,
        "data": data,
        "summary": summary,
    })


def emit_prediction(model: str, target: str, value: Any, confidence: float = 0.0) -> None:
    """Signal a prediction result."""
    emit({
        "type": EventType.PREDICTION,
        "model": model,
        "target": target,
        "value": value,
        "confidence": confidence,
    })


def emit_candidate(candidate_id: str, smiles: str, score: float, tier: str = "") -> None:
    """Signal a ranked candidate."""
    emit({
        "type": EventType.CANDIDATE,
        "candidate_id": candidate_id,
        "smiles": smiles,
        "score": score,
        "tier": tier,
    })


def emit_warning(message: str, source: str = "") -> None:
    """Signal a warning."""
    emit({
        "type": EventType.WARNING,
        "message": message,
        "source": source,
    })


def emit_run_complete(status: str, run_id: str, summary: dict[str, Any] | None = None) -> None:
    """Signal run completion."""
    emit({
        "type": EventType.RUN_COMPLETE,
        "run_id": run_id,
        "status": status,
        "summary": summary or {},
    })
