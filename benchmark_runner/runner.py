"""Provider-independent adapters + BenchmarkRunner (Sprint 2B).

Design:
- TaskInput: standardized, validated task input (parsed from a frozen case file).
- Adapters: one interface per system (PROTACXtend, Biomni, AI-Co-Scientist
  compatible, base LLM, DeepSeek Flash, Ollama) plus a DEV adapter used only
  with non-benchmark fixtures.
- BenchmarkRunner: executes via an adapter, preserves raw responses, captures
  provider/model/version, seed, temperature, timestamps, latency, tool calls,
  tokens, cost, status/errors and artifacts, and supports retries/timeouts.

NO real benchmark execution: production adapters raise unless `allow_real`
is set (and even then only after freeze verification).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmark_runner import freeze

SYSTEM_IDS = [
    "PROTACXtend", "Biomni", "AI-Co-Scientist-compatible",
    "Base-LLM-control", "DeepSeek-Flash-control", "Local-Ollama-control",
]


class AdapterError(Exception):
    pass


class AdapterTimeout(AdapterError):
    pass


class AdapterToolFailure(AdapterError):
    pass


@dataclass
class TaskInput:
    """Standardized task input (validated against a frozen case record)."""

    task_id: str
    capability: str
    difficulty: str
    title: str
    question: str
    supplied_inputs: List[str]
    hidden_information: List[str]
    permitted_tools: List[str]
    forbidden: List[str]
    contamination_risk: str
    data_cutoff_date: str
    systems: List[str]
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_case(cls, case_path: Path | str) -> "TaskInput":
        import json
        data = json.loads(Path(case_path).read_text(encoding="utf-8"))
        return cls(
            task_id=data["task_id"],
            capability=data["capability"],
            difficulty=data.get("difficulty", ""),
            title=data.get("title", ""),
            question=data.get("scientific_question", ""),
            supplied_inputs=list(data.get("supplied_inputs", [])),
            hidden_information=list(data.get("hidden_information", [])),
            permitted_tools=list(data.get("permitted_tools_databases", [])),
            forbidden=list(data.get("forbidden_information", [])),
            contamination_risk=data.get("contamination_risk", ""),
            data_cutoff_date=data.get("data_cutoff_date", ""),
            systems=list(data.get("systems", [])),
            raw=data,
        )

    def to_run_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id, "capability": self.capability,
            "difficulty": self.difficulty, "title": self.title,
            "scientific_question": self.question,
            "supplied_inputs": self.supplied_inputs,
            "permitted_tools": self.permitted_tools,
            "forbidden": self.forbidden,
            "contamination_risk": self.contamination_risk,
        }


class SystemAdapter:
    """Interface every system implements."""

    system_id: str = "base"

    def execute(self, task: TaskInput, ctx: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class _StubAdapter(SystemAdapter):
    """Refuses real execution (fail closed)."""

    def __init__(self, system_id: str, allow_real: bool = False) -> None:
        self.system_id = system_id
        self.allow_real = allow_real

    def execute(self, task, ctx):
        if not self.allow_real:
            raise AdapterError(
                f"adapter {self.system_id}: real benchmark execution disabled "
                "(Sprint 2B infra only; run with DEV fixtures)")
        raise AdapterError(f"adapter {self.system_id} not implemented")


ADAPTER_FACTORY: Dict[str, type] = {
    "PROTACXtend": _StubAdapter,
    "Biomni": _StubAdapter,
    "AI-Co-Scientist-compatible": _StubAdapter,
    "Base-LLM-control": _StubAdapter,
    "DeepSeek-Flash-control": _StubAdapter,
    "Local-Ollama-control": _StubAdapter,
}


def build_adapter(system_id: str, allow_real: bool = False) -> SystemAdapter:
    if system_id == "DEV":
        return DevFixtureAdapter()
    if system_id not in ADAPTER_FACTORY:
        raise ValueError(f"unknown system {system_id!r}")
    return ADAPTER_FACTORY[system_id](system_id, allow_real=allow_real)


class DevFixtureAdapter(SystemAdapter):
    """Dev-only adapter that replays non-benchmark fixture responses."""

    system_id = "DEV"

    def execute(self, task: TaskInput, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if not task.task_id.startswith("DEV-"):
            raise AdapterError("DevFixtureAdapter refuses non-DEV (benchmark) tasks")
        from benchmark_runner.fixtures import load_fixture_response
        fixture = load_fixture_response(task.raw.get("fixture_kind", "perfect"),
                                        task.raw.get("fixture_name"))
        return {
            "status": fixture["status"],
            "raw": fixture["raw"],
            "answer": fixture.get("answer"),
            "provider": fixture.get("provider", "dev-provider"),
            "model": fixture.get("model", "dev-model"),
            "version": fixture.get("version", "0.0.0"),
            "tool_calls": fixture.get("tool_calls", 0),
            "tokens_in": fixture.get("tokens_in", 0),
            "tokens_out": fixture.get("tokens_out", 0),
            "cost_usd": fixture.get("cost_usd", 0.0),
            "artifacts": fixture.get("artifacts", []),
            "error": fixture.get("error"),
        }


@dataclass
class RunConfig:
    provider: str = "unknown"
    model: str = "unknown"
    version: str = "unknown"
    seed: int = 0
    temperature: float = 0.0
    timeout_s: float = 60.0
    retries: int = 0
    allow_real: bool = False  # infra lock: real systems off unless explicitly allowed
    system_id: str = "PROTACXtend"


class BenchmarkRunner:
    """Executes ONE task through a system adapter (fixtures only in Sprint 2B)."""

    def __init__(self, config: RunConfig, benchmark_root: Path | str,
                 check_freeze: bool = True) -> None:
        self.config = config
        self.root = Path(benchmark_root)
        if check_freeze:
            freeze.assert_frozen(self.root)  # fail closed on drift

    # ── task lifecycle ────────────────────────────────────────────────
    def run(self, task: TaskInput) -> Dict[str, Any]:
        adapter = build_adapter(self.config.system_id, allow_real=self.config.allow_real)
        run_id = uuid.uuid4().hex[:12]
        started = datetime.now(timezone.utc).isoformat()
        t0 = time.monotonic()
        last_error: Optional[str] = None
        attempts = self.config.retries + 1
        outcome: Dict[str, Any] = {}
        for attempt in range(1, attempts + 1):
            try:
                outcome = self._execute_once(adapter, task, attempt)
                break
            except AdapterTimeout as exc:
                last_error = f"timeout: {exc}"
                outcome = {"status": "timeout", "raw": "",
                           "error": last_error}
            except AdapterError as exc:
                last_error = f"tool_failure: {exc}"
                outcome = {"status": "tool_failure", "raw": "",
                           "error": last_error}
        latency_s = round(time.monotonic() - t0, 4)
        ended = datetime.now(timezone.utc).isoformat()
        return self._envelope(task, run_id, outcome, started, ended,
                              latency_s, attempts, last_error)

    def _execute_once(self, adapter, task, attempt) -> Dict[str, Any]:
        ctx = {"attempt": attempt, "seed": self.config.seed,
               "temperature": self.config.temperature,
               "provider": self.config.provider, "model": self.config.model}
        # timeout enforcement (wall-clock guard for dev fixtures)
        deadline = time.monotonic() + self.config.timeout_s
        result = adapter.execute(task, ctx)
        if time.monotonic() > deadline:
            raise AdapterTimeout("exceeded timeout budget")
        if result.get("status") == "timeout":
            raise AdapterTimeout(str(result.get("error") or "timeout"))
        if result.get("status") == "tool_failure":
            raise AdapterToolFailure(str(result.get("error") or "tool failure"))
        return result

    # ── result envelope (RESULT_SCHEMA.json) ──────────────────────────
    def _envelope(self, task, run_id, outcome, started, ended, latency_s,
                  attempts, last_error) -> Dict[str, Any]:
        status = outcome.get("status", "error")
        errors = [outcome.get("error")] if outcome.get("error") else []
        env = {
            "benchmark_envelope_version": "1.0.0",
            "base_schema_version": "1.0.0",
            "status": "ok" if status == "ok" else ("partial" if status == "partial"
                                                   else "failed"),
            "task_id": task.task_id,
            "capability": task.capability,
            "system": self.config.system_id,
            "workflow": "KNOW-REASON-DESIGN-DISCOVER",
            "metadata": {
                "run_id": run_id,
                "attempts": attempts,
                "fixture_only": not self.config.allow_real,
                "frozen_at": freeze.load_freeze_manifest(self.root).get("frozen_at"),
            },
            "provider": outcome.get("provider", self.config.provider),
            "model": outcome.get("model", self.config.model),
            "provider_model_version": outcome.get("version", self.config.version),
            "answer": outcome.get("answer"),
            "summary": (f"task {task.task_id} -> {self.config.system_id}: {status}"
                        if status in ("ok", "partial")
                        else f"task {task.task_id} -> {self.config.system_id}: failed ({status})"),
            "evidence": [],
            "tools": [],
            "artifacts": list(outcome.get("artifacts", [])),
            "warnings": [last_error] if status in ("timeout", "tool_failure") else [],
            "errors": errors,
            "provenance": [{"tool": f"adapter:{self.config.system_id}",
                            "source": "dev-fixture" if not self.config.allow_real else "live"}],
            "run": {
                "seed": self.config.seed,
                "temperature": self.config.temperature,
                "repeat": 1,
                "tool_calls": int(outcome.get("tool_calls", 0)),
                "runtime_s": latency_s,
                "tokens_in": outcome.get("tokens_in"),
                "tokens_out": outcome.get("tokens_out"),
                "api_cost_usd": outcome.get("cost_usd"),
                "provider_model_version": outcome.get("version", self.config.version),
                "blinded": True,
                "started_at": started,
                "ended_at": ended,
            },
            "raw_response": outcome.get("raw", ""),  # always preserved
        }
        # optional scoring stub
        env.setdefault("scoring", None)
        return env


def parse_case(path: Path | str) -> TaskInput:
    return TaskInput.from_case(path)
