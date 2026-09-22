"""Authoritative memory lifecycle state machine (Master Prompt §30).

The nine canonical statuses in ``domain.protac.ontology`` are the only legal
states. This module is the *single* source of truth for which directed
transitions between them are permitted. Nothing else in the codebase may
mutate ``memory_traces.status`` directly; everything routes through
``BaseStore.set_status`` (validated) or ``BaseStore.force_status`` (explicit
administrative override).

Design principles
-----------------
* **Terminal-ish sinks.** ``superseded`` and ``retracted`` may only move to
  ``archived``. ``archived`` is terminal. Scientific history is never revived
  implicitly — a resurrection requires ``force_status`` with an audited reason.
* **No silent rewrites.** ``active``/``consolidated`` knowledge may be
  contradicted, reviewed, superseded, retracted or archived, but never deleted.
* **Self-transitions are idempotent no-ops**, not errors (see ``set_status``).
* The graph is intentionally conservative: if a transition is not listed here it
  is illegal, even if no current caller needs it.
"""

from __future__ import annotations

from ..domain.protac.ontology import (
    MEMORY_STATUSES,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_CANDIDATE,
    STATUS_CONSOLIDATED,
    STATUS_CONSOLIDATING,
    STATUS_CONTRADICTED,
    STATUS_NEEDS_REVIEW,
    STATUS_RETRACTED,
    STATUS_SUPERSEDED,
)
from ..errors import InvalidMemoryTransition

# ── the transition graph ─────────────────────────────────────────────────────
# current status -> set of permitted target statuses.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_CANDIDATE: frozenset({
        STATUS_ACTIVE,
        STATUS_NEEDS_REVIEW,
        STATUS_CONTRADICTED,
        STATUS_ARCHIVED,
    }),
    STATUS_ACTIVE: frozenset({
        STATUS_CONSOLIDATING,
        STATUS_CONSOLIDATED,
        STATUS_NEEDS_REVIEW,
        STATUS_CONTRADICTED,
        STATUS_SUPERSEDED,
        STATUS_RETRACTED,
        STATUS_ARCHIVED,
    }),
    STATUS_CONSOLIDATING: frozenset({
        STATUS_ACTIVE,          # consolidation aborted / rolled back
        STATUS_CONSOLIDATED,
        STATUS_NEEDS_REVIEW,
        STATUS_CONTRADICTED,
        STATUS_SUPERSEDED,
        STATUS_ARCHIVED,
    }),
    STATUS_CONSOLIDATED: frozenset({
        STATUS_ACTIVE,          # reactivated by a successful reconsolidation
        STATUS_CONSOLIDATING,
        STATUS_NEEDS_REVIEW,
        STATUS_CONTRADICTED,
        STATUS_SUPERSEDED,
        STATUS_RETRACTED,
        STATUS_ARCHIVED,
    }),
    STATUS_NEEDS_REVIEW: frozenset({
        STATUS_ACTIVE,
        STATUS_CONSOLIDATING,
        STATUS_CONSOLIDATED,
        STATUS_CONTRADICTED,
        STATUS_SUPERSEDED,
        STATUS_RETRACTED,
        STATUS_ARCHIVED,
    }),
    STATUS_CONTRADICTED: frozenset({
        STATUS_ACTIVE,          # conflict resolved in this memory's favour
        STATUS_CONSOLIDATING,
        STATUS_NEEDS_REVIEW,
        STATUS_SUPERSEDED,
        STATUS_RETRACTED,
        STATUS_ARCHIVED,
    }),
    STATUS_SUPERSEDED: frozenset({STATUS_ARCHIVED}),
    STATUS_RETRACTED: frozenset({STATUS_ARCHIVED}),
    STATUS_ARCHIVED: frozenset(),   # terminal
}

# Statuses with no outgoing transitions.
TERMINAL_STATUSES = frozenset(
    status for status, targets in ALLOWED_TRANSITIONS.items() if not targets
)

# Statuses excluded from normal (non-forced) mutation once reached.
_SINK_STATUSES = frozenset({STATUS_SUPERSEDED, STATUS_RETRACTED, STATUS_ARCHIVED})


def is_known_status(status: str) -> bool:
    """Return True if ``status`` is a canonical lifecycle status."""
    return status in MEMORY_STATUSES


def allowed_targets(current: str) -> frozenset[str]:
    """Return the set of legal target statuses from ``current``."""
    return ALLOWED_TRANSITIONS.get(current, frozenset())


def can_transition(current: str, target: str) -> bool:
    """Return True if ``current -> target`` is a legal, non-no-op transition."""
    if not is_known_status(current) or not is_known_status(target):
        return False
    if current == target:
        return False
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def validate_transition(memory_id: str, current: str, target: str) -> None:
    """Raise ``InvalidMemoryTransition`` unless ``current -> target`` is legal.

    Self-transitions and unknown statuses are rejected here; ``set_status``
    handles the idempotent self-transition case *before* calling this, so a
    no-op never reaches validation.
    """
    if not is_known_status(target):
        raise InvalidMemoryTransition(memory_id, current, target, allowed_targets(current))
    if current == target:
        raise InvalidMemoryTransition(memory_id, current, target, allowed_targets(current))
    if not is_known_status(current):
        raise InvalidMemoryTransition(memory_id, current, target, allowed_targets(current))
    if not can_transition(current, target):
        raise InvalidMemoryTransition(memory_id, current, target, allowed_targets(current))


def is_sink(status: str) -> bool:
    """True for statuses that should not be mutated without ``force_status``."""
    return status in _SINK_STATUSES


def transition_counts() -> dict[str, int]:
    """Introspection helper for tests/reporting."""
    legal = sum(len(targets) for targets in ALLOWED_TRANSITIONS.values())
    n = len(ALLOWED_TRANSITIONS)
    ordered_pairs = n * (n - 1)          # exclude self-transitions
    return {
        "states": n,
        "legal": legal,
        "illegal": ordered_pairs - legal,
        "ordered_pairs": ordered_pairs,
    }


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATUSES",
    "InvalidMemoryTransition",
    "allowed_targets",
    "can_transition",
    "is_known_status",
    "is_sink",
    "transition_counts",
    "validate_transition",
]
