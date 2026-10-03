"""Regression tests for the four-case reconciliation (2026-09-24).

Covers: grader empty/mismatched ranked answers no longer score 0.5; the
after-repair pilot keeps KNOW/REASON abstentions visible; blinded adjudication
sheets carry no provisional machine scores; DISCOVER-04 scored-only metric is
not presented as comparable."""

from __future__ import annotations

import glob
import json
import os
import warnings

import pytest

warnings.filterwarnings("ignore")
os.environ["PROTACXTEND_PLANNER_OFFLINE"] = "1"

from benchmark_runner.grader import grade_answer  # noqa: E402


def test_empty_ranked_answer_is_unanswered_not_half():
    d = grade_answer("DISCOVER-04", "")
    assert d["score"] == 0.0
    assert d["status"] == "unanswered"
    assert d["dimensions"].get("no_prediction") is True


def test_mismatched_ranked_answer_is_zero_not_half():
    d = grade_answer("DISCOVER-04", "some random portfolio text")
    assert d["score"] == 0.0
    assert d["status"] == "scored"
    assert "undefined" in d["dimensions"].get("reason", "")


def test_after_pilot_keeps_abstentions_visible():
    p = "docs/architecture/benchmark_traces/four_case_after.json"
    if not os.path.exists(p):
        pytest.skip("after trace not present")
    data = json.load(open(p))
    results = {t["task"]: t["pilot"]["result"] for t in data["tasks"]}
    for task in ("KNOW-06", "REASON-03", "REASON-05"):
        assert results[task]["abstained"] is True, task
        assert results[task]["score"] is None, task
        assert "retrieval produced no supporting evidence" in results[task]["abstention_reason"]
    d4 = results["DISCOVER-04"]
    assert d4["abstained"] is False
    assert (d4["score"] or {}).get("score") == 0.0      # grader fix (was 0.5 artifact)


def test_supported_correctness_zero_on_fixed_denominator():
    p = "docs/architecture/benchmark_traces/four_case_after.json"
    data = json.load(open(p))
    results = {t["task"]: t["pilot"]["result"] for t in data["tasks"]}
    n_total = len(results)
    n_abstained = sum(1 for r in results.values() if r.get("abstained"))
    n_scored = sum(1 for r in results.values()
                   if r.get("score") is not None and (r.get("score") or {}).get("score") is not None)
    assert n_total == 4 and n_abstained == 3 and n_scored == 1
    # no case has a retrieval-supported correct answer
    correct_supported = 0
    for r in results.values():
        claims = (r.get("evidence_trace") or {}).get("answer_claims") or []
        if claims and (r.get("score") or {}).get("score") == 1.0:
            correct_supported += 1
    assert correct_supported == 0


def test_blinded_sheets_have_no_provisional_scores():
    sheets = glob.glob("docs/architecture/adjudication_packet/sheets/*_BLINDED.md")
    assert len(sheets) == 48
    for path in sheets:
        text = open(path).read()
        assert "before-repair" not in text and "machine_after" not in text
        assert "provisional machine" not in text.lower()
        assert "abstained:" not in text and "abstention_reason" not in text
        assert "reviewer_1" in text


def test_evidence_traces_record_queries_and_missing_support():
    for task in ("KNOW-06", "REASON-03", "REASON-05"):
        p = f"outputs/evidence_traces/{task}.json"
        assert os.path.exists(p), f"missing trace {p}"
        d = json.load(open(p))
        assert d["generated_queries"]
        assert "results" in d and "relevance_judgments" in d
        assert "answer_claims" in d and "missing_support" in d
        assert d["synthesis_rule"].startswith("claims derived only from retrieved supporting results")