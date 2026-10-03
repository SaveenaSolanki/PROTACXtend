"""/plan task graph, causal evidence record, diagnosis and row-audit tests.

A test only passes if changing an observation changes the agent's next
action appropriately — not merely because stage names are present.
"""

from __future__ import annotations

import os
import warnings

import pytest

warnings.filterwarnings("ignore")
os.environ["PROTACXTEND_PLANNER_OFFLINE"] = "1"

import protacxtend.tui_bridge.server as server  # noqa: E402
from protacxtend.planning.causal import (  # noqa: E402
    CausalEvidenceRecord, egfr_strong_binding_no_degradation_case, empty_record, set_item,
)
from protacxtend.planning.diagnose import diagnose  # noqa: E402
from protacxtend.planning.goal_planner import build_plan  # noqa: E402
from protacxtend.planning.planner import reset_session  # noqa: E402
from protacxtend.planning.row_audit import audit_binder_count, audit_degradation_rows  # noqa: E402


def _bridge(command: str, request: str, cid: str = "m") -> list[dict]:
    captured: list[dict] = []
    server.emit = lambda payload: captured.append(payload)  # type: ignore[assignment]
    server.handle_command(command, {"request": request, "conversation_id": cid})
    return captured


# ---------------------------------------------------------------------------
# Observation -> action flips (the real contract)
# ---------------------------------------------------------------------------

def test_strong_binding_absent_deg_never_suggests_linker_change():
    rec = egfr_strong_binding_no_degradation_case()
    diag = diagnose(rec)
    assert diag.observations["target_engagement"] == "measured"
    assert diag.observations["cellular_degradation"] == "absent"
    assert "linker change" in diag.gated                      # withheld...
    assert "Do NOT change the linker" in diag.recommended_action  # ...until diagnosis
    rec2 = diagnose(rec)
    assert rec2.discriminating_measurement.experiment
    assert "ternary_low" in rec2.discriminating_measurement.outcomes
    assert "ternary_ok_and_uptake_low" in rec2.discriminating_measurement.outcomes


def test_flip_degradation_present_changes_next_action():
    rec = egfr_strong_binding_no_degradation_case()
    set_item(rec, "proteasome_loss", tag="measured", compound="degrader", cell="A431",
             dose="100 nM", time="24 h", endpoint="DC50 20 nM / Dmax 90%",
             source="case assay record", detail="cellular degradation observed")
    diag = diagnose(rec)
    assert diag.observations["cellular_degradation"] == "present"
    assert diag.recommended_action != ""
    assert "linker change" not in diag.gated or diag.recommended_action != (
        "Run the discriminating measurement (ternary engagement + cellular uptake). "
        "Do NOT change the linker before the bottleneck is identified.")
    # degradation observed -> the next action is NOT a bottleneck-gated linker
    assert "proceed to dose/time/hook characterization" in diag.recommended_action


def test_flip_binding_missing_changes_next_action():
    rec = egfr_strong_binding_no_degradation_case()
    for i in rec.items:
        if i.step == "target_engagement":
            i.tag = "missing"
    diag = diagnose(rec)
    assert diag.observations["target_engagement"] == "missing"
    assert "Binding is not measured" in diag.recommended_action
    assert "cellular degradation interpretation" in diag.gated


# ---------------------------------------------------------------------------
# /plan task graph: EGFR vs GSPT1 (why plans differ)
# ---------------------------------------------------------------------------

def test_plan_task_graph_egfr_vs_gspt1_differ_by_evidence():
    reset_session("egfr-tasks")
    plan_egfr = build_plan("/plan EGFR protac", conversation_id="egfr-tasks", offline=True)
    reset_session("gspt1-tasks")
    plan_gspt1 = build_plan("/plan GSPT1 protac", conversation_id="gspt1-tasks", offline=True)

    tg_e = {t["task_id"]: t for t in plan_egfr.tasks_graph}
    tg_g = {t["task_id"]: t for t in plan_gspt1.tasks_graph}
    assert "t1_target_identity" in tg_e and "t2_degradation_precedent" in tg_e
    # EGFR: measured precedent -> positive branch to t3; GSPT1: no rows -> negative branch
    e_br = tg_e["t2_degradation_precedent"]["branches"]
    g_br = tg_g["t2_degradation_precedent"]["branches"]
    assert any(b["on"] == "positive" and b["next"] == "t3_binders" for b in e_br)
    assert any(b["on"] == "negative" for b in g_br)
    # mechanistic question, tool, input, expected artifact, evidence required present
    t = tg_e["t1_target_identity"]
    for key in ("mechanistic_question", "tool", "input", "expected_artifact", "evidence_required", "branches"):
        assert key in t and t[key]
    assert plan_egfr.plan_difference != plan_gspt1.plan_difference
    assert "measured degradation precedent (18 rows)" in plan_egfr.plan_difference.lower()
    assert "no measured degradation precedent" in plan_gspt1.plan_difference.lower()


# ---------------------------------------------------------------------------
# Causal evidence record: tags and labels
# ---------------------------------------------------------------------------

def test_causal_record_tags_and_validation_label():
    rec = egfr_strong_binding_no_degradation_case()
    steps = rec.by_step()
    assert steps["target_engagement"].tag == "measured"
    assert steps["proteasome_loss"].tag == "missing"
    allowed = {"measured", "computed", "inferred", "proposed", "missing"}
    assert all(i.tag in allowed for i in rec.items)
    # validation label corrected: proposed, never computational
    plan = build_plan("/plan EGFR protac", conversation_id="v-lab", offline=True)
    stage = {s["step"]: s for s in plan.stage_evidence}
    assert stage["validation"]["label"] == "proposed"
    assert "PENDING" in stage["validation"]["summary"]


# ---------------------------------------------------------------------------
# Row-level audit: 18 EGFR rows and 500-binder count gate
# ---------------------------------------------------------------------------

def test_row_audit_egfr_18_rows_and_binder_count_gate():
    audit = audit_degradation_rows("EGFR")
    assert audit.n_rows_raw == 18
    assert audit.n_unique_after_dedup >= 1
    assert audit.dedup_rule and "doi" in audit.dedup_rule
    for r in audit.rows[:3]:
        assert r.doi and r.cell_line
    # usable subset for a VHL objective
    vhl = audit_degradation_rows("EGFR", e3_filter="VHL")
    assert all(r.e3.upper() == "VHL" for r in vhl.usable_for_objective)
    # binder count: 500 is count-only (no row-level source in package)
    b = audit_binder_count("EGFR")
    assert b.binder_count == 500
    assert b.binder_count_only is True
    assert b.binder_rows_in_package == 0
    # counts alone never pass: the plan task records the retrieval requirement
    plan = build_plan("/plan EGFR protac", conversation_id="audit", offline=True)
    tg = {t["task_id"]: t for t in plan.tasks_graph}
    assert "count-only" in tg["t3_binders"]["branches"][0]["note"].lower()


# ---------------------------------------------------------------------------
# Bridge: /reason -> /experiment -> /optimize on the EGFR case
# ---------------------------------------------------------------------------

def test_bridge_reason_experiment_optimize_diagnosis():
    r = [p for p in _bridge("reason", "EGFR binding strong but no degradation") if p.get("type") == "diagnosis_answer"][-1]
    assert r["command"] == "reason"
    assert len(r["hypotheses"]) >= 2
    assert all(h["evidence_for"] and h["evidence_against"] for h in r["hypotheses"])

    e = [p for p in _bridge("experiment", "diagnose EGFR") if p.get("type") == "diagnosis_answer"][-1]
    assert e["command"] == "experiment"
    assert "ternary" in e["experiment"].lower() and "uptake" in e["experiment"].lower()
    assert {"ternary_low", "ternary_ok_and_uptake_low", "ternary_ok_uptake_ok"} <= set(e["outcomes"].keys())

    o = [p for p in _bridge("optimize", "optimize EGFR degrader") if p.get("type") == "diagnosis_answer"][-1]
    assert o["command"] == "optimize"
    assert "Do NOT change the linker" in o["recommended_action"]
    assert "linker change" in o["gated"]