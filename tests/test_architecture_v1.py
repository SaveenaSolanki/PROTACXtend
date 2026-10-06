"""Architecture v1 contract tests (state, evidence, critic, coordinator, resume).

Fast: network-backed tools are stubbed; local verified-component logic is real.
"""
from __future__ import annotations

import json

import pytest


# ── canonical state ───────────────────────────────────────────────────

def test_canonical_state_has_all_required_sections():
    from protacxtend.architecture.state import TherapeuticHypothesisState
    s = TherapeuticHypothesisState()
    for section in ("run_identity", "request", "biological_context", "target_biology",
                    "protac_design", "interaction_state", "residence",
                    "cellular_pharmacology", "translational", "evidence", "axes",
                    "epistemics", "plan", "control", "finalization"):
        assert hasattr(s, section), section
    assert s.run_identity.architecture_version == "PROTACXTEND_AGENTIC_ARCHITECTURE_V1"
    assert s.interaction_state.ubiquitination_competence == "UNKNOWN"
    assert s.residence.status == "INSUFFICIENT_EVIDENCE"     # no invented residence value


# ── evidence ontology ─────────────────────────────────────────────────

def test_evidence_kind_and_status_are_separate():
    from protacxtend.architecture.ontology import EvidenceKind, EvidenceStatus, EvidenceRecordV1
    r = EvidenceRecordV1(evidence_id="e", evidence_kind=EvidenceKind.MODEL_PREDICTED,
                         evidence_status=EvidenceStatus.PARTIALLY_SUPPORTED)
    assert r.evidence_kind is EvidenceKind.MODEL_PREDICTED
    assert r.evidence_status is EvidenceStatus.PARTIALLY_SUPPORTED


def test_demo_and_exploratory_cannot_back_scientific_claims():
    from protacxtend.architecture.ontology import EvidenceKind, EvidenceStatus, EvidenceRecordV1
    for kind in (EvidenceKind.DEMO, EvidenceKind.EXPLORATORY):
        r = EvidenceRecordV1(evidence_id="x", evidence_kind=kind,
                             evidence_status=EvidenceStatus.SUPPORTED)
        assert r.scientific_claim_allowed() is False
    for kind in (EvidenceKind.OBSERVED, EvidenceKind.RETRIEVED, EvidenceKind.DERIVED,
                 EvidenceKind.MODEL_PREDICTED, EvidenceKind.HYPOTHESIZED):
        assert EvidenceRecordV1(evidence_id="y", evidence_kind=kind).scientific_claim_allowed() is True


# ── critic ────────────────────────────────────────────────────────────

def test_critic_blocks_demo_only_claim_and_passes_supported():
    from protacxtend.architecture.critic import ScientificCritic, CriticVerdictV1
    from protacxtend.architecture.ontology import EvidenceKind, EvidenceStatus, EvidenceRecordV1, Claim
    from protacxtend.architecture.state import TherapeuticHypothesisState
    st = TherapeuticHypothesisState()
    st.add_evidence(EvidenceRecordV1(evidence_id="d", evidence_kind=EvidenceKind.DEMO,
                                     evidence_status=EvidenceStatus.SUPPORTED))
    st.add_claim(Claim(claim_id="c", statement="valid", evidence_ids=["d"],
                       evidence_kind=EvidenceKind.DEMO))
    assert ScientificCritic().evaluate_claim(st, "c").verdict is CriticVerdictV1.BLOCK

    st2 = TherapeuticHypothesisState()
    st2.add_evidence(EvidenceRecordV1(evidence_id="r", evidence_kind=EvidenceKind.RETRIEVED,
                                      evidence_status=EvidenceStatus.SUPPORTED))
    st2.add_claim(Claim(claim_id="c", statement="valid", evidence_ids=["r"],
                        evidence_kind=EvidenceKind.RETRIEVED))
    assert ScientificCritic().evaluate_claim(st2, "c").verdict is CriticVerdictV1.PASS


# ── disagreement / experiment ─────────────────────────────────────────

def test_disagreement_is_per_axis_and_names_a_resolving_action():
    from protacxtend.architecture.ontology import ScientificAxisProfile
    from protacxtend.architecture.deliberation import analyze_disagreement
    axes = ScientificAxisProfile(degradation_ml="HIGH", ternary_geometry="LOW", permeability="LOW")
    dis = analyze_disagreement(axes)
    assert dis and all(d.axis and d.resolving_action and "positions" in d.model_dump() for d in dis)
    assert any("ternary" in d.axis for d in dis)


def test_experiment_selects_max_discrimination():
    from protacxtend.architecture.deliberation import select_discriminating_experiment
    H = ["H1", "H2", "H3"]
    chosen = select_discriminating_experiment(H, [
        {"name": "weak", "outcomes": {"H1": "a", "H2": "a", "H3": "a"}},
        {"name": "strong", "outcomes": {"H1": "a", "H2": "b", "H3": "c"},
         "controls": ["ctrl"], "decision_after": {"H1": "x", "H2": "y", "H3": "z"}},
    ])
    assert chosen["experiment"] == "strong"
    assert chosen["discrimination_score"] == 3
    assert set(chosen["predicted_outcome_under"]) == set(H)


# ── coordinator (stubbed tools, real verified-component logic) ────────

def _stub_runtool(self, tool, params, *, allow_network=False):
    self.budget.tool_calls_used += 1
    if tool == "resolve_target":
        return {"status": "ok", "provider": "stub",
                "scientific_result": {"result": {"data": {"matches": [
                    {"accession": "O60885", "gene": "BRD4", "organism": "Homo sapiens"}]}}}}
    if tool == "retrieve_target_binders":
        return {"status": "ok", "provider": "stub",
                "scientific_result": {"result": {"data": {"binders": [{"name": "JQ1-like"}]}}}}
    if tool == "predict_admet":
        return {"status": "ok", "scientific_result": {"result": {"data": {"mw": 500}}}}
    raise RuntimeError(f"stub: {tool} unavailable")


def _coord(monkeypatch, request, target, e3):
    import protacxtend.architecture.coordinator as co
    monkeypatch.setattr(co.AdaptiveCoordinator, "_run_tool", _stub_runtool, raising=True)
    return co.AdaptiveCoordinator(request, target=target, e3=e3, run_id="t")


def test_coordinator_replans_on_missing_verified_route(monkeypatch):
    c = _coord(monkeypatch, "Design a VHL-recruiting PROTAC for BTK", "BTK", "VHL")
    st = c.run()
    assert st.plan.version >= 2
    assert st.plan.revision_reason and st.plan.triggering_evidence_ids
    assert st.protac_design.e3_recruiters == ["CRBN"]
    assert any(t["action"] == "revise_plan" for t in c.trace)
    assert st.plan_history and st.plan_history[0].version == 1  # old plan preserved


def test_coordinator_abstains_without_source_backed_route(monkeypatch):
    c = _coord(monkeypatch, "Design a VHL-recruiting PROTAC for MYC", "MYC", "VHL")
    st = c.run()
    assert st.finalization.terminal_status.value in {"JUSTIFIED_ABSTENTION", "INSUFFICIENT_EVIDENCE"}
    assert not st.protac_design.candidate_structures


def test_coordinator_falls_back_on_tool_failure(monkeypatch):
    c = _coord(monkeypatch, "Design a CRBN-recruiting PROTAC for BRD4", "BRD4", "CRBN")
    c.fault["predict_cooperativity"] = "unavailable"
    c.run()
    assert c.state.control.fallbacks


def test_coordinator_checkpoint_resume_roundtrip(monkeypatch, tmp_path):
    import protacxtend.architecture.coordinator as co
    c = _coord(monkeypatch, "Design a CRBN-recruiting PROTAC for BRD4", "BRD4", "CRBN")
    c.understand(); c.initial_plan()
    ckpt = c.checkpoint(tmp_path / "ck.json")
    c2 = co.AdaptiveCoordinator.resume(ckpt)
    assert c2.state.run_identity.run_id == "t"
    assert c2.state.plan.version == c.state.plan.version
    st = c2.run()
    assert st.finalization.terminal_status.value in {"SUCCESS", "PARTIAL_SUCCESS"}
    assert st.protac_design.candidate_structures


def test_no_fabricated_residence_or_ubiquitination_values(monkeypatch):
    c = _coord(monkeypatch, "Design a CRBN-recruiting PROTAC for BRD4", "BRD4", "CRBN")
    st = c.run()
    assert st.residence.ternary_residence is None
    assert st.residence.status == "INSUFFICIENT_EVIDENCE"
    # ubiquitination remains UNKNOWN unless a real tool sets it
    assert st.interaction_state.ubiquitination_competence == "UNKNOWN"
