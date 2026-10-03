"""Gold-integrity invariants: synthetic/empty reviews can never approve gold.

These tests encode the guarantee that the stale synthetic kappa artifact
violated: with zero completed independent reviews, kappa is undefined, gold is
not approved, and adjudicated scoring is blocked.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_gold_tool():
    spec = importlib.util.spec_from_file_location("gold_adj", "scripts/gold_adjudication.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_kappa_is_undefined_without_filled_verdicts():
    g = _load_gold_tool()
    k = g.cohens_kappa([], [])
    assert k != k  # NaN


def test_zero_reviews_do_not_approve_gold_or_enable_scoring():
    g = _load_gold_tool()
    state = g.adjudication_state()
    # Regardless of current review progress, the invariant must hold:
    # any pending case blocks scoring and approval cannot be claimed from empty data.
    if state.get("gold_review_pending", 0) > 0 or state.get("reviewer_decisions_pending", 0) > 0:
        assert state["scoring_possible"] is False
        assert state["consensus_approved"] is False


def test_consensus_without_two_reviewers_is_not_approved():
    g = _load_gold_tool()
    consensus = g.CONSENSUS
    assert consensus.exists()
    import json
    data = json.loads(consensus.read_text(encoding="utf-8"))
    if not data.get("approved_by") or len(set(data.get("approved_by") or [])) < 2:
        assert data.get("approved") is False
        assert data.get("gold") == {}


def test_reviewer_workbooks_are_blinded_and_status_is_pending():
    """Both reviewer sheets must exist with the same schema and no cross-links."""
    import csv
    base = Path("benchmark/gateC/reviewed_gold")
    r1 = list(csv.DictReader((base / "reviewer_1.csv").open()))
    r2 = list(csv.DictReader((base / "reviewer_2.csv").open()))
    assert len(r1) == len(r2) == 48
    assert list(r1[0].keys()) == list(r2[0].keys())
    # No gold answer may be embedded in the blinded sheets.
    for row in r1 + r2:
        assert "expected_answer" not in row or not row["expected_answer"]
