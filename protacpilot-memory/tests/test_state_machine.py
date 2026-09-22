"""Exhaustive lifecycle state-machine tests (Sprint V1 / Master Prompt §30).

Every legal and illegal directed transition between the canonical statuses is
exercised. Test setup uses ``force_status`` (the explicit administrative
override) to place a memory into an arbitrary starting state; the behaviour
under test always uses the validated ``set_status`` path.
"""

from __future__ import annotations

import pytest
from protacpilot_memory.cognitive.state_machine import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    allowed_targets,
    can_transition,
    is_known_status,
    transition_counts,
    validate_transition,
)
from protacpilot_memory.domain.protac.ontology import MEMORY_STATUSES
from protacpilot_memory.errors import ConflictError, InvalidMemoryTransition

STATES = sorted(MEMORY_STATUSES)
LEGAL = {
    (current, target)
    for current, targets in ALLOWED_TRANSITIONS.items()
    for target in targets
}
ILLEGAL = {
    (current, target)
    for current in STATES
    for target in STATES
    if current != target and (current, target) not in LEGAL
}


# ── fixtures/helpers ─────────────────────────────────────────────────────────
def _new_memory(mem, project, *, status: str | None = None) -> str:
    result = mem.save_episode(
        title="linker geometry observation",
        content="observed dmax for PEG linker",
        event_type="degradation_assay",
        project_id=project,
        context={"target_gene": "BRD4", "e3_ligase": "VHL", "cell_line": "HEK293"},
        evidence=[{"evidence_type": "internal_experiment", "experiment_id": "EXP-SM"}],
    )
    mid = result["episode_id"]
    if status and status != "active":
        mem.store.force_status(mid, status, reason="test setup")
    return mid


def _state_events(mem, mid: str) -> list[dict]:
    return [e for e in mem.store.events_for(mid) if e["event_type"] == "STATE_CHANGED"]


# ── graph shape ──────────────────────────────────────────────────────────────
def test_graph_shape_and_counts():
    counts = transition_counts()
    assert counts["states"] == len(MEMORY_STATUSES) == 9
    assert counts["legal"] == len(LEGAL)
    assert counts["illegal"] == len(ILLEGAL)
    assert counts["ordered_pairs"] == len(STATES) * (len(STATES) - 1)
    # every canonical status is a node
    assert set(ALLOWED_TRANSITIONS) == MEMORY_STATUSES
    # archived is the only true sink
    assert TERMINAL_STATUSES == {"archived"}
    # superseded/retracted are sink-ish: only archive is reachable
    assert allowed_targets("superseded") == {"archived"}
    assert allowed_targets("retracted") == {"archived"}


def test_unknown_statuses_are_not_known():
    assert not is_known_status("replay_eligible")
    assert not is_known_status("bogus")
    assert not can_transition("active", "bogus")
    assert not can_transition("bogus", "active")
    with pytest.raises(InvalidMemoryTransition):
        validate_transition("MEM", "active", "bogus")


# ── every legal transition succeeds ──────────────────────────────────────────
@pytest.mark.parametrize(("current", "target"), sorted(LEGAL))
def test_every_legal_transition_succeeds(mem, project, current, target):
    mid = _new_memory(mem, project, status=current)
    before = len(_state_events(mem, mid))
    assert mem.store.set_status(mid, target, reason="legal") is True
    assert mem.store.get_trace(mid)["status"] == target
    events = _state_events(mem, mid)
    assert len(events) == before + 1
    detail = events[-1]["detail_json"]
    assert detail["from"] == current and detail["to"] == target
    assert detail["reason"] == "legal"


# ── every illegal transition fails ───────────────────────────────────────────
@pytest.mark.parametrize(("current", "target"), sorted(ILLEGAL))
def test_every_illegal_transition_fails(mem, project, current, target):
    mid = _new_memory(mem, project, status=current)
    before_events = len(mem.store.events_for(mid))
    before_updated = mem.store.get_trace(mid)["updated_at"]
    with pytest.raises(InvalidMemoryTransition) as exc:
        mem.store.set_status(mid, target)
    assert exc.value.current == current and exc.value.target == target
    # no mutation, no event (validation happens before the transaction)
    assert mem.store.get_trace(mid)["status"] == current
    assert mem.store.get_trace(mid)["updated_at"] == before_updated
    assert len(mem.store.events_for(mid)) == before_events


# ── self-transitions ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("state", STATES)
def test_self_transition_is_idempotent_noop(mem, project, state):
    mid = _new_memory(mem, project, status=state)
    before_events = len(mem.store.events_for(mid))
    before_updated = mem.store.get_trace(mid)["updated_at"]
    assert mem.store.set_status(mid, state) is False
    assert mem.store.get_trace(mid)["status"] == state
    assert mem.store.get_trace(mid)["updated_at"] == before_updated
    assert len(mem.store.events_for(mid)) == before_events


def test_validate_transition_rejects_self_transition():
    with pytest.raises(InvalidMemoryTransition):
        validate_transition("MEM", "active", "active")


# ── unknown target / corrupt current ─────────────────────────────────────────
def test_unknown_target_rejected_no_mutation(mem, project):
    mid = _new_memory(mem, project)
    before = len(mem.store.events_for(mid))
    with pytest.raises(InvalidMemoryTransition):
        mem.store.set_status(mid, "consolidating_forever")
    assert mem.store.get_trace(mid)["status"] == "active"
    assert len(mem.store.events_for(mid)) == before


def test_unknown_current_status_rejected(mem, project):
    mid = _new_memory(mem, project)
    # simulate on-disk corruption of the current status
    mem.store.db.execute("UPDATE memory_traces SET status = 'corrupt' WHERE id = ?", (mid,))
    before = len(mem.store.events_for(mid))
    with pytest.raises(InvalidMemoryTransition):
        mem.store.set_status(mid, "active")
    assert mem.store.get_trace(mid)["status"] == "corrupt"
    assert len(mem.store.events_for(mid)) == before


# ── event-log correctness ────────────────────────────────────────────────────
def test_event_log_records_transition_and_timestamp(mem, project, session):
    mid = _new_memory(mem, project)
    mem.store.set_status(mid, "needs_review", reason="stale", session_id=session)
    events = _state_events(mem, mid)
    assert events, "expected a STATE_CHANGED event"
    last = events[-1]
    assert last["detail_json"] == {
        "from": "active", "to": "needs_review", "reason": "stale",
    }
    assert last["session_id"] == session
    assert last["created_at"]


# ── rollback on failure ──────────────────────────────────────────────────────
def test_rejected_transition_is_fully_rolled_back(mem, project):
    mid = _new_memory(mem, project, status="superseded")
    snapshot = dict(mem.store.get_trace(mid))
    with pytest.raises(InvalidMemoryTransition):
        mem.store.set_status(mid, "active")  # superseded -> active is illegal
    after = mem.store.get_trace(mid)
    assert after["status"] == snapshot["status"]
    assert after["updated_at"] == snapshot["updated_at"]
    assert not any(
        e["event_type"] == "STATE_CHANGED" and e["detail_json"].get("to") == "active"
        for e in mem.store.events_for(mid)
    )


# ── terminal states ──────────────────────────────────────────────────────────
def test_archived_is_terminal(mem, project):
    mid = _new_memory(mem, project, status="archived")
    for target in STATES:
        if target == "archived":
            continue
        with pytest.raises(InvalidMemoryTransition):
            mem.store.set_status(mid, target)
    assert mem.store.get_trace(mid)["status"] == "archived"
    assert allowed_targets("archived") == frozenset()


def test_sink_states_only_archive(mem, project):
    for sink in ("superseded", "retracted"):
        mid = _new_memory(mem, project, status=sink)
        with pytest.raises(InvalidMemoryTransition):
            mem.store.set_status(mid, "active")
        assert mem.store.set_status(mid, "archived") is True
        assert mem.store.get_trace(mid)["status"] == "archived"


# ── administrative override ──────────────────────────────────────────────────
def test_force_status_bypasses_graph_and_is_audited(mem, project):
    mid = _new_memory(mem, project)  # active
    assert mem.store.force_status(mid, "candidate", reason="admin reset") is True
    assert mem.store.get_trace(mid)["status"] == "candidate"
    last = _state_events(mem, mid)[-1]["detail_json"]
    assert last["forced"] is True
    assert last["from"] == "active" and last["to"] == "candidate"
    # and the normal path still works from candidate
    assert mem.store.set_status(mid, "active") is True


def test_force_status_rejects_unknown(mem, project):
    mid = _new_memory(mem, project)
    with pytest.raises(InvalidMemoryTransition):
        mem.store.force_status(mid, "not_a_status")
    assert mem.store.get_trace(mid)["status"] == "active"


def test_force_status_can_resurrect_archived(mem, project):
    mid = _new_memory(mem, project, status="archived")
    assert mem.store.force_status(mid, "active", reason="manual restore") is True
    assert mem.store.get_trace(mid)["status"] == "active"


# ── concurrency / optimistic-lock guard ──────────────────────────────────────
def test_stale_expected_status_raises_conflict_and_logs_nothing(mem, project):
    mid = _new_memory(mem, project)  # active
    before = len(mem.store.events_for(mid))
    # Simulate another committed writer: DB is now needs_review, but we apply
    # with a stale expectation of "active".
    mem.store.db.execute("UPDATE memory_traces SET status = 'needs_review' WHERE id = ?", (mid,))
    with pytest.raises(ConflictError):
        mem.store._apply_status(
            mid, "active", "archived", "race", None, "STATE_CHANGED", None
        )
    assert mem.store.get_trace(mid)["status"] == "needs_review"  # not overwritten
    assert len(mem.store.events_for(mid)) == before  # no event appended


def test_concurrent_status_change_is_revalidated(mem, project):
    mid = _new_memory(mem, project)  # active
    mem.store.db.execute("UPDATE memory_traces SET status = 'archived' WHERE id = ?", (mid,))
    # set_status re-reads current status inside the call: archived -> active is
    # illegal, so the transition is rejected rather than silently applied.
    with pytest.raises(InvalidMemoryTransition):
        mem.store.set_status(mid, "active")
    assert mem.store.get_trace(mid)["status"] == "archived"
