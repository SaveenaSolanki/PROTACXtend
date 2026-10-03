"""TargetTherapeuticsAssessment tests: typed record, evidence tiers,
association-vs-causality/expression-vs-function separation, gates (no design
bypass), TUI bridge, and /plan + /investigate integration."""

from __future__ import annotations

import json
import os
import warnings

import pytest

warnings.filterwarnings("ignore")
os.environ["PROTACXTEND_PLANNER_OFFLINE"] = "1"

from protacxtend.therapeutics.api import (  # noqa: E402
    TherapeuticallyUnsuitable, design_gate, run_assessment,
)
from protacxtend.therapeutics.decision import assess  # noqa: E402
from protacxtend.therapeutics.evidence import gather  # noqa: E402


# ---------------------------------------------------------------------------
# Assessments build + persist
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec,expected",
                         [("EGFR", "degradation_justified"),
                          ("BRD4", "degradation_justified"),
                          ("KRAS G12C", "degradation_uncertain")])
def test_assessment_builds_and_persists(spec, expected):
    rec = run_assessment(spec, offline=True)
    assert rec.decision.verdict == expected
    assert os.path.exists(rec.artifact_path)
    stored = json.loads(open(rec.artifact_path).read())
    assert stored["schema_version"] == "TargetTherapeuticsAssessment.v1"


def test_kras_variant_parsed():
    rec = run_assessment("KRAS G12C", offline=True)
    assert rec.target.get("variant") == "G12C"
    assert rec.target.get("symbol") == "KRAS"


# ---------------------------------------------------------------------------
# Conclusion contract: every conclusion carries sources, assay context,
# conflicting evidence, missing data, and the experiment that would change it.
# ---------------------------------------------------------------------------

def test_conclusions_are_complete_and_typed():
    rec = run_assessment("EGFR", offline=True)
    assert len(rec.conclusions) == 6
    for c in rec.conclusions:
        assert isinstance(c.source_ids, list)
        assert c.assay_context
        assert c.experiment_to_change
        assert c.evidence_tier in (
            "genetic_association", "experimental_causality", "dependency",
            "expression", "predicted", "curated_template", "unavailable")
    for name in ("disease", "dependency", "normal_tissue", "binder_structure", "e3_opportunity"):
        b = rec.blocks[name]
        assert b.name == name
        assert isinstance(b.sources, list)
        assert isinstance(b.missing, list)


# ---------------------------------------------------------------------------
# Association vs causality and expression vs functional ligase activity
# ---------------------------------------------------------------------------

def test_association_not_causality_from_template():
    rec = run_assessment("BRD4", offline=True)
    disease = rec.blocks["disease"]
    assert disease.evidence_tier in ("genetic_association", "curated_template")
    # a curated template must never claim experimental_causality
    assert "experimental_causality" not in disease.evidence_tier
    assert rec.conclusions[1].evidence_tier in ("genetic_association", "curated_template")


def test_expression_never_implies_functional_ligase_activity():
    rec = run_assessment("KRAS G12C", offline=True)
    nts = rec.blocks["normal_tissue"]
    assert "expression" in nts.evidence_tier or nts.evidence_tier == "unavailable"
    # the conclusion text must mark expression as non-functional
    assert ("NOT ligase activity" in nts.assay_context
            or "not ligase activity" in nts.assay_context.lower()
            or "expression, not functional" in nts.assay_context.lower())
    dep = rec.blocks["dependency"]
    assert dep.evidence_tier == "unavailable"   # never inferred from expression


def test_identity_not_biology():
    rec = run_assessment("EGFR", offline=True)
    id_conc = rec.conclusions[0]
    assert id_conc.dimension == "target_identity"
    assert "no biological claim" in id_conc.assay_context.lower()


# ---------------------------------------------------------------------------
# Design gates: no bypass
# ---------------------------------------------------------------------------

def test_kras_gate_blocks_design():
    run_assessment("KRAS G12C", offline=True)
    with pytest.raises(TherapeuticallyUnsuitable):
        design_gate("KRAS G12C")


def test_brd4_gate_passes_with_requires_review_flag():
    run_assessment("BRD4", offline=True)
    out = design_gate("BRD4")
    # window data missing (dependency + normal-tissue) -> requires_review, which
    # is NOT a silent pass; research design may proceed with the flag visible.
    assert out["status"] in ("pass", "pass_with_requires_review")
    assert out["verdict"] == "degradation_justified"
    assert out["therapeutic_suitability"] == "requires_review"
    assert out["gates"]["therapeutic_window"] == "requires_review"


def test_require_assessment_blocks_when_missing():
    with pytest.raises(TherapeuticallyUnsuitable):
        design_gate("NONEXISTENT_TARGET", require_assessment=True)


def test_runtime_design_blocked_no_bypass():
    from protacxtend.agents.runtime import run_protacpilot
    run_assessment("KRAS G12C", offline=True)
    r = run_protacpilot("Design a PROTAC for KRAS G12C", mode="deterministic",
                        config={"target_spec": "KRAS G12C", "record_run": False})
    assert r.get("status") == "blocked"
    assert "therapeutics" in (r.get("gate") or "")
    assert "design blocked" in (r.get("error") or "")


# ---------------------------------------------------------------------------
# TUI bridge + /plan + /investigate integration
# ---------------------------------------------------------------------------

def test_tui_bridge_therapeutics_command():
    import protacxtend.tui_bridge.server as server
    captured: list[dict] = []
    server.emit = lambda payload: captured.append(payload)  # type: ignore[assignment]
    server.handle_command("therapeutics", {"target": "EGFR"})
    answers = [p for p in captured if p.get("type") == "therapeutics_answer"]
    assert answers
    a = answers[-1]
    assert a["kind"] == "assessment"
    assert a["verdict"] == "degradation_justified"
    assert a["gates"]["identity"] == "pass"
    assert a["artifact"].endswith(".json") and "EGFR__" in a["artifact"]


def test_plan_and_investigate_include_assessment_stage():
    from protacxtend.planning.goal_planner import build_plan
    from protacxtend.planning.planner import reset_session
    reset_session("tass")
    plan = build_plan("/plan KRAS G12C protac", conversation_id="tass", offline=True)
    ids = [t.id for t in plan.tasks]
    assert "T1b_therapeutic_assessment" in ids
    stage = next(t for t in plan.tasks if t.id == "T1b_therapeutic_assessment")
    assert stage.dependencies == ["T0_confirm_target"]
    assert "must not bypass" in stage.why_for_this_request

    import protacxtend.tui_bridge.server as server
    captured: list[dict] = []
    server.emit = lambda payload: captured.append(payload)  # type: ignore[assignment]
    server.handle_command("investigate", {"task": "T1b_therapeutic_assessment",
                                          "request": "/plan KRAS G12C protac",
                                          "conversation_id": "tass"})
    answers = [p for p in captured if p.get("type") == "investigate_answer"]
    assert answers and answers[-1]["kind"] == "assessment"
    assert answers[-1]["verdict"] == "degradation_uncertain"
    assert answers[-1]["executed_design"] is False


def test_depmap_and_hpa_unavailable_are_recorded_not_fabricated():
    rec = run_assessment("BRD4", offline=True)
    assert rec.blocks["dependency"].status == "unavailable"
    assert rec.blocks["normal_tissue"].status in ("unavailable", "partial")
    # their experiment_to_change fields must be present
    assert rec.blocks["dependency"].experiment_to_change
    assert rec.blocks["normal_tissue"].experiment_to_change