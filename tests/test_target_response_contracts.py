"""Shared target-resolution and response-completeness contracts."""

from __future__ import annotations

import os
import uuid

os.environ["PROTACXTEND_PLANNER_OFFLINE"] = "1"

from protacxtend.tui.engine import execute_command


def _run(cmd: str, args: str, cid: str | None = None, **extra):
    return execute_command(cmd, args, offline=True,
                           conversation_id=cid or f"contract-{uuid.uuid4().hex[:8]}",
                           extra=extra or None)


def test_hmgb2_recognized_target_gets_evidence_bounded_plan_not_clarification(monkeypatch, tmp_path):
    from protacxtend.planning import contract as planning_contract
    monkeypatch.setattr(planning_contract, "PLAN_ROOT", tmp_path)

    out = _run("plan", "HMGB2 protac", "hmgb2-recognized")
    answer = out["answer"]

    assert answer["type"] == "plan_answer"
    assert answer["kind"] != "clarification_needed"
    assert answer["target"]["symbol"] == "HMGB2"
    assert answer["request_completed"] is True
    assert answer["plan_generated"] is True
    assert answer["scientific_answer_supported"] is True
    assert any("binder" in q.lower() or "precedent" in q.lower() for q in answer["open_questions"])


def test_unknown_target_gets_specific_clarification_not_plan(monkeypatch, tmp_path):
    from protacxtend.planning import contract as planning_contract
    monkeypatch.setattr(planning_contract, "PLAN_ROOT", tmp_path)

    out = _run("plan", "ZZZZ9 protac", "unknown-specific")
    answer = out["answer"]

    assert answer["kind"] == "clarification_needed"
    assert answer["request_completed"] is True
    assert answer["plan_generated"] is False
    assert answer["scientific_answer_supported"] is False
    assert "exact" in answer["question"].lower()
    assert "ZZZZ9" in answer["question"]


def test_resource_retrieval_timeout_is_typed_and_preserves_partial_plan(monkeypatch, tmp_path):
    from protacxtend.planning import contract as planning_contract
    monkeypatch.setattr(planning_contract, "PLAN_ROOT", tmp_path)
    monkeypatch.setenv("PROTACXTEND_PLAN_RESOURCE_TIMEOUT_S", "0.01")

    def slow_resource(text, *, offline=True):
        import time
        time.sleep(0.25)
        return {"schema_version": "late", "selected": [{"name": "late"}]}

    monkeypatch.setattr(planning_contract, "_resource_reason_summary_for", slow_resource)

    out = _run("plan", "EGFR protac", "slow-resource")
    answer = out["answer"]
    timeout_events = [e for e in out["events"] if e.get("stage") == "resource_retrieval" and e.get("status") == "timeout"]

    assert timeout_events
    assert answer["plan_generated"] is True
    assert answer["resource_reason_summary"]["status"] == "partial_timeout"
    assert answer["resource_reason_summary"]["late_results_can_overwrite"] is False


def test_reason_tui_payload_has_no_h_question_placeholders():
    out = _run("reason", "EGFR binding strong but no degradation", "reason-placeholders")
    answer = out["answer"]

    assert answer["type"] == "diagnosis_answer"
    assert answer["request_completed"] is True
    assert answer["scientific_answer_supported"] is True
    assert answer["hypotheses"]
    for h in answer["hypotheses"]:
        assert h.get("hypothesis_id")
        assert h.get("label") and h["label"] != "?"
        assert h.get("axis")
        assert h.get("evidence_for")
        assert h.get("evidence_against")


def test_investigate_hmgb2_returns_substantive_fields_not_empty_success():
    out = _run("investigate", "HMGB2 protac", "investigate-hmgb2")
    answer = out["answer"]

    assert answer["type"] == "research_answer"
    assert answer["request_completed"] is True
    assert answer["scientific_answer_supported"] is True
    findings = answer["findings"]
    assert findings["target"] == "HMGB2"
    assert findings["uniprot"]
    assert "evidence_gaps" in findings
    assert findings["interpretation"]
