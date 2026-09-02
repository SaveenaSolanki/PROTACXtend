"""LEGACY memory schema (v0.2-era).

`DesignMemoryRecord` is superseded by `LearningEntry` in
protacxtend/tools/learning_memory.py (structured, validated, source-tracked,
reuse-counted). Kept as a deprecated Pydantic alias so the legacy scaffold's
imports keep working.
"""

from __future__ import annotations

import warnings
from typing import Any, List, Optional

from pydantic import BaseModel, Field

warnings.warn(
    "memory_schema.DesignMemoryRecord is deprecated — use "
    "protacxtend.tools.learning_memory.LearningEntry instead.",
    DeprecationWarning,
    stacklevel=2,
)


class DesignMemoryRecord(BaseModel):
    """Deprecated. Use LearningEntry (learning_memory.py)."""

    run_id: str = ""
    timestamp: str = ""
    user_request: str = ""
    target: str = ""
    e3_ligase: str = ""
    warheads_used: List[str] = Field(default_factory=list)
    linkers_used: List[str] = Field(default_factory=list)
    exit_vectors_used: List[str] = Field(default_factory=list)
    candidates_generated: int = 0
    candidates_valid: int = 0
    candidates_failed: int = 0
    top_candidates: List[dict] = Field(default_factory=list)
    failure_modes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    model_versions: dict = {}
    tool_versions: dict = {}
    user_feedback: Optional[str] = None
    reusable_lessons: List[str] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__
