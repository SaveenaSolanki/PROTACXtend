"""Deterministic multi-dimension scoring — implemented **before** any comparison.

Requirement (Sections 21 & 25 of the specification):

    Each task needs a MACHINE component and an EXPERT component.
    Score these dimensions SEPARATELY, each on a 0–5 integer scale:

        scientific_correctness      0–5
        evidence_grounding          0–5
        tool_selection              0–5
        tool_execution              0–5
        mechanistic_correctness     0–5
        quantitative_correctness    0–5
        uncertainty_calibration     0–5
        reproducibility             0–5
        final_decision_quality      0–5

    Temporal tasks additionally:

        temporal_compliance           0–5
        future_outcome_concordance    0–5

    Do NOT lead the paper with one combined score. Keep all dimensions separate.

Design rules enforced here:

* Every dimension is scored 0–5 by a **machine** scorer and/or an **expert**
  panel. The two components are stored separately and are never averaged into a
  single dimension value.
* A dimension the harness cannot compute deterministically returns ``None`` for
  the machine component — it is never guessed, imputed or defaulted.
* Aggregation reports **per-dimension** statistics only. A composite exists but
  is opt-in, secondary, weighted, coverage-labelled and refuses to be presented
  as the headline.
* Any triggered failure criterion forces ``FAIL`` regardless of dimension scores.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from tpdeval import calibration, mechanism, toolenv, trajectory
from tpdeval.scoring import FAILURE_CRITERIA
from tpdeval.taskmodel import OBJECTIVE_GT_TYPES, RunRecord, ScoreRecord

SCALE_MIN, SCALE_MAX = 0, 5


# ─────────────────────────────────────────────────────────────────────────────
# Dimension registry
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Dimension:
    name: str
    applies: str                 # "all" | "temporal"
    machine_capable: bool
    expert_required: bool
    definition: str
    anchors: tuple               # 6 strings, index 0..5

    def is_applicable(self, partition: str, temporal_cutoff: str | None = None) -> bool:
        if self.applies == "all":
            return True
        return partition == "temporal" or bool(temporal_cutoff)


DIMENSIONS: tuple = (
    Dimension(
        "scientific_correctness", "all", True, True,
        "Does the final scientific answer match verified ground truth?",
        ("0 no answer / wrong domain",
         "1 wrong conclusion with no usable content",
         "2 partly relevant but incorrect conclusion",
         "3 correct conclusion with material omissions/errors",
         "4 correct conclusion, minor omissions",
         "5 exactly correct and complete against ground truth")),
    Dimension(
        "evidence_grounding", "all", True, True,
        "Is every claim traceable to a real, resolvable, context-matched source?",
        ("0 no evidence / fabricated citations",
         "1 claims asserted with no support",
         "2 some claims cited but unresolvable or off-context",
         "3 most claims supported, some gaps",
         "4 all material claims supported and resolvable",
         "5 every claim supported, primary-sourced and context-matched")),
    Dimension(
        "tool_selection", "all", True, True,
        "Were the right tools chosen and the wrong tools avoided?",
        ("0 no required tool used / only irrelevant tools",
         "1 mostly wrong tools",
         "2 some required tools, many unnecessary",
         "3 required tools mostly used, some noise",
         "4 all required tools, minimal noise",
         "5 exactly the required tools, no irrelevant calls")),
    Dimension(
        "tool_execution", "all", True, True,
        "Were chosen tools run correctly, on valid inputs, with QC?",
        ("0 execution failed / invalid outputs",
         "1 ran but wrong parameters, unusable output",
         "2 partial success, no QC",
         "3 mostly successful, output validity partly checked",
         "4 successful with QC and provenance",
         "5 fully correct execution, valid outputs, QC captured")),
    Dimension(
        "mechanistic_correctness", "all", True, True,
        "Does the causal mechanism match the verified causal graph?",
        ("0 no mechanism / wrong direction",
         "1 reversed or contradictory causality",
         "2 isolated correct nodes, no correct edges",
         "3 some correct edges, key edges missing",
         "4 correct causal chain, minor unsupported edges",
         "5 exactly the verified causal graph")),
    Dimension(
        "quantitative_correctness", "all", True, True,
        "Are numeric predictions within the stated tolerance of truth?",
        ("0 no numeric answer / grossly wrong",
         "1 >10x or sign error",
         "2 outside tolerance by a large factor",
         "3 close but outside tolerance",
         "4 within tolerance with minor error",
         "5 all quantities within stated tolerance")),
    Dimension(
        "uncertainty_calibration", "all", True, True,
        "Does stated confidence match observed correctness?",
        ("0 confidently wrong, no uncertainty stated",
         "1 severely overconfident",
         "2 overconfident, little calibration",
         "3 partially calibrated",
         "4 well calibrated, minor overconfidence",
         "5 calibrated (ECE near 0) with appropriate uncertainty")),
    Dimension(
        "reproducibility", "all", True, True,
        "Do independent repeats produce the same result?",
        ("0 non-reproducible / not run",
         "1 repeats disagree on the conclusion",
         "2 low agreement",
         "3 moderate agreement",
         "4 high agreement, minor variance",
         "5 identical conclusions across all repeats")),
    Dimension(
        "final_decision_quality", "all", True, True,
        "Is the final recommendation defensible and actionable?",
        ("0 no decision / unsafe recommendation",
         "1 decision not supported by the produced evidence",
         "2 weak decision, missing rationale",
         "3 reasonable decision, incomplete justification",
         "4 defensible decision with evidence and next step",
         "5 optimal, fully justified, experimentally actionable decision")),
    Dimension(
        "temporal_compliance", "temporal", True, True,
        "Was the T0/T1 cutoff respected with no leakage?",
        ("0 used post-cutoff / forbidden information",
         "1 clear leakage detected",
         "2 borderline leakage, undocumented",
         "3 cutoff respected but no leakage audit",
         "4 cutoff respected, leakage audited",
         "5 cutoff respected, leakage audited and clean")),
    Dimension(
        "future_outcome_concordance", "temporal", True, True,
        "Do predictions agree with the sealed future outcome?",
        ("0 confidently contradicts the later outcome",
         "1 wrong direction",
         "2 mostly discordant",
         "3 mixed concordance",
         "4 mostly concordant",
         "5 fully concordant with the sealed outcome")),
)

ALL_DIMENSION_NAMES: tuple = tuple(d.name for d in DIMENSIONS)
TEMPORAL_DIMENSION_NAMES: tuple = tuple(d.name for d in DIMENSIONS if d.applies == "temporal")
GENERAL_DIMENSION_NAMES: tuple = tuple(d.name for d in DIMENSIONS if d.applies == "all")
_BY_NAME: dict[str, Dimension] = {d.name: d for d in DIMENSIONS}


def get_dimension(name: str) -> Dimension:
    if name not in _BY_NAME:
        raise KeyError(f"unknown dimension {name!r}; known: {list(ALL_DIMENSION_NAMES)}")
    return _BY_NAME[name]


def applicable_dimensions(partition: str = "controlled",
                          temporal_cutoff: str | None = None) -> list[str]:
    return [d.name for d in DIMENSIONS if d.is_applicable(partition, temporal_cutoff)]


# ─────────────────────────────────────────────────────────────────────────────
# Scale helpers
# ─────────────────────────────────────────────────────────────────────────────

def validate_scale(value: Any, where: str = "score") -> int:
    """Scores are integers on the closed 0–5 scale. Never a percentage."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{where}: score must be a number in [0,5], got {value!r}")
    if float(value) != int(value):
        raise ValueError(f"{where}: score must be an integer 0–5, got {value!r}")
    v = int(value)
    if not (SCALE_MIN <= v <= SCALE_MAX):
        raise ValueError(f"{where}: score {v} outside [{SCALE_MIN},{SCALE_MAX}]")
    return v


def _band01(x: float | None) -> int | None:
    """Map a [0,1] ratio onto the 0–5 integer scale (deterministic half-up)."""
    if x is None:
        return None
    return max(SCALE_MIN, min(SCALE_MAX, int(math.floor(SCALE_MAX * float(x) + 0.5))))


@dataclass
class MachineResult:
    value: int | None
    detail: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic machine scorers (pure functions — no randomness, no LLM)
# ─────────────────────────────────────────────────────────────────────────────

def score_tool_selection(selected: Sequence[str], spec: toolenv.ToolSpec) -> MachineResult:
    m = toolenv.selection_metrics(selected, spec)
    if not (spec.required or spec.optional or spec.irrelevant):
        return MachineResult(None, m)
    value = _band01(m["f1"])
    if m["unnecessary_count"]:
        # using an explicitly irrelevant tool caps this dimension at 1
        value = min(value, 1)
    return MachineResult(value, m)


def score_tool_execution(tool_calls: Sequence[dict[str, Any]]) -> MachineResult:
    if not tool_calls:
        return MachineResult(None, {"n_calls": 0})
    e = toolenv.execution_metrics(tool_calls)
    h = toolenv.call_hygiene(tool_calls)
    ratio = (0.5 * e["execution_success_rate"]
             + 0.3 * e["output_validity_rate"]
             + 0.2 * e["qc_completion"])
    return MachineResult(_band01(ratio), {**h, **e, "ratio": round(ratio, 4)})


def score_evidence_grounding(claims: Sequence[dict[str, Any]]) -> MachineResult:
    """Each claim: {'supported': bool, 'citation_ids': [...], 'primary_source': bool,
    'fabricated': bool}. A fabricated citation forces 0."""
    if not claims:
        return MachineResult(None, {"n_claims": 0})
    n = len(claims)
    fabricated = sum(1 for c in claims if c.get("fabricated") is True)
    supported = sum(1 for c in claims if c.get("supported") is True)
    primary = sum(1 for c in claims
                  if c.get("supported") is True and c.get("primary_source") is True)
    ratio = (0.7 * supported / n) + (0.3 * primary / n)
    value = _band01(ratio)
    if fabricated:
        value = 0
    return MachineResult(value, {"n_claims": n, "supported": supported,
                                 "primary": primary, "fabricated": fabricated,
                                 "ratio": round(ratio, 4)})


def score_quantitative_correctness(pairs: Sequence[dict[str, Any]]) -> MachineResult:
    """pairs: [{'name', 'predicted', 'expected', 'tol'}] — tol is absolute (or 'rel')."""
    if not pairs:
        return MachineResult(None, {"n": 0})
    correct = 0
    for p in pairs:
        try:
            pred, exp = float(p["predicted"]), float(p["expected"])
        except (KeyError, TypeError, ValueError):
            continue
        tol = p.get("tol")
        if tol is None:
            tol = max(abs(exp) * 1e-6, 1e-12)
        if isinstance(tol, str) and tol.endswith("%"):
            tol = abs(exp) * float(tol[:-1]) / 100.0
        if abs(pred - exp) <= abs(float(tol)):
            correct += 1
    return MachineResult(_band01(correct / len(pairs)),
                         {"n": len(pairs), "within_tolerance": correct})


def score_uncertainty_calibration(confidences: Sequence[float],
                                  outcomes: Sequence[int]) -> MachineResult:
    if not confidences or len(confidences) != len(outcomes):
        return MachineResult(None, {"n": len(confidences)})
    ece = calibration.expected_calibration_error(confidences, outcomes)
    val = ece.get("ece")
    if val is None:
        return MachineResult(None, ece)
    return MachineResult(_band01(1.0 - float(val)),
                         {"ece": val, "brier": ece.get("brier"), "n": ece.get("n")})


def score_reproducibility(repeats: Sequence[Any]) -> MachineResult:
    """repeats: normalized outcome per repeat (hashable). Modal-agreement rate."""
    normalized = [str(r) for r in repeats]
    if len(normalized) < 2:
        return MachineResult(None, {"n_repeats": len(normalized)})
    counts: dict[str, int] = {}
    for r in normalized:
        counts[r] = counts.get(r, 0) + 1
    agree = max(counts.values())
    return MachineResult(_band01(agree / len(normalized)),
                         {"n_repeats": len(normalized), "modal_agreement": agree,
                          "distinct": len(counts)})


def score_temporal_compliance(leakage: Sequence[dict[str, Any]] | None) -> MachineResult:
    if leakage is None:
        return MachineResult(None, {"audited": False})
    n = len(leakage)
    return MachineResult(5 if n == 0 else 0, {"n_leakage_flags": n,
                                              "flags": list(leakage)})


def score_future_outcome_concordance(outcomes: Sequence[dict[str, Any]]) -> MachineResult:
    """outcomes: [{'predicted', 'actual', 'tol'?}] — categorical equality or numeric tol."""
    if not outcomes:
        return MachineResult(None, {"n": 0})
    concordant = 0
    for o in outcomes:
        pred, actual = o.get("predicted"), o.get("actual")
        try:
            tol = o.get("tol")
            if tol is not None:
                if abs(float(pred) - float(actual)) <= abs(float(tol)):
                    concordant += 1
            elif str(pred) == str(actual):
                concordant += 1
        except (TypeError, ValueError):
            if str(pred) == str(actual):
                concordant += 1
    return MachineResult(_band01(concordant / len(outcomes)),
                         {"n": len(outcomes), "concordant": concordant})


def score_objective_correctness(predicted: Any, expected: Any,
                                gt_type: str) -> MachineResult:
    """Machine component for scientific_correctness when GT is objectively scorable."""
    if gt_type not in OBJECTIVE_GT_TYPES or expected is None:
        return MachineResult(None, {"gt_type": gt_type, "objective": False})
    if gt_type == "exact":
        ratio = 1.0 if str(predicted).strip().lower() == str(expected).strip().lower() else 0.0
    elif gt_type == "categorical":
        accepted = expected if isinstance(expected, (list, tuple, set)) else [expected]
        ratio = 1.0 if predicted in accepted else 0.0
    elif gt_type == "set":
        p, e = set(predicted or []), set(expected or [])
        ratio = (len(p & e) / len(e)) if e else 0.0
    elif gt_type == "ranking":
        p, e = list(predicted or []), list(expected or [])
        ratio = trajectory_rank_agreement(p, e)
    elif gt_type == "numeric":
        ratio = 1.0 if _numeric_within(predicted, expected) else 0.0
    else:
        return MachineResult(None, {"gt_type": gt_type, "objective": False})
    return MachineResult(_band01(ratio),
                         {"gt_type": gt_type, "ratio": round(ratio, 4),
                          "objective": True})


def score_mechanistic_correctness(predicted_graph: dict[str, Any],
                                  truth_graph: dict[str, Any]) -> MachineResult:
    if not predicted_graph or not truth_graph:
        return MachineResult(None, {"causal_graph": False})
    pg = mechanism.CausalGraph.from_dict(predicted_graph)
    tg = mechanism.CausalGraph.from_dict(truth_graph)
    m = mechanism.match_causal_graph(pg, tg)
    contradictions = mechanism.contradiction_count(pg, tg)
    value = _band01(float(m["mechanistic_correctness"]))
    if contradictions:
        value = min(value, 1)
    return MachineResult(value, {**m, "contradictions": contradictions})


def score_final_decision_quality(steps: Sequence[Any] | None) -> MachineResult:
    """Machine component from the recorded decision trajectory (Section 12)."""
    if not steps:
        return MachineResult(None, {"trajectory": False})
    if all(isinstance(s, trajectory.StepDecision) for s in steps):
        t = trajectory.score_trajectory(list(steps))
    else:
        t = {"decision_validity": None}
    dv = t.get("decision_validity")
    if dv is None:
        return MachineResult(None, {"trajectory": True, "decision_validity": None})
    return MachineResult(_band01(float(dv)), t)


def trajectory_rank_agreement(predicted: Sequence[Any], expected: Sequence[Any]) -> float:
    if not predicted or not expected:
        return 0.0
    exp_idx = {str(v): i for i, v in enumerate(expected)}
    pairs = [(i, exp_idx[str(v)]) for i, v in enumerate(predicted) if str(v) in exp_idx]
    if len(pairs) < 2:
        return 1.0 if pairs else 0.0
    n = len(pairs)
    disc = sum(1 for a in range(n) for b in range(a + 1, n)
               if (pairs[a][0] - pairs[b][0]) * (pairs[a][1] - pairs[b][1]) < 0)
    total = n * (n - 1) / 2
    return max(0.0, 1.0 - 2 * disc / total)


def _numeric_within(predicted: Any, expected: Any) -> bool:
    try:
        p, e = float(predicted), float(expected)
    except (TypeError, ValueError):
        return False
    tol = max(abs(e) * 0.05, 1e-9)
    return abs(p - e) <= tol


# name -> deterministic machine scorer. Dimensions absent here are expert-only
# unless a scorer is supplied explicitly.
MACHINE_SCORERS = {
    "scientific_correctness": "score_objective_correctness",
    "evidence_grounding": "score_evidence_grounding",
    "tool_selection": "score_tool_selection",
    "tool_execution": "score_tool_execution",
    "mechanistic_correctness": "score_mechanistic_correctness",
    "quantitative_correctness": "score_quantitative_correctness",
    "uncertainty_calibration": "score_uncertainty_calibration",
    "reproducibility": "score_reproducibility",
    "final_decision_quality": "score_final_decision_quality",
    "temporal_compliance": "score_temporal_compliance",
    "future_outcome_concordance": "score_future_outcome_concordance",
}


# ─────────────────────────────────────────────────────────────────────────────
# Per-dimension components and the task scorecard
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DimensionScore:
    """Machine and expert components for ONE dimension. Never averaged together."""
    name: str
    machine: int | None = None
    machine_detail: dict[str, Any] = field(default_factory=dict)
    expert: int | None = None
    reviewers: list[int] = field(default_factory=list)
    notes: str = ""

    def present(self) -> bool:
        return self.machine is not None or self.expert is not None

    def disagreement(self) -> int | None:
        if self.machine is None or self.expert is None:
            return None
        return abs(self.machine - self.expert)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "machine": self.machine,
                "expert": self.expert, "reviewers": list(self.reviewers),
                "machine_expert_gap": self.disagreement(),
                "machine_detail": self.machine_detail, "notes": self.notes}


@dataclass
class TaskScorecard:
    """All applicable dimensions for one (task, system, run). No headline composite."""
    task_id: str
    system: str
    run_id: str = ""
    condition: str = "native"
    partition: str = "controlled"
    temporal_cutoff: str | None = None
    scores: dict[str, DimensionScore] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    expert_meta: dict[str, Any] = field(default_factory=dict)

    # -- population -----------------------------------------------------------
    def _slot(self, name: str) -> DimensionScore:
        get_dimension(name)  # validates the name
        if name not in self.scores:
            self.scores[name] = DimensionScore(name=name)
        return self.scores[name]

    def set_machine(self, name: str, value: int | None,
                    detail: dict[str, Any] | None = None) -> TaskScorecard:
        if value is not None:
            value = validate_scale(value, f"machine.{name}")
        s = self._slot(name)
        s.machine = value
        s.machine_detail = detail or {}
        return self

    def set_expert(self, name: str, reviewers: Sequence[int],
                   notes: str = "") -> TaskScorecard:
        revs = [validate_scale(r, f"expert.{name}") for r in reviewers]
        if not revs:
            raise ValueError(f"expert.{name}: at least one reviewer score required")
        s = self._slot(name)
        s.reviewers = revs
        # consensus = half-up mean, stored separately from the raw reviewer list
        s.expert = int(math.floor(sum(revs) / len(revs) + 0.5))
        if notes:
            s.notes = notes
        return self

    def mark_failure(self, criterion: str) -> TaskScorecard:
        if criterion not in FAILURE_CRITERIA:
            raise ValueError(f"unknown failure criterion {criterion!r}")
        if criterion not in self.failures:
            self.failures.append(criterion)
        return self

    # -- queries --------------------------------------------------------------
    def applicable(self) -> list[str]:
        return applicable_dimensions(self.partition, self.temporal_cutoff)

    def missing(self) -> list[str]:
        return [n for n in self.applicable() if not self.scores.get(n, DimensionScore(n)).present()]

    def expert_only_missing(self) -> list[str]:
        """Applicable dimensions that require an expert but have none yet."""
        return [n for n in self.applicable()
                if get_dimension(n).expert_required
                and self.scores.get(n, DimensionScore(n)).expert is None]

    @property
    def complete(self) -> bool:
        return not self.missing()

    @property
    def verdict(self) -> str:
        if self.failures:
            return "FAIL"
        if not self.complete:
            return "INCOMPLETE"
        return "SCORED"

    def dimension_table(self) -> list[dict[str, Any]]:
        rows = []
        for name in self.applicable():
            s = self.scores.get(name) or DimensionScore(name=name)
            d = get_dimension(name)
            rows.append({"dimension": name, "machine": s.machine,
                         "expert": s.expert, "reviewers": s.reviewers,
                         "gap": s.disagreement(), "present": s.present(),
                         "expert_required": d.expert_required})
        return rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "system": self.system, "run_id": self.run_id,
            "condition": self.condition, "partition": self.partition,
            "temporal_cutoff": self.temporal_cutoff,
            "verdict": self.verdict, "failures": list(self.failures),
            "missing_dimensions": self.missing(),
            "expert_review_missing": self.expert_only_missing(),
            "expert_meta": dict(self.expert_meta),
            "dimensions": {n: s.to_dict() for n, s in self.scores.items()},
            "note": "Dimensions are independent. No headline composite is defined.",
        }

    def to_score_record(self) -> ScoreRecord:
        """Persist into the canonical ScoreRecord, keeping machine and expert apart.

        The machine value is written to the dimension field; expert values (raw
        reviewer list + consensus) are written to ``expert_scores`` so the two
        components never collapse.
        """
        alias = {"future_outcome_concordance": "future_outcome_match"}
        rec = ScoreRecord(run_id=self.run_id, task_id=self.task_id, system=self.system)
        for name, s in self.scores.items():
            field_name = alias.get(name, name)
            if hasattr(rec, field_name) and s.machine is not None:
                setattr(rec, field_name, float(s.machine))
            if s.present():
                rec.expert_scores[name] = {
                    "machine": s.machine, "expert": s.expert,
                    "reviewers": list(s.reviewers),
                    "machine_expert_gap": s.disagreement(),
                }
        rec.notes = "; ".join(self.failures)
        return rec


# ─────────────────────────────────────────────────────────────────────────────
# High-level deterministic scorer
# ─────────────────────────────────────────────────────────────────────────────

def score_task(task: Any, run: RunRecord, *,
               selected_tools: Sequence[str] | None = None,
               tool_calls: Sequence[dict[str, Any]] | None = None,
               claims: Sequence[dict[str, Any]] | None = None,
               quantitative: Sequence[dict[str, Any]] | None = None,
               repeats: Sequence[Any] | None = None,
               confidences: Sequence[float] | None = None,
               outcomes: Sequence[int] | None = None,
               predicted_answer: Any = None,
               predicted_graph: dict[str, Any] | None = None,
               trajectory_steps: Sequence[Any] | None = None,
               temporal_outcomes: Sequence[dict[str, Any]] | None = None,
               expert: dict[str, Any] | None = None,
               failures: Sequence[str] | None = None) -> TaskScorecard:
    """Compute the machine components deterministically from recorded evidence,
    then attach expert components (if a panel has scored this run).

    Nothing is inferred: a component that cannot be computed stays ``None`` and
    the dimension shows up in ``missing()``.
    """
    gt = task.ground_truth
    card = TaskScorecard(
        task_id=task.task_id, system=run.system, run_id=run.run_id,
        condition=run.condition, partition=task.partition,
        temporal_cutoff=getattr(task, "temporal_cutoff", None),
    )
    spec = getattr(task, "tool_spec", None) or toolenv.ToolSpec()

    def apply(res: MachineResult, name: str) -> None:
        card.set_machine(name, res.value, res.detail)

    apply(score_tool_selection(
        selected_tools if selected_tools is not None else run.selected_tools, spec),
        "tool_selection")
    apply(score_tool_execution(
        tool_calls if tool_calls is not None else run.tool_calls), "tool_execution")
    apply(score_evidence_grounding(
        claims if claims is not None else run.claims), "evidence_grounding")
    apply(score_quantitative_correctness(quantitative or []), "quantitative_correctness")
    apply(score_uncertainty_calibration(confidences or [], outcomes or []),
          "uncertainty_calibration")
    apply(score_reproducibility(repeats or []), "reproducibility")
    apply(score_final_decision_quality(trajectory_steps), "final_decision_quality")

    if predicted_answer is not None:
        apply(score_objective_correctness(predicted_answer, gt.expected, gt.gt_type),
              "scientific_correctness")
    elif gt.gt_type in OBJECTIVE_GT_TYPES:
        card.set_machine("scientific_correctness", None, {"gt_type": gt.gt_type,
                                                          "awaiting_prediction": True})

    if predicted_graph:
        apply(score_mechanistic_correctness(predicted_graph, gt.causal_graph or {}),
              "mechanistic_correctness")

    if get_dimension("temporal_compliance").is_applicable(card.partition, card.temporal_cutoff):
        apply(score_temporal_compliance(
            getattr(run, "temporal_leakage", None)), "temporal_compliance")
        apply(score_future_outcome_concordance(temporal_outcomes or []),
              "future_outcome_concordance")

    for name, rev in (expert or {}).items():
        if name not in ALL_DIMENSION_NAMES:
            raise KeyError(f"expert score for unknown dimension {name!r}")
        card.set_expert(name, rev if isinstance(rev, (list, tuple)) else [rev])

    for f in failures or []:
        card.mark_failure(f)
    return card


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation — per-dimension only, composite strictly secondary
# ─────────────────────────────────────────────────────────────────────────────

# Weights exist ONLY for the optional secondary composite. They are never used
# to produce a headline number.
SECONDARY_WEIGHTS: dict[str, float] = {
    "scientific_correctness": 0.18,
    "evidence_grounding": 0.12,
    "tool_selection": 0.06,
    "tool_execution": 0.06,
    "mechanistic_correctness": 0.16,
    "quantitative_correctness": 0.08,
    "uncertainty_calibration": 0.05,
    "reproducibility": 0.05,
    "final_decision_quality": 0.14,
    "temporal_compliance": 0.05,
    "future_outcome_concordance": 0.05,
}


def _mean(xs: Sequence[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def _median(xs: Sequence[float]) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    mid = n // 2
    return round(xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2, 4)


def aggregate_dimensions(scorecards: Iterable[TaskScorecard]) -> dict[str, Any]:
    """Per-dimension summary across scorecards. Deliberately has NO composite."""
    cards = list(scorecards)
    dims = sorted({n for c in cards for n in c.applicable()})
    summary: dict[str, Any] = {}
    for name in dims:
        machine = [c.scores[name].machine for c in cards
                   if name in c.scores and c.scores[name].machine is not None]
        expert = [c.scores[name].expert for c in cards
                  if name in c.scores and c.scores[name].expert is not None]
        gaps = [c.scores[name].disagreement() for c in cards
                if name in c.scores and c.scores[name].disagreement() is not None]
        summary[name] = {
            "n": len([c for c in cards if name in c.scores and c.scores[name].present()]),
            "machine_n": len(machine), "machine_mean": _mean(machine),
            "machine_median": _median(machine),
            "expert_n": len(expert), "expert_mean": _mean(expert),
            "expert_median": _median(expert),
            "mean_machine_expert_gap": _mean(gaps),
            "scale": f"{SCALE_MIN}-{SCALE_MAX}",
        }
    return {
        "n_scorecards": len(cards),
        "n_by_system": _count_by(cards, lambda c: c.system),
        "failures": _count_by(
            [c for c in cards if c.failures], lambda c: c.system),
        "dimensions": summary,
        "note": ("Dimensions are reported independently. No composite is "
                 "computed here; use secondary_composite() explicitly if a "
                 "secondary number is required, and never lead with it."),
    }


def _count_by(items: Sequence[Any], key) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        k = str(key(it))
        out[k] = out.get(k, 0) + 1
    return out


def secondary_composite(scores: dict[str, float | None],
                        weights: dict[str, float] | None = None) -> dict[str, Any]:
    """Opt-in, weighted, coverage-labelled composite. NEVER the headline.

    Uses the expert component when present, otherwise the machine component.
    Missing dimensions reduce coverage instead of being imputed.
    """
    w = weights or SECONDARY_WEIGHTS
    num = den = 0.0
    used: dict[str, float] = {}
    for name, weight in w.items():
        dim = scores.get(name)
        if dim is None:
            continue
        v = dim.get("expert") if isinstance(dim, dict) else dim
        if v is None and isinstance(dim, dict):
            v = dim.get("machine")
        if v is None:
            continue
        num += weight * float(v) / SCALE_MAX
        den += weight
        used[name] = weight
    total_w = sum(w.values())
    return {
        "composite_secondary": round(num / den, 4) if den else None,
        "weights_used": used,
        "coverage": round(den / total_w, 4) if total_w else 0.0,
        "scale": "0-1 (normalized from 0-5)",
        "label": "SECONDARY composite — report the 11 dimensions separately first",
        "claim_boundary": claim_boundary(),
    }


def claim_boundary() -> str:
    return (
        "Scores are computational-benchmark measurements under stated evidence "
        "and tool constraints, not experimental or clinical validation. Tool "
        "success is not correctness; docking is not affinity; predicted "
        "degradation is not measured degradation.")


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────

def markdown_scorecard(card: TaskScorecard) -> str:
    """One scorecard as a Markdown table. Machine and expert stay separate."""
    lines = [
        f"### {card.task_id} · {card.system}",
        "",
        f"- verdict: **{card.verdict}**",
        f"- partition: `{card.partition}`"
        + (f" · cutoff `{card.temporal_cutoff}`" if card.temporal_cutoff else ""),
        f"- machine+expert present: {len(card.applicable()) - len(card.missing())}"
        f"/{len(card.applicable())}"
        + (f" · expert pending: {', '.join(card.expert_only_missing())}"
           if card.expert_only_missing() else ""),
        "",
        "| dimension | machine (0–5) | expert (0–5) | gap | expert required |",
        "|---|---|---|---|---|",
    ]
    for r in card.dimension_table():
        m = "—" if r["machine"] is None else str(r["machine"])
        e = "—" if r["expert"] is None else str(r["expert"])
        g = "—" if r["gap"] is None else str(r["gap"])
        lines.append(f"| {r['dimension']} | {m} | {e} | {g} | "
                     f"{'yes' if r['expert_required'] else 'no'} |")
    if card.failures:
        lines += ["", "**Failure criteria triggered:** " + ", ".join(card.failures)]
    lines += ["", "_No composite score is shown: dimensions are reported separately._"]
    return "\n".join(lines)


def scorecard_schema() -> dict[str, Any]:
    return {
        "schema": "TPD-SCORECARD/1.0.0",
        "scale": {"min": SCALE_MIN, "max": SCALE_MAX, "type": "integer"},
        "dimensions": {d.name: {"applies": d.applies,
                                "machine_capable": d.machine_capable,
                                "expert_required": d.expert_required,
                                "anchors": list(d.anchors)} for d in DIMENSIONS},
        "temporal_dimensions": list(TEMPORAL_DIMENSION_NAMES),
        "components": ["machine", "expert"],
        "composite": "SECONDARY ONLY — must not be the headline result",
        "failure_criteria": list(FAILURE_CRITERIA),
    }


if __name__ == "__main__":  # pragma: no cover - self-documenting CLI
    import json

    print(json.dumps(scorecard_schema(), indent=2))
