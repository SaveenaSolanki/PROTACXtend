"""Escalation orchestrator — the self-healing control loop.

Public entry points
-------------------
``escalate_failure``
    Diagnose a failure, persist it, resolve external candidates, optionally
    install/version-check/register the chosen external tool, and record an
    audit entry. Returns an :class:`EscalationResult`.

``run_with_escalation``
    Run an internal callable; on exception automatically invoke the full
    escalation pipeline. This is the one-liner other modules should wrap their
    fragile internal calls with.

``guarded``
    Decorator form of ``run_with_escalation``.

The loop is:

    internal call
        │ success ─────────────────────────────────► return
        └ failure
            → diagnose      (diagnosis.py)
            → store         (failures.jsonl)
            → resolve       (resolver.py)
            → install/check (installer.py, opt-in)
            → register      (dynamic_registry.json)
            → execute       (executors.py)
            → audit         (audit.jsonl)
"""

from __future__ import annotations

import hashlib
import json
import traceback
import uuid
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from protacxtend.escalation.capabilities import capability_for
from protacxtend.escalation.contracts import (
    EscalationResult,
    ExternalToolCandidate,
    FailureRecord,
    utcnow,
)
from protacxtend.escalation.diagnosis import diagnose
from protacxtend.escalation.executors import run_external
from protacxtend.escalation.installer import InstallManager
from protacxtend.escalation.ledger import get_ledgers
from protacxtend.escalation.registry import DynamicToolRegistry
from protacxtend.escalation.resolver import resolve_candidates, resolve_tool


def _digest(payload: Any) -> str:
    try:
        blob = json.dumps(payload, sort_keys=True, default=str)
    except Exception:
        blob = str(payload)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _pick(candidates: list[ExternalToolCandidate]) -> ExternalToolCandidate | None:
    if not candidates:
        return None
    installed = [c for c in candidates if c.installed]
    if installed:
        return installed[0]
    installable = [c for c in candidates if c.installable and not c.commercial]
    if installable:
        return installable[0]
    return candidates[0]


def escalate_failure(
    capability: str,
    internal_tool: str,
    exc: BaseException,
    *,
    inputs: dict[str, Any] | None = None,
    mode: str = "check",
    context: dict[str, Any] | None = None,
    run_id: str = "",
    ledgers=None,
    dynamic_registry: DynamicToolRegistry | None = None,
    installer: InstallManager | None = None,
) -> EscalationResult:
    """Full escalation pipeline for one internal failure.

    ``mode``:
      * ``check``  — diagnose/resolve/version/register if already installed (default)
      * ``dry_run``— same as check but installs are only planned, never run
      * ``install``— permit pip/conda installation for non-commercial tools
      * ``auto``   — alias for install
    """
    ledgers = ledgers or get_ledgers()
    installer = installer or InstallManager(ledgers)
    registry = dynamic_registry or DynamicToolRegistry(ledgers=ledgers)

    capability = capability_for(capability or internal_tool)
    diag = diagnose(exc, internal_tool=internal_tool, capability=capability, context=context)

    failure = FailureRecord(
        failure_id=uuid.uuid4().hex[:12],
        created_at=utcnow(),
        capability=capability,
        internal_tool=internal_tool,
        error_type=diag.error_type,
        error_message=str(exc)[:1000],
        traceback_tail="".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-1500:],
        failure_class=diag.failure_class,
        diagnosis=diag.root_cause,
        root_cause=diag.root_cause,
        recovery_hint=diag.recovery_hint,
        inputs_digest=_digest(inputs or {}),
        run_id=run_id,
        extra={"context": context or {}},
    )
    ledgers.failures.append(failure.to_dict())

    candidates = resolve_candidates(capability)
    chosen = _pick(candidates)

    install_record = None
    registration = None
    external_result: dict[str, Any] | None = None
    resolved_by = "none"

    if chosen is not None:
        # 1) provision if needed
        if not chosen.installed and chosen.installable and not chosen.commercial:
            allow = mode in {"install", "auto"}
            install_record = installer.install(chosen, allow=allow)
            if install_record.success:
                refreshed = resolve_tool(chosen.tool_name, capability)
                if refreshed is not None:
                    chosen = refreshed
        # 2) version check (record evidence of what would run)
        if chosen.installed and not chosen.version:
            check = installer.check(chosen)
            install_record = install_record or check
            if check.version_after:
                chosen.version = check.version_after
        # 3) register into dynamic registry
        if chosen.installed:
            registration = registry.register(
                chosen.tool_name,
                capabilities=[capability],
                version=chosen.version,
                status="installed",
                source="escalation",
                pip_package=chosen.pip_package,
                install_method=chosen.install_method,
                category=chosen.category,
                notes=chosen.purpose or chosen.notes,
            )
            # 4) execute honestly
            external_result = run_external(capability, chosen, inputs)
            resolved_by = (
                "external"
                if external_result.get("status") in {"ok", "ready"}
                else "external_registered"
            )
        else:
            external_result = {
                "status": "not_installed",
                "evidence_type": "NOT AVAILABLE",
                "tool": chosen.tool_name,
                "reason": "candidate identified but not installed; run with mode='install' "
                          "or install manually via the install hint",
                "install_hint": chosen.install_hint,
                "install_method": chosen.install_method,
                "pip_package": chosen.pip_package,
            }
            resolved_by = "external_candidate_only"

    ok = resolved_by in {"external", "external_registered"}
    summary = _summarize(failure, chosen, install_record, registration, resolved_by)
    result = EscalationResult(
        ok=ok,
        capability=capability,
        internal_tool=internal_tool,
        mode=mode,
        failure=failure,
        candidates=candidates,
        chosen=chosen,
        install=install_record,
        registration=registration,
        external_result=external_result,
        resolved_by=resolved_by,
        summary=summary,
    )
    ledgers.audits.append(
        {
            "event": "escalation",
            "failure_id": failure.failure_id,
            "capability": capability,
            "internal_tool": internal_tool,
            "mode": mode,
            "failure_class": failure.failure_class,
            "resolved_by": resolved_by,
            "chosen_tool": chosen.tool_name if chosen else "",
            "chosen_version": chosen.version if chosen else "",
            "installed": bool(chosen.installed) if chosen else False,
            "registered": bool(registration and registration.registered),
            "external_status": (external_result or {}).get("status", ""),
            "created_at": result.created_at,
        }
    )
    return result


def _summarize(failure, chosen, install_record, registration, resolved_by) -> str:
    parts = [
        f"[{failure.failure_class}] {failure.internal_tool} failed: {failure.root_cause}"
    ]
    if chosen:
        parts.append(
            f"best external candidate: {chosen.tool_name} "
            f"({'installed ' + chosen.version if chosen.installed else chosen.status})"
        )
    if install_record:
        parts.append(f"install/{install_record.action}: success={install_record.success}")
    if registration:
        parts.append(f"registered={registration.registered}")
    parts.append(f"resolved_by={resolved_by}")
    return " | ".join(parts)


def run_with_escalation(
    capability: str,
    internal_tool: str,
    fn: Callable[..., Any],
    *args: Any,
    inputs: dict[str, Any] | None = None,
    mode: str = "check",
    run_id: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Run ``fn``; on failure escalate automatically.

    Returns a dict::

        {"ok": bool, "resolved_by": "internal|external|none",
         "value": <internal value or external result>, "escalation": <EscalationResult|None>,
         "error": <exception str|None>}
    """
    try:
        value = fn(*args, **kwargs)
        return {
            "ok": True,
            "resolved_by": "internal",
            "value": value,
            "escalation": None,
            "error": None,
        }
    except Exception as exc:
        escalation = escalate_failure(
            capability,
            internal_tool,
            exc,
            inputs=inputs,
            mode=mode,
            run_id=run_id,
        )
        return {
            "ok": escalation.ok,
            "resolved_by": escalation.resolved_by,
            "value": escalation.external_result,
            "escalation": escalation,
            "error": str(exc),
        }


def guarded(capability: str, internal_tool: str, mode: str = "check"):
    """Decorator: wrap a fragile internal call with escalation."""

    def decorator(fn: Callable[..., Any]):
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            inputs = kwargs.pop("_escalation_inputs", None)
            return run_with_escalation(
                capability, internal_tool, fn, *args, inputs=inputs, mode=mode, **kwargs
            )

        return wrapper

    return decorator


def to_tool_result(result: EscalationResult):
    """Convert an escalation outcome into the agentic :class:`ToolResult`."""
    from protacxtend.agentic.contract import EvidenceType, ToolResult, ToolStatus

    data = result.external_result or {}
    evidence = data.get("evidence_type", "NOT AVAILABLE")
    try:
        evidence_type = EvidenceType(evidence)
    except Exception:
        evidence_type = EvidenceType.NOT_AVAILABLE
    status = ToolStatus.SUCCESS if result.ok else ToolStatus.WARNING
    limitations = [
        "External escalation result — verify provenance before scientific use.",
    ]
    if result.install and not result.install.success:
        limitations.append(f"install action '{result.install.action}' did not succeed.")
    return ToolResult(
        tool=(result.chosen.tool_name if result.chosen else result.internal_tool),
        status=status,
        summary=result.summary,
        data={**data, "escalation": result.to_dict()},
        sources=[f"escalation:{result.capability}"],
        model_version=(result.chosen.version if result.chosen else None),
        evidence_type=evidence_type,
        limitations=limitations,
    )
