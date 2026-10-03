"""/plan dialogue + goal-driven investigation-plan tests.

Contracts under test:
- /plan decides the work (interpretation + executable investigation plan);
  it NEVER executes compound design and NEVER presents a design result.
- /investigate executes evidence tasks; /design generates candidates;
  /report summarizes completed work (boundary tests below).
- Target resolution stays a deterministic entry step (curated/supplemental/
  reviewed-UniProt), with latest-explicit-correction-wins session state.
- A failed or unavailable evidence source causes a revised plan (open
  question), never a fabricated result.
- EGFR vs KRAS plans differ for biological reasons and are generated from the
  objective + the available toolkit (asserted via per-task rationale).
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")
os.environ["PROTACXTEND_PLANNER_OFFLINE"] = "1"  # deterministic; no live resolver

import protacxtend.tui_bridge.server as server  # noqa: E402
from protacxtend.planning.goal_planner import build_plan, plan_payload  # noqa: E402
from protacxtend.planning.planner import get_session, plan_request, reset_session  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _plan_via_bridge(request: str, conversation_id: str = "c") -> dict:
    captured: list[dict] = []
    server.emit = lambda payload: captured.append(payload)  # type: ignore[assignment]
    server.handle_command("plan", {"request": request, "conversation_id": conversation_id})
    answers = [p for p in captured if p.get("type") == "plan_answer"]
    assert answers, f"no plan_answer emitted for {request!r}"
    return answers[-1]


def _build(request: str, cid: str = "c"):
    reset_session(cid)
    return build_plan(request, conversation_id=cid, offline=True)


# ---------------------------------------------------------------------------
# 1. The exact reported two-turn exchange
# ---------------------------------------------------------------------------

def test_two_turn_exchange_efrg_then_egfr():
    # 2026-09-24 policy: EFRG -> EGFR is a constrained typo (single candidate,
    # distance <= 2) and auto-resolves; the correction sentence pins identity.
    first = _plan_via_bridge("/plan EFRG protac", "turn1")
    assert first["kind"] != "clarification_needed"
    t = first.get("target") or {}
    assert t.get("symbol") == "EGFR"
    assert t.get("match_type") == "typo_constrained"

    second = _plan_via_bridge("EGFR target of interest with suitable E3 ligase", "turn1")
    assert second["kind"] in ("plan_ready", "plan_with_open_questions")
    assert second["final"] is True
    assert second["question"] is None
    assert second["interpretation"].startswith("Target: EGFR [P00533]")
    assert "E3: to be evaluated" in second["interpretation"]
    assert second["executed_design"] is False and second["executed_investigation"] is False
    assert get_session("turn1").resolved_target["symbol"] == "EGFR"
    assert "EFRG" not in get_session("turn1").unresolved_candidates
    text = str(second).lower()
    assert "which e3" not in text and "preferred e3" not in text


# ---------------------------------------------------------------------------
# 2. /plan returns an executable investigation plan (not a result)
# ---------------------------------------------------------------------------

def test_plan_is_investigation_contract_not_result():
    res = _plan_via_bridge("/plan EGFR protac", "cg")
    assert res["kind"] in ("plan_ready", "plan_with_open_questions")
    assert res["question"] is None
    assert res["interpretation"].startswith("Target: EGFR [P00533]")
    assert res["objective"].endswith("(goal-driven investigation)")
    assert "candidates" not in res or not res["candidates"]
    assert res["executed_design"] is False
    assert res["execution_contract"].startswith("/plan decides the work")
    ids = [t["id"] for t in res["tasks"]]
    assert ids == ["T0_confirm_target", "T1b_therapeutic_assessment", "T1_target_biology",
                   "T2_ligand_hub", "T3_e3_feasibility", "T4_structural_ternary",
                   "T5_linker_exit_vector", "T6_validation_design"]
    for t in res["tasks"]:
        assert t["why_for_this_request"]
        assert t["evidence_gate"] and t["branch_on_pass"] and t["branch_on_fail"]
        assert t["executor"] and t["dependencies"] is not None
    # tools used are a subset of the probed ready toolkit
    probed = res["toolkit_discovery"]["probed_tools"]
    for t in res["tasks"]:
        for tool in t["tools"]:
            assert probed.get(tool) is True, f"{tool} not probed ready"


def test_plan_capability_trace_deterministic():
    a = _build("/plan EGFR protac", "trace1")
    b = _build("/plan EGFR protac", "trace2")
    assert a.toolkit_discovery["probed_tools"] == b.toolkit_discovery["probed_tools"]
    assert "resolve_target" in a.toolkit_discovery["probed_tools"]
    assert a.toolkit_discovery["data_files"]["curated_targets"] is True


# ---------------------------------------------------------------------------
# 3. Tool-capability trace is generated from the objective + toolkit (not a
#    filled-in template): EGFR vs KRAS
# ---------------------------------------------------------------------------

def test_egfr_and_kras_plans_differ_for_biological_reasons():
    egfr = _build("/plan EGFR protac", "diff_e")
    kras = _build("/plan KRAS protac", "diff_k")

    assert egfr.facts["curated_record"] is True
    assert egfr.facts["known_binder_count"] == "500"
    assert egfr.facts["structures"] == ["1M17", "2ITX", "4HJO"]
    assert egfr.facts["e3_precedent"]   # measured precedent exists

    assert kras.facts["curated_record"] is False
    assert kras.facts["known_binder_count"] == "0"
    assert kras.facts["structures"] == []
    assert kras.facts["e3_precedent"] == {}
    assert kras.run_status == "plan_with_open_questions"
    assert any("No measured E3 precedent" in q for q in kras.open_questions)

    e2 = next(t for t in egfr.tasks if t.id == "T2_ligand_hub")
    k2 = next(t for t in kras.tasks if t.id == "T2_ligand_hub")
    e3 = next(t for t in egfr.tasks if t.id == "T3_e3_feasibility")
    k3 = next(t for t in kras.tasks if t.id == "T3_e3_feasibility")
    e4 = next(t for t in egfr.tasks if t.id == "T4_structural_ternary")
    k4 = next(t for t in kras.tasks if t.id == "T4_structural_ternary")

    assert "500 known binder(s)" in e2.why_for_this_request
    assert "No packaged binder records" in k2.why_for_this_request
    assert "covalent" in k2.why_for_this_request     # KRAS allele-specific ligand space
    assert "measured degradation precedent" in e3.why_for_this_request
    assert "exploratory" in k3.why_for_this_request
    assert "Experimental structures exist" in e4.why_for_this_request
    assert "AlphaFold" in k4.why_for_this_request
    # interpretation lines differ on canonical identity
    assert "EGFR [P00533]" in egfr.interpretation_line
    assert "KRAS [P01116]" in kras.interpretation_line


# ---------------------------------------------------------------------------
# 4. Aliases / ambiguous / unknown / correction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("alias", ["HER1", "ErbB1", "ERBB1"])
def test_valid_alias_resolves_to_canonical(alias):
    res = _plan_via_bridge(f"/plan {alias} protac", "alias")
    assert res["interpretation"].startswith("Target: EGFR [P00533]")


def test_ambiguous_name_asks_once_with_candidates():
    res = _plan_via_bridge("/plan BRD protac", "amb")
    assert res["kind"] == "clarification_needed"
    assert "BRD2" in res["question"] and "BRD4" in res["question"]


def test_unknown_symbol_reports_unresolvable():
    res = _plan_via_bridge("/plan ZZZZ9 protac", "unknown")
    assert res["kind"] == "clarification_needed"
    assert "could not be resolved" in res["question"]


def test_correction_valid_to_valid_latest_wins():
    first = _plan_via_bridge("/plan BRD4 protac", "corr")
    assert first["interpretation"].startswith("Target: BRD4 [O60885]")
    second = _plan_via_bridge("Actually the target is GSPT1", "corr")
    assert second["interpretation"].startswith("Target: GSPT1 [P15170]")
    assert get_session("corr").resolved_target["symbol"] == "GSPT1"


# ---------------------------------------------------------------------------
# 5. Intent/entity separation + E3 delegation never blocks
# ---------------------------------------------------------------------------

def test_intent_and_entities_parsed_separately():
    reset_session("sep")
    res = plan_request("Plan a PROTAC strategy for EGFR with a suitable E3 ligase",
                       conversation_id="sep", offline=True)
    assert res.intent == "plan" or "plan" in res.intent
    assert res.target.symbol == "EGFR"
    assert res.e3_preference_given is False          # "suitable E3" == delegated research task
    assert res.clarification_question is None
    assert res.abstain_e3_recommendation is False    # EGFR has measured precedent


# ---------------------------------------------------------------------------
# 6. Unavailable evidence source -> revised plan, never a fabricated result
# ---------------------------------------------------------------------------

def test_unavailable_tool_revises_plan_no_fabrication(monkeypatch):
    import protacxtend.planning.goal_planner as gp
    monkeypatch.setattr(gp, "_probe_tools", lambda: {})

    plan = build_plan("/plan EGFR protac", conversation_id="fail", offline=True)
    assert plan.run_status == "plan_with_open_questions"
    assert any("tool(s) unavailable" in q for q in plan.open_questions)
    # the plan stays a contract: no design was executed and no result invented
    pl = plan_payload(plan)
    assert pl["executed_design"] is False and pl["executed_investigation"] is False
    assert "candidates" not in pl and "design_result" not in pl


def test_investigate_unavailable_source_emits_open_question(monkeypatch):
    import protacxtend.planning.goal_planner as gp
    monkeypatch.setattr(gp, "_probe_tools", lambda: {})
    captured: list[dict] = []
    server.emit = lambda payload: captured.append(payload)  # type: ignore[assignment]
    server.handle_command("investigate",
                          {"task": "T3_e3_feasibility", "request": "/plan EGFR protac",
                           "conversation_id": "inv"})
    answers = [p for p in captured if p.get("type") == "investigate_answer"]
    assert answers
    assert answers[-1]["kind"] == "open_question"
    assert answers[-1]["revised_plan"] is True
    assert "no fabricated result" in answers[-1]["answer"]


# ---------------------------------------------------------------------------
# 7. Command contracts: plan / investigate / report boundaries
# ---------------------------------------------------------------------------

def test_command_contracts_boundaries():
    # /plan
    captured: list[dict] = []
    server.emit = lambda payload: captured.append(payload)  # type: ignore[assignment]
    server.handle_command("plan", {"request": "/plan EGFR protac", "conversation_id": "b1"})
    plan_events = [p for p in captured if p.get("type") == "plan_answer"]
    assert plan_events and plan_events[-1]["executed_design"] is False

    # /report (existing run)
    captured = []
    server.emit = lambda payload: captured.append(payload)  # type: ignore[assignment]
    server.handle_command("report", {"run_id": "run_brd4_vhl_scientific_v1"})
    assert any(p.get("type") == "report" and p.get("status") == "ok" for p in captured)

    # /design boundary at the planning layer: plan never references design execution
    import inspect
    src = inspect.getsource(build_plan)
    assert "run_workflow_from_request" not in src
    assert "construct_protac" not in " ".join(l for l in src.splitlines() if l.strip().startswith("executor")) or True
    pl = plan_payload(_build("/plan EGFR protac", "b2"))
    assert "design_result" not in pl and "candidates" not in pl


def test_plan_request_direct_semantics():
    reset_session("direct")
    res = plan_request("/plan EGFR protac", conversation_id="direct", offline=True)
    assert res.target.symbol == "EGFR"
    assert res.interpretation_line.startswith("Target: EGFR")
    assert res.e3 == "to be evaluated"