"""P0-B — hidden fixture/default elimination tests.

Encodes the contract:

* three explicit execution modes (DEMO / TEST / SCIENTIFIC);
* six typed InputOrigins on every tool call;
* typed FailureCodes instead of silent fixture substitution;
* removing a required scientific input makes the tool *abstain*, not guess.
"""
from __future__ import annotations

import pytest

from protacxtend.agentic.contract import ToolResult, ToolStatus
from protacxtend.runtime import modes
from protacxtend.runtime.agent_tools import PROBE_FIXTURES, run_agent_tool

REAL_SMILES = "CC(=O)Oc1ccccc1C(=O)O"  # aspirin — a real molecule


@pytest.fixture(autouse=True)
def _clean_mode_env(monkeypatch):
    monkeypatch.delenv("PROTACXTEND_EXECUTION_MODE", raising=False)
    yield


# ── typed vocabulary ────────────────────────────────────────────────────────

def test_input_origin_has_exactly_the_six_required_values():
    assert {o.value for o in modes.InputOrigin} == {
        "USER", "RETRIEVED", "GENERATED", "COMPUTED", "FIXTURE", "SYNTHETIC"}


def test_failure_codes_include_the_four_required():
    values = {c.value for c in modes.FailureCode}
    for required in ("MISSING_SCIENTIFIC_INPUT", "STRUCTURE_UNAVAILABLE",
                     "NO_KNOWN_BINDER", "TOOL_UNAVAILABLE"):
        assert required in values


def test_exceptions_carry_typed_failure_codes():
    assert modes.MissingScientificInput("x").code is modes.FailureCode.MISSING_SCIENTIFIC_INPUT
    assert modes.SyntheticInputNotAllowed("x").code is modes.FailureCode.SYNTHETIC_INPUT_FORBIDDEN
    assert modes.FixtureUsageError("x").code is modes.FailureCode.FIXTURE_FORBIDDEN
    failure = modes.MissingScientificInput("missing smiles", ).to_failure("ctx")
    assert failure["status"] == "failed"
    assert failure["failure_code"] == "MISSING_SCIENTIFIC_INPUT"
    assert failure["evidence_kind"] == "missing"


# ── origin classification ───────────────────────────────────────────────────

def test_classify_origin_user_vs_fixture_vs_synthetic():
    probe = {"smiles": REAL_SMILES}
    assert modes.classify_input_origin({"smiles": REAL_SMILES}, fixture=probe) == \
        {"smiles": "FIXTURE"}
    assert modes.classify_input_origin({"smiles": "c1ccccc1"}, fixture=probe) == \
        {"smiles": "USER"}
    assert modes.classify_input_origin({"smiles": "CCO"}, fixture=probe) == \
        {"smiles": "SYNTHETIC"}
    assert modes.classify_input_origin(
        {"identifier": "outputs/stepwise_module_smoke/synthetic_ternary_pose.pdb"}) == \
        {"identifier": "SYNTHETIC"}


def test_classify_origin_respects_declared_retrieved():
    origins = modes.classify_input_origin(
        {"smiles": REAL_SMILES}, declared={"smiles": "RETRIEVED"})
    assert origins == {"smiles": "RETRIEVED"}
    assert modes.dominant_input_origin(origins) == "RETRIEVED"


def test_dominant_origin_precedence():
    assert modes.dominant_input_origin({"a": "USER", "b": "SYNTHETIC"}) == "SYNTHETIC"
    assert modes.dominant_input_origin({"a": "USER", "b": "FIXTURE"}) == "FIXTURE"
    assert modes.dominant_input_origin({"a": "USER"}) == "USER"


# ── run_agent_tool records origin ───────────────────────────────────────────

def test_demo_fixture_call_records_fixture_origin():
    run = run_agent_tool("inspect_smiles")  # demo default -> probe fixture
    assert run["used_fixture"] is True
    assert run["input_origin"] == "FIXTURE"
    assert run["input_origins"]["smiles"] == "FIXTURE"


def test_real_input_records_user_origin():
    run = run_agent_tool("inspect_smiles", {"smiles": REAL_SMILES})
    assert run["input_origin"] == "USER"
    assert run["failure_code"] == ""


def test_placeholder_in_demo_is_labelled_synthetic_not_silent():
    run = run_agent_tool("inspect_smiles", {"smiles": "CCO"})
    assert run["input_origins"]["smiles"] == "SYNTHETIC"
    assert run["input_origin"] == "SYNTHETIC"


def test_unknown_tool_returns_tool_unavailable_code():
    run = run_agent_tool("definitely_not_a_tool", {})
    assert run["failure_code"] == "TOOL_UNAVAILABLE"
    assert run["RESOLVED"] is False


# ── scientific mode abstains instead of substituting ────────────────────────

@pytest.mark.parametrize("tool", [
    "inspect_smiles", "predict_degradation", "predict_admet", "predict_cell_context",
    "detect_exit_vectors", "check_synthetic_feasibility", "retrieve_pdb",
    "model_ternary_complex", "resolve_target", "retrieve_e3_evidence",
    "simulate_hook_effect",
])
def test_scientific_mode_abstains_when_required_input_removed(tool):
    with modes.execution_mode("scientific"):
        with pytest.raises(modes.MissingScientificInput) as exc:
            run_agent_tool(tool, {})
    assert exc.value.code is modes.FailureCode.MISSING_SCIENTIFIC_INPUT


def test_scientific_mode_rejects_hidden_default_e3_and_cell_line():
    """predict_degradation must not fall back to CRBN/default in SCIENTIFIC."""
    with modes.execution_mode("scientific"):
        with pytest.raises(modes.MissingScientificInput) as exc:
            run_agent_tool("predict_degradation", {"smiles": REAL_SMILES})
    assert "e3" in str(exc.value) and "cell_line" in str(exc.value)


def test_scientific_mode_rejects_probe_fixture_request():
    with modes.execution_mode("scientific"):
        with pytest.raises(modes.FixtureUsageError) as exc:
            run_agent_tool("inspect_smiles", {}, use_fixture=True)
    assert exc.value.code is modes.FailureCode.FIXTURE_FORBIDDEN


def test_scientific_mode_rejects_placeholder_and_synthetic_structure():
    with modes.execution_mode("scientific"):
        with pytest.raises(modes.SyntheticInputNotAllowed):
            run_agent_tool("inspect_smiles", {"smiles": "CCO"})
        with pytest.raises(modes.SyntheticInputNotAllowed):
            run_agent_tool("score_lysine_ubiquitination", {
                "target": "BRD4", "e3": "CRBN",
                "structure_paths": ["outputs/stepwise_module_smoke/synthetic_ternary_pose.pdb"]})


def test_scientific_mode_executes_only_with_real_complete_input():
    with modes.execution_mode("scientific"):
        run = run_agent_tool("inspect_smiles", {"smiles": REAL_SMILES})
    assert run["executed"] if "executed" in run else run["EXECUTED"]
    assert run["input_origin"] == "USER"
    assert run["used_fixture"] is False


# ── workflow node: E3 default elimination ───────────────────────────────────

def test_real_nodes_e3_abstains_in_scientific_instead_of_defaulting_to_crbn():
    from protacxtend.agents.real_nodes import _e3

    with modes.execution_mode("scientific"):
        out = _e3({"parsed_objective": {"e3": "ZZZNOTANE3"}, "user_request": ""})
    assert out["selected_e3_ligands"] == []
    assert out["failure_code"] == "E3_LIGAND_UNAVAILABLE"
    assert "parsed_objective" not in out  # no silent CRBN rewrite


def test_real_nodes_e3_demo_still_labels_the_fallback():
    from protacxtend.agents.real_nodes import _e3

    out = _e3({"parsed_objective": {"e3": "ZZZNOTANE3"}, "user_request": ""})
    assert out.get("input_origin") == "FIXTURE"
    assert out["parsed_objective"]["e3"] == "CRBN"


# ── no fabricated scores ────────────────────────────────────────────────────

def test_linker_generator_no_longer_uses_constant_fabricated_score():
    from protacxtend.tools.linker_generator import generate_linkers_for_pair

    linkers = generate_linkers_for_pair(max_linkers=6)
    if not linkers:
        pytest.skip("no linkers generated")
    scores = {round(l.synthetic_feasibility_proxy, 3) for l in linkers}
    assert not (scores == {0.55}), "synthetic feasibility is still a hard-coded constant"
    for l in linkers:
        assert 0.0 <= l.synthetic_feasibility_proxy <= 1.0
        # the fragment-combination path must cite its real estimator
        if l.provenance.get("generation_method") == "fragment_combination":
            assert l.provenance.get("synthetic_feasibility_source") == \
                "linker_scanner.score_synthesis"


# ── fixture inventory is explicit ───────────────────────────────────────────

def test_probe_fixtures_are_demo_only_and_never_used_in_scientific():
    """The DEMO fixture table may contain placeholders, but SCIENTIFIC mode
    forbids every fixture, so they can never reach a scientific run."""
    assert PROBE_FIXTURES, "fixtures should be explicit, not hidden"
    with modes.execution_mode("scientific"):
        for tool in PROBE_FIXTURES:
            with pytest.raises((modes.FixtureUsageError, modes.MissingScientificInput,
                                modes.SyntheticInputNotAllowed)):
                run_agent_tool(tool, {}, use_fixture=True)
