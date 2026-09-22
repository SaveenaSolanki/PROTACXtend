"""
P0 regression / provenance / replay tests for ``predict_degradation``.
====================================================================

These tests lock the fix for the Chemprop/fallback-provenance defect:

  1. REGRESSION — RDKit's ``MolFromSmiles`` is a pybind11 binding and raises
     ``TypeError: No registered converter ...`` when handed a float/None.
     ``Chem.MolFromSmiles('')`` additionally returns an *empty* mol (not
     ``None``), so an empty/NaN SMILES slipped past the old filter, was written
     to CSV as NaN, and made the Chemprop CLI crash on a float. Non-string and
     empty inputs must never reach Chemprop, and must never fabricate a number.

  2. PROVENANCE — the three required outcomes are explicit:
        PRIMARY_SUCCESS                       -> result_source, no fallback
        PRIMARY_FAILURE + FALLBACK_SUCCESS    -> result_source=fallback,
                                                 degraded_fallback=True,
                                                 primary_error / fallback_reason /
                                                 fallback_backend recorded
        PRIMARY_FAILURE + FALLBACK_FAILURE    -> status=NOT_AVAILABLE, no numbers

  3. REPLAY — deterministic given identical (mocked) backend responses.

The expensive/subprocess-backed backends are monkeypatched so the suite is
fast and hermetic; the live backends have their own contract tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import protacxtend.tools.degradation_endpoint as dep
import protacxtend.tools.uncertainty_aware_prediction as uap
from protacxtend.tools.degradation_endpoint import (
    _coerce_smiles,
    _is_valid_smiles,
    predict_degradation_endpoint,
    predict_degradation_batch,
)

VALID = "CC(=O)Oc1ccccc1C(=O)O"


# ── deterministic fake backends ───────────────────────────────────────

def _chemprop_ok(smiles_list, use_conformal=True):
    return [
        {
            "smiles": s,
            "dc50_nM": 42.0,
            "log_dc50": 1.6232,
            "unc_log10": 0.5,
            "ad_status": "in_domain",
            "nn_tanimoto": 0.7,
            "verdict": "high_confidence",
            "confidence": 0.9,
        }
        for s in smiles_list
    ]


def _chemprop_raise(*a, **k):
    raise RuntimeError("forced_chemprop_down")


def _multitarget_ok(smiles_list):
    rows = [
        {"smiles": s, "log_dc50": 1.62, "dmax": 88.0}
        for s in smiles_list
        if isinstance(s, str) and s
    ]
    return {"ok": True, "rows": rows, "n_valid": len(rows)}


def _multitarget_fail(*a, **k):
    return {"ok": False, "reason": "forced_multitarget_failure"}


def _tack_ok(smiles, e3_ligase="", cell_line="", target=""):
    return {
        "dc50_nM": 33.0,
        "log_dc50": 1.5185,
        "dmax_pct": 77.0,
        "active": True,
        "active_prob": 0.9,
        "provenance": {"model": "tack-style-v1", "val_metrics": {"dc50_rho": 0.8}},
    }


def _tack_none(*a, **k):
    return None


@pytest.fixture
def backends(monkeypatch):
    """Install deterministic, hermetic fake backends."""
    monkeypatch.setattr(uap, "predict_with_uncertainty", _chemprop_ok)
    monkeypatch.setattr(dep, "_run_multitarget", _multitarget_ok)
    monkeypatch.setattr(dep, "_tack_primary", _tack_ok)
    return monkeypatch


# ── 1. regression: the Chemprop TypeError ─────────────────────────────

class TestChempropTypeErrorRegression:
    @pytest.mark.parametrize("bad", [123.0, 0, None, float("nan"), b"CCO"])
    def test_coerce_never_returns_non_string(self, bad):
        assert isinstance(_coerce_smiles(bad), str)

    @pytest.mark.parametrize("bad", [123.0, None, float("nan"), "", "not-a-smiles"])
    def test_is_valid_smiles_rejects_bad(self, bad):
        assert _is_valid_smiles(bad) is False

    def test_empty_smiles_is_not_valid(self):
        # Regression guard: RDKit returns an EMPTY mol (not None) for ''.
        from rdkit import Chem
        assert Chem.MolFromSmiles("") is not None
        assert _is_valid_smiles("") is False

    def test_multitarget_float_does_not_raise(self):
        # Will subprocess only if RDKit considers something valid; nothing here.
        res = dep._run_multitarget([123.0, None, float("nan")])
        assert res["ok"] is True
        assert res["n_valid"] == 0
        assert all(r is None for r in res["rows"])

    def test_endpoint_float_returns_not_available(self):
        r = predict_degradation_endpoint(123.0)
        assert r.status == "NOT_AVAILABLE"
        assert r.dc50_nM is None and r.dmax_pct is None
        assert r.primary_error == "invalid_smiles"

    def test_batch_with_nan_and_empty_is_not_available(self):
        rows = predict_degradation_batch(
            [123.0, None, float("nan"), ""], candidate_ids=list("abcd")
        )
        assert [r["status"] for r in rows] == ["NOT_AVAILABLE"] * 4
        assert all(r["dc50_nM"] is None and r["dmax_pct"] is None for r in rows)

    def test_chemprop_batch_filters_empty_and_nan(self):
        from protacxtend.tools.chemprop_degradation import predict_log_dc50_batch
        res = predict_log_dc50_batch(["", float("nan"), None])
        assert res["ok"] is True
        assert res["n_valid"] == 0
        assert res["dc50_nM"] == [None, None, None]

    def test_uncertainty_chemprop_filters_empty(self):
        from protacxtend.tools.uncertainty_aware_prediction import _run_chemprop_predict
        res = _run_chemprop_predict(["", float("nan")], uap.ENSEMBLE_PATHS)
        assert res["ok"] is True
        assert res["n_valid"] == 0


# ── 2. provenance state machine ───────────────────────────────────────

class TestProvenanceStateMachine:
    def test_primary_success_uses_primary_no_fallback(self, backends):
        r = predict_degradation_endpoint(VALID)
        assert r.status == "OK"
        assert r.result_source == "tack-style-v1"
        assert r.degraded_fallback is False
        assert r.primary_error == ""
        assert r.fallback_reason == ""
        assert r.fallback_backend == ""
        assert r.dc50_nM == 33.0
        assert r.dmax_pct == 77.0

    def test_primary_failure_fallback_success_records_provenance(self, monkeypatch):
        monkeypatch.setattr(uap, "predict_with_uncertainty", _chemprop_ok)
        monkeypatch.setattr(dep, "_run_multitarget", _multitarget_ok)
        monkeypatch.setattr(dep, "_tack_primary", _tack_none)
        r = predict_degradation_endpoint(VALID)
        assert r.status == "OK"
        assert r.result_source == "chemprop"
        assert r.degraded_fallback is True
        assert r.primary_error == "tack-style-v1:unavailable"
        assert r.fallback_reason == "primary_unavailable"
        assert r.fallback_backend == "chemprop"
        assert r.dc50_nM == 42.0
        assert r.dmax_pct == 88.0

    def test_cross_check_failure_makes_degradation_visible(self, monkeypatch):
        # PRIMARY (TACK) works; the Chemprop cross-check fails. Previously
        # degraded_fallback was reset to False and the broken path vanished.
        monkeypatch.setattr(uap, "predict_with_uncertainty", _chemprop_raise)
        monkeypatch.setattr(dep, "_run_multitarget", _multitarget_fail)
        monkeypatch.setattr(dep, "_tack_primary", _tack_ok)
        r = predict_degradation_endpoint(VALID)
        assert r.status == "OK"
        assert r.result_source == "tack-style-v1"
        assert r.degraded_fallback is True
        assert "chemprop" in r.primary_error
        assert r.fallback_backend == "tack-style-v1"

    def test_primary_and_fallback_failure_is_not_available(self, monkeypatch):
        monkeypatch.setattr(uap, "predict_with_uncertainty", _chemprop_raise)
        monkeypatch.setattr(dep, "_run_multitarget", _multitarget_fail)
        monkeypatch.setattr(dep, "_tack_primary", _tack_none)
        r = predict_degradation_endpoint(VALID)
        assert r.status == "NOT_AVAILABLE"
        assert r.result_source == "none"
        assert r.degraded_fallback is True
        assert r.primary_error  # both failures recorded
        assert r.fallback_reason == "all_backends_failed"
        # No fabricated degradation prediction.
        assert r.dc50_nM is None
        assert r.dmax_pct is None
        assert r.log_dc50 is None
        assert r.activity_class == "unknown"
        assert r.confidence == 0.0

    def test_batch_fallback_dmax_not_dropped(self, monkeypatch):
        # Regression for the missing SMILES join: the multi-target Dmax head
        # used to be silently dropped in the batch path, leaving 500/50 fabrications.
        monkeypatch.setattr(uap, "predict_with_uncertainty", _chemprop_ok)
        monkeypatch.setattr(dep, "_run_multitarget", _multitarget_ok)
        monkeypatch.setattr(dep, "_tack_primary", _tack_none)
        rows = predict_degradation_batch([VALID], candidate_ids=["c1"])
        r = rows[0]
        assert r["result_source"] == "chemprop"
        assert r["chemprop_dmax_pct"] == 88.0
        assert r["dmax_pct"] == 88.0
        assert r["dc50_nM"] == 42.0

    def test_batch_both_fail_not_available(self, monkeypatch):
        monkeypatch.setattr(uap, "predict_with_uncertainty", _chemprop_raise)
        monkeypatch.setattr(dep, "_run_multitarget", _multitarget_fail)
        monkeypatch.setattr(dep, "_tack_primary", _tack_none)
        rows = predict_degradation_batch([VALID], candidate_ids=["c1"])
        r = rows[0]
        assert r["status"] == "NOT_AVAILABLE"
        assert r["dc50_nM"] is None and r["dmax_pct"] is None
        assert r["primary_error"]
        assert r["fallback_reason"] == "all_backends_failed"

    def test_result_source_always_populated(self, backends):
        for smiles in (VALID, "not-a-smiles", 123.0):
            r = predict_degradation_endpoint(smiles)
            assert r.result_source != ""


# ── 3. replay / determinism ───────────────────────────────────────────

class TestReplay:
    def test_endpoint_replay_identical(self, backends):
        a = predict_degradation_endpoint(VALID).model_dump()
        b = predict_degradation_endpoint(VALID).model_dump()
        assert a == b

    def test_batch_replay_identical(self, backends):
        a = predict_degradation_batch([VALID, "CCO"], candidate_ids=["c1", "c2"])
        b = predict_degradation_batch([VALID, "CCO"], candidate_ids=["c1", "c2"])
        assert a == b

    def test_fallback_replay_identical(self, monkeypatch):
        monkeypatch.setattr(uap, "predict_with_uncertainty", _chemprop_ok)
        monkeypatch.setattr(dep, "_run_multitarget", _multitarget_ok)
        monkeypatch.setattr(dep, "_tack_primary", _tack_none)
        a = predict_degradation_endpoint(VALID).model_dump()
        b = predict_degradation_endpoint(VALID).model_dump()
        assert a == b
        assert a["result_source"] == "chemprop"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
