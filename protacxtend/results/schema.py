"""Shared scientific result schema for every PROTACXtend workflow.

One format for status / workflow / summary / result / evidence /
confidence / uncertainty / warnings / provenance. Confidence and
uncertainty are only ever *reported* when a real backend module supplies
them — the schema never invents numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Evidence provenance kinds used across the system. Every datum carries one.
EVIDENCE_KINDS = ("measured", "retrieved", "calculated", "predicted", "inferred", "missing")


@dataclass
class Provenance:
    """Where a result or evidence item came from (tool + source + ref)."""

    tool: str = ""
    source: str = ""
    reference: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"tool": self.tool, "source": self.source}
        if self.reference:
            out["reference"] = self.reference
        return out


@dataclass
class EvidenceItem:
    """A single piece of evidence with an explicit provenance kind.

    kind ∈ {measured, retrieved, calculated, predicted, inferred, missing} —
    nothing is labelled as measured unless an experiment produced it, and
    "inferred" is used only when a model reasoned from other data.
    """

    summary: str
    source: str = ""
    kind: str = "retrieved"
    detail: Optional[dict[str, Any]] = None
    reference: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind not in EVIDENCE_KINDS:
            raise ValueError(f"evidence kind must be one of {EVIDENCE_KINDS}, got {self.kind!r}")

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "source": self.source,
            "summary": self.summary,
        }
        if self.detail:
            out["detail"] = self.detail
        if self.reference:
            out["reference"] = self.reference
        return out


@dataclass
class ScientificResult:
    """Canonical envelope emitted by every workflow / tool."""

    workflow: str
    summary: str
    task_id: Optional[str] = None  # stable id for this task/run
    status: str = "ok"  # ok | partial | failed
    result: dict[str, Any] = field(default_factory=dict)
    evidence: list[EvidenceItem] = field(default_factory=list)
    confidence: Optional[float] = None  # only when a real model provides it
    uncertainty: Optional[list[str]] = None  # only when provided
    warnings: list[str] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)

    def add_evidence(
        self,
        summary: str,
        source: str = "",
        kind: str = "retrieved",
        detail: Optional[dict[str, Any]] = None,
        reference: Optional[str] = None,
    ) -> "ScientificResult":
        self.evidence.append(
            EvidenceItem(summary=summary, source=source, kind=kind, detail=detail, reference=reference)
        )
        return self

    def add_warning(self, message: str) -> "ScientificResult":
        self.warnings.append(message)
        return self

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status": self.status,
            "task_id": self.task_id,
            "workflow": self.workflow,
            "summary": self.summary,
            "result": self.result,
            "evidence": [e.to_dict() for e in self.evidence],
            "warnings": list(self.warnings),
            "provenance": [p.to_dict() for p in self.provenance],
        }
        if self.confidence is not None:
            out["confidence"] = self.confidence
        if self.uncertainty:
            out["uncertainty"] = list(self.uncertainty)
        return out


def from_dict(data: dict[str, Any]) -> ScientificResult:
    """Rebuild a ScientificResult from its dict form (strict about kinds)."""
    return ScientificResult(
        workflow=str(data.get("workflow", "")),
        summary=str(data.get("summary", "")),
        task_id=data.get("task_id"),
        status=str(data.get("status", "ok")),
        result=dict(data.get("result") or {}),
        evidence=[
            EvidenceItem(
                summary=str(e.get("summary", "")),
                source=str(e.get("source", "")),
                kind=str(e.get("kind", "retrieved")),
                detail=e.get("detail"),
                reference=e.get("reference"),
            )
            for e in (data.get("evidence") or [])
        ],
        confidence=data.get("confidence"),
        uncertainty=list(data["uncertainty"]) if data.get("uncertainty") else None,
        warnings=list(data.get("warnings") or []),
        provenance=[
            Provenance(tool=str(p.get("tool", "")), source=str(p.get("source", "")),
                       reference=p.get("reference"))
            for p in (data.get("provenance") or [])
        ],
    )
