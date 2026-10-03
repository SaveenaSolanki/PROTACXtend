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

# Direction of an evidence item relative to the claim it is attached to.
EVIDENCE_DIRECTIONS = ("supports", "contradicts", "neutral")

# Frozen, stable schema for result.json (Sprint 1).
SCHEMA_VERSION = "1.0.0"


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
class ToolRun:
    """Typed record of a single tool/backend invocation.

    Every claim that a tool ran must be backed by one of these records.  The
    record captures the resolved tool identity, version, inputs (hashed),
    outcome, evidence tier, timing and provenance link.  ``executed=False``
    is the fail-closed state: a tool that did not run contributes no evidence.
    """

    tool: str
    status: str = "unknown"          # ok | partial | failed | not_available
    executed: bool = False
    valid_output: bool = False
    version: str = ""
    backend: str = ""
    execution_mode: str = ""
    evidence_kind: str = "missing"
    params: dict[str, Any] = field(default_factory=dict)
    params_sha256: str = ""
    error: str = ""
    started_at: str = ""
    ended_at: str = ""
    latency_s: float = 0.0
    artifacts: list[str] = field(default_factory=list)
    provenance: Optional[Provenance] = None

    def __post_init__(self) -> None:
        if self.evidence_kind not in EVIDENCE_KINDS:
            raise ValueError(
                f"tool-run evidence kind must be one of {EVIDENCE_KINDS}, "
                f"got {self.evidence_kind!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "tool": self.tool,
            "status": self.status,
            "executed": self.executed,
            "valid_output": self.valid_output,
            "evidence_kind": self.evidence_kind,
            "params_sha256": self.params_sha256,
            "latency_s": self.latency_s,
        }
        for name in ("version", "backend", "execution_mode", "error", "started_at", "ended_at"):
            value = getattr(self, name)
            if value:
                out[name] = value
        if self.params:
            out["params"] = self.params
        if self.artifacts:
            out["artifacts"] = list(self.artifacts)
        if self.provenance is not None:
            out["provenance"] = self.provenance.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolRun":
        prov = data.get("provenance")
        return cls(
            tool=str(data.get("tool", "")),
            status=str(data.get("status", "unknown")),
            executed=bool(data.get("executed", False)),
            valid_output=bool(data.get("valid_output", False)),
            version=str(data.get("version", "")),
            backend=str(data.get("backend", "")),
            execution_mode=str(data.get("execution_mode", "")),
            evidence_kind=str(data.get("evidence_kind", "missing")),
            params=dict(data.get("params") or {}),
            params_sha256=str(data.get("params_sha256", "")),
            error=str(data.get("error", "")),
            started_at=str(data.get("started_at", "")),
            ended_at=str(data.get("ended_at", "")),
            latency_s=float(data.get("latency_s", 0.0) or 0.0),
            artifacts=list(data.get("artifacts") or []),
            provenance=(
                Provenance(tool=str(prov.get("tool", "")), source=str(prov.get("source", "")),
                           reference=prov.get("reference"))
                if isinstance(prov, dict) else None
            ),
        )


@dataclass
class EvidenceItem:
    """A single piece of typed evidence with explicit provenance.

    ``kind`` is the evidence tier and is restricted to :data:`EVIDENCE_KINDS`.
    ``direction`` records whether the item supports, contradicts or is neutral
    toward the associated claim (contradictions are preserved, never averaged).
    All other fields are optional metadata used by the evidence graph, critics
    and the benchmark grader.
    """

    summary: str
    source: str = ""
    kind: str = "retrieved"
    detail: Optional[dict[str, Any]] = None
    reference: Optional[str] = None
    # ── audit evidence-graph fields ──
    date: Optional[str] = None
    entity: str = ""
    context: str = ""
    direction: str = "neutral"
    strength: Optional[float] = None
    experimental_system: str = ""
    sample_size: Optional[int] = None
    limitations: Optional[list[str]] = None
    claim: str = ""
    confidence: Optional[float] = None
    provenance: Optional[dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.kind not in EVIDENCE_KINDS:
            raise ValueError(f"evidence kind must be one of {EVIDENCE_KINDS}, got {self.kind!r}")
        if self.direction not in EVIDENCE_DIRECTIONS:
            raise ValueError(
                f"evidence direction must be one of {EVIDENCE_DIRECTIONS}, got {self.direction!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "source": self.source,
            "summary": self.summary,
            "direction": self.direction,
        }
        for name in ("detail", "reference", "date", "entity", "context",
                     "strength", "experimental_system", "sample_size",
                     "limitations", "claim", "confidence", "provenance"):
            value = getattr(self, name)
            if value not in (None, "", [], {}):
                out[name] = value
        return out


@dataclass
class ScientificResult:
    """Canonical envelope emitted by every workflow / tool (schema 1.0.0)."""

    workflow: str
    summary: str
    task_id: Optional[str] = None  # stable id for this task/run
    status: str = "ok"  # ok | partial | failed
    metadata: dict[str, Any] = field(default_factory=dict)   # run metadata (request, timestamps, version)
    provider: Optional[str] = None
    model: Optional[str] = None
    result: dict[str, Any] = field(default_factory=dict)     # structured answer
    tools: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)       # file paths (outputs/…)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    confidence: Optional[float] = None  # only when a real model provides it
    uncertainty: Optional[list[str]] = None  # only when provided
    provenance: list[Provenance] = field(default_factory=list)
    tool_runs: list["ToolRun"] = field(default_factory=list)

    def add_tool_run(self, run: "ToolRun") -> "ScientificResult":
        self.tool_runs.append(run)
        return self

    def add_evidence(
        self,
        summary: str,
        source: str = "",
        kind: str = "retrieved",
        detail: Optional[dict[str, Any]] = None,
        reference: Optional[str] = None,
        **extra: Any,
    ) -> "ScientificResult":
        self.evidence.append(
            EvidenceItem(
                summary=summary, source=source, kind=kind, detail=detail,
                reference=reference, **extra,
            )
        )
        return self

    def add_warning(self, message: str) -> "ScientificResult":
        self.warnings.append(message)
        return self

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "task_id": self.task_id,
            "workflow": self.workflow,
            "metadata": dict(self.metadata),
            "provider": self.provider,
            "model": self.model,
            "summary": self.summary,
            "result": dict(self.result),
            "tools": list(self.tools),
            "artifacts": list(self.artifacts),
            "evidence": [e.to_dict() for e in self.evidence],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "provenance": [p.to_dict() for p in self.provenance],
            "tool_runs": [t.to_dict() for t in self.tool_runs],
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
        metadata=dict(data.get("metadata") or {}),
        provider=data.get("provider"),
        model=data.get("model"),
        result=dict(data.get("result") or {}),
        tools=list(data.get("tools") or []),
        artifacts=list(data.get("artifacts") or []),
        errors=list(data.get("errors") or []),
        evidence=[
            EvidenceItem(
                summary=str(e.get("summary", "")),
                source=str(e.get("source", "")),
                kind=str(e.get("kind", "retrieved")),
                detail=e.get("detail"),
                reference=e.get("reference"),
                date=e.get("date"),
                entity=str(e.get("entity", "")),
                context=str(e.get("context", "")),
                direction=str(e.get("direction", "neutral")),
                strength=e.get("strength"),
                experimental_system=str(e.get("experimental_system", "")),
                sample_size=e.get("sample_size"),
                limitations=list(e["limitations"]) if e.get("limitations") else None,
                claim=str(e.get("claim", "")),
                confidence=e.get("confidence"),
                provenance=e.get("provenance"),
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
        tool_runs=[ToolRun.from_dict(t) for t in (data.get("tool_runs") or [])],
    )
