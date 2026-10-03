"""Tests for the Gate C gold-adjudication tooling.

These tests exercise the operational driver only. They never invent scientific
gold and never approve consensus gold.
"""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gold_adjudication.py"


def _load():
    spec = importlib.util.spec_from_file_location("gold_adjudication", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


ga = _load()


def test_cohens_kappa_perfect_agreement():
    assert ga.cohens_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0


def test_cohens_kappa_total_disagreement_is_low():
    # 2x2 balanced disagreement -> negative or zero kappa
    assert ga.cohens_kappa(["a", "b"], ["b", "a"]) <= 0.0


def test_norm_is_case_and_whitespace_insensitive():
    assert ga._norm("  Approve ") == "approve"
    assert ga._norm(None) == ""


def test_gold_jsonl_has_48_cases_and_no_accepted_answer():
    rows = ga.load_gold()
    assert len(rows) == 48
    # No gold may be pre-approved in the source file.
    assert all(not str(r.get("acceptable_answer") or "").strip() for r in rows)
    assert {r["capability"] for r in rows} == {"KNOW", "REASON", "DESIGN", "DISCOVER"}


def test_empty_reviewer_workbook_fails_validation(tmp_path: Path):
    rows = []
    for g in ga.load_gold():
        rows.append({
            "case_id": g["case_id"], "capability": g.get("capability", ""),
            "split": g.get("split", ""), "gold_answer_type": g.get("gold_answer_type", ""),
            "question": "", "required_entities": "", "acceptable_answer": "",
            "mandatory_answer_elements": "", "acceptable_alternatives": "",
            "evidence_spans": "", "answerability": "", "verdict": "", "confidence": "",
            "reviewer_name": "", "notes": "",
        })
    path = tmp_path / "reviewer_1.csv"
    ga.write_csv(path, ga.REVIEWER_COLUMNS, rows)
    report = ga.validate_workbook(path)
    assert report["n_rows"] == 48
    assert report["errors"]  # empty verdicts/answerability must be rejected


def test_merge_refuses_without_names(tmp_path: Path, monkeypatch):
    """Merge must never set approved=true from unfilled workbooks."""
    dirpath = tmp_path
    for name in ("reviewer_1.csv", "reviewer_2.csv", "adjudicator.csv"):
        rows = []
        for g in ga.load_gold():
            if name == "adjudicator.csv":
                rows.append({"case_id": g["case_id"], "question": "",
                             "reviewer_1_acceptable_answer": "", "reviewer_2_acceptable_answer": "",
                             "reviewer_1_answerability": "", "reviewer_2_answerability": "",
                             "proposed_answer_from_frozen_gt": "", "adjudicator_decision": "",
                             "adjudicator_answerability": "", "adjudicator_acceptable_answer": "",
                             "adjudicator_mandatory_answer_elements": "",
                             "adjudicator_acceptable_alternatives": "",
                             "adjudicator_name": "", "adjudication_notes": ""})
            else:
                rows.append({"case_id": g["case_id"], "capability": "", "split": "",
                             "gold_answer_type": "", "question": "", "required_entities": "",
                             "acceptable_answer": "", "mandatory_answer_elements": "",
                             "acceptable_alternatives": "", "evidence_spans": "",
                             "answerability": "", "verdict": "", "confidence": "",
                             "reviewer_name": "", "notes": ""})
        cols = ga.ADJUDICATOR_COLUMNS if name == "adjudicator.csv" else ga.REVIEWER_COLUMNS
        ga.write_csv(dirpath / name, cols, rows)

    class Args:
        dir = str(dirpath)

    rc = ga.cmd_merge(Args())
    assert rc == 1
    consensus = json.loads((dirpath / "consensus.json").read_text())
    assert consensus["approved"] is False


def test_reviewer_workbooks_are_blinded():
    """The shipped reviewer workbooks must not expose the frozen proposal."""
    for name in ("reviewer_1.csv", "reviewer_2.csv"):
        path = ga.REVIEWED / name
        if not path.exists():
            continue
        header = path.read_text(encoding="utf-8").splitlines()[0]
        assert "proposed_answer_from_frozen_gt" not in header
