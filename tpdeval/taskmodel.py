"""Canonical task / run / scoring data model (Section 27).

Every field required by the specification is represented. The model is strict:
a task without authored, citation-backed ground truth is marked
``ground_truth_status = REQUIRES_AUTHORING`` and **cannot** be counted as a
scored benchmark task. This is the anti-fabrication guard.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from tpdeval.taxonomy import DOMAINS, DIFFICULTIES, PARTITIONS

GT_STATUS = ("REQUIRES_AUTHORING", "AUTHORED_UNREVIEWED", "EXPERT_REVIEWED",
             "FROZEN", "CONTRADICTED")

# Ground-truth types and whether they are objectively machine-scorable
GT_TYPES = ("exact", "categorical", "set", "ranking", "constraint", "numeric",
            "causal_graph", "trajectory", "rubric")
OBJECTIVE_GT_TYPES = {"exact", "categorical", "set", "ranking", "constraint",
                      "numeric", "causal_graph", "trajectory"}


@dataclass
class ToolSpec:
    """Required / optional / irrelevant tool declaration for one task (Section 8)."""
    required: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)
    irrelevant: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        problems: List[str] = []
        req, opt, irr = set(self.required), set(self.optional), set(self.irrelevant)
        if req & irr:
            problems.append(f"tools in both required and irrelevant: {sorted(req & irr)}")
        if req & opt:
            problems.append(f"tools in both required and optional: {sorted(req & opt)}")
        if opt & irr:
            problems.append(f"tools in both optional and irrelevant: {sorted(opt & irr)}")
        return problems


@dataclass
class GroundTruth:
    """Authored, citation-backed truth for one task. Never a prediction."""
    gt_type: str = "REQUIRES_AUTHORING"
    expected: Any = None
    mandatory_elements: List[str] = field(default_factory=list)
    accepted_alternatives: List[str] = field(default_factory=list)
    causal_graph: Optional[Dict[str, Any]] = None       # nodes/edges (Section 11)
    decision_trajectory: Optional[List[Dict[str, Any]]] = None  # Section 12
    evidence_sources: List[Dict[str, Any]] = field(default_factory=list)
    temporal: Optional[Dict[str, Any]] = None            # T0/T1 (Section 13)
    status: str = "REQUIRES_AUTHORING"
    authored_by: str = ""
    reviewed_by: List[str] = field(default_factory=list)
    immutable: bool = False

    def validate(self) -> List[str]:
        p: List[str] = []
        if self.status not in GT_STATUS:
            p.append(f"bad gt status {self.status!r}")
        if self.status in ("EXPERT_REVIEWED", "FROZEN"):
            if not self.evidence_sources:
                p.append("reviewed/frozen ground truth requires evidence_sources")
            if self.gt_type == "REQUIRES_AUTHORING":
                p.append("reviewed/frozen ground truth requires a real gt_type")
            if not self.reviewed_by:
                p.append("reviewed/frozen ground truth requires >=1 reviewer")
        if self.gt_type not in GT_TYPES and self.gt_type != "REQUIRES_AUTHORING":
            p.append(f"unknown gt_type {self.gt_type!r}")
        if self.gt_type == "causal_graph" and not self.causal_graph:
            p.append("causal_graph gt requires causal_graph payload")
        if self.gt_type == "trajectory" and not self.decision_trajectory:
            p.append("trajectory gt requires decision_trajectory payload")
        return p

    def is_scorable(self) -> bool:
        return self.status in ("EXPERT_REVIEWED", "FROZEN") and self.gt_type in GT_TYPES


@dataclass
class TaskRecord:
    """One benchmark task (Section 27 'for every task store')."""
    task_id: str
    benchmark_domain: str
    difficulty: str
    partition: str
    title: str
    target: str
    disease_context: str
    e3_context: Optional[str]
    question: str
    available_evidence: List[str] = field(default_factory=list)
    structures: List[str] = field(default_factory=list)
    molecules: List[str] = field(default_factory=list)
    permitted_tools: List[str] = field(default_factory=list)
    tool_spec: ToolSpec = field(default_factory=ToolSpec)
    expected_conclusion: Optional[str] = None
    accepted_alternatives: List[str] = field(default_factory=list)
    required_evidence: List[str] = field(default_factory=list)
    reference_provenance: List[Dict[str, Any]] = field(default_factory=list)
    tpd_stress_subset: bool = False
    temporal_cutoff: Optional[str] = None
    ground_truth: GroundTruth = field(default_factory=GroundTruth)

    def validate(self) -> List[str]:
        p: List[str] = []
        if self.benchmark_domain not in DOMAINS:
            p.append(f"unknown domain {self.benchmark_domain!r}")
        if self.difficulty not in DIFFICULTIES:
            p.append(f"unknown difficulty {self.difficulty!r}")
        if self.partition not in PARTITIONS:
            p.append(f"unknown partition {self.partition!r}")
        if not self.task_id:
            p.append("task_id required")
        if not self.question:
            p.append("question required")
        p += self.tool_spec.validate()
        p += self.ground_truth.validate()
        if self.tpd_stress_subset and self.benchmark_domain not in (
                "e3_selection", "linker_protac_design", "ternary_complex",
                "degradation", "failure_analysis"):
            p.append("tpd_stress_subset tag only valid on the 5 stress domains")
        if self.partition == "temporal" and not self.temporal_cutoff:
            p.append("temporal partition requires temporal_cutoff (T0)")
        return p

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def content_hash(self) -> str:
        # Ground truth excluded from the task hash: tasks are blinded, GT is sealed.
        d = self.to_dict()
        d.pop("ground_truth", None)
        return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:16]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaskRecord":
        d = dict(d)
        d["tool_spec"] = ToolSpec(**d.get("tool_spec", {}))
        d["ground_truth"] = GroundTruth(**d.get("ground_truth", {}))
        return cls(**d)


@dataclass
class RunRecord:
    """One (task, system, condition, repeat) execution (Section 27 'for every run store')."""
    run_id: str
    task_id: str
    system: str
    system_version: str
    condition: str                  # native | matched_tool
    model: str
    model_version: str
    seed: int
    repeat: int
    start_time: str
    end_time: str
    selected_tools: List[str] = field(default_factory=list)
    tool_order: List[str] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)  # params/status/qc
    tool_failures: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    final_answer: Optional[str] = None
    confidence: Optional[float] = None
    claims: List[Dict[str, Any]] = field(default_factory=list)      # per-claim grounding
    trajectory: List[Dict[str, Any]] = field(default_factory=list)  # decision path
    failure_events: List[Dict[str, Any]] = field(default_factory=list)
    efficiency: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    status: str = "ok"
    provenance: Dict[str, Any] = field(default_factory=dict)
    temporal_leakage: List[Dict[str, Any]] = field(default_factory=list)

    def validate(self) -> List[str]:
        p: List[str] = []
        if self.condition not in ("native", "matched_tool"):
            p.append(f"unknown condition {self.condition!r}")
        if self.repeat < 0:
            p.append("repeat must be >= 0")
        if self.status not in ("ok", "partial", "failed", "contaminated", "timeout"):
            p.append(f"unknown status {self.status!r}")
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            p.append("confidence must be in [0,1]")
        return p


@dataclass
class ScoreRecord:
    """For scoring store (Section 27). All dimensions kept separate."""
    run_id: str
    task_id: str
    system: str
    scientific_correctness: Optional[float] = None
    evidence_grounding: Optional[float] = None
    retrieval_correctness: Optional[float] = None
    tool_selection: Optional[float] = None
    tool_execution: Optional[float] = None
    quantitative_correctness: Optional[float] = None
    mechanistic_correctness: Optional[float] = None
    tpd_decision_quality: Optional[float] = None
    experimental_design: Optional[float] = None
    uncertainty_calibration: Optional[float] = None
    failure_recovery: Optional[float] = None
    reproducibility: Optional[float] = None
    temporal_compliance: Optional[float] = None
    future_outcome_match: Optional[float] = None
    efficiency: Optional[float] = None
    final_decision_quality: Optional[float] = None
    composite_secondary: Optional[float] = None
    expert_scores: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    DIMENSIONS = [
        "scientific_correctness", "evidence_grounding", "retrieval_correctness",
        "tool_selection", "tool_execution", "quantitative_correctness",
        "mechanistic_correctness", "tpd_decision_quality", "experimental_design",
        "uncertainty_calibration", "failure_recovery", "reproducibility",
        "temporal_compliance", "future_outcome_match", "efficiency",
        "final_decision_quality",
    ]


# JSON-schema-ish descriptions for the three record families
SCHEMAS: Dict[str, Dict[str, Any]] = {
    "task": {"required": ["task_id", "benchmark_domain", "difficulty", "partition",
                          "question", "tool_spec", "ground_truth"]},
    "run": {"required": ["run_id", "task_id", "system", "condition", "model",
                         "seed", "repeat", "start_time", "end_time"]},
    "score": {"required": ["run_id", "task_id", "system"]},
}
