"""Universal answer sufficiency contracts.

This module decides whether existing evidence is sufficient to answer the
user's scientific question. It does not run tools, add models, or create new
scientific capabilities.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class AnswerState(str, Enum):
    SUPPORTED_ANSWER = "SUPPORTED_ANSWER"
    SUPPORTED_WITH_LIMITATIONS = "SUPPORTED_WITH_LIMITATIONS"
    APPROXIMATE_ANSWER = "APPROXIMATE_ANSWER"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    AMBIGUOUS_REQUEST = "AMBIGUOUS_REQUEST"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"


class ApproximationPolicy(str, Enum):
    ALLOWED = "ALLOWED"
    ALLOWED_WITH_WARNING = "ALLOWED_WITH_WARNING"
    FORBIDDEN = "FORBIDDEN"


class ApplicabilityPolicy(str, Enum):
    REQUIRED = "REQUIRED"
    REQUIRED_FOR_PREDICTION = "REQUIRED_FOR_PREDICTION"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True)
class TaskAnswerContract:
    task_type: str
    required_output: str
    required_entities: list[str]
    required_evidence: list[str]
    minimum_evidence_tier: str
    approximation_policy: ApproximationPolicy
    applicability_policy: ApplicabilityPolicy
    abstention_allowed: bool = True

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["approximation_policy"] = self.approximation_policy.value
        out["applicability_policy"] = self.applicability_policy.value
        return out


@dataclass
class AnswerEvidence:
    task_type: str
    entities: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    output_present: bool = False
    evidence_tier: str = "none"
    approximation: bool = False
    applicability_status: str = "not_required"
    source_available: bool = True
    tool_available: bool = True
    license_available: bool = True
    ambiguous: bool = False
    conflicting: bool = False
    limitations: list[str] = field(default_factory=list)


@dataclass
class AnswerDecision:
    task_type: str
    answer_state: AnswerState
    satisfied: bool
    missing_entities: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    approximation_policy: str = ""
    applicability_policy: str = ""
    abstention_allowed: bool = True

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["answer_state"] = self.answer_state.value
        return out


EVIDENCE_ORDER = {
    "none": 0,
    "computed": 1,
    "curated": 2,
    "source_provenance": 3,
    "binding_evidence": 4,
    "observed": 5,
}


TASK_CONTRACTS: dict[str, TaskAnswerContract] = {
    "binder_retrieval": TaskAnswerContract(
        task_type="binder_retrieval",
        required_output="target-matched binder records or explicit evidence gap",
        required_entities=["resolved_target", "exact_compound_identity"],
        required_evidence=["binding_evidence", "source_provenance"],
        minimum_evidence_tier="binding_evidence",
        approximation_policy=ApproximationPolicy.FORBIDDEN,
        applicability_policy=ApplicabilityPolicy.NOT_REQUIRED,
    ),
    "protac_nomination": TaskAnswerContract(
        task_type="protac_nomination",
        required_output="nomination or abstention with candidate-level gates",
        required_entities=["verified_target", "verified_target_binder", "verified_e3_ligand"],
        required_evidence=[
            "verified_exit_vectors",
            "valid_assembly",
            "applicability_domain_status",
            "mechanistic_evidence_state",
        ],
        minimum_evidence_tier="curated",
        approximation_policy=ApproximationPolicy.FORBIDDEN,
        applicability_policy=ApplicabilityPolicy.REQUIRED,
    ),
    "docking_question": TaskAnswerContract(
        task_type="docking_question",
        required_output="docking result or explicit backend blocker",
        required_entities=["valid_receptor", "valid_ligand"],
        required_evidence=["valid_docking_execution"],
        minimum_evidence_tier="computed",
        approximation_policy=ApproximationPolicy.ALLOWED_WITH_WARNING,
        applicability_policy=ApplicabilityPolicy.REQUIRED,
    ),
    "degradation_prediction": TaskAnswerContract(
        task_type="degradation_prediction",
        required_output="prediction with model/version/uncertainty/applicability",
        required_entities=["valid_candidate"],
        required_evidence=["model_output", "applicability_domain_status"],
        minimum_evidence_tier="computed",
        approximation_policy=ApproximationPolicy.ALLOWED_WITH_WARNING,
        applicability_policy=ApplicabilityPolicy.REQUIRED_FOR_PREDICTION,
    ),
    "target_investigation": TaskAnswerContract(
        task_type="target_investigation",
        required_output="target facts or explicit evidence-gap conclusion",
        required_entities=["resolved_target"],
        required_evidence=["source_provenance"],
        minimum_evidence_tier="source_provenance",
        approximation_policy=ApproximationPolicy.ALLOWED_WITH_WARNING,
        applicability_policy=ApplicabilityPolicy.NOT_REQUIRED,
    ),
    "mechanistic_reasoning": TaskAnswerContract(
        task_type="mechanistic_reasoning",
        required_output="hypothesis with rationale and discriminating test",
        required_entities=["case_context"],
        required_evidence=["rationale", "discriminating_test"],
        minimum_evidence_tier="computed",
        approximation_policy=ApproximationPolicy.ALLOWED_WITH_WARNING,
        applicability_policy=ApplicabilityPolicy.NOT_REQUIRED,
    ),
    "synthesis_route": TaskAnswerContract(
        task_type="synthesis_route",
        required_output="route proposal or backend availability blocker",
        required_entities=["valid_molecule"],
        required_evidence=["route_output"],
        minimum_evidence_tier="computed",
        approximation_policy=ApproximationPolicy.ALLOWED_WITH_WARNING,
        applicability_policy=ApplicabilityPolicy.NOT_REQUIRED,
    ),
}


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return bool(value)


def _tier_ok(observed: str, minimum: str) -> bool:
    return EVIDENCE_ORDER.get(observed, 0) >= EVIDENCE_ORDER.get(minimum, 0)


def evaluate_answer_contract(evidence: AnswerEvidence,
                             registry: dict[str, TaskAnswerContract] | None = None) -> AnswerDecision:
    registry = registry or TASK_CONTRACTS
    contract = registry[evidence.task_type]
    reasons: list[str] = []

    if evidence.ambiguous:
        return AnswerDecision(
            evidence.task_type, AnswerState.AMBIGUOUS_REQUEST, False,
            reasons=["request or entity resolution is ambiguous"],
            limitations=evidence.limitations,
            approximation_policy=contract.approximation_policy.value,
            applicability_policy=contract.applicability_policy.value,
            abstention_allowed=contract.abstention_allowed,
        )
    if evidence.conflicting:
        return AnswerDecision(
            evidence.task_type, AnswerState.CONFLICTING_EVIDENCE, False,
            reasons=["evidence records conflict"],
            limitations=evidence.limitations,
            approximation_policy=contract.approximation_policy.value,
            applicability_policy=contract.applicability_policy.value,
            abstention_allowed=contract.abstention_allowed,
        )
    if not evidence.tool_available:
        return AnswerDecision(evidence.task_type, AnswerState.TOOL_UNAVAILABLE, False,
                              reasons=["required tool/backend unavailable"],
                              limitations=evidence.limitations,
                              approximation_policy=contract.approximation_policy.value,
                              applicability_policy=contract.applicability_policy.value,
                              abstention_allowed=contract.abstention_allowed)
    if not evidence.license_available:
        return AnswerDecision(evidence.task_type, AnswerState.LICENSE_REQUIRED, False,
                              reasons=["required backend license unavailable"],
                              limitations=evidence.limitations,
                              approximation_policy=contract.approximation_policy.value,
                              applicability_policy=contract.applicability_policy.value,
                              abstention_allowed=contract.abstention_allowed)
    if not evidence.source_available:
        return AnswerDecision(evidence.task_type, AnswerState.TOOL_UNAVAILABLE, False,
                              reasons=["source unavailable; not scientific negative evidence"],
                              limitations=evidence.limitations,
                              approximation_policy=contract.approximation_policy.value,
                              applicability_policy=contract.applicability_policy.value,
                              abstention_allowed=contract.abstention_allowed)

    missing_entities = [k for k in contract.required_entities if not _has_value(evidence.entities.get(k))]
    missing_evidence = [k for k in contract.required_evidence if not _has_value(evidence.evidence.get(k))]
    if not evidence.output_present:
        reasons.append("required output absent")
    if missing_entities:
        reasons.append("missing required entities")
    if missing_evidence:
        reasons.append("missing required evidence")
    if not _tier_ok(evidence.evidence_tier, contract.minimum_evidence_tier):
        reasons.append(
            f"evidence tier {evidence.evidence_tier!r} below minimum {contract.minimum_evidence_tier!r}"
        )
    if contract.applicability_policy in {ApplicabilityPolicy.REQUIRED, ApplicabilityPolicy.REQUIRED_FOR_PREDICTION}:
        if evidence.applicability_status in {"out_of_domain", "outside", "OOD"}:
            return AnswerDecision(evidence.task_type, AnswerState.OUT_OF_DOMAIN, False,
                                  missing_entities, missing_evidence,
                                  reasons + ["outside applicability domain"],
                                  evidence.limitations,
                                  contract.approximation_policy.value,
                                  contract.applicability_policy.value,
                                  contract.abstention_allowed)
        if evidence.applicability_status in {"", "unknown", "not_assessed", "not_required"}:
            reasons.append("applicability domain not established")
    if evidence.approximation and contract.approximation_policy is ApproximationPolicy.FORBIDDEN:
        return AnswerDecision(evidence.task_type, AnswerState.INSUFFICIENT_EVIDENCE, False,
                              missing_entities, missing_evidence,
                              reasons + ["approximation forbidden for this task"],
                              evidence.limitations,
                              contract.approximation_policy.value,
                              contract.applicability_policy.value,
                              contract.abstention_allowed)
    if reasons:
        return AnswerDecision(evidence.task_type, AnswerState.INSUFFICIENT_EVIDENCE, False,
                              missing_entities, missing_evidence, reasons,
                              evidence.limitations,
                              contract.approximation_policy.value,
                              contract.applicability_policy.value,
                              contract.abstention_allowed)
    if evidence.approximation and contract.approximation_policy is ApproximationPolicy.ALLOWED_WITH_WARNING:
        return AnswerDecision(evidence.task_type, AnswerState.APPROXIMATE_ANSWER, True,
                              limitations=evidence.limitations + ["approximation used"],
                              approximation_policy=contract.approximation_policy.value,
                              applicability_policy=contract.applicability_policy.value,
                              abstention_allowed=contract.abstention_allowed)
    if evidence.limitations:
        return AnswerDecision(evidence.task_type, AnswerState.SUPPORTED_WITH_LIMITATIONS, True,
                              limitations=evidence.limitations,
                              approximation_policy=contract.approximation_policy.value,
                              applicability_policy=contract.applicability_policy.value,
                              abstention_allowed=contract.abstention_allowed)
    return AnswerDecision(evidence.task_type, AnswerState.SUPPORTED_ANSWER, True,
                          approximation_policy=contract.approximation_policy.value,
                          applicability_policy=contract.applicability_policy.value,
                          abstention_allowed=contract.abstention_allowed)


def registry_as_dict() -> dict[str, Any]:
    return {k: v.to_dict() for k, v in TASK_CONTRACTS.items()}

