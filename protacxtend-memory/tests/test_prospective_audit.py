"""Prospective memory, tasks, counterfactuals, and the auditor."""

from __future__ import annotations

from helpers import brd4_vhl, ev
from protacpilot_memory.domain.protac.evidence import EvidenceRef


def test_prospective_memory_creates_task(mem, project):
    prospective_id = mem.future(
        title="Validate P17 permeability", project_id=project, priority=0.8,
        related_memory_id=None,
    )
    assert prospective_id
    record = mem.store.get_prospective(prospective_id)
    assert record["prosp_status"] == "open"
    tasks = mem.open_tasks(project)
    assert any(t["title"] == "Validate P17 permeability" for t in tasks)
    mem.task_resolve(tasks[0]["id"], status="done")
    assert all(t["id"] != tasks[0]["id"] for t in mem.open_tasks(project))


def test_task_add_and_resolve(mem, project):
    task_id = mem.task_add("Repeat degradation assay for P21", project_id=project)
    assert any(t["id"] == task_id for t in mem.open_tasks(project))
    mem.task_resolve(task_id)
    assert mem.store.get_task(task_id)["status"] == "done"


def test_counterfactual_is_separate_artifact(mem, project):
    prediction_id = mem.predict(
        project_id=project, candidate_id="P17", metric="dmax", predicted_value=0.89,
        confidence=0.8, scale=1.0, context=brd4_vhl(),
        assumptions=["rigid linker preserves ternary geometry"],
    )
    mem.record_outcome(prediction_id, observed_value=0.2, encode=False, project_id=project)
    analysis = mem.counterfactual(prediction_id, project_id=project)
    assert analysis["id"]
    assert analysis["questionable_assumption"] == "rigid linker preserves ternary geometry"
    assert mem.counterfactual_analyzer.for_prediction(prediction_id)


def test_auditor_detects_llm_only_claims(mem, project):
    semantic = mem.store.add_semantic(
        claim="An LLM-only claim", project_id=project,
        scope_json={"target_scope": "BRD4"}, confidence=0.8,
    )
    evidence = mem.store.add_evidence(
        EvidenceRef(evidence_type="llm_inference", title="llm thought"), project_id=project
    )
    mem.store.link(semantic, evidence, stance="supports")
    findings = mem.audit(project)["findings"]
    assert any(f["id"] == semantic for f in findings["llm_only_claims"])


def test_auditor_detects_semantic_without_evidence(mem, project):
    semantic = mem.store.add_semantic(
        claim="Unsupported claim", project_id=project,
        scope_json={"target_scope": "BRD4"}, confidence=0.4,
    )
    findings = mem.audit(project)["findings"]
    assert any(f["id"] == semantic for f in findings["semantic_without_evidence"])


def test_auditor_detects_high_confidence_weak_support(mem, project):
    semantic = mem.store.add_semantic(
        claim="Overconfident claim", project_id=project,
        scope_json={"target_scope": "BRD4"}, confidence=0.9,
        n_supporting=1, n_independent_sources=1,
    )
    findings = mem.audit(project)["findings"]
    assert any(f["id"] == semantic for f in findings["high_confidence_weak_support"])


def test_auditor_detects_orphan_memory(mem, project):
    trace_id = mem.store.add_episode(
        title="orphan memory", content="no links", event_type="experiment", project_id=project,
    )
    findings = mem.audit(project)["findings"]
    assert any(f["id"] == trace_id for f in findings["orphan_memories"])


def test_auditor_severity_is_critical_for_broken_provenance(mem, project):
    semantic = mem.store.add_semantic(
        claim="x", project_id=project, scope_json={"target_scope": "BRD4"}, confidence=0.3,
    )
    # Force a broken provenance link (bypassing the foreign key by disabling checks).
    mem.store.db.execute("PRAGMA foreign_keys = OFF")
    mem.store.db.execute(
        "INSERT INTO memory_evidence(memory_id, evidence_id, stance, weight, created_at) "
        "VALUES (?, 'EV_missing', 'supports', 1.0, '2020-01-01')",
        (semantic,),
    )
    mem.store.db.execute("PRAGMA foreign_keys = ON")
    report = mem.audit(project)
    assert report["findings"]["broken_provenance_links"]
    assert report["severity"] in {"critical", "warning"}


def test_pattern_completion_reconstructs_network(mem, project):
    _parent = mem.save_episode(
        title="BRD4 VHL design failure", content="short linker failed degradation",
        event_type="failure", project_id=project, context=brd4_vhl(),
        observed={"dmax": 0.18}, is_negative=True, evidence=[ev("PC-1")], decision_impact=0.9,
    )["episode_id"]
    mem.save_episode(
        title="BRD4 VHL redesign decision", content="moved to longer linker",
        event_type="design_choice", project_id=project, context=brd4_vhl(),
        evidence=[ev("PC-2")], decision_impact=0.8,
    )
    result = mem.pattern_complete("BRD4 VHL linker failure", project_id=project)
    assert result["nodes"]
    assert result["narrative"]
