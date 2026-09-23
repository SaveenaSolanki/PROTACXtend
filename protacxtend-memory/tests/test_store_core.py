"""Store core: sessions, working memory, soft delete, versions, event ledger."""

from __future__ import annotations

from protacpilot_memory.util import iso_in_days


def test_project_and_session_lifecycle(mem):
    project_id = mem.ensure_project("p1", description="test")
    assert mem.store.get_project("p1")["id"] == project_id
    session_id = mem.start_session(project_id, goal="goal A")
    session = mem.store.get_session(session_id)
    assert session["status"] == "open" and session["goal"] == "goal A"
    mem.end_session(session_id, summary="done")
    assert mem.store.get_session(session_id)["status"] == "closed"


def test_current_project_never_errors(mem):
    result = mem.current_project("brand-new")
    assert result["project"]["name"] == "brand-new"


def test_working_memory_ttl(mem, project):
    session_id = mem.start_session(project)
    mem.remember_working(session_id, "target", "BRD4", project_id=project, goal_relevance=0.9)
    assert len(mem.working(session_id)) == 1
    mem.remember_working(session_id, "expired", "old", project_id=project, ttl_hours=-1)
    keys = {w["key"] for w in mem.working(session_id)}
    assert keys == {"target"}
    removed = mem.store.expire_working()
    assert removed >= 1


def test_soft_delete_hides_from_search(mem, project):
    episode = mem.save_episode(
        title="unique zebra degradation", content="zebra observation",
        event_type="degradation_assay", project_id=project,
        context={"target_gene": "BRD4", "e3_ligase": "VHL"}, decision_impact=0.9,
    )["episode_id"]
    assert mem.search("zebra", project_id=project).hits
    mem.archive(episode, reason="test")
    assert not mem.search("zebra", project_id=project).hits
    # provenance still exists for audit
    trace = mem.store.get_trace(episode, include_deleted=True)
    assert trace is not None
    assert trace["status"] == "archived"


def test_event_ledger_records_transitions(mem, project):
    episode = mem.save_episode(
        title="event ledger test", content="content", event_type="experiment",
        project_id=project, context={"target_gene": "BRD4"}, decision_impact=0.9,
    )["episode_id"]
    mem.archive(episode)
    events = [e["event_type"] for e in mem.store.events_for(episode)]
    assert "ENCODED" in events
    assert "ARCHIVED" in events


def test_semantic_versioning_preserves_history(mem, project):
    semantic = mem.store.add_semantic(
        claim="Old claim", project_id=project, scope_json={"target_scope": "BRD4"},
        confidence=0.5, n_supporting=3, n_independent_sources=2, provisional=True,
    )
    assert mem.store.require_trace(semantic)["version"] == 1
    new_version = mem.store.update_claim(semantic, "New claim", reason="test")
    assert new_version == 2
    versions = mem.store.versions_for(semantic)
    assert versions and versions[0]["content"] == "Old claim"
    assert mem.store.get_semantic(semantic)["claim"] == "New claim"


def test_stats_and_doctor(mem, project):
    mem.save_episode(title="t", content="c", event_type="experiment", project_id=project,
                     context={"target_gene": "BRD4"}, decision_impact=0.9)
    stats = mem.stats()
    assert stats["episodes"] >= 1
    doctor = mem.doctor()
    assert doctor["integrity"] == "ok"
    assert doctor["fts5_ok"] is True
