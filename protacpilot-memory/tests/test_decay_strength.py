"""Decay, controlled forgetting, and use-dependent strengthening."""

from __future__ import annotations

from helpers import brd4_vhl, ev
from protacpilot_memory.cognitive.decay import DecayModel
from protacpilot_memory.util import iso_in_days


def _episode(mem, project, index=0):
    return mem.save_episode(
        title=f"decay episode {index}", content="dmax observation",
        event_type="degradation_assay", project_id=project, context=brd4_vhl(),
        observed={"dmax": 0.2}, evidence=[ev(f"DECAY-{index}")], decision_impact=0.8,
    )["episode_id"]


def test_effective_strength_decays_over_time(mem, project):
    episode = _episode(mem, project)
    decay = DecayModel(mem.store, mem.config)
    trace = mem.store.require_trace(episode)
    fresh = decay.effective_strength(trace)
    mem.store.update_trace(episode, last_seen_at=iso_in_days(-400))
    aged = decay.effective_strength(mem.store.require_trace(episode))
    assert aged < fresh
    assert decay.strength_ratio(mem.store.require_trace(episode)) < 1.0


def test_half_life_is_class_specific(mem):
    decay = DecayModel(mem.store, mem.config)
    assert decay.half_life_days("semantic_validated") > decay.half_life_days("episodic")
    assert decay.half_life_days("observation") < decay.half_life_days("semantic")


def test_useful_retrieval_strengthens_only_when_useful(mem, project):
    episode = _episode(mem, project)
    decay = DecayModel(mem.store, mem.config)
    before = decay.effective_strength(mem.store.require_trace(episode))
    unchanged = decay.strengthen(episode, useful=False)
    import pytest
    assert unchanged == pytest.approx(before, rel=1e-6, abs=1e-9)
    after = decay.strengthen(episode, useful=True)
    assert after > before
    assert mem.store.require_trace(episode)["successful_retrieval_count"] == 1


def test_decay_never_deletes_provenance(mem, project):
    episode = _episode(mem, project)
    mem.store.update_trace(episode, memory_strength=0.05, last_seen_at=iso_in_days(-2000))
    flagged = DecayModel(mem.store, mem.config).mark_review_candidates(project)
    assert episode in flagged
    assert mem.store.get_trace(episode, include_deleted=True) is not None  # still exists
    assert mem.store.require_trace(episode)["status"] == "needs_review"


def test_weaken_reduces_strength(mem, project):
    episode = _episode(mem, project)
    decay = DecayModel(mem.store, mem.config)
    before = decay.effective_strength(mem.store.require_trace(episode))
    after = decay.weaken(episode, factor=0.5)
    assert after < before
