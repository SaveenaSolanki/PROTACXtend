"""Shared benchmark task schema.

One schema for three task kinds:

- ``tool``   — invoke a registered tool on an input and check its output
- ``agent``  — run an agent-graph stage/objective and check the state
- ``system`` — end-to-end workflow run (KNOW→…→DISCOVER) with artefacts

Ground-truth references are optional and never auto-derived from a
prospective case study (no outcome-derived inputs).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

TASK_KINDS = ("tool", "agent", "system")


@dataclass
class BenchmarkTask:
    task_id: str
    kind: str  # tool | agent | system
    name: str
    manifest_ref: str  # e.g. tools/tools:pymol, agents/supervisor, workflows/design
    description: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)  # machine-checkable
    ground_truth_ref: Optional[str] = None  # path under benchmark/ground_truth/
    uses_ground_truth: bool = False
    status: str = "pending"  # pending | running | passed | failed | skipped
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in TASK_KINDS:
            raise ValueError(f"kind must be one of {TASK_KINDS}, got {self.kind!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "name": self.name,
            "manifest_ref": self.manifest_ref,
            "description": self.description,
            "inputs": self.inputs,
            "expected": self.expected,
            "ground_truth_ref": self.ground_truth_ref,
            "uses_ground_truth": self.uses_ground_truth,
            "status": self.status,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


def new_task(kind: str, name: str, manifest_ref: str, **kw: Any) -> BenchmarkTask:
    task_id = kw.pop("task_id", f"{kind}-{uuid.uuid4().hex[:8]}")
    return BenchmarkTask(task_id=task_id, kind=kind, name=name,
                         manifest_ref=manifest_ref, **kw)
