"""PROTACXtend failure-escalation subsystem.

Self-healing control loop: when an internal scientific step fails, diagnose the
cause, persist it, resolve an external toolkit fallback, (optionally) install
and version-check it, register it in the dynamic tool registry, execute it
honestly, and write an audit trail.

Quick start
-----------
>>> from protacxtend.escalation import run_with_escalation
>>> outcome = run_with_escalation(
...     "ligand_docking", "protacxtend.tools.docking_pipeline",
...     my_internal_dock, smiles="CCO", mode="check")
>>> outcome["resolved_by"]

Typical outcome values: ``"internal"`` (no failure), ``"external"`` (a
registered external tool produced a result), ``"external_registered"`` (tool
installed/registered but capability executor returned readiness only),
``"external_candidate_only"`` (no install available), ``"none"``.
"""

from __future__ import annotations

from protacxtend.escalation.capabilities import (
    CAPABILITY_DESCRIPTIONS,
    CAPABILITY_FALLBACKS,
    INTERNAL_TOOL_CAPABILITY,
    all_capabilities,
    capability_for,
    fallbacks_for,
)
from protacxtend.escalation.contracts import (
    EscalationResult,
    ExternalToolCandidate,
    FailureRecord,
    InstallRecord,
    RegistrationRecord,
)
from protacxtend.escalation.diagnosis import diagnose
from protacxtend.escalation.installer import InstallManager
from protacxtend.escalation.ledger import get_ledgers
from protacxtend.escalation.orchestrator import (
    escalate_failure,
    guarded,
    run_with_escalation,
    to_tool_result,
)
from protacxtend.escalation.registry import DynamicToolRegistry
from protacxtend.escalation.report import (
    build_escalation_report,
    capability_readiness,
    render_markdown,
)
from protacxtend.escalation.resolver import (
    resolve_candidates,
    resolve_tool,
)

__all__ = [
    "CAPABILITY_DESCRIPTIONS",
    "CAPABILITY_FALLBACKS",
    "INTERNAL_TOOL_CAPABILITY",
    "all_capabilities",
    "capability_for",
    "fallbacks_for",
    "EscalationResult",
    "ExternalToolCandidate",
    "FailureRecord",
    "InstallRecord",
    "RegistrationRecord",
    "diagnose",
    "InstallManager",
    "get_ledgers",
    "escalate_failure",
    "guarded",
    "run_with_escalation",
    "to_tool_result",
    "DynamicToolRegistry",
    "build_escalation_report",
    "capability_readiness",
    "render_markdown",
    "resolve_candidates",
    "resolve_tool",
]
