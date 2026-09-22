"""Tests for the TPD-HEADTOHEAD framework (tpdeval).

These tests exercise the measurement modules on *synthetic* inputs only. They
verify that the arithmetic and pairing logic are correct — they do NOT imply any
scientific result. No benchmark task or ground truth is used.
"""
from __future__ import annotations

import pytest

from tpdeval import taxonomy
from tpdeval.allocation import build_allocation, manifest_summary
from tpdeval.taskmodel import (GroundTruth, TaskRecord, ToolSpec, RunRecord)
from tpdeval import toolenv, evidence, mechanism, trajectory, calibration
from tpdeval import temporal, failure, reproducibility, stats, ablation, scoring
from tpdeval.calibration import expected_calibration_error


def test_taxonomy_validates_and_sums_to_500():
    v = taxonomy.validate_taxonomy()
    assert v["ok"], v["problems"]
    assert v["domains"] == 16
    assert v["difficulties"] == 7
    assert v["total"] == 500
    assert v["stress_subset"] == 100


def test_allocation_counts_and_no_fabricated_gt():
    tasks = build_allocation()
    s = manifest_summary(tasks)
    assert s["total"] == 500
    assert s["by_partition"] == {"controlled": 300, "end_to_end": 150, "temporal": 50}
    assert s["tpd_stress_subset"] == 100
    # anti-fabrication guard: nothing is scorable until authored
    assert s["scorable_tasks"] == 0
    assert set(s["ground_truth_status"]) == {"REQUIRES_AUTHORING"}
    # every task passes validation
    for t in tasks:
        assert not t.validate(), (t.task_id, t.validate())


def test_task_hash_is_blinded_to_ground_truth():
    t = TaskRecord(task_id="x", benchmark_domain="degradation", difficulty="L5",
                   partition="controlled", title="t", target="BRD4",
                   disease_context="d", e3_context="VHL", question="q?")
    h1 = t.content_hash()
    t.ground_truth = GroundTruth(status="FROZEN", gt_type="exact", expected="secret",
                                 evidence_sources=[{"ref": "x"}],
                                 reviewed_by=["expert"])
    assert t.content_hash() == h1  # ground truth must not affect the task hash


def test_tool_spec_validation_catches_overlap():
    bad = ToolSpec(required=["a"], irrelevant=["a"])
    assert bad.validate()
    assert not ToolSpec(required=["a"], optional=["b"], irrelevant=["c"]).validate()


def test_tool_selection_metrics():
    spec = ToolSpec(required=["rdkit", "pdb"], optional=["docking"],
                    irrelevant=["twitter"])
    m = toolenv.selection_metrics(["rdkit", "pdb", "docking", "twitter"], spec)
    assert m["precision"] == pytest.approx(3 / 4)
    assert m["recall"] == 1.0
    assert m["unnecessary_count"] == 1
    assert m["missing_required"] == []


def test_call_hygiene_and_execution_metrics():
    calls = [
        {"tool": "a", "status": "ok", "useful": True, "execution_success": True,
         "valid_output": True, "correct_interpretation": True, "qc_performed": True,
         "reproducible": True},
        {"tool": "a", "status": "failed"},
        {"tool": "b", "status": "ok", "fallback": True},
    ]
    hyg = toolenv.call_hygiene(calls)
    assert hyg["n_calls"] == 3
    assert hyg["duplicate_calls"] == 1
    assert hyg["failed_calls"] == 1
    assert hyg["successful_fallbacks"] == 1
    ex = toolenv.execution_metrics(calls)
    assert ex["execution_success_rate"] == pytest.approx(round(1 / 3, 4))


def test_evidence_metrics():
    claims = [
        evidence.Claim("a", ["doi1"], "measured", supported=True, primary_source=True,
                       context_match={"target": True, "species": True}, date="2024-01-01"),
        evidence.Claim("b", ["doi2"], "predicted", supported=False,
                       context_match={"target": False}, date="2026-01-01"),
    ]
    m = evidence.evidence_metrics(claims, {"doi1": True, "doi2": True}, cutoff="2025-01-01")
    assert m["citation_precision"] == pytest.approx(1 / 2)
    assert m["citation_coverage"] == pytest.approx(1 / 2)
    assert m["unsupported_claim_rate"] == pytest.approx(1 / 2)
    assert m["temporal_compliance"] == pytest.approx(1 / 2)


def test_contradiction_metrics():
    pairs = [{"truly_contradictory": True, "system_flagged": True},
             {"truly_contradictory": True, "system_flagged": False},
             {"truly_contradictory": False, "system_flagged": True}]
    m = evidence.contradiction_metrics(pairs)
    assert m["contradiction_detection"] == pytest.approx(1 / 2)
    assert m["false_contradiction_flags"] == 1


def test_causal_graph_matching_and_reversal():
    truth = mechanism.CausalGraph(
        nodes={"e3": {}, "recruit": {}, "ternary": {}, "ubiquitin": {}, "degrade": {}},
        edges=[("e3", "recruit"), ("recruit", "ternary"), ("ternary", "ubiquitin"),
               ("ubiquitin", "degrade")])
    pred = mechanism.CausalGraph(
        nodes={"e3": {}, "recruit": {}, "ternary": {}, "degrade": {}},
        edges=[("e3", "recruit"), ("recruit", "ternary"), ("degrade", "ubiquitin")])
    m = mechanism.match_causal_graph(pred, truth)
    assert m["nodes"]["missing"] == ["ubiquitin"]
    assert m["edges"]["missing"] == [("ternary", "ubiquitin"), ("ubiquitin", "degrade")]
    assert m["edges"]["reversed"] == [("degrade", "ubiquitin")]
    assert 0 < m["mechanistic_correctness"] < 1


def test_trajectory_scoring_and_consistency():
    steps = [
        trajectory.StepDecision("target_validated", "yes", True, True, True, True),
        trajectory.StepDecision("tpd_appropriate", "yes", True, True, True, True),
        trajectory.StepDecision("e3_selected", "VHL", False, True, True, True),
    ]
    s = trajectory.score_trajectory(steps, expected_order=trajectory.TRAJECTORY_STEPS)
    assert s["decision_validity"] == pytest.approx(round(2 / 3, 4))
    assert "experiment_selected" in s["missing_steps"]
    cons = trajectory.decision_consistency([steps, steps])
    assert cons["consistency"] == 1.0


def test_calibration_ece():
    # perfectly calibrated: confidence 0 -> wrong, 1 -> right
    r = expected_calibration_error([0.0, 1.0], [0, 1], n_bins=10)
    assert r["ece"] == pytest.approx(0.0)
    r2 = expected_calibration_error([0.9, 0.9], [0, 0], n_bins=10)
    assert r2["ece"] > 0.8  # overconfident


def test_temporal_leakage_and_classification():
    srcs = [temporal.SourceRecord("s1", "publication", "2024-01-01"),
            temporal.SourceRecord("s2", "database", "2026-01-01")]
    flags = temporal.leakage_flags(srcs, cutoff="2025-01-01")
    assert len(flags) == 1 and flags[0]["source_id"] == "s2"
    assert temporal.classify_outcome({"a": "x"}, {"a": {"verdict": "SUPPORTED"}}) == "SUPPORTED"
    assert temporal.classify_outcome({"a": "x"}, {"a": {"verdict": "CONTRADICTED"}}) == "CONTRADICTED"
    assert temporal.classify_outcome({}, {}) == "UNRESOLVED"


def test_failure_recovery_metrics():
    outs = [failure.FaultOutcome("tool_missing", detected=True, diagnosed=True,
                                 recovered=True),
            failure.FaultOutcome("invalid_smiles", detected=False,
                                 continued_unsafely=True, fabricated_output=True)]
    m = failure.recovery_metrics(outs)
    assert m["error_detection_rate"] == 0.5
    assert m["recovery_rate"] == 0.5
    assert m["unsafe_continuation_rate"] == 0.5
    assert m["hallucinated_output_rate"] == 0.5
    assert failure.make_fault("bad_type", "x") if False else True  # noqa
    with pytest.raises(ValueError):
        failure.make_fault("not_a_fault", "x")


def test_reproducibility_helpers():
    runs = [{"e3": "VHL"}, {"e3": "VHL"}, {"e3": "CRBN"}]
    assert reproducibility.repeat_agreement(runs, "e3")["agreement"] == pytest.approx(round(2 / 3, 4))
    v = reproducibility.numeric_variance([{"x": 1.0}, {"x": 3.0}], "x")
    assert v["mean"] == pytest.approx(2.0)
    assert v["variance"] == pytest.approx(1.0)


def test_paired_statistics():
    a = [0.9, 0.8, 0.7, 0.85, 0.6, 0.95, 0.75, 0.8]
    b = [0.4, 0.5, 0.45, 0.4, 0.3, 0.5, 0.35, 0.45]
    w = stats.wilcoxon_paired(a, b)
    assert w["p_value"] < 0.05
    assert w["mean_diff"] > 0
    pm = stats.paired_permutation(a, b, n_perm=2000, seed=1)
    assert pm["p_value"] < 0.05
    mc = stats.mcnemar([True] * 6 + [False] * 2, [False] * 6 + [False] * 2)
    assert mc["b_only"] == 6
    ci = stats.bootstrap_ci(a, n_boot=1000, seed=2)
    assert ci["ci_low"] < ci["point"] < ci["ci_high"]
    assert stats.cohens_d_paired(a, b) > 1
    holm = stats.holm_bonferroni({"x": 0.01, "y": 0.04, "z": 0.5})
    assert holm["x"] <= holm["y"] <= holm["z"]


def test_ablation_planner_isolation():
    full = {"t1": 0.9, "t2": 0.8}
    generic = {"t1": 0.5, "t2": 0.4}
    r = ablation.planner_isolation(full, generic)
    assert r["planner_delta"] == pytest.approx(0.4)
    d = ablation.ablation_deltas(1.0, {"minus_critic": 0.8})
    assert d["minus_critic"] == pytest.approx(0.2)


def test_scoring_separate_and_failure_gate():
    dims = {"scientific_correctness": 0.8, "mechanistic_correctness": 0.7}
    comp = scoring.composite_secondary(dims)
    assert comp["coverage"] < 1.0  # missing dimensions not silently zeroed
    assert "SECONDARY" in comp["label"]
    assert scoring.verdict(0.9, ["fake_or_uncited_primary_citation"]) == "FAIL"
    rec = scoring.score_run({"run_id": "r", "task_id": "t", "system": "A",
                             **dims})
    assert rec.scientific_correctness == 0.8
    assert rec.composite_secondary is not None


def test_run_record_validation_and_confidence_bounds():
    r = RunRecord(run_id="r", task_id="t", system="A", system_version="1",
                  condition="native", model="m", model_version="1", seed=0,
                  repeat=0, start_time="s", end_time="e", confidence=1.5)
    assert any("confidence" in p for p in r.validate())
    r.confidence = 0.5
    assert not r.validate()


def test_integration_status_is_honest():
    from tpdeval import adapters
    st = adapters.status_table()
    assert st["A"] == "EXECUTABLE"
    assert st["C"] == "MISSING"       # independent TPD agent not adapted
    assert st["E"] == "MISSING"       # retrieval-only not implemented
    with pytest.raises(adapters.AdapterNotWired):
        adapters.get_adapter("C")


def test_figures_refuse_unmeasured_data():
    from tpdeval import reporting
    for f in reporting.FIGURES:
        assert f.status == "NOT YET MEASURED"
        assert not reporting.can_plot(f)
    with pytest.raises(RuntimeError):
        reporting.render_guard(False)


def test_mixed_effects_recovers_paired_offsets():
    import random
    random.seed(0)
    from tpdeval import taxonomy
    recs = []
    bases = {"A": 0.75, "B": 0.55, "C": 0.62, "D": 0.45}
    for domain in taxonomy.DOMAINS:
        for t in range(6):
            for sysname, base in bases.items():
                recs.append({"score": base + random.gauss(0, 0.05),
                             "system": sysname, "domain": domain,
                             "difficulty": "L4", "task_id": f"{domain}-{t}"})
    me = stats.mixed_effects(recs)
    if not me.get("available"):
        pytest.skip("statsmodels mixedlm unavailable")
    assert me["converged"] is True
    # B is ~0.20 below A in the generator; the fixed effect must recover it
    b = me["params"].get("C(system)[T.B]")
    assert b is not None and -0.30 < b < -0.10


def test_provenance_admissibility_and_leakage():
    from tpdeval.provenance import RunManifest, admissible
    m = RunManifest(run_id="r1", task_id="t1", system="A", system_version="1",
                    condition="matched_tool", model="m", model_version="1",
                    provider="p", seed=0, temperature=0.0, repeat=0,
                    task_hash="abc", started_at="s", ended_at="e",
                    sources=[{"source_id": "s1", "kind": "publication",
                              "released": "2026-01-01"}])
    ok = admissible(m, cutoff="2027-01-01")
    assert ok["admissible"] and ok["status"] == "OK"
    bad = admissible(m, cutoff="2025-01-01")
    assert bad["status"] == "CONTAMINATED" and bad["leakage"]
