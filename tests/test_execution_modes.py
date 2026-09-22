"""Execution-mode guardrail tests (DEMO / TEST / SCIENTIFIC).

These encode the P0 contract:

* fixtures, placeholder SMILES and synthetic structures are allowed only in
  DEMO/TEST;
* SCIENTIFIC mode fails closed with explicit exceptions
  (:class:`FixtureUsageError`, :class:`SyntheticInputNotAllowed`,
  :class:`MissingScientificInput`);
* the benchmark runner cannot replay a fixture in SCIENTIFIC mode.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmark_runner.runner import BenchmarkRunner, RunConfig, TaskInput
from protacxtend.agents.warhead_agent import WarheadSelectionAgent
from protacxtend.backend.schemas import ParsedObjective, WorkflowState
from protacxtend.runtime import modes
from protacxtend.runtime.agent_tools import run_agent_tool
from protacxtend.runtime.executor import AGENT_TOOL_RUNNERS, run_capability

BENCH = Path(__file__).resolve().parents[1] / "benchmark"
REAL_SMILES = "CC(=O)Oc1ccccc1C(=O)O"  # aspirin - a real molecule, not a placeholder


@pytest.fixture(autouse=True)
def _clean_mode_env(monkeypatch):
    monkeypatch.delenv("PROTACXTEND_EXECUTION_MODE", raising=False)
    yield


def _dev_task(task_id: str = "DEV-1") -> TaskInput:
    return TaskInput(
        task_id=task_id, capability="KNOW", difficulty="easy", title="dev",
        question="dev question", supplied_inputs=["dev input"], hidden_information=[],
        permitted_tools=[], forbidden=[], contamination_risk="low",
        data_cutoff_date="2026-08-31", systems=["DEV"],
        raw={"fixture_kind": "perfect", "fixture_name": "DEV-perfect"},
    )


# ── mode machinery ────────────────────────────────────────────────────

def test_exception_hierarchy_is_explicit():
    for exc in (modes.FixtureUsageError, modes.SyntheticInputNotAllowed,
                modes.MissingScientificInput):
        assert issubclass(exc, modes.ScientificInputError)
        assert issubclass(exc, RuntimeError)


def test_parse_mode_accepts_names_and_values():
    assert modes.parse_mode("scientific") is modes.ExecutionMode.SCIENTIFIC
    assert modes.parse_mode("SCIENTIFIC") is modes.ExecutionMode.SCIENTIFIC
    assert modes.parse_mode("demo") is modes.ExecutionMode.DEMO
    with pytest.raises(ValueError):
        modes.parse_mode("production")


def test_execution_mode_context_scoping():
    assert modes.get_execution_mode() is modes.ExecutionMode.DEMO
    with modes.execution_mode("scientific"):
        assert modes.is_scientific() is True
    assert modes.is_scientific() is False


def test_env_default_mode(monkeypatch):
    monkeypatch.setenv("PROTACXTEND_EXECUTION_MODE", "scientific")
    assert modes.get_execution_mode() is modes.ExecutionMode.SCIENTIFIC


# ── agent tool enforcement ────────────────────────────────────────────

def test_demo_mode_allows_probe_fixture():
    run = run_agent_tool("inspect_smiles")
    assert run["execution_mode"] == "demo"
    assert run["used_fixture"] is True


def test_scientific_mode_rejects_explicit_fixture():
    with modes.execution_mode("scientific"):
        with pytest.raises(modes.FixtureUsageError):
            run_agent_tool("inspect_smiles", {}, use_fixture=True)


def test_scientific_mode_rejects_missing_input():
    with modes.execution_mode("scientific"):
        with pytest.raises(modes.MissingScientificInput):
            run_agent_tool("inspect_smiles", {})


def test_scientific_mode_rejects_placeholder_smiles():
    with modes.execution_mode("scientific"):
        with pytest.raises(modes.SyntheticInputNotAllowed):
            run_agent_tool("inspect_smiles", {"smiles": "CCO"})


def test_scientific_mode_rejects_synthetic_pose_path():
    with modes.execution_mode("scientific"):
        with pytest.raises(modes.SyntheticInputNotAllowed):
            run_agent_tool(
                "score_lysine_ubiquitination",
                {"target": "BRD4", "e3": "CRBN",
                 "structure_paths": ["outputs/stepwise_module_smoke/synthetic_ternary_pose.pdb"]},
            )


def test_scientific_mode_rejects_nested_placeholder_params():
    with modes.execution_mode("scientific"):
        with pytest.raises(modes.SyntheticInputNotAllowed):
            run_agent_tool(
                "run_scientific_capability",
                {"capability": "chemistry", "params": {"smiles": "CCO"}},
            )


def test_scientific_mode_executes_with_real_input():
    with modes.execution_mode("scientific"):
        run = run_agent_tool("inspect_smiles", {"smiles": REAL_SMILES})
    assert run["execution_mode"] == "scientific"
    assert run["used_fixture"] is False
    assert run["status"] == "ok"


def test_fixture_default_table_is_empty():
    assert AGENT_TOOL_RUNNERS == {}


# ── direct registry executor enforcement ──────────────────────────────

def test_registry_execute_tool_fails_closed_in_scientific():
    from protacxtend.agentic.registry import execute_tool

    with modes.execution_mode("scientific"):
        with pytest.raises(modes.MissingScientificInput):
            execute_tool("inspect_smiles", {})


def test_capability_runner_fails_closed_in_scientific():
    with modes.execution_mode("scientific"):
        with pytest.raises(modes.MissingScientificInput):
            run_capability("chemistry", {"operation": "descriptors"})


# ── warhead demo fallback ─────────────────────────────────────────────

def _warhead_state(target: str) -> WorkflowState:
    state = WorkflowState(user_request=f"degrade {target}")
    state.parsed_objective = ParsedObjective(target_name=target)
    return state


def test_scientific_mode_forbids_demo_warheads():
    with modes.execution_mode("scientific"):
        state = WarheadSelectionAgent().run(_warhead_state("ZZZNOTAGENE"))
    assert any("No warheads selected" in error for error in state.errors)
    assert state.selected_warheads == []


def test_demo_mode_still_allows_demo_warheads():
    state = WarheadSelectionAgent().run(_warhead_state("ZZZNOTAGENE"))
    assert state.selected_warheads  # curated demo fallback in DEMO mode


# ── benchmark runner ──────────────────────────────────────────────────

def test_benchmark_runner_refuses_fixture_in_scientific_mode():
    runner = BenchmarkRunner(RunConfig(system_id="DEV"), BENCH, check_freeze=False)
    with pytest.raises(modes.FixtureUsageError):
        runner.run(_dev_task())


def test_benchmark_runner_default_mode_is_scientific():
    assert RunConfig().mode is modes.ExecutionMode.SCIENTIFIC


def test_benchmark_runner_allows_fixture_only_in_test_mode():
    runner = BenchmarkRunner(
        RunConfig(system_id="DEV", mode=modes.ExecutionMode.TEST),
        BENCH, check_freeze=False,
    )
    env = runner.run(_dev_task())
    assert env["status"] == "ok"
    assert env["metadata"]["execution_mode"] == "test"
