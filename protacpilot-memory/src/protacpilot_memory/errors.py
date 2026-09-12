"""Typed errors for the cognitive memory subsystem."""

from __future__ import annotations


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
