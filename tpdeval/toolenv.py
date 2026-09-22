"""Tool-selection and tool-execution experiments (Sections 8 & 9).

Everything is computed from a harness-recorded call log — never from model
self-report. Execution is decomposed, not collapsed to success/failure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from tpdeval.taskmodel import ToolSpec


def _as_set(xs: Sequence[str]) -> Set[str]:
    return {str(x) for x in xs}


def selection_metrics(selected: Sequence[str], spec: ToolSpec) -> Dict[str, Any]:
    """Section 8 metrics: precision, recall, efficiency, call hygiene."""
    sel = _as_set(selected)
    required = _as_set(spec.required)
    optional = _as_set(spec.optional)
    irrelevant = _as_set(spec.irrelevant)
    appropriate = sel & (required | optional)
    unnecessary = sel & irrelevant
    precision = (len(appropriate) / len(sel)) if sel else 0.0
    recall = (len(sel & required) / len(required)) if required else 1.0
    return {
        "selected": sorted(sel),
        "required": sorted(required),
        "appropriate_count": len(appropriate),
        "unnecessary_count": len(unnecessary),
        "unnecessary": sorted(unnecessary),
        "missing_required": sorted(required - sel),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4)
        if (precision + recall) else 0.0,
    }


def call_hygiene(tool_calls: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Duplicate / failed / fallback counts from the call log."""
    names = [str(c.get("tool", "")) for c in tool_calls]
    seen: Set[str] = set()
    duplicates = 0
    for n in names:
        if n in seen:
            duplicates += 1
        seen.add(n)
    failed = sum(1 for c in tool_calls if c.get("status") in ("failed", "error", "timeout"))
    fallbacks = sum(1 for c in tool_calls if c.get("fallback") is True)
    return {
        "n_calls": len(tool_calls),
        "n_unique_tools": len(seen),
        "duplicate_calls": duplicates,
        "failed_calls": failed,
        "successful_fallbacks": fallbacks,
    }


def tool_efficiency(useful_successes: int, total_calls: int) -> float:
    return round(useful_successes / total_calls, 4) if total_calls else 0.0


EXEC_STEPS = ("correct_tool", "correct_input", "correct_parameterization",
              "execution_success", "valid_output", "qc_performed",
              "correct_interpretation", "provenance_captured")


def execution_metrics(tool_calls: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Section 9: separate execution success / output validity / interpretation /
    QC / reproducibility. Each call carries explicit boolean flags."""
    n = len(tool_calls) or 1
    def frac(step: str) -> float:
        return round(sum(1 for c in tool_calls if c.get(step) is True) / n, 4)
    per_step = {step: frac(step) for step in EXEC_STEPS}
    reproducible = round(
        sum(1 for c in tool_calls if c.get("reproducible") is True) / n, 4)
    return {
        "n_calls": len(tool_calls),
        "execution_success_rate": frac("execution_success"),
        "output_validity_rate": frac("valid_output"),
        "interpretation_accuracy": frac("correct_interpretation"),
        "qc_completion": frac("qc_performed"),
        "reproducibility": reproducible,
        "step_breakdown": per_step,
    }


@dataclass
class ToolExperiment:
    """Aggregates one system's tool behaviour across tasks (Section 8/9)."""
    per_task: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def add_task(self, task_id: str, selected: Sequence[str], spec: ToolSpec,
                 tool_calls: Sequence[Dict[str, Any]]) -> None:
        sel = selection_metrics(selected, spec)
        hyg = call_hygiene(tool_calls)
        useful = sum(1 for c in tool_calls
                     if c.get("useful") is True and c.get("status") == "ok")
        sel.update(hyg)
        sel["tool_efficiency"] = tool_efficiency(useful, hyg["n_calls"])
        sel["execution"] = execution_metrics(tool_calls)
        self.per_task[task_id] = sel

    def aggregate(self) -> Dict[str, Any]:
        if not self.per_task:
            return {}
        keys = ("precision", "recall", "f1", "tool_efficiency", "duplicate_calls",
                "failed_calls", "successful_fallbacks")
        agg = {k: round(sum(v.get(k, 0.0) for v in self.per_task.values())
                        / len(self.per_task), 4) for k in keys}
        exec_keys = ("execution_success_rate", "output_validity_rate",
                     "interpretation_accuracy", "qc_completion", "reproducibility")
        agg["execution"] = {
            k: round(sum(v["execution"].get(k, 0.0) for v in self.per_task.values())
                     / len(self.per_task), 4) for k in exec_keys}
        return agg
