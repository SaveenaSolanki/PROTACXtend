"""Conflict classification and versioned reconsolidation."""

from __future__ import annotations

from helpers import add_degradation_episode, brd4_vhl, build_semantic, ev


def _add_good(mem, project, index, dmax=0.9, **context_overrides):
    return mem.save_episode(
        title=f"good degradation {index}",
        content=f"observed dmax={dmax} for PEG linker architecture",
        event_type="degradation_assay", project_id=project,
        context=brd4_vhl(**context_overrides), observed={"dmax": dmax},
        interpretation="rigid linker supports productive ternary complex",
        evidence=[ev(f"GOOD-{index}")], decision_impact=0.8,
    )["episode_id"]


# ── classification ───────────────────────────────────────────────────────────
def test_conflict_classification_variants(mem, project):
    low = _add_good(mem, project, "low", dmax=0.2)
    high_same = _add_good(mem, project, "high", dmax=0.9)
    high_cell = _add_good(mem, project, "cell", dmax=0.9, cell_line="MV4-11")
    high_assay = _add_good(mem, project, "assay", dmax=0.9, assay_type="HiBiT")
    high_target = _add_good(mem, project, "target", dmax=0.9, target_gene="BRD2")
    high_same_2 = _add_good(mem, project, "high2", dmax=0.95)

    assert mem.judge_conflict(low, high_same)["verdict"] == "true_contradiction"
    assert mem.judge_conflict(low, high_cell)["verdict"] == "contextual_difference"
    assert mem.judge_conflict(low, high_assay)["verdict"] == "assay_difference"
    assert mem.judge_conflict(low, high_target)["verdict"] == "scope_difference"
    assert mem.judge_conflict(high_same, high_same_2)["verdict"] == "compatible_evidence"


def test_conflict_verdicts_are_cached(mem, project):
    low = _add_good(mem, project, "l", dmax=0.2)
    high = _add_good(mem, project, "h", dmax=0.9)
    first = mem.judge_conflict(low, high)
    second = mem.judge_conflict(low, high)
    assert first["verdict"] == second["verdict"]
    count = mem.store.db.scalar("SELECT COUNT(*) FROM conflict_verdicts")
    assert int(count) >= 1


# ── outcomes ─────────────────────────────────────────────────────────────────
def test_strengthen_with_additional_support(mem, project):
    semantic = build_semantic(mem, project, n_support=3)
    new_episode = add_degradation_episode(mem, project, 99, 0.19)
    mem.store.add_relation(new_episode, semantic, "supports", confidence=0.9, created_by="test")
    result = mem.reconsolidate(semantic)
    assert result["outcome"] == "STRENGTHEN"
    assert result["confidence_after"] >= result["confidence_before"]


def test_weaken_on_moderate_contradiction(mem, project):
    semantic = build_semantic(mem, project, n_support=3)
    for i in range(2):
        _add_good(mem, project, i, dmax=0.9)
    mem.detect_conflicts(project)
    result = mem.reconsolidate(semantic)
    assert result["outcome"] in {"WEAKEN", "BRANCH"}
    assert result["confidence_after"] <= result["confidence_before"]


def test_branch_on_context_separable_contradiction(mem, project):
    semantic = build_semantic(mem, project, n_support=3)
    for i in range(3):
        _add_good(mem, project, i, dmax=0.9)
    mem.detect_conflicts(project)
    result = mem.reconsolidate(semantic)
    assert result["outcome"] == "BRANCH"
    assert result["child_semantic_id"]
    child = mem.store.get_semantic(result["child_semantic_id"])
    assert child is not None
    parent_relations = [r["relation_type"] for r in mem.store.relations_for(result["child_semantic_id"])]
    assert "exception_to" in parent_relations


def test_supersede_preserves_version(mem, project):
    semantic = build_semantic(mem, project, n_support=3)
    for i in range(5):
        _add_good(mem, project, i, dmax=0.9)
    mem.detect_conflicts(project)
    result = mem.reconsolidate(semantic)
    assert result["outcome"] in {"SUPERSEDE", "BRANCH"}
    if result["outcome"] == "SUPERSEDE":
        assert result["version_after"] == result["version_before"] + 1
        versions = mem.store.versions_for(semantic)
        assert versions, "previous version must be preserved"
        assert mem.store.require_trace(semantic)["status"] != "deleted"


def test_retract_when_no_support_remains(mem, project):
    semantic = mem.store.add_semantic(
        claim="Unsupported claim", project_id=project, confidence=0.6,
        n_supporting=0, n_contradicting=0, provisional=True,
    )
    for i in range(2):
        episode = _add_good(mem, project, i, dmax=0.9)
        mem.store.add_relation(semantic, episode, "contradicts", confidence=0.8, created_by="test")
    result = mem.reconsolidate(semantic)
    assert result["outcome"] == "RETRACT"
    assert result["confidence_after"] == 0.0
    assert mem.store.require_trace(semantic)["status"] == "retracted"


def test_no_change_when_evidence_is_compatible(mem, project):
    semantic = build_semantic(mem, project, n_support=3)
    result = mem.reconsolidate(semantic)
    assert result["outcome"] == "NO_CHANGE"


def test_reconsolidation_event_is_recorded(mem, project):
    semantic = build_semantic(mem, project, n_support=3)
    _add_good(mem, project, 0, dmax=0.9)
    mem.detect_conflicts(project)
    mem.reconsolidate(semantic)
    events = mem.store.db.query(
        "SELECT * FROM reconsolidation_events WHERE semantic_memory_id = ?", (semantic,)
    )
    assert events
