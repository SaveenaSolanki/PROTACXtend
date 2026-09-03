"""Typed schemas for Module 7 — active learning / experiment selection.

Plain dataclasses (no pydantic dependency) so the module runs anywhere the
platform runs; JSON round-trips are explicit helpers.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ActiveLearningParams:
    """Search-control parameters for one recommendation run."""

    budget_evals: int = 40                 # total objective evaluations allowed
    n_initial_random: int = 8              # random seed points before BO
    n_proposals: int = 200                 # acquisition proposal pool per round
    acq: str = "ei"                        # "ei" | "ucb"
    ucb_beta: float = 1.6                  # exploration weight for UCB
    weights: Dict[str, float] = field(default_factory=lambda: {"y": 1.0})
    generations: int = 6                   # (mu+lambda) refinement generations
    mu: int = 8
    lam: int = 16
    diversity_top_k: int = 10              # batch size recommendation
    seed: int = 42
    dose_levels: List[float] = field(
        default_factory=lambda: [1.0, 3.16, 10.0, 31.6, 100.0, 316.0, 1000.0])
    max_stereo_centers: int = 2            # orthogonal-design cap for enumeration

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActiveLearningParams":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Candidate:
    """One searchable design decision point."""

    candidate_id: str
    linker_id: str = ""
    linker_smiles: str = ""
    linker_family: str = "unknown"         # curated | rule | generative
    warhead: str = ""
    e3: str = ""
    stereoisomer: str = ""
    dose_nM: float = 100.0
    features: Dict[str, float] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Candidate":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})  # type: ignore[attr-defined]


@dataclass
class Evaluation:
    """Scored candidate: objectives (maximise convention) + constraint flags."""

    candidate: Candidate
    objectives: Dict[str, float] = field(default_factory=dict)
    constraints: Dict[str, bool] = field(default_factory=dict)
    sources: Dict[str, str] = field(default_factory=dict)   # objective -> predicted/calculated/synthetic
    warnings: List[str] = field(default_factory=list)

    def score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Weighted scalarisation (maximise). Missing objectives get -inf (rejected)."""
        w = weights or {}
        if not self.objectives:
            return float("-inf")
        total = 0.0
        for name, value in self.objectives.items():
            total += w.get(name, 1.0) * value
        return total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "objectives": self.objectives,
            "constraints": self.constraints,
            "sources": self.sources,
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Evaluation":
        return cls(
            candidate=Candidate.from_dict(data["candidate"]),
            objectives=data.get("objectives", {}),
            constraints=data.get("constraints", {}),
            sources=data.get("sources", {}),
            warnings=data.get("warnings", []),
        )


@dataclass
class BatchRecommendation:
    """Recommendation of the next experiment/design batch."""

    recommended: List[Candidate] = field(default_factory=list)
    pareto_ids: List[str] = field(default_factory=list)
    rationale: str = ""
    n_evaluated: int = 0
    budget_used: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommended": [c.to_dict() for c in self.recommended],
            "pareto_ids": self.pareto_ids,
            "rationale": self.rationale,
            "n_evaluated": self.n_evaluated,
            "budget_used": self.budget_used,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchRecommendation":
        return cls(
            recommended=[Candidate.from_dict(c) for c in data.get("recommended", [])],
            pareto_ids=data.get("pareto_ids", []),
            rationale=data.get("rationale", ""),
            n_evaluated=data.get("n_evaluated", 0),
            budget_used=data.get("budget_used", 0),
            meta=data.get("meta", {}),
        )


@dataclass
class SearchOutcome:
    """Result of an optimizer run (JSON-safe)."""

    best_objective: float = float("-inf")
    best_candidate: Optional[Candidate] = None
    pareto: List[Evaluation] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    budget_used: int = 0
    objective_name: str = "y"
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_objective": float(self.best_objective),
            "best_candidate": self.best_candidate.to_dict() if self.best_candidate else None,
            "pareto": [e.to_dict() for e in self.pareto],
            "history": self.history,
            "budget_used": self.budget_used,
            "objective_name": self.objective_name,
            "warnings": self.warnings,
        }


def dump_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)
