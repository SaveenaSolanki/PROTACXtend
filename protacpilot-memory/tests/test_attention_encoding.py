"""Attentional gate and episodic encoding."""

from __future__ import annotations

from protacpilot_memory import CognitiveMemory, MemoryConfig
from protacpilot_memory.cognitive.attention import (
    DECISION_ENCODE,
    DECISION_IGNORE,
    DECISION_PRIORITY,
    DECISION_TEMPORARY,
    AttentionGate,
    AttentionInput,
)
from protacpilot_memory.config import EncodingThresholds

from helpers import brd4_vhl, ev


def test_exact_duplicate_is_not_re_encoded(mem, project):
    kwargs = dict(
        title="identical experiment", content="identical content dmax=0.2",
        event_type="degradation_assay", project_id=project, context=brd4_vhl(),
        observed={"dmax": 0.2}, evidence=[ev("DUP-1")], decision_impact=0.8,
    )
    first = mem.save_episode(**kwargs)
    second = mem.save_episode(**kwargs)
    assert first["episode_id"]
    assert second["decision"] == DECISION_TEMPORARY
    assert second["duplicate_of"] == first["episode_id"]
    assert second["episode_id"] == first["episode_id"]


def test_pattern_separation_keeps_distinct_replicates(mem, project):
    a = mem.save_episode(
        title="BRD4 VHL replicate", content="dmax measured 0.21 for PEG linker",
        event_type="degradation_assay", project_id=project, context=brd4_vhl(),
        observed={"dmax": 0.21}, evidence=[ev("REP-1")], decision_impact=0.8,
    )
    b = mem.save_episode(
        title="BRD4 VHL replicate", content="dmax measured 0.22 for PEG linker",
        event_type="degradation_assay", project_id=project, context=brd4_vhl(),
        observed={"dmax": 0.22}, evidence=[ev("REP-2")], decision_impact=0.8,
    )
    assert a["episode_id"] and b["episode_id"]
    assert a["episode_id"] != b["episode_id"]
    assert b["duplicate_of"] is None


def test_same_context_different_target_are_different_episodes(mem, project):
    a = mem.save_episode(title="t", content="dmax 0.2", event_type="degradation_assay",
                         project_id=project, context=brd4_vhl(), observed={"dmax": 0.2},
                         evidence=[ev("T-1")], decision_impact=0.8)
    b = mem.save_episode(title="t", content="dmax 0.2", event_type="degradation_assay",
                         project_id=project, context=brd4_vhl(target_gene="BRD2"),
                         observed={"dmax": 0.2}, evidence=[ev("T-2")], decision_impact=0.8)
    assert a["fingerprint"] != b["fingerprint"]


def test_high_surprise_is_priority(mem, project):
    gate = AttentionGate(mem.store, mem.config)
    decision = gate.evaluate(AttentionInput(
        title="model prediction failed", content="observed far from prediction",
        event_type="outcome", project_id=project, context=brd4_vhl(),
        evidence=[ev("SUR-1")], prediction_error=0.9, prediction_confidence=0.8,
        decision_impact=0.85,
    ))
    assert decision.decision == DECISION_PRIORITY
    assert decision.components["surprise"] > 0.5
    assert "contradicted" in decision.reason or "priority" in decision.reason


def test_low_value_event_is_ignored_with_strict_thresholds():
    config = MemoryConfig().with_overrides(
        thresholds=EncodingThresholds(t_ignore=0.5, t_episode=0.6, t_priority=0.9)
    )
    memory = CognitiveMemory.in_memory(config)
    project_id = memory.ensure_project("low")
    result = memory.save_episode(
        title="random chatter", content="nothing important", event_type="procedure_run",
        project_id=project_id, decision_impact=0.1,
    )
    assert result["decision"] == DECISION_IGNORE
    assert result["episode_id"] is None
    memory.close()


def test_negative_memory_is_first_class(mem, project):
    result = mem.save_episode(
        title="FAILED shortened linker", content="dmax fell to 18%",
        event_type="failure", project_id=project, context=brd4_vhl(),
        observed={"dmax": 0.18}, is_negative=True, evidence=[ev("NEG-1")],
        decision_impact=0.95,
    )
    assert result["decision"] in (DECISION_ENCODE, DECISION_PRIORITY)
    episode = mem.store.get_episode(result["episode_id"])
    assert episode["is_negative"] == 1
    assert mem.store.require_trace(result["episode_id"])["memory_type"] == "negative"


def test_encoding_breakdown_is_recorded(mem, project):
    result = mem.save_episode(
        title="evidence backed", content="dmax 0.3", event_type="degradation_assay",
        project_id=project, context=brd4_vhl(), observed={"dmax": 0.3},
        evidence=[ev("EB-1")], decision_impact=0.8,
    )
    assert "encoding_score" in result["breakdown"]
    assert set(result["breakdown"]) >= {
        "goal_relevance", "novelty", "surprise", "evidence_strength",
        "recurrence", "decision_impact", "reason",
    }
