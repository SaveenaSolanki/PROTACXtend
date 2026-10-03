"""Priority integrity gates: input parsing, canonical routing, and scientific-mode cleanliness.

These tests cover the public contracts requested for the next hardening step:
blind/ambiguous inputs fail safely, design commands use one canonical runtime
path, and SCIENTIFIC mode cannot emit placeholder/demo/fixture payloads.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from protacxtend.planning.planner import plan_request, reset_session
from protacxtend.runtime import modes
from protacxtend.workflows.api import run_command


@pytest.mark.parametrize(
    "case_id, text, expected_symbol, expected_status",
    [
        ("blind_hmgb2", "/plan HMGB2 protac", "HMGB2", "resolved"),
        ("blind_ar_alias", "/plan androgen receptor degrader", "AR", "verified"),
        ("blind_egfr_alias", "/plan HER1 protac", "EGFR", "verified"),
    ],
)
def test_input_integrity_blind_resolved_cases(case_id, text, expected_symbol, expected_status):
    reset_session(case_id)
    result = plan_request(text, conversation_id=case_id, offline=True)
    assert result.status in {"plan_ready", "plan_with_limitation"}
    assert result.target.symbol == expected_symbol
    assert result.target.status in {expected_status, "verified", "resolved", "tentative"}
    assert result.clarification_question is None


@pytest.mark.parametrize(
    "case_id, text, expected_candidates",
    [
        ("amb_brd", "/plan BRD protac", ["BRD2", "BRD3", "BRD4"]),
        ("amb_jak", "/plan JAK degrader", ["JAK1", "JAK2", "JAK3"]),
        ("amb_egfr1", "/plan EGFR1 protac", ["EGFR", "ERBB3"]),
    ],
)
def test_input_integrity_ambiguous_inputs_fail_safely(case_id, text, expected_candidates):
    reset_session(case_id)
    result = plan_request(text, conversation_id=case_id, offline=True)
    assert result.status == "clarification_needed"
    assert result.target.status == "ambiguous"
    for candidate in expected_candidates:
        assert candidate in result.clarification_question


def test_input_integrity_unknown_input_needs_specific_symbol():
    reset_session("unknown_blind")
    result = plan_request("/plan ZZZZ9 degrader", conversation_id="unknown_blind", offline=True)
    assert result.status == "clarification_needed"
    assert "could not be resolved" in result.clarification_question
    assert "exact" in result.clarification_question.lower()


def test_canonical_core_design_route_uses_workflows_api_and_runtime(monkeypatch):
    calls: list[tuple[str, str, dict]] = []

    def fake_run_protacpilot(request, mode="deterministic", config=None):
        calls.append((request, mode, dict(config or {})))

        class State:
            stage_ledger = []
            target_record = None
            retrieved_binders = []
            selected_warheads = []
            selected_e3_ligands = []
            generated_linkers = []
            assembled_candidates = []
            valid_candidates = []
            degradation_predictions = []
            admet_predictions = []
            ranking_results = []
            final_ranked_candidates = []
            exit_vectors = []

        return {"status": "abstained", "run_id": (config or {}).get("run_id", "fake"), "mode": mode, "state": State(), "artifacts": {}}

    monkeypatch.setattr("protacxtend.agents.runtime.run_protacpilot", fake_run_protacpilot)
    payload = run_command("run", "run Design a CRBN-recruiting PROTAC for BRD4", offline=True)
    assert payload["engine"] == "run_protacpilot"
    assert payload["mode"] == "deterministic"
    assert payload["executed_design"] is True
    assert len(calls) == 1
    request, mode, config = calls[0]
    assert "BRD4" in request
    assert mode == "deterministic"
    assert config["capability"] == "DESIGN"
    assert config["record_run"] is True


def test_canonical_core_no_tui_side_design_implementation():
    server_src = Path("protacxtend/tui_bridge/server.py").read_text()
    designer_src = Path("protacxtend/workflows/designer.py").read_text()
    api_src = Path("protacxtend/workflows/api.py").read_text()
    assert "workflows.api import run_command" in server_src
    assert "run_protacpilot" in designer_src
    assert "from protacxtend.workflows.designer import run_design" in api_src
    assert "construct_protac" not in server_src


def test_scientific_payload_scan_flags_placeholder_smiles_and_fixture_sources():
    payload = {
        "candidate_evidence_table": [
            {"candidate_id": "bad1", "canonical_smiles": "CCO", "provenance": {"source": "local_demo_warhead"}},
        ],
        "artifacts": {"pose_path": "outputs/stepwise_module_smoke/synthetic_ternary_pose.pdb"},
    }
    findings = modes.scan_scientific_payload(payload)
    reasons = {f["reason"] for f in findings}
    assert {"placeholder_smiles", "demo_or_fixture_source", "synthetic_or_fixture_path"} <= reasons
    with pytest.raises(modes.SyntheticInputNotAllowed):
        modes.assert_scientific_payload_clean("unit-test", payload)


def test_scientific_payload_scan_does_not_flag_exclusion_language():
    payload = {
        "scientific_findings": ["demo rows excluded from scientific mode"],
        "candidate_evidence_table": [{"canonical_smiles": "CC(=O)Oc1ccccc1C(=O)O", "provenance": {"source": "doi:10.1000/example"}}],
    }
    assert modes.scan_scientific_payload(payload) == []


def test_scientific_design_summary_fails_closed_on_leaked_fixture(monkeypatch):
    from protacxtend.workflows import designer

    class State:
        stage_ledger = []
        target_record = None
        retrieved_binders = []
        selected_warheads = []
        selected_e3_ligands = []
        generated_linkers = []
        assembled_candidates = [{"candidate_id": "bad1"}]
        valid_candidates = [{
            "candidate_id": "bad1",
            "full_protac_smiles": "CCO",
            "canonical_smiles": "CCO",
            "provenance": {"source": "local_demo_warhead", "identity_assembly_gate": {"all_required_passed": True}},
        }]
        degradation_predictions = []
        admet_predictions = []
        ranking_results = []
        final_ranked_candidates = []
        exit_vectors = []

    with modes.execution_mode("scientific"):
        with pytest.raises(modes.SyntheticInputNotAllowed):
            designer.summarize_design_result({"status": "ok", "run_id": "integrity_fixture", "state": State()}, request="Design fixture")
