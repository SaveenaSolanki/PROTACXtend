"""Evidence and provenance schemas."""

from __future__ import annotations

from typing import Any, Optional

from protacxtend.backend.schemas import BaseModel, Field


class EvidenceRecord(BaseModel):
    evidence_id: str = ""
    evidence_type: str = "missing"
    source_tool_or_database: str = ""
    source_file_or_url: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    confidence: Optional[float] = None
    uncertainty: Optional[float] = None
    limitations: str = ""
    claim_allowed: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)

