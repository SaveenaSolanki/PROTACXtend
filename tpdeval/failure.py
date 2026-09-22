"""Failure-recovery experiment (Section 15).

A controlled fault injector plus recovery metrics. Injection is a *harness*
action; the system under test must detect / diagnose / recover / abstain.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

FAULT_TYPES = [
    "pdb_unavailable",
    "tool_missing",
    "api_timeout",
    "invalid_smiles",
    "deprecated_uniprot_id",
    "protonation_failure",
    "database_disagreement",
    "insufficient_e3_expression",
    "conflicting_papers",
    "admet_failure",
]


@dataclass
class InjectedFault:
    fault_type: str
    target_tool: str
    severity: str = "hard"          # hard | soft
    expected_behaviours: List[str] = field(default_factory=lambda: [
        "detect", "diagnose", "retry", "fallback", "recover", "abstain"])
    payload: Dict[str, Any] = field(default_factory=dict)


def make_fault(fault_type: str, target_tool: str, **payload: Any) -> InjectedFault:
    if fault_type not in FAULT_TYPES:
        raise ValueError(f"unknown fault {fault_type!r}")
    return InjectedFault(fault_type=fault_type, target_tool=target_tool,
                         payload=payload)


@dataclass
class FaultOutcome:
    fault_type: str
    detected: bool = False
    diagnosed: bool = False
    retried: bool = False
    fallback_used: bool = False
    recovered: bool = False
    abstained: bool = False
    continued_unsafely: bool = False
    fabricated_output: bool = False
    final_answer_status: str = "ok"      # ok | abstained | failed


def recovery_metrics(outcomes: Sequence[FaultOutcome]) -> Dict[str, Any]:
    n = len(outcomes) or 1
    def rate(attr: str) -> float:
        return round(sum(1 for o in outcomes if getattr(o, attr)) / n, 4)
    return {
        "n_faults": len(outcomes),
        "error_detection_rate": rate("detected"),
        "diagnosis_rate": rate("diagnosed"),
        "retry_rate": rate("retried"),
        "fallback_rate": rate("fallback_used"),
        "recovery_rate": rate("recovered"),
        "appropriate_abstention_rate": rate("abstained"),
        "unsafe_continuation_rate": rate("continued_unsafely"),
        "hallucinated_output_rate": rate("fabricated_output"),
    }


def apply_fault_plan(plan: Sequence[InjectedFault],
                     executor: Callable[[InjectedFault], Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run each fault through an executor that returns observed behaviour flags."""
    results = []
    for f in plan:
        observed = executor(f)
        results.append({
            "fault_type": f.fault_type, "target_tool": f.target_tool,
            "severity": f.severity, "observed": observed,
        })
    return results
