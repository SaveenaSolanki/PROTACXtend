"""Tests for P1 benchmark readiness: matched-tool registry, baselines and the
external-system adapters (Biomni, TPD comparator).

Fast and offline. The external adapters are exercised through a fake command so
the JSON stdin/stdout contract is verified without any real external system.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmark" / "cases"

from benchmark_runner import external  # noqa: E402
from benchmark_runner.baselines import (  # noqa: E402
    LLMBaseline,
    RetrievalOnlyBaseline,
    ToolOnlyBaseline,
    build_baseline,
)
from benchmark_runner.matched_tools import (  # noqa: E402
    MATCHED_TOOLS,
    coverage,
    match_task,
    unmatched_ids,
)
from benchmark_runner.runner import (  # noqa: E402
    AdapterError,
    RunConfig,
    TaskInput,
    build_adapter,
)


def _load_tasks():
    tasks = []
    for path in sorted(CASES.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        tasks.append(TaskInput.from_case(path))
    return tasks


# ══════════════════════════════════════════════════════════════════════
# Matched-tool registry
# ══════════════════════════════════════════════════════════════════════

class TestMatchedTools:
    def test_every_permitted_id_is_matched_across_frozen_cases(self):
        report = coverage(_load_tasks())
        assert report["n_distinct_unmatched"] == 0, report["unmatched_ids"]
        assert report["n_distinct_permitted"] == report["n_distinct_matched"]

    def test_match_task_resolves_agent_tools(self):
        task = TaskInput.from_case(CASES / "DESIGN-01.json")
        matched = match_task(task)
        assert matched["unmatched"] == []
        assert "inspect_smiles" in matched["agent_tools"] or "generate_linkers" in matched["agent_tools"]

    def test_unknown_id_is_reported_not_silently_dropped(self):
        assert unmatched_ids(["rdkit", "totally_made_up"]) == ["totally_made_up"]

    def test_registry_entries_have_backends(self):
        for permitted_id, entry in MATCHED_TOOLS.items():
            assert entry.backends, f"{permitted_id} has no backend"
            assert entry.agent_tools, f"{permitted_id} has no agent tool"


# ══════════════════════════════════════════════════════════════════════
# External adapters (Biomni / TPD comparator)
# ══════════════════════════════════════════════════════════════════════

def _echo_task(task: TaskInput):
    return {
        "status": "ok", "raw": "", "answer": "echoed",
        "provider": "test", "model": "test", "version": "1.0",
        "tool_calls": 1, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
        "artifacts": [], "error": None,
    }


class TestExternalAdapters:
    def test_fail_closed_without_allow_real(self):
        adapter = external.BiomniAdapter("Biomni", allow_real=False)
        with pytest.raises(AdapterError):
            adapter.execute(_load_tasks()[0], {})

    def test_unavailable_when_unconfigured(self, monkeypatch):
        monkeypatch.delenv("PROTACXTEND_BIOMNI_CMD", raising=False)
        adapter = external.BiomniAdapter("Biomni", allow_real=True)
        result = adapter.execute(_load_tasks()[0], {})
        assert result["status"] == "unavailable"
        assert result["answer"] is None
        assert "not configured" in result["error"]

    def test_command_contract_parses_json_stdout(self, monkeypatch):
        script = "import json,sys; json.load(sys.stdin); print(json.dumps({'answer': 'biomni answer'}))"
        monkeypatch.setenv(
            "PROTACXTEND_BIOMNI_CMD",
            f"{sys.executable} -c {json.dumps(script)}",
        )
        monkeypatch.setenv("PROTACXTEND_BIOMNI_VERSION", "biomni-1.2.3")
        adapter = external.BiomniAdapter("Biomni", allow_real=True)
        result = adapter.execute(_load_tasks()[0], {"seed": 0})
        assert result["status"] == "ok"
        assert result["answer"] == "biomni answer"
        assert result["version"] == "biomni-1.2.3"
        assert result["external"]["returncode"] == 0

    def test_nonzero_exit_is_tool_failure(self, monkeypatch):
        monkeypatch.setenv(
            "PROTACXTEND_TPD_COMPARATOR_CMD",
            f"{sys.executable} -c \"import sys; sys.exit(2)\"",
        )
        adapter = external.TPDComparatorAdapter("TPD-comparator", allow_real=True)
        result = adapter.execute(_load_tasks()[0], {})
        assert result["status"] == "tool_failure"

    def test_factory_builds_external_adapters(self):
        assert isinstance(build_adapter("Biomni", allow_real=True), external.BiomniAdapter)
        assert isinstance(build_adapter("TPD-comparator", allow_real=True), external.TPDComparatorAdapter)
        # without allow_real the factory still returns a fail-closed adapter
        stub = build_adapter("Biomni", allow_real=False)
        with pytest.raises(AdapterError):
            stub.execute(_load_tasks()[0], {})


# ══════════════════════════════════════════════════════════════════════
# Baselines
# ══════════════════════════════════════════════════════════════════════

class TestBaselines:
    def test_build_baseline_known_systems(self):
        for system in ("retrieval-only", "tool-only", "Base-LLM-control", "PROTACXtend-offline"):
            assert build_baseline(system).system_id

    def test_retrieval_only_returns_structured_answer(self):
        task = TaskInput.from_case(CASES / "KNOW-01.json")
        answer = RetrievalOnlyBaseline().run(task, offline_only=True)
        assert answer.task_id == "KNOW-01"
        assert answer.status in {"ok", "abstained"}
        assert isinstance(answer.answer, str)

    def test_tool_only_runs_and_preserves_calls(self):
        task = TaskInput.from_case(CASES / "DESIGN-01.json")
        answer = ToolOnlyBaseline().run(task, offline_only=True)
        assert answer.status in {"ok", "abstained"}
        assert isinstance(answer.tool_calls, list)

    def test_llm_baseline_skips_without_credentials(self, monkeypatch):
        from benchmark_runner import live

        monkeypatch.setattr(live, "_api_key", lambda: "")
        answer = LLMBaseline().run(_load_tasks()[0], offline_only=True)
        assert answer.status == "skipped_no_credentials"
        assert answer.answer == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
