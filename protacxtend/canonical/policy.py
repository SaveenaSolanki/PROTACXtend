"""Retry / fallback / abstention policy for the canonical control plane.

The default behaviour of a canonical run is *fail closed*: a required module
that fails stops the run. This module makes that behaviour explicit and
configurable, and adds two recoverable responses that a scientific agent must
have:

* **retry** — transient tool/network failures (:data:`RETRYABLE_CLASSES`) are
  retried up to ``max_retries`` with optional backoff, recording every attempt;
* **fallback** — a module may declare a fallback implementation; when the
  primary fails the fallback runs and the node is marked ``degraded``;
* **abstain** — when a required module cannot be recovered, the run emits an
  explicit typed abstention (``TaskStatus.ABSTAINED``) instead of fabricating a
  result or crashing the whole pipeline (unless ``abstain_on_required`` is
  disabled, in which case it stops).

The policy is pure and deterministic: given the same failure and attempt
number it always returns the same action. That is what makes the retry ledger
reproducible for benchmarking.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from protacxtend.backend.schemas import BaseModel, Field
from protacxtend.canonical.failures import (
    RETRYABLE_CLASSES,
    Failure,
    FailureClass,
    make_failure,
)


class PolicyAction(str, Enum):
    ADVANCE = "advance"   # continue, no recovery needed (e.g. optional failure)
    RETRY = "retry"       # rerun the same module
    FALLBACK = "fallback"  # run the declared fallback
    ABSTAIN = "abstain"   # explicit typed non-answer
    STOP = "stop"         # hard stop, run fails


class RetryPolicy(BaseModel):
    """Configuration for recovery behaviour."""

    max_retries: int = 0
    backoff_s: float = 0.0
    retryable_classes: list[str] = Field(
        default_factory=lambda: sorted(cls.value for cls in RETRYABLE_CLASSES)
    )
    fallback_enabled: bool = False
    #: Required-module failure -> explicit abstention rather than hard stop.
    abstain_on_required: bool = False
    #: Optional-module failure -> degrade and continue.
    degrade_optional: bool = True

    def is_retryable(self, failure: Failure) -> bool:
        return (
            failure.retryable
            or failure.failure_class in RETRYABLE_CLASSES
            or failure.failure_class.value in self.retryable_classes
        )


class PolicyDecision(BaseModel):
    action: PolicyAction = PolicyAction.STOP
    reason: str = ""
    failure_class: str = ""
    module_id: str = ""
    attempt: int = 1
    max_attempts: int = 1
    next_module: str = ""
    backoff_s: float = 0.0

    @property
    def is_recovery(self) -> bool:
        return self.action in {PolicyAction.RETRY, PolicyAction.FALLBACK}


class ExecutionPolicy:
    """Deterministic retry / fallback / abstention decision function."""

    name = "ExecutionPolicy"

    def __init__(self, retry: RetryPolicy | None = None):
        self.retry = retry or RetryPolicy()

    # ------------------------------------------------------------------
    def on_failure(
        self,
        failure: Failure,
        *,
        module_id: str,
        attempt: int = 1,
        required: bool = True,
        has_fallback: bool = False,
        fallback_module: str = "",
        fallback_available: bool = True,
    ) -> PolicyDecision:
        """Decide what to do after a module failure."""
        max_attempts = self.retry.max_retries + 1
        # 1. retry transient failures
        if self.retry.is_retryable(failure) and attempt < max_attempts:
            return PolicyDecision(
                action=PolicyAction.RETRY,
                reason=f"retryable {failure.failure_class.value}; attempt {attempt}/{max_attempts}",
                failure_class=failure.failure_class.value,
                module_id=module_id,
                attempt=attempt,
                max_attempts=max_attempts,
                backoff_s=self.retry.backoff_s,
            )
        # 2. fallback when the module declares one and it is usable
        if self.retry.fallback_enabled and has_fallback and fallback_available:
            return PolicyDecision(
                action=PolicyAction.FALLBACK,
                reason=f"primary failed ({failure.failure_class.value}); running fallback",
                failure_class=failure.failure_class.value,
                module_id=module_id,
                attempt=attempt,
                max_attempts=max_attempts,
                next_module=fallback_module,
            )
        # 3. explicit abstention for unrecoverable required modules
        if required and self.retry.abstain_on_required:
            return PolicyDecision(
                action=PolicyAction.ABSTAIN,
                reason=f"required module {module_id} unrecoverable ({failure.failure_class.value}); abstaining",
                failure_class=failure.failure_class.value,
                module_id=module_id,
                attempt=attempt,
                max_attempts=max_attempts,
            )
        if not required and self.retry.degrade_optional:
            return PolicyDecision(
                action=PolicyAction.ADVANCE,
                reason=f"optional module {module_id} failed; degrading and continuing",
                failure_class=failure.failure_class.value,
                module_id=module_id,
                attempt=attempt,
                max_attempts=max_attempts,
            )
        # 4. fail closed
        return PolicyDecision(
            action=PolicyAction.STOP,
            reason=f"required module {module_id} failed ({failure.failure_class.value})",
            failure_class=failure.failure_class.value,
            module_id=module_id,
            attempt=attempt,
            max_attempts=max_attempts,
        )

    # ------------------------------------------------------------------
    def retry_exhausted(self, failure: Failure, *, module_id: str, attempts: int) -> Failure:
        """Convert a transient failure into an explicit ``retry_exhausted`` one."""
        return make_failure(
            FailureClass.RETRY_EXHAUSTED if failure.retryable else failure.failure_class,
            message=failure.message,
            module_id=module_id,
            tool=failure.tool,
            attempt=attempts,
            context={**failure.context, "original_class": failure.failure_class.value},
        )

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "max_retries": self.retry.max_retries,
            "backoff_s": self.retry.backoff_s,
            "retryable_classes": list(self.retry.retryable_classes),
            "fallback_enabled": self.retry.fallback_enabled,
            "abstain_on_required": self.retry.abstain_on_required,
            "degrade_optional": self.retry.degrade_optional,
        }


def policy_from_config(config: dict[str, Any] | None) -> ExecutionPolicy:
    """Build a policy from a run config (CLI / API / benchmark)."""
    config = dict(config or {})
    raw = config.get("retry_policy") or config.get("policy") or {}
    if isinstance(raw, RetryPolicy):
        return ExecutionPolicy(raw)
    if isinstance(raw, ExecutionPolicy):
        return raw
    if not isinstance(raw, dict):
        return ExecutionPolicy()
    known = {
        key: raw[key]
        for key in (
            "max_retries",
            "backoff_s",
            "retryable_classes",
            "fallback_enabled",
            "abstain_on_required",
            "degrade_optional",
        )
        if key in raw
    }
    return ExecutionPolicy(RetryPolicy(**known))


__all__ = [
    "ExecutionPolicy",
    "PolicyAction",
    "PolicyDecision",
    "RetryPolicy",
    "policy_from_config",
]
