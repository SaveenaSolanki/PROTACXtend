"""Typed errors for the cognitive memory subsystem."""

from __future__ import annotations

from typing import Iterable


class CogMemoryError(Exception):
    """Base class for all protacpilot-memory errors."""


class MigrationError(CogMemoryError):
    """Raised when the database schema cannot be safely migrated."""


class ValidationError(CogMemoryError):
    """Raised when caller input violates a scientific/structural contract."""


class NotFoundError(CogMemoryError):
    """Raised when a requested memory/entity/prediction does not exist."""

    def __init__(self, kind: str, ident: str):
        super().__init__(f"{kind} not found: {ident}")
        self.kind = kind
        self.ident = ident


class ConflictError(CogMemoryError):
    """Raised when an operation would violate provenance/identity invariants."""


class InvalidMemoryTransition(CogMemoryError):
    """Raised when a memory lifecycle transition is not permitted (Master Prompt §30)."""

    def __init__(
        self,
        memory_id: str,
        current: str,
        target: str,
        allowed: Iterable[str] | None = None,
    ) -> None:
        self.memory_id = memory_id
        self.current = current
        self.target = target
        self.allowed = sorted(allowed or [])
        allowed_text = ", ".join(self.allowed) if self.allowed else "<none>"
        super().__init__(
            f"invalid memory transition for {memory_id}: "
            f"{current!r} -> {target!r} (allowed from {current!r}: {allowed_text})"
        )
