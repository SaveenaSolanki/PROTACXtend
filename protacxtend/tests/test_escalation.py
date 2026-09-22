"""Tests for the failure-escalation subsystem."""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def isolated_ledgers(tmp_path, monkeypatch):
    """Point every ledger at a temp dir and reset the cached singleton."""
    monkeypatch.setenv("PROTACXTEND_ESCALATION_DIR", str(tmp_path))
    import protacxtend.escalation.ledger as ledger_mod

    monkeypatch.setattr(ledger_mod, "_LEDGERS", None)
    yield ledger_mod.get_ledgers()
    monkeypatch.setattr(ledger_mod, "_LEDGERS", None)


def test_capability_mapping():
    from protacxtend.escalation import capability_for

    assert capability_for("protacxtend.tools.docking_pipeline") == "ligand_docking"
    assert capability_for("docking_pipeline") == "ligand_docking"
    assert capability_for("ligand_docking") == "ligand_docking"
    assert capability_for("protacxtend.tools.synglue_degradation") == "degradation_prediction"


def test_diagnosis_import_error():
    from protacxtend.escalation import diagnose

    diag = diagnose(ImportError("No module named 'vina'"), internal_tool="docking_pipeline")
    assert diag.failure_class == "MISSING_DEPENDENCY"
    assert diag.recommend_external is True
    assert "Install" in diag.recovery_hint or "install" in diag.recovery_hint


def test_diagnosis_timeout_and_network():
    from protacxtend.escalation import diagnose

    assert diagnose(TimeoutError("timed out")).failure_class == "TOOL_TIMEOUT"
    assert diagnose(ConnectionError("Connection refused")).failure_class == "NETWORK_UNAVAILABLE"


def test_resolve_candidates_installed_first():
    from protacxtend.escalation import resolve_candidates

    candidates = resolve_candidates("ligand_docking")
    assert candidates, "expected at least one docking candidate"
    installed = [c for c in candidates if c.installed]
    if installed:
        assert candidates[0].installed, "installed candidates must rank first"


def test_run_with_escalation_internal_success(isolated_ledgers):
    from protacxtend.escalation import run_with_escalation

    out = run_with_escalation(
        "cheminformatics", "protacxtend.tools.rdkit_chemistry", lambda: 42
    )
    assert out["ok"] is True
    assert out["resolved_by"] == "internal"
    assert out["value"] == 42
    assert isolated_ledgers.failures.read_all() == []


def test_run_with_escalation_failure_is_recorded(isolated_ledgers):
    from protacxtend.escalation import run_with_escalation

    def broken():
        raise ImportError("No module named 'vina'")

    out = run_with_escalation(
        "ligand_docking", "protacxtend.tools.docking_pipeline", broken, mode="check"
    )
    failures = isolated_ledgers.failures.read_all()
    assert len(failures) == 1
    assert failures[0]["capability"] == "ligand_docking"
    assert failures[0]["failure_class"] == "MISSING_DEPENDENCY"
    assert out["escalation"] is not None
    # audit event must always be written
    audits = isolated_ledgers.audits.read_all()
    assert audits and audits[0]["event"] == "escalation"


def test_escalation_registers_installed_candidate(isolated_ledgers):
    from protacxtend.escalation import capability_readiness, run_with_escalation
    from protacxtend.escalation.registry import DynamicToolRegistry

    # cheminformatics has RDKit installed in the test environment
    ready = {r["capability"]: r for r in capability_readiness()}
    if not ready["cheminformatics"]["installed"]:
        pytest.skip("no installed cheminformatics fallback in this environment")

    def broken():
        raise ImportError("simulated failure")

    out = run_with_escalation(
        "cheminformatics", "protacxtend.tools.chemistry_core", broken
    )
    assert out["resolved_by"] in {"external", "external_registered", "external_candidate_only"}
    reg = DynamicToolRegistry(ledgers=isolated_ledgers)
    assert reg.list(), "expected a dynamic registration for the chosen tool"
    assert isolated_ledgers.registrations.read_all()


def test_dynamic_registry_roundtrip(tmp_path, isolated_ledgers):
    from protacxtend.escalation.registry import DynamicToolRegistry

    reg = DynamicToolRegistry(path=tmp_path / "dyn.json", ledgers=isolated_ledgers)
    reg.register("OpenBabel", capabilities=["cheminformatics"], version="3.1.1")
    assert reg.is_registered("OpenBabel")
    assert reg.find_by_capability("cheminformatics")
    candidates = reg.as_candidates()
    assert candidates and candidates[0].tool_name == "OpenBabel"
    assert reg.unregister("OpenBabel")
    assert not reg.is_registered("OpenBabel")


def test_dynamic_registry_candidates_rank_first(isolated_ledgers):
    from protacxtend.escalation import resolve_candidates
    from protacxtend.escalation.registry import DynamicToolRegistry

    reg = DynamicToolRegistry(ledgers=isolated_ledgers)
    reg.register("OpenBabel", capabilities=["cheminformatics"], version="3.1.1")
    candidates = resolve_candidates("cheminformatics")
    assert candidates and candidates[0].tool_name == "OpenBabel"
    assert candidates[0].installed


def test_report_builds(isolated_ledgers):
    from protacxtend.escalation import build_escalation_report, render_markdown

    report = build_escalation_report()
    assert "capability_readiness" in report
    assert report["counts"]["failures"] == 0
    md = render_markdown(report)
    assert "Capability coverage" in md


def test_agentic_execute_tool_escalates_on_error(isolated_ledgers, monkeypatch):
    import protacxtend.agentic.registry as reg

    def boom(params):
        raise ImportError("No module named 'vina'")

    monkeypatch.setitem(reg._EXECUTORS, "inspect_smiles", boom)
    result = reg.execute_tool("inspect_smiles", {"smiles": "CCO"})
    assert result.status.value == "error"
    assert "escalation" in result.data
    assert result.data["escalation"]["failure"]["failure_class"] == "MISSING_DEPENDENCY"
    assert isolated_ledgers.failures.read_all()


def test_orchestrator_to_tool_result(isolated_ledgers):
    from protacxtend.agentic.contract import ToolResult
    from protacxtend.escalation import escalate_failure, to_tool_result

    try:
        raise ImportError("No module named 'vina'")
    except ImportError as exc:
        result = escalate_failure(
            "ligand_docking", "docking_pipeline", exc, inputs={"smiles": "CCO"}
        )
    tool_result = to_tool_result(result)
    assert isinstance(tool_result, ToolResult)
    assert tool_result.tool
    assert "escalation" in tool_result.data
