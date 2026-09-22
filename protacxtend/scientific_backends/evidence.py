"""Scientific evidence tiers and result envelope.

Every capability in :mod:`protacxtend.scientific_backends` returns a
:class:`ScientificResult` carrying the capability, the backend that produced it,
the evidence tier, whether it is an approximation, GPU usage, runtime, licence
class, citations and warnings. Nothing is allowed to claim more certainty than
its tier.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvidenceTier(str, Enum):
    """Ordered strength-of-evidence ladder (never hidden from the caller)."""

    TIER_0_GEOMETRY = "TIER_0_GEOMETRY"
    TIER_1_MINIMIZED = "TIER_1_MINIMIZED"
    TIER_2_DOCKED = "TIER_2_DOCKED"
    TIER_3_SHORT_MD = "TIER_3_SHORT_MD"
    TIER_4_REPLICATE_MD = "TIER_4_REPLICATE_MD"
    TIER_5_ENDPOINT_FREE_ENERGY = "TIER_5_ENDPOINT_FREE_ENERGY"

    @property
    def rank(self) -> int:
        return [
            EvidenceTier.TIER_0_GEOMETRY,
            EvidenceTier.TIER_1_MINIMIZED,
            EvidenceTier.TIER_2_DOCKED,
            EvidenceTier.TIER_3_SHORT_MD,
            EvidenceTier.TIER_4_REPLICATE_MD,
            EvidenceTier.TIER_5_ENDPOINT_FREE_ENERGY,
        ].index(self)


class CapabilityStatus(str, Enum):
    """Explicit scientific outcome taxonomy.

    A backend must never report ``SUCCESS`` unless it produced a *scientifically
    valid* artefact.  The extra states make silent failures impossible:

    ``REJECTED_INPUT``          input failed validation before any computation
    ``OUTPUT_INVALID``          backend ran but emitted an artefact that fails
                                structural validation (NaN, wrong atom count...)
    ``SCIENTIFIC_SANITY_FAILED`` output parsed but is physically implausible
    ``BACKEND_UNAVAILABLE``     engine/binary/model is not installed/reachable
    ``TIMEOUT``                 backend exceeded its declared time budget
    ``FALLBACK_SUCCESS``        primary failed; a labelled fallback produced the
                                result (never silently promoted to SUCCESS)
    """

    SUCCESS = "success"
    WARNING = "warning"
    FALLBACK_SUCCESS = "FALLBACK_SUCCESS"
    REJECTED_INPUT = "REJECTED_INPUT"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    SCIENTIFIC_SANITY_FAILED = "SCIENTIFIC_SANITY_FAILED"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    ERROR = "error"


#: Outcomes that may never be counted as a scientific success in an audit.
NON_SUCCESS_OUTCOMES = frozenset({
    CapabilityStatus.REJECTED_INPUT.value,
    CapabilityStatus.OUTPUT_INVALID.value,
    CapabilityStatus.SCIENTIFIC_SANITY_FAILED.value,
    CapabilityStatus.BACKEND_UNAVAILABLE.value,
    CapabilityStatus.CAPABILITY_UNAVAILABLE.value,
    CapabilityStatus.TIMEOUT.value,
    CapabilityStatus.LICENSE_REQUIRED.value,
    CapabilityStatus.ERROR.value,
})

#: Outcomes that represent a usable *computation* (a real number/pose exists).
USABLE_OUTCOMES = frozenset({
    CapabilityStatus.SUCCESS.value,
    CapabilityStatus.WARNING.value,
    CapabilityStatus.FALLBACK_SUCCESS.value,
})


@dataclass
class ScientificResult:
    """Uniform envelope for every scientific capability result."""

    capability: str
    backend: str = ""
    backend_version: str = ""
    evidence_tier: str = EvidenceTier.TIER_0_GEOMETRY.value
    approximation: bool = False
    gpu_used: bool = False
    runtime_seconds: float = 0.0
    license_class: str = "open_source_permissive"
    citations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = CapabilityStatus.SUCCESS.value
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    method_label: str = ""
    _started: float = field(default=0.0, repr=False, compare=False)

    # ── construction helpers ───────────────────────────────────────────
    @classmethod
    def begin(cls, capability: str, **kwargs: Any) -> "ScientificResult":
        return cls(capability=capability, _started=time.time(), **kwargs)

    def finish(self) -> "ScientificResult":
        if self._started:
            self.runtime_seconds = round(time.time() - self._started, 3)
        return self

    def ok(self) -> bool:
        return self.status in USABLE_OUTCOMES

    def succeeded(self) -> bool:
        """True only for an unqualified primary-path success."""
        return self.status == CapabilityStatus.SUCCESS.value

    def is_fallback(self) -> bool:
        return self.status == CapabilityStatus.FALLBACK_SUCCESS.value

    def outcome(self) -> str:
        """Coarse audit bucket used by the benchmark statistics."""
        if self.status in USABLE_OUTCOMES:
            return "usable"
        if self.status == CapabilityStatus.REJECTED_INPUT.value:
            return "rejected_input"
        if self.status == CapabilityStatus.OUTPUT_INVALID.value:
            return "output_invalid"
        if self.status == CapabilityStatus.SCIENTIFIC_SANITY_FAILED.value:
            return "sanity_failed"
        if self.status in {CapabilityStatus.BACKEND_UNAVAILABLE.value,
                           CapabilityStatus.CAPABILITY_UNAVAILABLE.value}:
            return "backend_unavailable"
        if self.status == CapabilityStatus.TIMEOUT.value:
            return "timeout"
        if self.status == CapabilityStatus.LICENSE_REQUIRED.value:
            return "license_required"
        return "error"

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "capability": self.capability,
            "backend": self.backend,
            "backend_version": self.backend_version,
            "evidence_tier": self.evidence_tier,
            "approximation": self.approximation,
            "gpu_used": self.gpu_used,
            "runtime_seconds": self.runtime_seconds,
            "license_class": self.license_class,
            "citations": list(self.citations),
            "warnings": list(self.warnings),
            "status": self.status,
            "summary": self.summary,
            "method_label": self.method_label,
            "sources": list(self.sources),
            "data": self.data,
        }
        return payload

    @classmethod
    def license_required(cls, capability: str, backend: str, reason: str,
                         citation: str = "") -> "ScientificResult":
        return cls(
            capability=capability, backend=backend, status=CapabilityStatus.LICENSE_REQUIRED.value,
            license_class="commercial", summary=reason, method_label="LICENSE_REQUIRED",
            warnings=[reason], citations=[citation] if citation else [],
        )

    @classmethod
    def unavailable(cls, capability: str, reason: str,
                    tried: list[str] | None = None) -> "ScientificResult":
        return cls(
            capability=capability, status=CapabilityStatus.BACKEND_UNAVAILABLE.value,
            summary=reason, method_label="BACKEND_UNAVAILABLE",
            warnings=[f"tried: {', '.join(tried)}"] if tried else [],
        )

    # ── explicit scientific-outcome constructors ───────────────────────
    @classmethod
    def rejected_input(cls, capability: str, backend: str, reason: str) -> "ScientificResult":
        return cls(capability=capability, backend=backend,
                   status=CapabilityStatus.REJECTED_INPUT.value, summary=reason,
                   method_label="REJECTED_INPUT", warnings=[reason])

    @classmethod
    def output_invalid(cls, capability: str, backend: str, reason: str) -> "ScientificResult":
        return cls(capability=capability, backend=backend,
                   status=CapabilityStatus.OUTPUT_INVALID.value, summary=reason,
                   method_label="OUTPUT_INVALID", warnings=[reason])

    @classmethod
    def sanity_failed(cls, capability: str, backend: str, reason: str) -> "ScientificResult":
        return cls(capability=capability, backend=backend,
                   status=CapabilityStatus.SCIENTIFIC_SANITY_FAILED.value, summary=reason,
                   method_label="SCIENTIFIC_SANITY_FAILED", warnings=[reason])

    @classmethod
    def timed_out(cls, capability: str, backend: str, seconds: float) -> "ScientificResult":
        return cls(capability=capability, backend=backend,
                   status=CapabilityStatus.TIMEOUT.value,
                   summary=f"{backend} exceeded its time budget ({seconds:.0f}s)",
                   method_label="TIMEOUT")

    @classmethod
    def fallback_success(cls, capability: str, backend: str, primary: str,
                         reason: str) -> "ScientificResult":
        result = cls(capability=capability, backend=backend,
                     status=CapabilityStatus.FALLBACK_SUCCESS.value,
                     summary=f"fallback after {primary} failed: {reason}",
                     method_label="FALLBACK_SUCCESS")
        result.warnings.append(f"primary backend '{primary}' failed: {reason}")
        result.data["fallback"] = {"primary": primary, "fallback": backend,
                                   "primary_failure": reason}
        return result


__all__ = ["EvidenceTier", "CapabilityStatus", "ScientificResult",
           "NON_SUCCESS_OUTCOMES", "USABLE_OUTCOMES"]
