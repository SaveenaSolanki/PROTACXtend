"""System-wide planning contract tests for the real TUI bridge."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pytest

os.environ["PROTACXTEND_PLANNER_OFFLINE"] = "1"

from protacxtend.planning import contract as planning_contract
from protacxtend.tui.engine import execute_command


def _plan_events(target: str, cid: str | None = None, **extra):
    return execute_command(
        "plan",
        f"{target} protac",
        offline=True,
        conversation_id=cid or f"plan-contract-{uuid.uuid4().hex[:8]}",
        extra=extra,
    )


def test_real_tui_plan_contract_hmgb2_persists_stage_statuses(tmp_path, monkeypatch):
    monkeypatch.setattr(planning_contract, "PLAN_ROOT", tmp_path)

    out = _plan_events("HMGB2", "hmgb2-contract")
    events = out["events"]
    answer = out["answer"]

    assert events[0]["type"] == "plan_start"
    run_id = events[0]["run_id"]
    request_id = events[0]["request_id"]
    assert run_id and request_id
    assert answer and answer["type"] == "plan_answer"
    assert answer["run_id"] == run_id
    assert answer["request_id"] == request_id
    assert answer["planning_mode"] in {"deterministic", "deterministic_fallback"}
    assert answer["llm_completed"] is False

    progress = [e for e in events if e.get("type") == "progress"]
    stage_names = [e.get("stage") for e in progress]
    for stage in ["target_resolution", "resource_retrieval", "planner", "response_serialization", "persistence"]:
        assert stage in stage_names
    assert all(e.get("run_id") == run_id for e in progress)
    assert all(e.get("request_id") == request_id for e in progress)

    paths = answer["artifact_paths"]
    assert Path(paths["plan_json"]).exists()
    assert Path(paths["status_json"]).exists()
    assert Path(paths["timeline_json"]).exists()
    status = json.loads(Path(paths["status_json"]).read_text())
    assert status["status"] in {"ready", "clarification_needed"}
    assert status["run_id"] == run_id


def test_retry_reuses_existing_plan_run_without_duplicate_work(tmp_path, monkeypatch):
    monkeypatch.setattr(planning_contract, "PLAN_ROOT", tmp_path)

    calls = {"n": 0}
    real_build_plan = planning_contract.build_plan

    def counted(*args, **kwargs):
        calls["n"] += 1
        return real_build_plan(*args, **kwargs)

    monkeypatch.setattr(planning_contract, "build_plan", counted)

    first = _plan_events("EGFR", "retry-contract")
    second = _plan_events("EGFR", "retry-contract")

    assert calls["n"] == 1
    assert first["answer"]["run_id"] == second["answer"]["run_id"]
    assert second["answer"]["cache_hit"] is True
    assert any(e.get("stage") == "dedupe" and e.get("status") == "cache_hit" for e in second["events"])


def test_llm_timeout_returns_typed_stage_and_labeled_deterministic_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(planning_contract, "PLAN_ROOT", tmp_path)
    monkeypatch.setenv("PROTACXTEND_PLAN_LLM_TIMEOUT_S", "0.05")

    def slow_llm(**kwargs):
        time.sleep(0.3)
        return {"status": "plan_ready", "llm_completed": True}

    monkeypatch.setattr(planning_contract, "llm_plan", slow_llm)

    out = _plan_events("BRD4", "slow-llm-contract", use_llm_planner=True)
    answer = out["answer"]
    assert answer["planning_mode"] == "deterministic_fallback"
    assert answer["llm_completed"] is False
    timeout_events = [e for e in out["events"] if e.get("status") == "timeout"]
    assert timeout_events
    assert timeout_events[-1]["stage"] == "llm_planning"
    assert answer["typed_failure"]["stage"] == "llm_planning"
    assert answer["typed_failure"]["error_type"] == "timeout"
    assert answer["typed_failure"]["backend_continues_after_timeout"] is True


def test_unavailable_planning_backend_reports_typed_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(planning_contract, "PLAN_ROOT", tmp_path)

    def unavailable(*args, **kwargs):
        raise planning_contract.PlanningBackendUnavailable("planner backend unavailable")

    monkeypatch.setattr(planning_contract, "build_plan", unavailable)

    out = _plan_events("KRAS", "unavailable-contract")
    answer = out["answer"]
    assert answer["kind"] == "failed"
    assert answer["status"] == "failed"
    assert answer["typed_failure"]["stage"] == "planner"
    assert answer["typed_failure"]["error_type"] == "backend_unavailable"
    assert answer["final"] is True


@pytest.mark.parametrize("target", ["HMGB2", "EGFR", "KRAS"])
def test_real_bridge_plan_contract_multiple_targets(tmp_path, monkeypatch, target):
    monkeypatch.setattr(planning_contract, "PLAN_ROOT", tmp_path)

    out = _plan_events(target)
    answer = out["answer"]
    assert answer and answer["type"] == "plan_answer"
    assert answer["run_id"]
    assert answer["stage_timeline"]
    assert answer["backend_health"]
    assert answer.get("executed_design") is False


def test_workflows_api_plan_uses_same_persisted_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(planning_contract, "PLAN_ROOT", tmp_path)

    from protacxtend.workflows.api import run_command

    payload = run_command("plan", "/plan HMGB2 protac", offline=True)
    assert payload["type"] == "plan_answer"
    assert payload["run_id"]
    assert payload["request_id"]
    assert payload["artifact_paths"]
    assert Path(payload["artifact_paths"]["plan_json"]).exists()
    assert payload["executed_design"] is False
