"""Typed contracts for the PROTACXtend failure-escalation subsystem.

Every stage of the escalation pipeline records a typed, serialisable record:

    failure -> diagnosis -> external candidate -> install -> registration -> result

Records are dataclasses so they can be written to the JSONL audit ledgers and
rendered in the TUI/CLI without lossy dict juggling.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FailureRecord:
    """One internal-tool failure, fully described."""
    failure_id: str
    created_at: str
    capability: str
    internal_tool: str
    error_type: str
    error_message: str
    traceback_tail: str = ""
    failure_class: str = "HARD_ERROR"
    diagnosis: str = ""
    root_cause: str = ""
    recovery_hint: str = ""
    inputs_digest: str = ""
    run_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailureRecord:
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class ExternalToolCandidate:
    """A toolkit-registry tool that could substitute for the failed internal step."""
    tool_name: str
    category: str
    subcategory: str = ""
    purpose: str = ""
    reason: str = ""
    source: str = ""              # dynamic | toolkit
    status: str = "unknown"
    installed: bool = False
    version: str = ""
    install_hint: str = ""
    installable: bool = False
    install_method: str = ""          # pip | conda | binary | docker | none
    pip_package: str = ""
    executable_names: list[str] = field(default_factory=list)
    python_imports: list[str] = field(default_factory=list)
    web_service: bool = False
    api_required: bool = False
    commercial: bool = False
    license_type: str = ""
    reliability_level: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExternalToolCandidate:
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class InstallRecord:
    tool_name: str
    action: str                        # check | dry_run | install | skip
    command: str = ""
    success: bool = False
    version_before: str = ""
    version_after: str = ""
    stdout_tail: str = ""
    stderr_tail: str = ""
    created_at: str = field(default_factory=utcnow)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RegistrationRecord:
    tool_name: str
    registered: bool
    source: str                        # toolkit_registry | dynamic
    version: str = ""
    capabilities: list[str] = field(default_factory=list)
    status: str = ""
    created_at: str = field(default_factory=utcnow)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EscalationResult:
    ok: bool
    capability: str
    internal_tool: str
    mode: str = "check"
    failure: FailureRecord | None = None
    candidates: list[ExternalToolCandidate] = field(default_factory=list)
    chosen: ExternalToolCandidate | None = None
    install: InstallRecord | None = None
    registration: RegistrationRecord | None = None
    external_result: dict[str, Any] | None = None
    resolved_by: str = ""
    summary: str = ""
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "capability": self.capability,
            "internal_tool": self.internal_tool,
            "mode": self.mode,
            "failure": self.failure.to_dict() if self.failure else None,
            "candidates": [c.to_dict() for c in self.candidates],
            "chosen": self.chosen.to_dict() if self.chosen else None,
            "install": self.install.to_dict() if self.install else None,
            "registration": self.registration.to_dict() if self.registration else None,
            "external_result": self.external_result,
            "resolved_by": self.resolved_by,
            "summary": self.summary,
            "created_at": self.created_at,
        }
