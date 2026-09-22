"""Consolidation gates and scope-aware generalization."""

from __future__ import annotations

from helpers import add_degradation_episode, brd4_vhl, ev
from protacpilot_memory.domain.protac.evidence import EvidenceRef


def test_requires_minimum_episode_count(mem, project):
    add_degradation_episode(mem, project, 0, 0.2)
    add_degradation_episode(mem, project, 1, 0.2)
    report = mem.consolidate(project)
    assert report["created"] == []
    assert report["groups_examined"] == 0


def test_creates_scoped_semantic_with_provenance(mem, project):
    for i in range(3):
        add_degradation_episode(mem, project, i, 0.2)
    report = mem.consolidate(project)
    assert len(report["created"]) == 1
    created = report["created"][0]
    semantic_id = created["semantic_id"]
    semantic = mem.store.get_semantic(semantic_id)
    assert "BRD4" in semantic["claim"] and "VHL" in semantic["claim"]
    assert semantic["provisional"] == 1
    assert semantic["n_supporting"] == 3
    assert mem.store.evidence_count(semantic_id) >= 3
    assert created["scope"]["target_scope"] == "BRD4"


def test_independence_requires_distinct_sources(mem, project):
    # Same experiment id repeated is not independent evidence.
    for i in range(3):
        add_degradation_episode(mem, project, i, 0.2, evidence=[ev("SAME-EXP")])
    candidates = mem.consolidation.find_candidates(project)
    assert candidates and not candidates[0].eligible
    assert any("independent" in reason for reason in candidates[0].gate_reasons)


def test_contradiction_ratio_blocks_generalization(mem, project):
    for i, value in enumerate([0.2, 0.2, 0.9, 0.9]):
        add_degradation_episode(mem, project, i, value)
    candidates = mem.consolidation.find_candidates(project)
    assert candidates
    assert candidates[0].contradiction_ratio >= 0.4
    assert not candidates[0].eligible


def test_llm_only_evidence_cannot_generalize(mem, project):
    session = mem.start_session(project, goal="BRD4 VHL degradation assay")
    for i, value in enumerate([0.2, 0.21, 0.19]):
        add_degradation_episode(
            mem, project, i, value,
            evidence=[EvidenceRef(evidence_type="llm_inference", experiment_id=f"LLM-{i}")],
            decision_impact=1.0, goal_relevance=1.0, session_id=session,
        )
    candidates = mem.consolidation.find_candidates(project)
    assert candidates and not candidates[0].eligible


def test_different_targets_do_not_merge(mem, project):
    for i in range(3):
        add_degradation_episode(mem, project, i, 0.2, context=brd4_vhl())
        add_degradation_episode(mem, project, 100 + i, 0.8, context=brd4_vhl(target_gene="BRD2"))
    report = mem.consolidate(project)
    assert len(report["created"]) == 2
    targets = {c["scope"]["target_scope"] for c in report["created"]}
    assert targets == {"BRD4", "BRD2"}


def test_existing_topic_is_extended_not_duplicated(mem, project):
    for i in range(3):
        add_degradation_episode(mem, project, i, 0.2)
    mem.consolidate(project)
    before = len(mem.store.semantics(project_id=project))
    for i in range(3, 6):
        add_degradation_episode(mem, project, i, 0.2)
    report = mem.consolidate(project)
    after = len(mem.store.semantics(project_id=project))
    assert after == before
    assert report["updated"]
