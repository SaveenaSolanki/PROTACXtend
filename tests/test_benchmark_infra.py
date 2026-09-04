"""Tests for benchmark infrastructure (manifests, task schema, layout)."""

import json

import pytest

from protacxtend.benchmark.manifest import (
    LAYOUT_DIRS,
    discover_agents,
    discover_workflows,
    ensure_layout,
    load_manifest,
    write_manifests,
)
from protacxtend.benchmark.task_schema import BenchmarkTask, new_task, TASK_KINDS


def test_layout_created(tmp_path):
    root = ensure_layout(tmp_path)
    assert (root / "manifests").is_dir()
    for d in LAYOUT_DIRS:
        assert (root / d).is_dir()


def test_manifests_reflect_live_registries(tmp_path):
    # counts must come from the live registries, never hard-coded
    counts = write_manifests(tmp_path)
    agents = load_manifest("agents", tmp_path)
    workflows = load_manifest("workflows", tmp_path)
    tools = load_manifest("tools", tmp_path)

    live_agents = discover_agents()
    live_workflows = discover_workflows()
    assert counts["agents"] == len(agents) == len(live_agents) > 0
    assert counts["workflows"] == len(workflows) == len(live_workflows) >= 14
    assert counts["tools"] == len(tools) > 0

    agent_ids = {a["id"] for a in agents}
    assert agent_ids == {a["id"] for a in live_agents}
    wf_cmds = {w["cmd"] for w in workflows}
    assert wf_cmds == {w["cmd"] for w in live_workflows}


def test_manifest_files_are_valid_json(tmp_path):
    write_manifests(tmp_path)
    for name in ("tools", "agents", "workflows"):
        with open(tmp_path / "manifests" / f"{name}.json", encoding="utf-8") as fh:
            data = json.load(fh)
        assert isinstance(data, list)


def test_task_schema_kinds():
    for kind in TASK_KINDS:
        t = new_task(kind, f"task-{kind}", f"{kind}s/demo")
        d = t.to_dict()
        assert d["kind"] == kind
        assert d["uses_ground_truth"] is False  # safe default
        assert d["status"] == "pending"
    with pytest.raises(ValueError):
        BenchmarkTask(task_id="x", kind="nope", name="x", manifest_ref="x")


def test_prospective_inputs_never_ground_truth():
    # tasks built from pre-outcome inputs must not reference ground truth
    t = new_task("system", "brd4-vhl-case-study", "workflows/run")
    assert t.uses_ground_truth is False
    assert t.ground_truth_ref is None
