"""Tests for the benchmark scoring engine and scorable manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark_runner.grader import (
    grade_answer,
    load_ground_truth,
    scorable_status,
)

ROOT = Path(__file__).resolve().parents[1]
GT_DIR = ROOT / "benchmark" / "ground_truth"
MANIFEST = ROOT / "benchmark" / "SCORABLE_MANIFEST.json"


def test_exact_structured_grading():
    gt = {"type": "exact", "expected_value": "O60885"}
    r = grade_answer("X", "O60885", gt=gt)
    assert r["status"] == "scored" and r["score"] == 1.0
    assert grade_answer("X", "Q99999", gt=gt)["score"] == 0.0


def test_categorical_grading():
    gt = {"type": "categorical", "expected_set": ["JQ1", "OTX015"],
          "mandatory_answer_elements": ["JQ1", "OTX015"]}
    r = grade_answer("X", "JQ1 and OTX015 bind BRD4", gt=gt)
    assert r["status"] == "scored"
    assert r["score"] == 1.0


def test_ranked_grading():
    gt = {"type": "ranked", "expected_ranking": ["a", "b", "c"]}
    r = grade_answer("X", ["a", "b", "c"], gt=gt)
    assert r["status"] == "scored" and r["score"] == 1.0


def test_numeric_grading_with_tolerance():
    gt = {"type": "numeric", "expected_value": 14.4, "tolerance": 0.5}
    assert grade_answer("X", "14.6 nM", gt=gt)["score"] == 1.0
    assert grade_answer("X", "20 nM", gt=gt)["score"] == 0.0


def test_rubric_never_silently_complete():
    gt = {"type": "mechanistic_rubric",
          "mandatory_answer_elements": ["ternary complex", "CRBN"]}
    r = grade_answer("X", "A ternary complex forms via CRBN", gt=gt)
    assert r["status"] == "requires_expert_review"
    assert r["score"] == 1.0
    assert r["requires_expert_review"] is True


def test_unscorable_reported_not_faked():
    gt = {"type": "constraint"}  # no constraints/checklist
    r = grade_answer("X", "anything", gt=gt)
    assert r["status"] == "unscorable_missing_fields"
    assert r["score"] is None


def test_all_frozen_tasks_are_scorable_via_overlay():
    task_ids = sorted(p.stem for p in GT_DIR.glob("*.json") if not p.stem.startswith("_"))
    assert len(task_ids) >= 48
    for task_id in task_ids:
        gt = load_ground_truth(task_id)
        status = scorable_status(gt, task_id=task_id)
        assert status["scorable"], f"{task_id}: {status}"
        assert status["mode"] in {"deterministic", "checklist", "rubric_checklist", "structured"}


def test_scorable_manifest_matches_ground_truth_count():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["n_cases"] == manifest["n_ground_truth"] == 48
    assert manifest["cases_without_ground_truth"] == []
    assert manifest["n_automatically_scorable"] == 48
    assert manifest["n_not_scorable"] == 0


def test_grader_roundtrip_on_real_task():
    r = grade_answer("DESIGN-01", "5 valid SMILES with components preserved")
    assert r["task_id"] == "DESIGN-01"
    assert r["status"] == "requires_expert_review"
    assert r["score"] is not None
