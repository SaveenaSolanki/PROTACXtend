"""Stable, auditable run record for one scientific run.

Purpose: every user-visible number must trace to a run record that preserves
the raw JSON. This schema is deliberately one-run-scoped and separate from the
capability landscape (landscape.py). Fields:

- question / inputs          : the exact user request + parsed objective
- tool_calls[]              : node-level or tool-level executions with name,
                              version (protacxtend + external tool), parameters
                              (bounded), outputs (bounded or omitted), errors,
                              timestamps (started/finished, monotonic + wall),
                              source identifiers (accessions/DOIs/URLs),
                              artifact paths (optional)
- final_output              : dict summary of the typed strategy
- raw_json_path             : path to the preserved raw JSON (strategy.json)
- provenance                : engine, execution mode, package version, host,
                              runtime accounting, warnings, errors
- validation                : reviewer/date/status fields (default unassessed)
"""

from __future__ import annotations

import hashlib, json, os, time
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "EvidenceRunRecord.v1"


class ToolCallRecord(BaseModel):
    tool: str = ""
    version: str = "protacxtend-0.3.0"
    parameters: dict[str, Any] = Field(default_factory=dict)
    output: Optional[str] = None          # bounded string (never secrets)
    output_artifact: Optional[str] = None
    error: Optional[str] = None
    started_wall: Optional[str] = None
    finished_wall: Optional[str] = None
    elapsed_s: Optional[float] = None
    source_identifiers: list[str] = Field(default_factory=list)  # accessions / DOIs / URLs


class EvidenceRunRecord(BaseModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    question: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    final_output: dict[str, Any] = Field(default_factory=dict)
    raw_json_path: Optional[str] = None
    artifact_paths: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(
        default_factory=lambda: {
            "reviewer": "", "date": "", "status": "unassessed", "reason": "",
        }
    )
    reproducibility_hash: str = ""

    def compute_hash(self) -> str:
        data = self.model_dump()
        data.pop("reproducibility_hash", None)
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def write_run_record(record: EvidenceRunRecord, out_dir: str) -> str:
    """Persist the raw run record as run.json inside ``out_dir``.

    Always preserves the referenced raw strategy JSON alongside it.
    """
    os.makedirs(out_dir, exist_ok=True)
    record.reproducibility_hash = record.compute_hash()
    path = os.path.join(out_dir, "run.json")
    with open(path, "w") as f:
        json.dump(record.model_dump(), f, indent=1, default=str)
    if record.raw_json_path and os.path.exists(record.raw_json_path):
        raw_target = os.path.join(out_dir, "raw_strategy.json")
        with open(record.raw_json_path) as src, open(raw_target, "w") as dst:
            dst.write(src.read())
        if raw_target not in record.artifact_paths:
            record.artifact_paths.append(raw_target)
    return path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_run_record(path: str) -> EvidenceRunRecord:
    with open(path) as f:
        return EvidenceRunRecord(**json.load(f))