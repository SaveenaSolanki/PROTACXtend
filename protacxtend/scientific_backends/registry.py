"""Capability-first scientific backend registry.

The agent asks for a *capability* (``ligand_docking``, ``molecular_dynamics``,
…); this registry returns the best **locally available, licence-compatible**
implementation. Commercial / academic-only / web-only engines are registered
only as optional adapters and are excluded by the default licence policy — they
are never required for a normal run.

Design rules
------------
* capability first, implementation second;
* every backend declares licence + capability + health + priority;
* the resolver filters by :class:`~protacxtend.scientific_backends.licenses.LicensePolicy`;
* unsupported capabilities degrade to the next backend, never to a hard error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from protacxtend.scientific_backends.dispatch import Availability
from protacxtend.scientific_backends.licenses import (
    DEFAULT_POLICY,
    LicenseInfo,
    LicensePolicy,
    OPEN_SOURCE_PERMISSIVE,
)


class Capability(str, Enum):
    CHEMISTRY = "chemistry"
    CONFORMER_GENERATION = "conformer_generation"
    PROTEIN_PREPARATION = "protein_preparation"
    POCKET_DETECTION = "pocket_detection"
    LIGAND_DOCKING = "ligand_docking"
    PPI_DOCKING = "ppi_docking"
    TERNARY_DOCKING = "ternary_docking"
    MOLECULAR_DYNAMICS = "molecular_dynamics"
    MD_ANALYSIS = "md_analysis"
    INTERACTION_ENERGY = "interaction_energy"
    BINDING_ENERGY = "binding_energy"
    ADMET = "admet"
    INTERACTION_FINGERPRINT = "interaction_fingerprint"
    LINKER_ANALYSIS = "linker_analysis"
    PROTAC_SCORING = "protac_scoring"
    MOLECULAR_GLUE_SCORING = "molecular_glue_scoring"
    METABOLITE_PPI_SCORING = "metabolite_ppi_scoring"
    PROTEIN_STRUCTURE = "protein_structure"
    CANDIDATE_RANKING = "candidate_ranking"


@dataclass
class BackendSpec:
    """Declarative description of one scientific backend."""

    name: str
    capabilities: tuple[Capability, ...]
    license: LicenseInfo = OPEN_SOURCE_PERMISSIVE
    priority: int = 50
    description: str = ""
    version: str = ""
    citation: str = ""
    requires_gpu: bool = False
    requires_external_binary: bool = False
    requires_network: bool = False
    optional: bool = False
    handlers: dict[Capability, Callable[..., Any]] = field(default_factory=dict)
    health_check: Callable[[], Availability] | None = None

    # ── licence-derived flags (explicit in the required backend contract) ──
    @property
    def redistributable(self) -> bool:
        return self.license.redistributable

    @property
    def academic_only(self) -> bool:
        return self.license.academic_only

    @property
    def commercial_use_restricted(self) -> bool:
        return self.license.commercial_use_restricted

    @property
    def license_class(self) -> str:
        return self.license.license_class.value

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def health(self) -> Availability:
        if self.health_check is None:
            return Availability(available=True, version=self.version, detail="no health check")
        try:
            return self.health_check()
        except Exception as exc:  # noqa: BLE001
            return Availability(available=False, detail=f"health check error: {exc}")

    def to_dict(self, capability: Capability | None = None) -> dict[str, Any]:
        health = self.health()
        return {
            "name": self.name,
            "capabilities": [c.value for c in self.capabilities],
            "license": self.license.name,
            "license_class": self.license_class,
            "redistributable": self.redistributable,
            "requires_gpu": self.requires_gpu,
            "requires_external_binary": self.requires_external_binary,
            "requires_network": self.requires_network,
            "academic_only": self.academic_only,
            "commercial_use_restricted": self.commercial_use_restricted,
            "priority": self.priority,
            "optional": self.optional,
            "version": health.version or self.version,
            "available": health.available,
            "health_detail": health.detail,
            "gpu": health.gpu,
            "citation": self.citation,
            "description": self.description,
            "capability": capability.value if capability else "",
        }


class BackendRegistry:
    def __init__(self) -> None:
        self._backends: dict[str, BackendSpec] = {}

    def register(self, spec: BackendSpec) -> BackendSpec:
        self._backends[spec.name] = spec
        return spec

    def get(self, name: str) -> BackendSpec | None:
        return self._backends.get(name)

    def all(self) -> list[BackendSpec]:
        return list(self._backends.values())

    def for_capability(self, capability: Capability) -> list[BackendSpec]:
        return [b for b in self._backends.values() if b.supports(capability)]

    def resolve(
        self,
        capability: Capability,
        policy: LicensePolicy | None = None,
        *,
        include_restricted: bool = False,
        only_available: bool = True,
    ) -> list[BackendSpec]:
        """Ordered list of usable backends for a capability (best first)."""
        policy = policy or DEFAULT_POLICY
        candidates = self.for_capability(capability)
        allowed: list[BackendSpec] = []
        for spec in candidates:
            ok, _ = policy.allows(spec.license)
            if not ok and not include_restricted:
                continue
            if only_available and not spec.health().available:
                continue
            allowed.append(spec)
        allowed.sort(key=lambda s: (-s.priority, s.name))
        return allowed

    def resolve_one(
        self,
        capability: Capability,
        policy: LicensePolicy | None = None,
        *,
        include_restricted: bool = False,
    ) -> BackendSpec | None:
        resolved = self.resolve(capability, policy, include_restricted=include_restricted)
        return resolved[0] if resolved else None

    def health_report(self, policy: LicensePolicy | None = None) -> list[dict[str, Any]]:
        policy = policy or DEFAULT_POLICY
        rows: list[dict[str, Any]] = []
        for spec in sorted(self._backends.values(), key=lambda s: (-s.priority, s.name)):
            health = spec.health()
            allowed, reason = policy.allows(spec.license)
            row = spec.to_dict()
            row["policy_allowed"] = allowed
            row["policy_reason"] = reason
            rows.append(row)
        return rows

    def capability_matrix(self, policy: LicensePolicy | None = None) -> list[dict[str, Any]]:
        policy = policy or DEFAULT_POLICY
        rows: list[dict[str, Any]] = []
        for capability in Capability:
            usable = self.resolve(capability, policy, only_available=True)
            any_registered = self.for_capability(capability)
            rows.append({
                "capability": capability.value,
                "usable_backends": [b.name for b in usable],
                "best_backend": usable[0].name if usable else "",
                "registered": [b.name for b in any_registered],
                "status": "ready" if usable else ("LICENSE_REQUIRED" if any_registered else "unavailable"),
            })
        return rows


REGISTRY = BackendRegistry()
_BACKENDS_LOADED = False


def load_backends() -> BackendRegistry:
    """Import every backend module once (idempotent)."""
    global _BACKENDS_LOADED
    if not _BACKENDS_LOADED:
        from protacxtend.scientific_backends import backends  # noqa: F401
        from protacxtend.scientific_backends import optional_backends  # noqa: F401
        _BACKENDS_LOADED = True
    return REGISTRY


def register(spec: BackendSpec) -> BackendSpec:
    return REGISTRY.register(spec)


def resolve(capability: Capability | str, policy: LicensePolicy | None = None,
            **kwargs: Any) -> list[BackendSpec]:
    load_backends()
    capability = capability if isinstance(capability, Capability) else Capability(capability)
    return REGISTRY.resolve(capability, policy, **kwargs)


def resolve_one(capability: Capability | str, policy: LicensePolicy | None = None,
                **kwargs: Any) -> BackendSpec | None:
    load_backends()
    capability = capability if isinstance(capability, Capability) else Capability(capability)
    return REGISTRY.resolve_one(capability, policy, **kwargs)


__all__ = [
    "Capability",
    "BackendSpec",
    "BackendRegistry",
    "REGISTRY",
    "register",
    "resolve",
    "resolve_one",
    "load_backends",
]
