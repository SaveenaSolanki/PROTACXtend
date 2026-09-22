"""Tests for the deterministic multi-dimension scoring module (tpdeval.dimensions).

These verify: the 11-dimension contract, the 0–5 scale, machine/expert
separation, deterministic machine scorers, temporal gating, failure gating,
per-dimension aggregation, and that a composite is never the headline.
"""
from __future__ import annotations

import pytest

from tpdeval import dimensions as D
from tpdeval.dimensions import (
    ALL_DIMENSION_NAMES,
    GENERAL_DIMENSION_NAMES,
    TEMPORAL_DIMENSION_NAMES,
    MachineResult,
    TaskScorecard,
    aggregate_dimensions,
    applicable_dimensions,
    markdown_scorecard,
    score_task,
    secondary_composite,
    validate_scale,
)
from tpdeval.scoring import FAILURE_CRITERIA
from tpdeval.taskmodel import GroundTruth, RunRecord, TaskRecord, ToolSpec

# ── contract ────────────────────────────────────────────────────────────────

def test_exactly_eleven_dimensions_nine_plus_two_temporal():
    assert len(D.DIMENSIONS) == 11
    assert len(GENERAL_DIMENSION_NAMES) == 9
    assert len(TEMPORAL_DIMENSION_NAMES) == 2
    assert set(TEMPORAL_DIMENSION_NAMES) == {"temporal_compliance",
                                             "future_outcome_concordance"}
    assert set(GENERAL_DIMENSION_NAMES) == {
        "scientific_correctness", "evidence_grounding", "tool_selection",
        "tool_execution", "mechanistic_correctness", "quantitative_correctness",
        "uncertainty_calibration", "reproducibility", "final_decision_quality"}


def test_every_dimension_has_six_anchors_and_both_components():
    for d in D.DIMENSIONS:
        assert len(d.anchors) == 6, d.name
        assert d.machine_capable is True, d.name
        assert d.expert_required is True, d.name


def test_scale_is_integer_0_to_5():
    for ok in (0, 1, 3, 5):
        assert validate_scale(ok) == ok
    for bad in (-1, 6, 2.5):
        with pytest.raises(ValueError):
            validate_scale(bad)
    with pytest.raises(TypeError):
        validate_scale(True)
    with pytest.raises(TypeError):
        validate_scale("4")


def test_temporal_dimensions_only_apply_to_temporal_partition():
    assert applicable_dimensions("controlled") == list(GENERAL_DIMENSION_NAMES)
    assert set(applicable_dimensions("temporal")) == set(ALL_DIMENSION_NAMES)
    assert set(applicable_dimensions("controlled", temporal_cutoff="2026-01-01")) \
        == set(ALL_DIMENSION_NAMES)


# ── deterministic machine scorers ───────────────────────────────────────────

def test_tool_selection_scores_and_irrelevant_cap():
    spec = ToolSpec(required=["a", "b"], optional=["d"], irrelevant=["c"])
    assert D.score_tool_selection(["a", "b"], spec).value == 5
    assert D.score_tool_selection(["a"], spec).value == 3
    # an explicitly irrelevant tool caps the dimension at 1
    assert D.score_tool_selection(["a", "b", "c"], spec).value <= 1
    # no declared spec -> not computable, never guessed
    assert D.score_tool_selection(["a"], ToolSpec()).value is None


def test_tool_execution_uses_recorded_flags():
    good = [{"tool": "a", "status": "ok", "execution_success": True,
             "valid_output": True, "qc_performed": True}]
    assert D.score_tool_execution(good).value == 5
    bad = [{"tool": "a", "status": "failed", "execution_success": False,
            "valid_output": False, "qc_performed": False}]
    assert D.score_tool_execution(bad).value == 0
    assert D.score_tool_execution([]).value is None


def test_evidence_grounding_and_fabricated_citation_hard_zero():
    good = [{"supported": True, "citation_ids": ["doi:1"], "primary_source": True},
            {"supported": True, "citation_ids": ["doi:2"], "primary_source": True}]
    assert D.score_evidence_grounding(good).value == 5
    fab = [{"supported": True, "fabricated": True}]
    assert D.score_evidence_grounding(fab).value == 0
    assert D.score_evidence_grounding([]).value is None


def test_quantitative_correctness_tolerance():
    r = D.score_quantitative_correctness([
        {"predicted": 1.0, "expected": 1.0, "tol": 0.01},
        {"predicted": 2.0, "expected": 2.05, "tol": 0.1}])
    assert r.value == 5
    r = D.score_quantitative_correctness([
        {"predicted": 1.0, "expected": 1.0, "tol": 0.01},
        {"predicted": 2.0, "expected": 4.0, "tol": 0.1}])
    assert r.value == 3  # 1 of 2 within tolerance -> 0.5
    assert D.score_quantitative_correctness([]).value is None


def test_uncertainty_calibration_rewards_calibrated_confidence():
    cal = D.score_uncertainty_calibration([0.9, 0.1], [1, 0])
    over = D.score_uncertainty_calibration([0.9, 0.9], [0, 0])
    assert cal.value == 5
    assert over.value <= 1
    assert D.score_uncertainty_calibration([], []).value is None


def test_reproducibility_modal_agreement():
    assert D.score_reproducibility(["a", "a", "a"]).value == 5
    assert D.score_reproducibility(["a", "a", "b"]).value == 3
    assert D.score_reproducibility(["a"]).value is None


def test_temporal_compliance_and_leakage():
    assert D.score_temporal_compliance([]).value == 5
    assert D.score_temporal_compliance([{"kind": "post_cutoff"}]).value == 0
    assert D.score_temporal_compliance(None).value is None


def test_future_outcome_concordance_categorical_and_numeric():
    assert D.score_future_outcome_concordance(
        [{"predicted": "yes", "actual": "yes"},
         {"predicted": "no", "actual": "no"}]).value == 5
    assert D.score_future_outcome_concordance(
        [{"predicted": 1.0, "actual": 1.02, "tol": 0.05}]).value == 5
    assert D.score_future_outcome_concordance([]).value is None


def test_objective_correctness_for_exact_categorical_numeric():
    assert D.score_objective_correctness("O60885", "O60885", "exact").value == 5
    assert D.score_objective_correctness("Q60885", "O60885", "exact").value == 0
    assert D.score_objective_correctness("b", ["a", "b"], "categorical").value == 5
    assert D.score_objective_correctness(1.0, 1.01, "numeric").value == 5
    # rubric GT is not machine-scorable
    assert D.score_objective_correctness("anything", "x", "rubric").value is None


def test_mechanistic_correctness_reversal_is_punished():
    truth = {"nodes": {"a": {}, "b": {}}, "edges": [["a", "b"]]}
    exact = {"nodes": {"a": {}, "b": {}}, "edges": [["a", "b"]]}
    reversed_ = {"nodes": {"a": {}, "b": {}}, "edges": [["b", "a"]]}
    assert D.score_mechanistic_correctness(exact, truth).value == 5
    assert D.score_mechanistic_correctness(reversed_, truth).value <= 1


def test_machine_scorers_are_deterministic():
    spec = ToolSpec(required=["a", "b"], irrelevant=["c"])
    first = D.score_tool_selection(["a", "b", "c"], spec)
    second = D.score_tool_selection(["a", "b", "c"], spec)
    assert first.value == second.value
    assert first.detail == second.detail


# ── scorecard: components & gating ──────────────────────────────────────────

def _task(partition="controlled", cutoff=None, gt_type="exact", expected="X"):
    return TaskRecord(
        task_id="T-1", benchmark_domain="target_biology", difficulty="L1",
        partition=partition, title="t", target="BRD4", disease_context="c",
        e3_context=None, question="q",
        tool_spec=ToolSpec(required=["uniprot"], irrelevant=["irrelevant_tool"]),
        temporal_cutoff=cutoff,
        ground_truth=GroundTruth(gt_type=gt_type, expected=expected,
                                 status="FROZEN", immutable=True,
                                 evidence_sources=[{"type": "db", "name": "UniProt"}],
                                 reviewed_by=["r1"]))


def _run(**kw):
    base = dict(run_id="R-1", task_id="T-1", system="PROTACXtend",
                system_version="0.3.0", condition="native", model="m",
                model_version="1", seed=42, repeat=0, start_time="t0",
                end_time="t1", selected_tools=["uniprot"], temporal_leakage=[])
    base.update(kw)
    return RunRecord(**base)


def test_score_task_keeps_machine_and_expert_separate():
    card = score_task(
        _task(), _run(),
        predicted_answer="X",
        tool_calls=[{"tool": "uniprot", "status": "ok", "execution_success": True,
                     "valid_output": True, "qc_performed": True}],
        claims=[{"supported": True, "citation_ids": ["d"], "primary_source": True}],
        expert={"scientific_correctness": [4, 5], "final_decision_quality": [4]})
    sc = card.scores["scientific_correctness"]
    assert sc.machine == 5
    assert sc.reviewers == [4, 5]
    assert sc.expert == 5              # half-up mean of [4,5]
    assert sc.disagreement() == 0
    # providing expert did not overwrite the machine component
    assert card.scores["scientific_correctness"].machine == 5


def test_score_task_temporal_dimensions_gated_by_partition():
    controlled = score_task(_task(partition="controlled"), _run())
    # controlled partition: temporal dims not applicable
    assert "temporal_compliance" not in [r["dimension"] for r in controlled.dimension_table()]
    temporal = score_task(
        _task(partition="temporal", cutoff="2026-01-01"), _run(),
        temporal_outcomes=[{"predicted": "degrades", "actual": "degrades"}])
    names = [r["dimension"] for r in temporal.dimension_table()]
    assert "temporal_compliance" in names
    assert temporal.scores["future_outcome_concordance"].machine == 5


def test_missing_dimensions_are_reported_not_defaulted():
    card = score_task(_task(), _run(), predicted_answer="X")
    assert "mechanistic_correctness" in card.missing()          # no graph supplied
    assert not card.complete
    assert card.verdict == "INCOMPLETE"
    assert "final_decision_quality" in card.expert_only_missing()


def test_failure_criterion_forces_fail():
    card = score_task(_task(), _run(), predicted_answer="X",
                      failures=["fake_or_uncited_primary_citation"])
    assert card.verdict == "FAIL"
    assert card.failures == ["fake_or_uncited_primary_citation"]
    with pytest.raises(ValueError):
        card.mark_failure("not_a_real_criterion")


# ── aggregation & composite discipline ──────────────────────────────────────

def test_aggregate_is_per_dimension_without_composite():
    cards = [
        score_task(_task(), _run(run_id="R-1", system="A"), predicted_answer="X"),
        score_task(_task(), _run(run_id="R-2", system="B"), predicted_answer="wrong"),
    ]
    agg = aggregate_dimensions(cards)
    assert agg["n_scorecards"] == 2
    assert "composite" not in agg
    assert "composite_secondary" not in agg
    assert agg["dimensions"]["scientific_correctness"]["machine_mean"] == 2.5
    assert agg["dimensions"]["scientific_correctness"]["scale"] == "0-5"


def test_secondary_composite_is_opt_in_labelled_and_coverage_aware():
    out = secondary_composite({
        "scientific_correctness": {"machine": 5, "expert": 4},
        "mechanistic_correctness": {"machine": 2, "expert": None},
    })
    assert "SECONDARY" in out["label"]
    assert out["coverage"] < 1.0          # only 2 of 11 dimensions present
    assert out["composite_secondary"] is not None
    assert len(out["weights_used"]) == 2


def test_markdown_scorecard_shows_no_composite():
    card = score_task(_task(), _run(), predicted_answer="X")
    md = markdown_scorecard(card)
    assert "| dimension | machine (0–5) | expert (0–5) |" in md
    assert "No composite score is shown" in md


def test_scorecard_schema_lists_dimensions_and_composite_discipline():
    schema = D.scorecard_schema()
    assert schema["scale"] == {"min": 0, "max": 5, "type": "integer"}
    assert set(schema["dimensions"]) == set(ALL_DIMENSION_NAMES)
    assert set(schema["temporal_dimensions"]) == set(TEMPORAL_DIMENSION_NAMES)
    assert "SECONDARY" in schema["composite"]
    assert set(schema["failure_criteria"]) == set(FAILURE_CRITERIA)


def test_scorecard_to_dict_has_no_headline_composite():
    card = score_task(_task(), _run(), predicted_answer="X")
    d = card.to_dict()
    assert d["verdict"] == "INCOMPLETE"
    assert "composite" not in d
    assert "No headline composite" in d["note"]


def test_to_score_record_persists_machine_and_expert_separately():
    card = score_task(_task(partition="temporal", cutoff="2026-01-01"), _run(),
                      predicted_answer="X",
                      temporal_outcomes=[{"predicted": "degrades", "actual": "degrades"}],
                      expert={"scientific_correctness": [4, 5]})
    rec = card.to_score_record()
    # machine component lands on the canonical dimension fields
    assert rec.scientific_correctness == 5.0
    assert rec.temporal_compliance == 5.0
    # future_outcome_concordance maps onto the ScoreRecord alias field
    assert rec.future_outcome_match == 5.0
    # expert component is stored separately, with reviewers and the gap
    assert rec.expert_scores["scientific_correctness"]["machine"] == 5
    assert rec.expert_scores["scientific_correctness"]["expert"] == 5
    assert rec.expert_scores["scientific_correctness"]["reviewers"] == [4, 5]
    assert rec.expert_scores["scientific_correctness"]["machine_expert_gap"] == 0
