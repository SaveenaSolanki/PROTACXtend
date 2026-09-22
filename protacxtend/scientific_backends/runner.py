"""Capability runner: resolve a capability to the best backend and execute it.

This is the public entry point used by the agent and by the ``capabilities``
facade. It guarantees three things:

* restricted backends are skipped unless explicitly opted in;
* if no backend is usable it degrades to the next one (never a hard crash);
* if *only* restricted backends exist, the result is ``LICENSE_REQUIRED`` with
  the reason — never a silent failure.
"""

from __future__ import annotations

from typing import Any, Callable

from protacxtend.scientific_backends.evidence import (
    CapabilityStatus,
    EvidenceTier,
    ScientificResult,
    USABLE_OUTCOMES,
)
from protacxtend.scientific_backends.licenses import DEFAULT_POLICY, LicensePolicy, policy_from_env
from protacxtend.scientific_backends.registry import (
    Capability,
    BackendSpec,
    load_backends,
    REGISTRY,
)


def _coerce_capability(capability: Capability | str) -> Capability:
    if isinstance(capability, Capability):
        return capability
    key = str(capability).strip().lower()
    for candidate in Capability:
        if candidate.value == key:
            return candidate
    # tolerate aliases used elsewhere in the codebase
    aliases = {
        "docking": Capability.LIGAND_DOCKING,
        "protein_docking": Capability.PPI_DOCKING,
        "protein_protein_docking": Capability.PPI_DOCKING,
        "md": Capability.MOLECULAR_DYNAMICS,
        "free_energy": Capability.BINDING_ENERGY,
        "admet_toxicity": Capability.ADMET,
        "protac": Capability.PROTAC_SCORING,
        "glue": Capability.MOLECULAR_GLUE_SCORING,
        "metabolite_ppi": Capability.METABOLITE_PPI_SCORING,
    }
    if key in aliases:
        return aliases[key]
    raise KeyError(f"unknown capability '{capability}'")


def run_capability(
    capability: Capability | str,
    *,
    policy: LicensePolicy | None = None,
    include_restricted: bool = False,
    preferred_backend: str | None = None,
    disabled_backends: set[str] | None = None,
    mark_fallback_after: str | None = None,
    **kwargs: Any,
) -> ScientificResult:
    """Run *capability* on the best available backend.

    ``preferred_backend`` forces a specific backend (used to exercise optional
    adapters and to receive their ``LICENSE_REQUIRED`` result).

    ``disabled_backends`` deliberately removes backends from resolution, which
    is how the audit tests that a *registered fallback actually executes*.

    ``mark_fallback_after`` names the primary backend that was deliberately
    disabled; when another backend succeeds the result is labelled
    ``FALLBACK_SUCCESS`` (never silently promoted to ``SUCCESS``).
    """
    load_backends()
    policy = policy or policy_from_env()
    cap = _coerce_capability(capability)
    disabled = set(disabled_backends or ())

    if preferred_backend:
        spec = REGISTRY.get(preferred_backend)
        if spec is None or not spec.supports(cap):
            return ScientificResult.unavailable(
                cap.value, f"backend '{preferred_backend}' does not provide {cap.value}")
        return _invoke(spec, cap, kwargs, policy, include_restricted=True)

    usable = [s for s in REGISTRY.resolve(cap, policy, include_restricted=include_restricted)
              if s.name not in disabled]
    tried: list[str] = []
    errors: list[str] = []
    last: ScientificResult | None = None
    if not usable:
        restricted = [s for s in _restricted_available(cap, policy) if s.name not in disabled]
        if restricted and not include_restricted:
            first = restricted[0]
            return ScientificResult.license_required(
                cap.value, first.name,
                f"{cap.value}: only restricted backends available ({first.name}); "
                "default policy requires free/local engines",
                citation=first.citation)
        reason = f"no usable backend for {cap.value}"
        if disabled:
            reason += f" after disabling {', '.join(sorted(disabled))}"
        return ScientificResult.unavailable(cap.value, reason, tried=sorted(disabled))

    for spec in usable:
        result = _invoke(spec, cap, kwargs, policy, include_restricted=include_restricted)
        if result is None:
            tried.append(spec.name)
            continue
        if result.status in USABLE_OUTCOMES:
            if mark_fallback_after and spec.name != mark_fallback_after:
                result.status = CapabilityStatus.FALLBACK_SUCCESS.value
                result.method_label = "FALLBACK_SUCCESS"
                result.data.setdefault("fallback", {}).update({
                    "primary": mark_fallback_after,
                    "fallback": spec.name,
                    "primary_failure": "deliberately disabled for fallback test",
                })
                result.warnings.append(
                    f"result produced by fallback '{spec.name}' after primary "
                    f"'{mark_fallback_after}' was disabled")
            return result
        tried.append(spec.name)
        errors.append(f"{spec.name}: {result.summary}")
        last = result

    if last is not None:
        last.warnings.append("all usable backends failed: " + "; ".join(errors)[:500])
        return last
    return ScientificResult.unavailable(
        cap.value,
        f"no usable backend for {cap.value}; tried: {', '.join(tried) or 'none'}",
        tried=tried)


def execute_primary_then_fallback(
    capability: Capability | str,
    primary: str,
    fallback: str,
    *,
    policy: LicensePolicy | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute *primary* then, if it fails, the named *fallback*, honestly.

    Returns a dict with ``primary`` and ``fallback`` envelope payloads.  The
    fallback is executed through the normal handler so it does real work (not a
    resolver-only simulation).
    """
    load_backends()
    policy = policy or policy_from_env()
    cap = _coerce_capability(capability)
    primary_spec = REGISTRY.get(primary)
    fallback_spec = REGISTRY.get(fallback)
    primary_result = (
        _invoke(primary_spec, cap, kwargs, policy, include_restricted=True)
        if primary_spec and primary_spec.supports(cap) else None)
    if primary_result is None:
        primary_result = ScientificResult.unavailable(
            cap.value, f"primary '{primary}' does not provide {cap.value}")
    used_fallback = False
    fallback_result: ScientificResult | None = None
    if not primary_result.ok():
        if fallback_spec and fallback_spec.supports(cap):
            fallback_result = _invoke(fallback_spec, cap, kwargs, policy,
                                      include_restricted=True)
            if fallback_result is not None:
                used_fallback = True
                if fallback_result.ok():
                    fallback_result.status = CapabilityStatus.FALLBACK_SUCCESS.value
                    fallback_result.method_label = "FALLBACK_SUCCESS"
                    fallback_result.data.setdefault("fallback", {}).update({
                        "primary": primary, "fallback": fallback,
                        "primary_failure": primary_result.summary,
                    })
    return {
        "capability": cap.value,
        "primary_backend": primary,
        "fallback_backend": fallback,
        "primary": primary_result.to_dict(),
        "fallback": fallback_result.to_dict() if fallback_result else None,
        "fallback_used": used_fallback,
        "fallback_succeeded": bool(fallback_result and fallback_result.ok()),
    }


def _restricted_available(cap: Capability, policy: LicensePolicy) -> list[BackendSpec]:
    out: list[BackendSpec] = []
    for spec in REGISTRY.for_capability(cap):
        allowed, _ = policy.allows(spec.license)
        if allowed:
            continue
        if spec.health().available:
            out.append(spec)
    out.sort(key=lambda s: (-s.priority, s.name))
    return out


def _invoke(spec: BackendSpec, cap: Capability, kwargs: dict[str, Any],
            policy: LicensePolicy, *, include_restricted: bool) -> ScientificResult | None:
    handler: Callable[..., Any] | None = spec.handlers.get(cap)
    if handler is None:
        return None
    allowed, reason = policy.allows(spec.license)
    if not allowed:
        if include_restricted:
            return ScientificResult.license_required(cap.value, spec.name, reason,
                                                     citation=spec.citation)
        return None
    try:
        result = handler(**kwargs)
    except TypeError as exc:
        r = ScientificResult(capability=cap.value, backend=spec.name,
                             status=CapabilityStatus.WARNING.value,
                             summary=f"bad arguments for {spec.name}: {exc}")
        r.finish()
        return r
    except Exception as exc:  # noqa: BLE001 - backend isolation
        r = ScientificResult(capability=cap.value, backend=spec.name,
                             status=CapabilityStatus.ERROR.value,
                             summary=f"{spec.name} failed: {type(exc).__name__}: {exc}")
        r.finish()
        return r
    if isinstance(result, ScientificResult):
        if not result.backend:
            result.backend = spec.name
        if not result.backend_version:
            result.backend_version = spec.version
        if not result.license_class:
            result.license_class = spec.license_class
        if not result.citations and spec.citation:
            result.citations = [spec.citation]
        return result.finish()
    r = ScientificResult(capability=cap.value, backend=spec.name,
                         summary=f"{spec.name} returned a non-standard result")
    r.data = {"raw": result}
    r.finish()
    return r


def capability_matrix(policy: LicensePolicy | None = None) -> list[dict[str, Any]]:
    load_backends()
    return REGISTRY.capability_matrix(policy or policy_from_env())


def backend_health(policy: LicensePolicy | None = None) -> list[dict[str, Any]]:
    load_backends()
    return REGISTRY.health_report(policy or policy_from_env())


__all__ = ["run_capability", "capability_matrix", "backend_health",
           "execute_primary_then_fallback", "_coerce_capability"]
