"""Audit + readiness reporting for the escalation subsystem.

``build_escalation_report`` is the machine-readable audit. It joins:

* the failure / install / registration / audit ledgers,
* the dynamic registry,
* live toolkit status detection,

into one payload that answers: *what failed, why, what did we do about it, and
which capabilities still have no working fallback?*
"""

from __future__ import annotations

import collections
from typing import Any, Dict, List

from protacxtend.escalation.capabilities import (
    CAPABILITY_DESCRIPTIONS,
    CAPABILITY_FALLBACKS,
    INTERNAL_TOOL_CAPABILITY,
)
from protacxtend.escalation.ledger import get_ledgers
from protacxtend.escalation.registry import DynamicToolRegistry
from protacxtend.escalation.resolver import resolve_candidates


def capability_readiness() -> list[dict[str, Any]]:
    """Per-capability external fallback readiness (live detection)."""
    rows: list[dict[str, Any]] = []
    for capability in sorted(CAPABILITY_DESCRIPTIONS):
        candidates = resolve_candidates(capability, max_candidates=50)
        installed = [c for c in candidates if c.installed]
        installable = [c for c in candidates if c.installable and not c.installed and not c.commercial]
        web = [c for c in candidates if c.web_service]
        best = installed[0] if installed else (installable[0] if installable else (candidates[0] if candidates else None))
        rows.append(
            {
                "capability": capability,
                "description": CAPABILITY_DESCRIPTIONS[capability],
                "curated_fallbacks": len(CAPABILITY_FALLBACKS.get(capability, [])),
                "candidates": len(candidates),
                "installed": len(installed),
                "installable": len(installable),
                "web_fallbacks": len(web),
                "best_candidate": best.tool_name if best else "",
                "best_installed": bool(best and best.installed),
                "best_version": best.version if best else "",
                "readiness": (
                    "ready" if installed else
                    "installable" if installable else
                    "web_only" if web else
                    "none"
                ),
            }
        )
    return rows


def build_escalation_report() -> dict[str, Any]:
    ledgers = get_ledgers()
    failures = ledgers.failures.read_all()
    installs = ledgers.installs.read_all()
    registrations = ledgers.registrations.read_all()
    audits = ledgers.audits.read_all()
    registry = DynamicToolRegistry(ledgers=ledgers)

    by_class = collections.Counter(f.get("failure_class", "?") for f in failures)
    by_capability = collections.Counter(f.get("capability", "?") for f in failures)
    by_tool = collections.Counter(f.get("internal_tool", "?") for f in failures)

    install_success = sum(1 for i in installs if i.get("success"))
    audit_resolved = collections.Counter(a.get("resolved_by", "?") for a in audits)

    readiness = capability_readiness()
    ready = [r for r in readiness if r["readiness"] == "ready"]
    no_fallback = [r for r in readiness if r["readiness"] == "none"]
    installable = [r for r in readiness if r["readiness"] == "installable"]

    # capabilities that actually failed but have no installed fallback
    failed_caps = set(by_capability)
    gaps = [
        r for r in readiness
        if r["capability"] in failed_caps and r["readiness"] != "ready"
    ]

    return {
        "ledger_paths": ledgers.paths(),
        "counts": {
            "failures": len(failures),
            "installs": len(installs),
            "install_success": install_success,
            "registrations": len(registrations),
            "audit_events": len(audits),
            "dynamic_registry_entries": len(registry.list()),
        },
        "failures_by_class": dict(by_class.most_common()),
        "failures_by_capability": dict(by_capability.most_common()),
        "failures_by_internal_tool": dict(by_tool.most_common()),
        "resolved_by": dict(audit_resolved.most_common()),
        "capabilities": {
            "total": len(readiness),
            "ready": len(ready),
            "installable": len(installable),
            "none": len(no_fallback),
        },
        "capability_readiness": readiness,
        "gaps": gaps,
        "registered_tools": registry.list(),
        "recent_failures": failures[-10:],
        "recent_audits": audits[-10:],
    }


def render_markdown(report: dict[str, Any]) -> str:
    c = report["counts"]
    lines: list[str] = []
    lines.append("# PROTACXtend Escalation & Capability Audit\n")
    lines.append(f"- Ledger directory: `{report['ledger_paths']['directory']}`")
    lines.append(f"- Failures recorded: {c['failures']}")
    lines.append(f"- Installs attempted: {c['installs']} ({c['install_success']} succeeded)")
    lines.append(f"- Dynamic registrations: {c['registrations']}")
    lines.append(f"- Audit events: {c['audit_events']}")
    lines.append("")

    lines.append("## Capability coverage\n")
    cap = report["capabilities"]
    lines.append(f"- Capabilities tracked: {cap['total']}")
    lines.append(f"- With an installed external fallback: {cap['ready']}")
    lines.append(f"- Installable only: {cap['installable']}")
    lines.append(f"- No fallback at all: {cap['none']}")
    lines.append("")

    if report["failures_by_class"]:
        lines.append("## Failures by class\n")
        for k, v in report["failures_by_class"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    if report["failures_by_capability"]:
        lines.append("## Failures by capability\n")
        for k, v in report["failures_by_capability"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    if report["gaps"]:
        lines.append("## Gaps — failed capabilities with no installed fallback\n")
        lines.append("| capability | readiness | best candidate | installable fallbacks |")
        lines.append("|---|---|---|---|")
        for g in report["gaps"]:
            lines.append(
                f"| {g['capability']} | {g['readiness']} | {g['best_candidate']} | {g['installable']} |"
            )
        lines.append("")

    if report["registered_tools"]:
        lines.append("## Dynamically registered tools\n")
        lines.append("| tool | version | capabilities | status |")
        lines.append("|---|---|---|---|")
        for t in report["registered_tools"]:
            lines.append(
                f"| {t['tool_name']} | {t.get('version','')} | "
                f"{', '.join(t.get('capabilities', []))} | {t.get('status','')} |"
            )
        lines.append("")

    lines.append("## Capability readiness matrix\n")
    lines.append("| capability | installed | installable | web | readiness | best candidate |")
    lines.append("|---|---|---|---|---|---|")
    for r in report["capability_readiness"]:
        lines.append(
            f"| {r['capability']} | {r['installed']} | {r['installable']} | "
            f"{r['web_fallbacks']} | {r['readiness']} | {r['best_candidate']} |"
        )
    lines.append("")
    return "\n".join(lines)


def internal_capability_map() -> list[dict[str, str]]:
    return [
        {"internal_tool": k, "capability": v}
        for k, v in sorted(INTERNAL_TOOL_CAPABILITY.items())
    ]
