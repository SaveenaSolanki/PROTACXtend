"""Canonical failure taxonomy for the PROTACXtend control plane.

Every failure in a canonical run — module crash, missing evidence, an
out-of-domain candidate, an unsupported claim — is classified with exactly one
:class:`FailureClass`. This gives benchmarks, reports and the retry/fallback
policy a stable vocabulary instead of free-text error strings.

The taxonomy has four consumers:

* :mod:`protacxtend.canonical.policy` decides retry / fallback / abstain from
  ``retryable`` and ``severity``.
* the three critics emit :class:`Failure` objects.
* :class:`protacxtend.canonical.schemas.CriticVerdict` carries them to the
  decision engine and the typed strategy.
* the benchmark scorer can group errors by ``failure_class``.

Nothing here imports the rest of the canonical stack, so this module is a
dependency leaf (avoids import cycles with ``schemas``).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterable

from protacxtend.backend.schemas import BaseModel, Field


class FailureClass(str, Enum):
    """One stable category per failure mode."""

    # inputs / routing
    MISSING_INPUT = "missing_input"
    UNRESOLVED_ENTITY = "unresolved_entity"
    FIXTURE_IN_SCIENTIFIC_MODE = "fixture_in_scientific_mode"
    SYNTHETIC_INPUT = "synthetic_input"

    # tooling
    TOOL_UNAVAILABLE = "tool_unavailable"
    TOOL_ERROR = "tool_error"
    TOOL_TIMEOUT = "tool_timeout"
    RETRY_EXHAUSTED = "retry_exhausted"

    # evidence / provenance
    MISSING_EVIDENCE = "missing_evidence"
    MISSING_REQUIRED_MODULE = "missing_required_module"
    MODULE_FAILED = "module_failed"
    PROVENANCE_BREAK = "provenance_break"
    MEASURED_PREDICTED_CONFLATION = "measured_predicted_conflation"
    HEURISTIC_FALLBACK = "heuristic_fallback"
    UNSUPPORTED_CLAIM = "unsupported_claim"

    # scientific validity
    INVALID_CHEMISTRY = "invalid_chemistry"
    OUTSIDE_APPLICABILITY_DOMAIN = "outside_applicability_domain"
    STRUCTURAL_CLAIM_BLOCKED = "structural_claim_blocked"
    NO_VALID_CANDIDATES = "no_valid_candidates"
    MECHANISM_INCONSISTENT = "mechanism_inconsistent"
    CONTRADICTION = "contradiction"

    # process / governance
    OVERCONFIDENT = "overconfident_decision"
    NON_REPRODUCIBLE = "non_reproducible"
    ABSTAINED = "abstained"
    BUDGET_EXCEEDED = "budget_exceeded"
    UNKNOWN = "unknown"


#: Failures that a retry can plausibly recover from (transient tool/network).
RETRYABLE_CLASSES: frozenset[FailureClass] = frozenset(
    {
        FailureClass.TOOL_ERROR,
        FailureClass.TOOL_TIMEOUT,
        FailureClass.TOOL_UNAVAILABLE,
    }
)

#: Severity ordering; ``critical`` blocks advancement.
SEVERITY: dict[FailureClass, str] = {
    FailureClass.MISSING_INPUT: "error",
    FailureClass.UNRESOLVED_ENTITY: "error",
    FailureClass.FIXTURE_IN_SCIENTIFIC_MODE: "critical",
    FailureClass.SYNTHETIC_INPUT: "critical",
    FailureClass.TOOL_UNAVAILABLE: "warning",
    FailureClass.TOOL_ERROR: "error",
    FailureClass.TOOL_TIMEOUT: "warning",
    FailureClass.RETRY_EXHAUSTED: "error",
    FailureClass.MISSING_EVIDENCE: "error",
    FailureClass.MISSING_REQUIRED_MODULE: "critical",
    FailureClass.MODULE_FAILED: "error",
    FailureClass.PROVENANCE_BREAK: "critical",
    FailureClass.MEASURED_PREDICTED_CONFLATION: "critical",
    FailureClass.HEURISTIC_FALLBACK: "warning",
    FailureClass.UNSUPPORTED_CLAIM: "error",
    FailureClass.INVALID_CHEMISTRY: "critical",
    FailureClass.OUTSIDE_APPLICABILITY_DOMAIN: "warning",
    FailureClass.STRUCTURAL_CLAIM_BLOCKED: "warning",
    FailureClass.NO_VALID_CANDIDATES: "error",
    FailureClass.MECHANISM_INCONSISTENT: "error",
    FailureClass.CONTRADICTION: "warning",
    FailureClass.OVERCONFIDENT: "error",
    FailureClass.NON_REPRODUCIBLE: "critical",
    FailureClass.ABSTAINED: "info",
    FailureClass.BUDGET_EXCEEDED: "warning",
    FailureClass.UNKNOWN: "error",
}

#: Default recovery hint surfaced in reports and the policy ledger.
RECOVERY: dict[FailureClass, str] = {
    FailureClass.MISSING_INPUT: "supply the missing scientific input and rerun",
    FailureClass.UNRESOLVED_ENTITY: "resolve the target/E3 against curated identifiers",
    FailureClass.FIXTURE_IN_SCIENTIFIC_MODE: "remove the fixture or run in DEMO/TEST mode",
    FailureClass.SYNTHETIC_INPUT: "replace the synthetic input with real measured data",
    FailureClass.TOOL_UNAVAILABLE: "install/activate the backend or choose an available tool",
    FailureClass.TOOL_ERROR: "inspect the tool trace and retry",
    FailureClass.TOOL_TIMEOUT: "retry with a larger timeout or a cheaper backend",
    FailureClass.RETRY_EXHAUSTED: "escalate to fallback or abstain",
    FailureClass.MISSING_EVIDENCE: "run the required module or retrieve the evidence",
    FailureClass.MISSING_REQUIRED_MODULE: "restore the missing module in the task graph",
    FailureClass.MODULE_FAILED: "repair the module and rerun",
    FailureClass.PROVENANCE_BREAK: "restore tool/version provenance before claiming",
    FailureClass.MEASURED_PREDICTED_CONFLATION: "label predictions as PREDICTED, not measured",
    FailureClass.HEURISTIC_FALLBACK: "replace the heuristic with a validated model",
    FailureClass.UNSUPPORTED_CLAIM: "remove the claim or attach supporting evidence",
    FailureClass.INVALID_CHEMISTRY: "repair chemistry/stereochemistry before advancing",
    FailureClass.OUTSIDE_APPLICABILITY_DOMAIN: "revise the candidate or narrow the claim",
    FailureClass.STRUCTURAL_CLAIM_BLOCKED: "obtain ternary/structure evidence",
    FailureClass.NO_VALID_CANDIDATES: "generate or repair candidates",
    FailureClass.MECHANISM_INCONSISTENT: "reconcile the target/E3/warhead mechanism chain",
    FailureClass.CONTRADICTION: "adjudicate the contradictory evidence",
    FailureClass.OVERCONFIDENT: "lower confidence and gather decision-critical evidence",
    FailureClass.NON_REPRODUCIBLE: "pin versions, seeds and inputs; rerun deterministically",
    FailureClass.ABSTAINED: "report the explicit abstention, do not fabricate an answer",
    FailureClass.BUDGET_EXCEEDED: "reduce scope or raise the compute budget",
    FailureClass.UNKNOWN: "capture a typed failure and triage",
}

#: Map legacy free-text failure strings onto the taxonomy.
_LEGACY_ALIASES: dict[str, FailureClass] = {
    "required_module_failed": FailureClass.MODULE_FAILED,
    "missing_required_module": FailureClass.MISSING_REQUIRED_MODULE,
    "outside_applicability_domain": FailureClass.OUTSIDE_APPLICABILITY_DOMAIN,
    "provenance_break": FailureClass.PROVENANCE_BREAK,
    "no_valid_candidates": FailureClass.NO_VALID_CANDIDATES,
    "chemistry_or_stereochemistry_error": FailureClass.INVALID_CHEMISTRY,
    "overconfident_decision": FailureClass.OVERCONFIDENT,
    "missing_capability_model": FailureClass.MISSING_REQUIRED_MODULE,
    "missing_evidence_labels": FailureClass.MISSING_EVIDENCE,
    "heuristic_fallback": FailureClass.HEURISTIC_FALLBACK,
    "unsupported_claim": FailureClass.UNSUPPORTED_CLAIM,
    "tool_failure": FailureClass.TOOL_ERROR,
    "timeout": FailureClass.TOOL_TIMEOUT,
}

#: Keyword -> class, used by :func:`classify_failure` when no explicit class.
_KEYWORDS: list[tuple[tuple[str, ...], FailureClass]] = [
    (("fixture",), FailureClass.FIXTURE_IN_SCIENTIFIC_MODE),
    (("synthetic", "placeholder"), FailureClass.SYNTHETIC_INPUT),
    (("timeout", "timed out"), FailureClass.TOOL_TIMEOUT),
    (("not registered", "not available", "unavailable", "no backend", "missing backend"),
     FailureClass.TOOL_UNAVAILABLE),
    (("traceback", "raised", "exception", "error"), FailureClass.TOOL_ERROR),
    (("unresolved", "not resolved"), FailureClass.UNRESOLVED_ENTITY),
    (("missing", "required input", "no input"), FailureClass.MISSING_INPUT),
    (("stereochemistry", "invalid chem", "rdkit-invalid", "not rdkit"), FailureClass.INVALID_CHEMISTRY),
    (("applicability", "outside domain", "out of domain"), FailureClass.OUTSIDE_APPLICABILITY_DOMAIN),
    (("ternary", "structure evidence", "structural claim"), FailureClass.STRUCTURAL_CLAIM_BLOCKED),
    (("provenance",), FailureClass.PROVENANCE_BREAK),
    (("heuristic",), FailureClass.HEURISTIC_FALLBACK),
    (("contradict",), FailureClass.CONTRADICTION),
    (("mechanism", "inconsistent", "chain"), FailureClass.MECHANISM_INCONSISTENT),
    (("no valid candidate", "no candidate"), FailureClass.NO_VALID_CANDIDATES),
    (("budget", "token limit", "max_tokens"), FailureClass.BUDGET_EXCEEDED),
    (("unsupported",), FailureClass.UNSUPPORTED_CLAIM),
]


class Failure(BaseModel):
    """A single typed failure with provenance and a recovery hint."""

    failure_class: FailureClass = FailureClass.UNKNOWN
    message: str = ""
    module_id: str = ""
    tool: str = ""
    severity: str = "error"
    retryable: bool = False
    evidence_ref: str = ""
    recovery: str = ""
    attempt: int = 1
    context: dict[str, Any] = Field(default_factory=dict)


class CriticResult(BaseModel):
    """Output of one named critic.

    Three critics run per canonical run (evidence, mechanism, reproducibility)
    and their results are merged into the single :class:`CriticVerdict`.
    """

    name: str = ""
    status: str = "pass"  # pass | pass_with_warnings | fail | abstain
    failures: list[Failure] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    checks_run: list[str] = Field(default_factory=list)
    uncertainty: dict[str, str] = Field(default_factory=dict)

    @property
    def critical_failures(self) -> list[Failure]:
        return [f for f in self.failures if f.severity == "critical"]

    def failure_classes(self) -> list[str]:
        return sorted({f.failure_class.value for f in self.failures})


def make_failure(
    failure_class: FailureClass | str,
    message: str = "",
    *,
    module_id: str = "",
    tool: str = "",
    evidence_ref: str = "",
    severity: str = "",
    retryable: bool | None = None,
    recovery: str = "",
    attempt: int = 1,
    context: dict[str, Any] | None = None,
) -> Failure:
    """Build a :class:`Failure`, filling severity/retry/recovery from the class."""
    cls = failure_class if isinstance(failure_class, FailureClass) else FailureClass(failure_class)
    return Failure(
        failure_class=cls,
        message=message or "",
        module_id=module_id,
        tool=tool,
        severity=severity or SEVERITY.get(cls, "error"),
        retryable=(cls in RETRYABLE_CLASSES) if retryable is None else retryable,
        evidence_ref=evidence_ref,
        recovery=recovery or RECOVERY.get(cls, ""),
        attempt=attempt,
        context=dict(context or {}),
    )


def classify_failure(
    message: str,
    *,
    module_id: str = "",
    tool: str = "",
    evidence_ref: str = "",
    failure_class: FailureClass | str | None = None,
    attempt: int = 1,
    context: dict[str, Any] | None = None,
) -> Failure:
    """Classify a free-text failure, or build one from an explicit class."""
    if failure_class is not None:
        cls = FailureClass(failure_class) if not isinstance(failure_class, FailureClass) else failure_class
    else:
        text = (message or "").strip().lower()
        cls = _LEGACY_ALIASES.get(text, FailureClass.UNKNOWN)
        if cls is FailureClass.UNKNOWN:
            for tokens, candidate in _KEYWORDS:
                if any(token in text for token in tokens):
                    cls = candidate
                    break
    return make_failure(
        cls,
        message or "",
        module_id=module_id,
        tool=tool,
        evidence_ref=evidence_ref,
        attempt=attempt,
        context=context,
    )


def failure_taxonomy() -> list[dict[str, Any]]:
    """Serialisable description of the taxonomy (for docs and reports)."""
    rows: list[dict[str, Any]] = []
    for cls in FailureClass:
        rows.append(
            {
                "failure_class": cls.value,
                "severity": SEVERITY.get(cls, "error"),
                "retryable": cls in RETRYABLE_CLASSES,
                "recovery": RECOVERY.get(cls, ""),
            }
        )
    return rows


def as_failures(items: Iterable[Any], *, module_id: str = "", tool: str = "") -> list[Failure]:
    """Coerce a mixed list of strings / Failures / dicts into Failures."""
    out: list[Failure] = []
    for item in items:
        if isinstance(item, Failure):
            out.append(item)
        elif isinstance(item, dict):
            out.append(Failure(**item))
        else:
            out.append(classify_failure(str(item), module_id=module_id, tool=tool))
    return out


__all__ = [
    "CriticResult",
    "Failure",
    "FailureClass",
    "RECOVERY",
    "RETRYABLE_CLASSES",
    "SEVERITY",
    "as_failures",
    "classify_failure",
    "failure_taxonomy",
    "make_failure",
]
