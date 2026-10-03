"""Workflow-contract tests: overlap, fabricated evidence, degradation labels,
plan diversity, and run replanning. These exercise the 14-command mechanistic
workflows (kept separate from the request-understanding bucket)."""

import os

import pytest

from protacxtend.workflows.contracts import CONTRACTS, build_goal_plan, classify_goal, ensure_distinct
from protacxtend.workflows.api import run_command
from protacxtend.evidence.graph import DIMENSIONS, EvidenceGraph, make_claim
from protacxtend.request.controller import RequestController


# ------------------------------------------------------------------ overlap
def test_fourteen_distinct_contracts():
    assert len(CONTRACTS) == 14
    ensure_distinct()  # raises if any two commands share question/output schema


def test_no_command_shares_anothers_scientific_question():
    q = [c.scientific_question for c in CONTRACTS.values()]
    assert len(q) == len(set(q))


# ------------------------------------------------------------------ plan diversity
def _plan_for(text):
    u = RequestController(offline=True).understand(text, default_action="plan")
    return build_goal_plan(u)


def test_plans_differ_across_biologically_different_requests():
    p1 = _plan_for("/plan EGFR protac")
    p2 = _plan_for("/plan KRAS G12C protac")
    assert p1.signature != p2.signature
    n1 = {n.node_id for n in p1.nodes}; n2 = {n.node_id for n in p2.nodes}
    assert n1 != n2, "plans are identical — still a template"
    assert {"mutation_context", "allele_specific_binder_search"} <= n2
    d1 = {n.node_id: tuple(n.depends_on) for n in p1.nodes}
    d2 = {n.node_id: tuple(n.depends_on) for n in p2.nodes}
    assert d1 != d2, "dependency maps identical — still a template"


def test_plans_not_template_across_goals_same_target():
    u = RequestController(offline=True).understand("BRD4 optimisation of permeability", default_action="optimize")
    p_opt = build_goal_plan(u)
    u2 = RequestController(offline=True).understand("/investigate BRD4", default_action="investigate")
    p_inv = build_goal_plan(u2)
    u3 = RequestController(offline=True).understand("/design BRD4 protac", default_action="design")
    p_des = build_goal_plan(u3)
    sigs = {p_opt.signature, p_inv.signature, p_des.signature}
    assert len(sigs) == 3, "optimize/investigate/design collapsed onto one plan"


def test_plan_does_not_execute_design():
    p = _plan_for("/plan EGFR protac")
    assert p.goal_type == "plan"
    assert not any(n.node_id in ("construction_validation",) for n in p.nodes)
    payload = run_command("plan", "/plan EGFR protac", offline=True)
    assert payload["status"] == "plan_ready"
    assert "no design path is executed" in payload.get("note", "")


# ------------------------------------------------------------------ evidence honesty
def test_fabricated_evidence_guard():
    g = EvidenceGraph()
    with pytest.raises(ValueError):
        g.add(make_claim(command="test", dimension="degradation", kind="computed", statement="no tool"))
    # valid claim with provenance passes
    g.add(make_claim(command="test", dimension="exposure", kind="computed",
                     statement="ok", tool="rdkit.descriptors"))


def test_ml_degradation_predictions_cannot_be_observed():
    g = EvidenceGraph()
    with pytest.raises(ValueError, match="ML predictions cannot be observed"):
        g.add(make_claim(command="test", dimension="degradation", kind="observed",
                         statement="ML predicted DC50", tool="degradation_model",
                         assay="ML prediction", source_ids=["10.1021/example"]))


def test_workflow_degradation_outputs_labeled_predicted():
    payload = run_command("degradation", "degrade smiles:CC(=O)Oc1ccccc1C(=O)O", offline=True)
    if payload["status"] == "ok":
        assert payload.get("label", "").startswith("computational prediction")
        assert "measured" not in payload.get("label", "").lower()


def test_reason_hypotheses_are_inferred_with_tests():
    payload = run_command("reason", "strong binding, no cellular degradation", offline=True,
                          smiles_arg="CC(=O)Oc1ccccc1C(=O)O")
    assert payload["status"] == "ok"
    for h in payload["hypotheses"]:
        assert h["axis"] in DIMENSIONS or h["axis"] in ("degradation_kinetics",)
        assert h["discriminating_tests"]
    assert payload["tests"]  # /experiment-style discriminating tests present


def test_experiment_includes_controls():
    payload = run_command("experiment", "experiment H1,H2", offline=True)
    assert payload["status"] == "ok"
    for t in payload["tests"]:
        assert t["controls"], "control mandatory"


# ------------------------------------------------------------------ run replanning / evidence gates
def test_run_design_is_evidence_gated():
    payload = run_command("run", "run Design a CRBN-recruiting PROTAC for BRD4", offline=True)
    assert payload["status"] in ("ok", "completed_with_replan", "abstained")
    ev = payload.get("evidence_gates", {})
    assert ev.get("non_protac_rejection", {}).get("status") == "passed"
    assert ev.get("degradation", {}).get("status") in ("predicted", "not_assessable")
    assert ev.get("ternary_coordinates", {}).get("status") == "unevaluated"
    assert ev.get("synthesis_route", {}).get("status") == "unevaluated"
    assert ev.get("nomination", {}).get("status") == "gated"
    asserted = payload.get("unevaluated_stages", [])
    assert "ternary_coordinates" in asserted or "ternary" in asserted
    # only valid candidates reach downstream scoring
    rows = payload.get("candidate_evidence_table", [])
    scored = set(payload.get("downstream_scoring_candidate_ids", []))
    if rows:
        assert scored <= {r["candidate_id"] for r in rows}
        for r in rows:
            assert r["degradation"]["evidence_kind"] in ("predicted", "not_assessable")
            assert "measured" not in r["degradation"]["evidence_kind"]


# ------------------------------------------------------------------ per-command real work presence
def test_commands_have_real_work_not_just_text():
    # the 14 contracts explicitly declare what real computation happens
    assert all(CONTRACTS[c].real_work for c in CONTRACTS)
    assert "does not execute design" in CONTRACTS["plan"].real_work.lower()
    assert "executes the deterministic assembly pipeline" in CONTRACTS["design"].real_work.lower()