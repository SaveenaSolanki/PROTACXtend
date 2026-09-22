"""System adapters for TPD-HEADTOHEAD (Section 3 & 4).

Fail-closed by construction: an adapter that is not wired raises
``AdapterNotWired``. No adapter invents an answer. Integration status is
introspected so the framework can report exactly which systems are executable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tpdeval.systems import SYSTEMS


class AdapterNotWired(RuntimeError):
    pass


@dataclass
class AdapterStatus:
    key: str
    system: str
    wired: bool
    provenance: str
    blocker: str = ""
    external_dependency: str = ""


def integration_status() -> List[AdapterStatus]:
    """Current, evidence-based wiring status. Update only when code exists."""
    return [
        AdapterStatus("A", "PROTACXtend", True,
                      "benchmark_runner.live.PROTACXtendLiveAdapter",
                      external_dependency="protacxtend.agentic"),
        AdapterStatus("B", "Biomni", True,
                      "official biomni 0.0.8 (external venv)",
                      blocker="adapter shim not committed to tpdeval; native-only so far",
                      external_dependency="/tmp/biomni_venv"),
        AdapterStatus("C", "TPD-specific-agent", False, "",
                      blocker="third-party TPD agent/model not selected or adapted",
                      external_dependency="TBD"),
        AdapterStatus("D", "General-LLM", True,
                      "benchmark_runner.live.BaseLLMLiveAdapter",
                      external_dependency="deepseek API"),
        AdapterStatus("E", "Retrieval-only", False, "",
                      blocker="not implemented",
                      external_dependency="permitted DB connectors"),
        AdapterStatus("F", "Tool-only-scripted", False, "",
                      blocker="not implemented",
                      external_dependency="matched tool catalog"),
        AdapterStatus("G", "General-LLM+PROTACXtend-tools", False, "",
                      blocker="not implemented",
                      external_dependency="protacxtend tool registry"),
        AdapterStatus("H", "PROTACXtend-planner+generic-tools", False, "",
                      blocker="not implemented",
                      external_dependency="generic tool shims"),
    ]


def status_table() -> Dict[str, str]:
    return {s.key: ("EXECUTABLE" if s.wired and not s.blocker else
                    ("BLOCKED" if s.wired else "MISSING"))
            for s in integration_status()}


class SystemAdapter:
    key: str = "?"

    def execute(self, task: Dict[str, Any], condition: str) -> Dict[str, Any]:
        raise AdapterNotWired(
            f"adapter {self.key} is not wired; refusing to fabricate a result")

    def tool_catalog(self, condition: str) -> Optional[List[str]]:
        return None


class PROTACXtendAdapter(SystemAdapter):
    key = "A"

    def execute(self, task, condition):
        # Delegates to the existing live adapter; kept thin so the head-to-head
        # runner can drive both frameworks.
        from benchmark_runner.live import PROTACXtendLiveAdapter
        return PROTACXtendLiveAdapter("PROTACXtend", allow_real=True).execute(task, {})


class BaseLLMAdapter(SystemAdapter):
    key = "D"

    def execute(self, task, condition):
        from benchmark_runner.live import BaseLLMLiveAdapter
        return BaseLLMLiveAdapter("Base-LLM-control", allow_real=True).execute(task, {})


_ADAPTERS = {"A": PROTACXtendAdapter, "D": BaseLLMAdapter}


def get_adapter(key: str) -> SystemAdapter:
    if key not in _ADAPTERS:
        raise AdapterNotWired(
            f"system {key} ({SYSTEMS[key].name}) has no committed adapter")
    return _ADAPTERS[key]()
