"""
State + NodeResult foundation for agentic ProtacPilot.
========================================================

This is the layer everything else routes on. One file, state.py.

Three design properties that define the whole system:
  - decision_log uses operator.add → genuinely append-only, no node can
    overwrite another's reasoning
  - retry_counts increments through a reducer → a node just returns
    {"ternary": 1} and never has to read-then-write the old count
    (which is where race conditions hide)
  - evidence accumulates rather than replaces → a repair loop's second
    pass adds to what the first pass learned instead of clobbering it
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from operator import add
from typing import Annotated, Any, TypedDict


# ── Controlled vocabularies ──────────────────────────────────────────
# Reason codes replace free-text `thought` strings. A closed set is what
# makes decisions routable and aggregatable across runs.

class ReasonCode(str, Enum):
    TERNARY_CONF_OK        = "ternary_conf_ok"
    TERNARY_CONF_LOW      = "ternary_conf_low"
    OUT_OF_DOMAIN          = "out_of_domain"
    NO_VALID_CONFORMER     = "no_valid_conformer"
    ENSEMBLE_CONSENSUS     = "ensemble_consensus"
    ENSEMBLE_DISAGREE      = "ensemble_disagree"
    EVIDENCE_INSUFFICIENT  = "evidence_insufficient"
    RETRY_BUDGET_EXHAUSTED = "retry_budget_exhausted"
    HUMAN_REQUIRED         = "human_required"
    HARD_ERROR             = "hard_error"


class FailureClass(Enum):
    NO_VALID_CONFORMER = auto()
    LOW_CONFIDENCE     = auto()
    OUT_OF_DOMAIN      = auto()
    TOOL_TIMEOUT       = auto()
    MISSING_INPUT      = auto()
    HARD_ERROR         = auto()


# Failure → recovery action. The router reads this table; it never
# branches on failure inline. Adding a failure mode = one row here.
FAILURE_RESPONSES: dict[FailureClass, str] = {
    FailureClass.NO_VALID_CONFORMER: "retry_relaxed_params",
    FailureClass.LOW_CONFIDENCE:     "escalate_ensemble",
    FailureClass.OUT_OF_DOMAIN:      "flag_and_continue",
    FailureClass.TOOL_TIMEOUT:       "retry_once",
    FailureClass.MISSING_INPUT:      "human_gate",
    FailureClass.HARD_ERROR:         "abort_candidate",
}


# ── The structured decision record ───────────────────────────────────

@dataclass(frozen=True)
class DecisionLog:
    node: str
    decision_type: str               # "accept" | "retry" | "escalate" | "gate" | "abort"
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[str, ...]    # keys into state["evidence"]
    tool_version: str
    confidence: float
    next_proposed_node: str
    failure_class: FailureClass | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the append-only decision_log (JSON-safe)."""
        return {
            "node": self.node,
            "decision_type": self.decision_type,
            "reason_codes": [r.value if hasattr(r, "value") else str(r) for r in self.reason_codes],
            "evidence_refs": list(self.evidence_refs),
            "tool_version": self.tool_version,
            "confidence": self.confidence,
            "next_proposed_node": self.next_proposed_node,
            "failure_class": self.failure_class.name if self.failure_class else None,
        }


# ── What every node returns ──────────────────────────────────────────
# A node returns a PARTIAL state update. LangGraph merges it via the
# reducers declared on WorkflowState. No node mutates state in place.

@dataclass
class NodeResult:
    updates: dict[str, Any] = field(default_factory=dict)   # evidence/candidate changes
    decision: DecisionLog | None = None
    retry_bump: str | None = None    # name of the retry counter to increment, if any

    def to_state(self) -> dict[str, Any]:
        out = dict(self.updates)
        if self.decision is not None:
            out["decision_log"] = [self.decision]           # reducer=add → appended
        if self.retry_bump is not None:
            out["retry_counts"] = {self.retry_bump: 1}       # reducer sums → increments
        return out


# ── Reducers ─────────────────────────────────────────────────────────

def merge_evidence(old: dict, new: dict) -> dict:
    """Shallow-merge accumulated evidence; new keys win on collision."""
    return {**old, **new}

def sum_counts(old: dict[str, int], new: dict[str, int]) -> dict[str, int]:
    """Increment retry counters. {'ternary': 1} bumps the existing count."""
    out = dict(old)
    for k, v in new.items():
        out[k] = out.get(k, 0) + v
    return out


# ── The state object ─────────────────────────────────────────────────

class WorkflowState(TypedDict):
    target: dict                                        # POI + E3 context (set once)
    candidates: list                                    # last-write-wins
    evidence: Annotated[dict, merge_evidence]           # accumulates across nodes
    decision_log: Annotated[list, add]                  # append-only
    retry_counts: Annotated[dict, sum_counts]           # increments
    status: str