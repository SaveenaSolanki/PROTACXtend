"""Sprint 2B tests: freeze provenance, runner, deterministic + rubric scoring.

ALL runs use DEV fixtures only. None of the 48 frozen benchmark tasks is
executed here.
"""

import json
from pathlib import Path

import pytest

from benchmark_runner import freeze, runner as runner_mod
from benchmark_runner.freeze import (build_freeze_manifest, check_frozen,
                                     assert_frozen, FreezeViolation)
from benchmark_runner.runner import (BenchmarkRunner, RunConfig, TaskInput,
                                     build_adapter, AdapterError)
from benchmark_runner import fixtures as fx
from benchmark_runner import scoring as sc
from benchmark_runner import rubric as rb
from protacxtend.runtime.modes import ExecutionMode

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"


# ── helpers ───────────────────────────────────────────────────────────

def dev_task(kind: str = "perfect", task_id: str = "DEV-1") -> TaskInput:
    return TaskInput(task_id=task_id, capability="KNOW", difficulty="easy",
                     title=f"dev {kind}", question="dev question",
                     supplied_inputs=["dev input"], hidden_information=["none"],
                     permitted_tools=["dev-tool"], forbidden=["ground truth"],
                     contamination_risk="low", data_cutoff_date="2026-08-31",
                     systems=["DEV"], raw={"fixture_kind": kind,
                                           "fixture_name": f"DEV-{kind}"})


def run_kind(kind: str, **cfg) -> dict:
    fx.ensure_fixtures(write_files=False)
    runner = BenchmarkRunner(RunConfig(system_id="DEV", provider="dev",
                                       model="dev-model", seed=1,
                                       mode=ExecutionMode.TEST,
                                       retries=cfg.get("retries", 0),
                                       timeout_s=cfg.get("timeout_s", 60)),
                             benchmark_root=BENCH)
    return runner.run(dev_task(kind=kind))


# ── 1. freeze provenance ─────────────────────────────────────────────

def test_freeze_manifest_matches_frozen_files():
    manifest = json.loads((BENCH / "FREEZE_MANIFEST.json").read_text())
    assert manifest["counts"]["cases"] == 48
    assert manifest["counts"]["ground_truth"] == 48
    assert len(manifest["entries"]) == manifest["counts"]["total"] == 100
    assert_frozen(BENCH)  # no drift


def test_freeze_fails_closed_on_drift(tmp_path):
    root = tmp_path / "bench"
    (root / "cases").mkdir(parents=True)
    (root / "ground_truth").mkdir(parents=True)
    (root / "cases" / "KNOW-01.json").write_text('{"task_id": "KNOW-01"}\n')
    (root / "ground_truth" / "KNOW-01.json").write_text('{"id": "gt"}\n')
    (root / "benchmark_manifest.csv").write_text("x\n")
    (root / "BENCHMARK_PROTOCOL.md").write_text("p\n")
    (root / "BLINDNESS_RULES.md").write_text("b\n")
    (root / "SCORING_RUBRIC.md").write_text("s\n")
    import json as _json
    manifest = build_freeze_manifest(root)
    (root / "FREEZE_MANIFEST.json").write_text(_json.dumps(manifest, indent=2))
    # mutate a frozen file -> fail closed
    (root / "cases" / "KNOW-01.json").write_text('{"task_id": "KNOW-01", "tampered": 1}\n')
    result = check_frozen(root)
    assert not result["ok"]
    with pytest.raises(FreezeViolation):
        assert_frozen(root)


# ── 2. task input + adapters ─────────────────────────────────────────

def test_task_input_from_case(tmp_path):
    case = tmp_path / "DEV-PARSE.json"
    case.write_text(json.dumps({
        "schema_version": "2.0.0", "task_id": "DEV-PARSE", "capability": "KNOW",
        "difficulty": "easy", "title": "t", "scientific_question": "q",
        "supplied_inputs": ["i1"], "hidden_information": ["h"],
        "permitted_tools_databases": ["rdkit"], "forbidden_information": ["gt"],
        "contamination_risk": "low", "data_cutoff_date": "2026-08-31",
        "systems": ["DEV"], "expected_answer": None}) + "\n")
    t = TaskInput.from_case(case)
    assert t.task_id == "DEV-PARSE" and t.capability == "KNOW"


def test_adapters_exist_and_real_systems_are_locked():
    fx.ensure_fixtures(write_files=False)
    for sid in runner_mod.SYSTEM_IDS:
        adapter = build_adapter(sid)  # default allow_real=False
        with pytest.raises(AdapterError):
            adapter.execute(dev_task(), {})
    # DEV adapter is allowed
    adapter = build_adapter("DEV")
    out = adapter.execute(dev_task("perfect"), {})
    assert out["status"] == "ok"


def test_production_runner_refuses_real_tasks():
    # real systems are locked: the run fails closed with a tool_failure envelope
    runner = BenchmarkRunner(RunConfig(system_id="PROTACXtend"), benchmark_root=BENCH)
    env = runner.run(dev_task("perfect"))
    assert env["status"] == "failed"
    assert any("disabled" in w for w in env["warnings"])


# ── 3. runner envelope + capture ─────────────────────────────────────

def test_runner_preserves_raw_and_captures_run_fields():
    env = run_kind("perfect")
    assert env["status"] == "ok"
    assert env["raw_response"] == fx.DEFAULTS["perfect"]["raw"]
    assert env["run"]["tokens_in"] == fx.DEFAULTS["perfect"]["tokens_in"]
    assert env["run"]["tokens_out"] == 60
    assert env["run"]["api_cost_usd"] == 0.001
    assert env["run"]["seed"] == 1
    assert env["run"]["temperature"] == 0.0
    assert env["run"]["started_at"] and env["run"]["ended_at"]
    assert env["metadata"]["fixture_only"] is True
    assert env["artifacts"] == []


def test_runner_schema_compliance():
    env = run_kind("incorrect")
    required = ["benchmark_envelope_version", "base_schema_version", "status",
                "task_id", "capability", "system", "workflow", "metadata",
                "provider", "model", "answer", "summary", "evidence", "tools",
                "artifacts", "warnings", "errors", "provenance", "run"]
    assert set(required).issubset(set(env))
    assert env["benchmark_envelope_version"] == "1.0.0"


def test_runner_partial_and_malformed():
    env = run_kind("partial")
    assert env["status"] == "partial"
    env = run_kind("malformed")
    assert env["status"] == "failed"
    assert env["raw_response"] == "{not valid json"


def test_runner_retries_and_timeout():
    env = run_kind("timeout", retries=2)
    assert env["metadata"]["attempts"] == 3
    assert env["status"] == "failed"
    assert any("timeout" in w for w in env["warnings"])
    # tool failure also retried then recorded
    env2 = run_kind("tool_failure", retries=1)
    assert env2["metadata"]["attempts"] == 2
    assert env2["status"] == "failed"


# ── 4. deterministic scoring ─────────────────────────────────────────

def test_exact_and_categorical_scoring():
    assert sc.exact_score("Q60885", "Q60885") == 1.0
    assert sc.exact_score("q60885 ", "Q60885") == 1.0  # normalized
    assert sc.exact_score("Q1", "Q2") == 0.0
    cat = sc.categorical_score("JQ1 and OTX015 are BRD4 ligands",
                               ["JQ1", "OTX015"], mandatory=["JQ1", "OTX015"])
    assert cat["score"] == 1.0
    cat2 = sc.categorical_score("JQ1 only", ["JQ1", "OTX015"],
                                mandatory=["JQ1", "OTX015"])
    assert cat2["score"] == 0.5


def test_ranked_scoring():
    rs = sc.rank_score([1, 2, 3, 4], [1, 2, 3, 4])
    assert rs["spearman"] == 1.0
    rev = sc.rank_score([4, 3, 2, 1], [1, 2, 3, 4])
    assert rev["spearman"] == -1.0
    top = sc.topk_agreement(["A", "B", "C"], ["A", "B", "D"], k=3)
    assert top["topk"] == pytest.approx(2 / 3, abs=1e-3)


def test_deterministic_scoring_never_llm():
    # score() dispatches deterministically for exact/categorical/ranked
    assert sc.score("exact", "x", "x")["score"] == 1.0
    with pytest.raises(ValueError):
        sc.score("mechanistic_rubric", "a", "b")  # rubrics go to rubric scoring


# ── 5. rubric infrastructure ─────────────────────────────────────────

def test_rubric_schema_anchors_0_4():
    for rt in ("mechanistic_rubric", "design_rubric"):
        schema = rb.validate_rubric_schema(rt)
        assert schema["scale_max"] == 4
        for d in schema["dimensions"]:
            assert set(schema["dimension_anchors"][d]) == {0, 1, 2, 3, 4}


def test_rubric_weighted():
    w = rb.rubric_weighted({"evidence_grounding": 4, "mechanism_completeness": 4,
                            "uncertainty_handling": 4, "conclusion_validity": 4,
                            "hallucination_avoidance": 4}, "mechanistic_rubric")
    assert w["weighted"] == pytest.approx(1.0)
    w0 = rb.rubric_weighted({}, "mechanistic_rubric")
    assert w0["weighted"] == 0.0


def test_expert_review_blind_two_reviewer_export():
    answers = [{"system": "PROTACXtend", "answer": {"a": 1}},
               {"system": "Base-LLM-control", "answer": {"a": 2}}]
    scores1 = {"evidence_grounding": 4, "mechanism_completeness": 4,
               "uncertainty_handling": 3, "conclusion_validity": 4,
               "hallucination_avoidance": 4}
    scores2 = {"evidence_grounding": 4, "mechanism_completeness": 3,
               "uncertainty_handling": 2, "conclusion_validity": 4,
               "hallucination_avoidance": 4}  # uncertainty differs by 1 (tol) -> adjudicated
    presented = rb.anonymize_and_shuffle(answers, seed=5)
    idx = presented[0]["answer_index"]
    reviews = [rb.ExpertReview(answer_index=idx, rubric_type="mechanistic_rubric",
                               dimension_scores=dict(scores1), reviewer_id="R1"),
               rb.ExpertReview(answer_index=idx, rubric_type="mechanistic_rubric",
                               dimension_scores=dict(scores2), reviewer_id="R2")]
    exported = rb.export_expert_review("mechanistic_rubric", answers, reviews, seed=5)
    assert exported["system_ids_blinded"] is True
    blob = json.dumps(exported)
    assert "PROTACXtend" not in blob and "Base-LLM-control" not in blob
    item = exported["items"][0]
    assert len(item["dimension_scores"]) == 2
    res = item["disagreement_resolution"]
    # every dimension resolved (mean adjudication or flagged)
    assert all("adjudicated" in v or v["disagreement"] for v in res.values())
    # two-reviewer IRR available
    assert exported["inter_rater_reliability"]["method"]


def test_irr_kappa():
    k = rb.irr_kappa({"a": 4, "b": 4, "c": 3, "d": 4},
                     {"a": 4, "b": 4, "c": 3, "d": 4})
    assert k["kappa"] == 1.0


# ── 6. fixtures never overlap frozen tasks ───────────────────────────

def test_dev_fixtures_do_not_overlap_frozen_benchmark():
    fx.ensure_fixtures(write_files=False)
    manifest = json.loads((BENCH / "benchmark_manifest.csv").read_text() or "[]") if False else None
    import csv
    rows = list(csv.DictReader(open(BENCH / "benchmark_manifest.csv")))
    real_ids = {r["task_id"] for r in rows}
    assert len(real_ids) == 48
    assert all(r.startswith("DEV-") for r in fx.KINDS) is False  # kinds not ids
    # fixture files/ids are DEV-* and disjoint from the 48
    for kind in fx.KINDS:
        assert f"DEV-{kind}" not in real_ids
