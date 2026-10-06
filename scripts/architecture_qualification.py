#!/usr/bin/env python
"""Architecture qualification harness — Q1..Q9 for PROTACXTEND_AGENTIC_ARCHITECTURE_V1.

Runs real coordinator/tool executions and writes per-case artifacts under
outputs/execution/architecture_qualification/. No fabricated answers: cases that
require missing evidence must abstain; failures are recorded, not hidden.

Usage:
    PROTACXTEND_EXECUTION_MODE=scientific python scripts/architecture_qualification.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "outputs" / "execution" / "architecture_qualification"
RESULTS: list[dict] = []


def _write(q: str, result: dict, state=None, trace=None) -> None:
    d = OUT / q
    d.mkdir(parents=True, exist_ok=True)
    if trace is not None:
        with (d / "trace.jsonl").open("w", encoding="utf-8") as fh:
            for rec in trace:
                fh.write(json.dumps(rec, default=str) + "\n")
    if state is not None:
        dump = state.model_dump(mode="json") if hasattr(state, "model_dump") else state
        (d / "state.json").write_text(json.dumps(dump, indent=1, default=str), encoding="utf-8")
    (d / "result.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    RESULTS.append(result)


def _coord(*args, **kw):
    from protacxtend.architecture import AdaptiveCoordinator
    return AdaptiveCoordinator(*args, **kw)


# ── Q1 normal success ─────────────────────────────────────────────────
def q1():
    c = _coord("Design a CRBN-recruiting PROTAC for BRD4", target="BRD4", e3="CRBN",
               run_id="q1_normal")
    st = c.run()
    kinds = {e.evidence_kind.value for e in st.evidence.evidence_records}
    ok = (st.finalization.terminal_status.value == "SUCCESS"
          and st.protac_design.candidate_structures
          and "RETRIEVED" in kinds and len(c.trace) >= 6)
    _write("q1_normal", {
        "case": "Q1_normal_success", "status": "PASS" if ok else "FAIL",
        "terminal": st.finalization.terminal_status.value,
        "candidate_count": len(st.protac_design.candidate_structures),
        "e3": st.protac_design.e3_recruiters, "evidence_kinds": sorted(kinds),
        "steps": len(c.trace),
        "evidence": "state.json + trace.jsonl",
    }, st, c.trace)
    return ok


# ── Q2 true replanning ────────────────────────────────────────────────
def q2():
    c = _coord("Design a VHL-recruiting PROTAC for BTK", target="BTK", e3="VHL",
               run_id="q2_replan")
    st = c.run()
    revisions = [p for p in (list(st.plan_history) + [st.plan]) if p.revision_reason]
    ok = (bool(revisions) and st.plan.version > 1
          and st.protac_design.e3_recruiters == ["CRBN"]
          and bool(st.protac_design.candidate_structures)
          and any(t["action"] == "revise_plan" for t in c.trace))
    _write("q2_replan", {
        "case": "Q2_true_replanning", "status": "PASS" if ok else "FAIL",
        "plan_versions": [p.version for p in st.plan_history] + [st.plan.version],
        "revision_reason": revisions[0].revision_reason if revisions else "",
        "triggering_evidence_ids": revisions[0].triggering_evidence_ids if revisions else [],
        "final_e3": st.protac_design.e3_recruiters,
        "terminal": st.finalization.terminal_status.value,
        "evidence": "state.plan v2 revision_reason + triggering evidence + trace revise_plan record",
    }, st, c.trace)
    return ok


# ── Q3 tool failure + recovery ────────────────────────────────────────
def q3():
    c = _coord("Design a CRBN-recruiting PROTAC for BRD4", target="BRD4", e3="CRBN",
               run_id="q3_tool_failure")
    c.fault["predict_cooperativity"] = "unavailable"
    st = c.run()
    fallbacks = st.control.fallbacks
    trace_fb = [t for t in c.trace if t.get("fallback")]
    ok = bool(fallbacks) and bool(trace_fb)
    _write("q3_tool_failure", {
        "case": "Q3_tool_failure_recovery", "status": "PASS" if ok else "FAIL",
        "failures": st.control.failures, "fallbacks": fallbacks,
        "fallback_trace_steps": [t["step"] for t in trace_fb],
        "terminal": st.finalization.terminal_status.value,
        "evidence": "state.control.fallbacks + trace fallback field",
    }, st, c.trace)
    return ok


# ── Q4 contradictory evidence ─────────────────────────────────────────
def q4():
    from protacxtend.architecture.ontology import (EvidenceKind, EvidenceStatus,
                                                   EvidenceRecordV1, Claim, Contradiction)
    from protacxtend.architecture.critic import ScientificCritic
    from protacxtend.architecture.state import TherapeuticHypothesisState
    st = TherapeuticHypothesisState()
    st.target_biology.target = "BRD4"
    a = EvidenceRecordV1(evidence_id="evA", claim_id="c_coop",
                         content="5T35 ternary structure supports cooperative geometry",
                         evidence_kind=EvidenceKind.RETRIEVED,
                         evidence_status=EvidenceStatus.SUPPORTED,
                         source="10.1038/nchembio.2329", tool="verified_components")
    b = EvidenceRecordV1(evidence_id="evB", claim_id="c_coop",
                         content="linker strain predicts low cooperativity for this linker",
                         evidence_kind=EvidenceKind.DERIVED,
                         evidence_status=EvidenceStatus.CONTRADICTED,
                         tool="geometry_proxy")
    st.add_evidence(a); st.add_evidence(b)
    st.add_claim(Claim(claim_id="c_coop", statement="alpha>1 is supported",
                       evidence_ids=["evA", "evB"], evidence_kind=EvidenceKind.RETRIEVED,
                       evidence_status=EvidenceStatus.CONTRADICTED))
    st.evidence.contradictions.append(Contradiction(
        contradiction_id="con1", claim_id="c_coop", evidence_id_a="evA", evidence_id_b="evB",
        axis="cooperativity", description="retrieved structure vs derived geometry disagree",
        resolution="UNRESOLVED", decision_relevant=True))
    report = ScientificCritic().evaluate_claim(st, "c_coop")
    ok = (bool(st.evidence.contradictions)
          and report.verdict.value in {"REVISE", "PASS_WITH_LIMITATIONS", "BLOCK"}
          and report.verdict.value != "PASS")
    _write("q4_contradiction", {
        "case": "Q4_contradictory_evidence", "status": "PASS" if ok else "FAIL",
        "contradictions": [c.model_dump() for c in st.evidence.contradictions],
        "critic_verdict": report.verdict.value,
        "findings": [f.model_dump() for f in report.findings],
        "evidence": "state.contradictions + critic findings",
    }, st)
    return ok


# ── Q5 justified abstention ───────────────────────────────────────────
def q5():
    c = _coord("Design a VHL-recruiting PROTAC for MYC", target="MYC", e3="VHL",
               run_id="q5_abstention")
    st = c.run()
    ok = (st.finalization.terminal_status.value in {"JUSTIFIED_ABSTENTION",
                                                    "INSUFFICIENT_EVIDENCE"}
          and not st.protac_design.candidate_structures)
    _write("q5_abstention", {
        "case": "Q5_justified_abstention", "status": "PASS" if ok else "FAIL",
        "terminal": st.finalization.terminal_status.value,
        "termination_reason": st.finalization.termination_reason,
        "candidate_count": len(st.protac_design.candidate_structures),
        "evidence": "state.finalization + no candidate",
    }, st, c.trace)
    return ok


# ── Q6 scientific-mode integrity ──────────────────────────────────────
def q6():
    from protacxtend.architecture.ontology import (EvidenceKind, EvidenceStatus,
                                                   EvidenceRecordV1, Claim)
    from protacxtend.architecture.critic import ScientificCritic
    from protacxtend.architecture.state import TherapeuticHypothesisState
    from protacxtend.runtime.modes import scan_scientific_payload

    demo_allowed = EvidenceRecordV1(evidence_id="d", evidence_kind=EvidenceKind.DEMO,
                                    evidence_status=EvidenceStatus.SUPPORTED).scientific_claim_allowed()
    explor_allowed = EvidenceRecordV1(evidence_id="x", evidence_kind=EvidenceKind.EXPLORATORY,
                                      evidence_status=EvidenceStatus.SUPPORTED).scientific_claim_allowed()
    st = TherapeuticHypothesisState()
    st.add_evidence(EvidenceRecordV1(evidence_id="d", content="demo linker",
                                     evidence_kind=EvidenceKind.DEMO,
                                     evidence_status=EvidenceStatus.SUPPORTED))
    st.add_claim(Claim(claim_id="c", statement="candidate is valid", evidence_ids=["d"],
                       evidence_kind=EvidenceKind.DEMO))
    report = ScientificCritic().evaluate_claim(st, "c")

    # identity/linker policy: a demo-provenance candidate row is flagged by the
    # SCIENTIFIC payload scanner; a verified row is clean.
    demo_row = {"candidate_id": "X", "provenance": {"linker_source": "curated_demo_linker"}}
    verified_row = {"candidate_id": "V", "provenance": {"verified_components": True,
                                                        "source_protac": "dBET1"}}
    demo_flagged = bool(scan_scientific_payload(demo_row))
    verified_clean = not scan_scientific_payload(verified_row)
    ok = (demo_allowed is False and explor_allowed is False
          and report.verdict.value == "BLOCK" and demo_flagged and verified_clean)
    _write("q6_scientific_integrity", {
        "case": "Q6_scientific_mode_integrity", "status": "PASS" if ok else "FAIL",
        "demo_claim_allowed": demo_allowed, "exploratory_claim_allowed": explor_allowed,
        "critic_verdict_on_demo_only_claim": report.verdict.value,
        "demo_row_flagged": demo_flagged, "verified_row_clean": verified_clean,
        "evidence": "ontology policy + critic BLOCK + payload scanner",
    }, st)
    return ok


# ── Q7 model disagreement ─────────────────────────────────────────────
def q7():
    from protacxtend.architecture.ontology import ScientificAxisProfile
    from protacxtend.architecture.deliberation import analyze_disagreement
    axes = ScientificAxisProfile(degradation_ml="HIGH", ternary_geometry="LOW",
                                 permeability="LOW", cooperativity="LOW",
                                 ubiquitination_competence="LOW")
    dis = analyze_disagreement(axes, evidence_ids=["ev_deg", "ev_geom"])
    axes_ok = all(d.axis and d.resolving_action for d in dis)
    ok = len(dis) >= 1 and axes_ok and all(d.axis != "aggregate_score" for d in dis)
    _write("q7_model_disagreement", {
        "case": "Q7_model_disagreement", "status": "PASS" if ok else "FAIL",
        "axes": axes.as_dict(),
        "disagreements": [d.model_dump() for d in dis],
        "evidence": "per-axis disagreement objects with resolving actions (no averaging)",
    })
    return ok


# ── Q8 experiment discrimination ──────────────────────────────────────
def q8():
    from protacxtend.architecture.deliberation import select_discriminating_experiment
    H = ["H1_linker_too_short", "H2_e3_orientation", "H3_permeability"]
    experiments = [
        {"name": "binding_affinity_assay",
         "outcomes": {"H1_linker_too_short": "unchanged", "H2_e3_orientation": "unchanged",
                      "H3_permeability": "unchanged"},
         "controls": ["DMSO"], "decision_after": {}},
        {"name": "linker_length_series_degradation",
         "outcomes": {"H1_linker_too_short": "degradation increases with length",
                      "H2_e3_orientation": "no length dependence; E3 contacts lost",
                      "H3_permeability": "no length dependence; low cellular exposure"},
         "controls": ["parent warhead", "E3-only control"],
         "decision_after": {"H1_linker_too_short": "extend linker",
                            "H2_e3_orientation": "re-model ternary",
                            "H3_permeability": "permeability optimization"}},
        {"name": "permeability_assay",
         "outcomes": {"H1_linker_too_short": "no change", "H2_e3_orientation": "no change",
                      "H3_permeability": "low Papp"},
         "controls": ["propranolol"], "decision_after": {}},
    ]
    chosen = select_discriminating_experiment(H, experiments)
    ok = (chosen.get("experiment") == "linker_length_series_degradation"
          and chosen.get("discrimination_score", 0) == 3
          and set(chosen.get("predicted_outcome_under", {})) == set(H)
          and chosen.get("decision_after_each_outcome"))
    _write("q8_experiment_discrimination", {
        "case": "Q8_experiment_discrimination", "status": "PASS" if ok else "FAIL",
        "hypotheses": H, "chosen": chosen,
        "evidence": "max-distinct-outcome experiment selected with per-hypothesis outcomes",
    })
    return ok


# ── Q9 durability (checkpoint/resume) ─────────────────────────────────
def q9():
    from protacxtend.architecture.coordinator import AdaptiveCoordinator
    c = _coord("Design a CRBN-recruiting PROTAC for BRD4", target="BRD4", e3="CRBN",
               run_id="q9_resume")
    c.understand(); c.initial_plan()
    # run a few steps, then checkpoint
    for _ in range(4):
        d = c._pick_action()
        if d.decision_type.value == "RUN_VERIFIER":
            break
        c.budget.steps_used += 1
        obs_text, obs = c._execute(d)
        eid = obs.get("evidence_id", "")
        e = next((x for x in c.state.evidence.evidence_records if x.evidence_id == eid), None)
        c._record(role="agent", worker=d.selected_worker, action=d.selected_tool or d.decision_type.value,
                  decision=d, observation=obs_text, evidence_ids=[eid] if eid else [],
                  evidence_kind=e.evidence_kind.value if e else "",
                  failure=obs.get("failure", ""), fallback=obs.get("fallback", ""))
        c._maybe_replan(obs)
        if obs.get("no_progress"):
            c._blocked.add(d.selected_tool)
    ckpt = c.checkpoint(OUT / "q9_resume" / "checkpoint.json")
    steps_before = len(c.trace)
    cands_before = len(c.state.protac_design.candidate_structures)
    c2 = AdaptiveCoordinator.resume(ckpt)
    st = c2.run()
    steps_after = len(c2.trace)
    ok = (st.run_identity.run_id == "q9_resume"
          and steps_after > steps_before
          and len(st.protac_design.candidate_structures) == max(1, cands_before)
          and all(t["run_id"] == "q9_resume" for t in c2.trace))
    _write("q9_resume", {
        "case": "Q9_durability", "status": "PASS" if ok else "FAIL",
        "run_id": st.run_identity.run_id,
        "steps_before_checkpoint": steps_before, "steps_after_resume": steps_after,
        "candidates_before": cands_before,
        "candidates_after": len(st.protac_design.candidate_structures),
        "terminal": st.finalization.terminal_status.value,
        "trace_continuity": all(t["run_id"] == "q9_resume" for t in c2.trace),
        "evidence": "checkpoint.json + resumed trace.jsonl",
    }, st, c2.trace)
    return ok


def main() -> int:
    import os
    os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")
    OUT.mkdir(parents=True, exist_ok=True)
    order = [("q1", q1), ("q2", q2), ("q3", q3), ("q4", q4), ("q5", q5),
             ("q6", q6), ("q7", q7), ("q8", q8), ("q9", q9)]
    for name, fn in order:
        try:
            passed = fn()
        except Exception as exc:  # noqa: BLE001
            passed = False
            _write(name, {"case": name, "status": "FAIL",
                          "error": f"{type(exc).__name__}: {exc}"})
        print(f"{name}: {'PASS' if passed else 'FAIL'}")
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "architecture_version": "PROTACXTEND_AGENTIC_ARCHITECTURE_V1",
        "results": RESULTS,
        "passed": sum(1 for r in RESULTS if r.get("status") == "PASS"),
        "failed": sum(1 for r in RESULTS if r.get("status") == "FAIL"),
    }
    (OUT / "qualification_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"]}, indent=1))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
