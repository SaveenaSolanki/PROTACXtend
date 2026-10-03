"""Therapeutics audit tests: missing-evidence decisions, context-keyed
freshness/mismatch rejection, no-bypass on every public design entry point,
adversarial + missing-data cases, and KRAS G12C chemistry-block diagnosis."""

from __future__ import annotations

import json
import os
import warnings

import pytest

warnings.filterwarnings("ignore")
os.environ["PROTACXTEND_PLANNER_OFFLINE"] = "1"

from protacxtend.therapeutics.api import (  # noqa: E402
    TherapeuticallyUnsuitable, design_gate, load_assessment, mismatch_reason,
    run_assessment,
)
from protacxtend.therapeutics.record import TargetTherapeuticsAssessment  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Decisions made with missing evidence must be visible, never silent passes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec", ["EGFR", "BRD4", "KRAS G12C"])
def test_window_gate_is_requires_review_when_data_missing(spec):
    rec = run_assessment(spec, offline=True)
    assert rec.blocks["dependency"].status == "unavailable"
    assert rec.blocks["normal_tissue"].status == "unavailable"
    assert rec.decision.gates["therapeutic_window"] == "requires_review"
    assert rec.decision.therapeutic_suitability == "requires_review"
    assert "missing" in rec.decision.suitability_reason.lower()


def test_mechanism_and_suitability_are_separate():
    rec = run_assessment("BRD4", offline=True)
    # mechanism (biology) is justified; suitability (indication) is NOT asserted
    assert rec.decision.verdict == "degradation_justified"
    assert rec.decision.mechanism_rationale and "chemistry" not in rec.decision.mechanism_rationale.lower() or "chemistry and E3 opportunity met" in rec.decision.mechanism_rationale
    assert rec.decision.therapeutic_suitability == "requires_review"
    assert "window data missing" in rec.decision.suitability_reason


# ---------------------------------------------------------------------------
# 2. Context-keyed assessments + freshness/mismatch rejection
# ---------------------------------------------------------------------------

def test_context_keys_are_specific_and_rejected_on_mismatch():
    run_assessment("BRD4", disease="AML (MLL-rearranged)", cell_line="OCI-AML3", offline=True)
    assert load_assessment("BRD4", disease="AML (MLL-rearranged)", cell_line="OCI-AML3") is not None
    # same target, different disease/cell -> NO match (never silently reused)
    assert load_assessment("BRD4", disease="NSCLC", cell_line="A549") is None
    assert "no assessment for exact context" in mismatch_reason("BRD4", "", "NSCLC", "A549")


def test_variant_context_is_distinct():
    # purge any plain-KRAS record so the test is deterministic
    from protacxtend.therapeutics.api import OUT, _index_path
    import json as j
    idx = j.loads(_index_path().read_text()) if _index_path().exists() else {}
    for key in [k for k in idx if k.startswith("kras|")]:
        if key == "kras|g12c||":
            continue
        p_ = (idx[key]["path"])
        if os.path.exists(p_):
            os.remove(p_)
        idx.pop(key)
    j.dump(idx, open(_index_path(), "w"))

    run_assessment("KRAS G12C", offline=True)
    assert load_assessment("KRAS") is None                       # no-variant record must not serve G12C
    assert load_assessment("KRAS G12C") is not None


def test_stale_record_rejected_when_sources_change(monkeypatch):
    run_assessment("BRD4", offline=True)
    assert load_assessment("BRD4") is not None
    # adversarial: sources changed on disk -> current fingerprint differs from
    # the stored one -> the stored record is rejected as stale, never reused.
    import protacxtend.therapeutics.api as api
    monkeypatch.setattr(api, "_source_versions",
                        lambda: {"curated_targets": "changed", "curated_e3": "x",
                                 "context_joined": "y", "disease_template": "z"})
    reason = api.mismatch_reason("BRD4", "", "", "")
    assert "context/source mismatch" in reason
    assert api.load_assessment("BRD4") is None


# ---------------------------------------------------------------------------
# 3. No-bypass through all public design entry points + resume paths
# ---------------------------------------------------------------------------

def test_no_bypass_run_protacpilot():
    run_assessment("KRAS G12C", offline=True)
    from protacxtend.agents.runtime import run_protacpilot
    r = run_protacpilot("Design a PROTAC for KRAS G12C", mode="deterministic",
                        config={"target_spec": "KRAS G12C", "record_run": False})
    assert r.get("status") == "blocked"
    assert "chemistry" in str(r.get("error")) or "gates=" in str(r.get("error"))


def test_no_bypass_run_canonical():
    from protacxtend.canonical.orchestrator import CanonicalOrchestrator
    r = CanonicalOrchestrator().run("Design a PROTAC for KRAS G12C",
                                    config={"target_spec": "KRAS G12C"})
    assert r.status == "blocked"
    assert "design blocked" in (r.errors or [""])[0]


def test_no_bypass_workflow_api_including_resume():
    from protacxtend.workflows.api import run_command
    r = run_command("design", "Design a PROTAC for KRAS G12C", offline=True)
    assert r.get("status") == "blocked"
    r2 = run_command("run", "Design a PROTAC for KRAS G12C", offline=True,
                     resume_from="outputs/workflows/design/whatever/resume_state.json")
    assert r2.get("status") == "blocked"


def test_identity_unknown_blocks():
    rec = run_assessment("ZZZZ9", offline=True)
    assert rec.decision.verdict == "degradation_unsuitable"
    assert rec.decision.gates["identity"] == "block"
    with pytest.raises(TherapeuticallyUnsuitable):
        design_gate("ZZZZ9")


def test_requires_review_not_a_pass_strict_mode():
    run_assessment("EGFR", offline=True)
    with pytest.raises(TherapeuticallyUnsuitable):
        design_gate("EGFR", allow_requires_review=False)


# ---------------------------------------------------------------------------
# 4. KRAS G12C chemistry-block diagnosis
# ---------------------------------------------------------------------------

def test_kras_chemistry_block_diagnosis():
    rec = run_assessment("KRAS G12C", offline=True)
    bs = rec.blocks["binder_structure"]
    assert bs.status == "partial"
    assert "0" in bs.summary or "no packaged binder" in bs.summary
    chem = next(c for c in rec.conclusions if c.dimension == "chemistry_readiness")
    assert chem.verdict == "against_degradation"
    assert any("binder" in m.lower() for m in chem.missing_data)
    assert rec.decision.gates["chemistry"] == "block"
    assert any("chemistry" in m for m in rec.decision.criteria_missed)


# ---------------------------------------------------------------------------
# 5. Assessment record contract
# ---------------------------------------------------------------------------

def test_record_has_context_and_source_versions():
    rec = run_assessment("BRD4", offline=True)
    assert rec.context_fingerprint
    assert rec.source_versions.get("curated_targets")
    assert rec.schema_version == "TargetTherapeuticsAssessment.v1"