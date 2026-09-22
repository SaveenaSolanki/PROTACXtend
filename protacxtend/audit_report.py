"""Markdown/CSV renderers for the scientific audit."""

from __future__ import annotations

from typing import Any


def render_matrix_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Tool capability matrix", "",
             "| group | capability | primary | secondary | fallback | installed | functional | validated | "
             "offline | network | restricted | tier | smoke | scientific |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['group']} | {r['capability']} | {r['primary_backend']} | {r['secondary_backend']} | "
            f"{r['fallback_backend']} | {r['installed']} | {r['functional']} | "
            f"{r['scientifically_validated']} | {r['offline']} | {r['network_required']} | "
            f"{r['commercial_restricted']} | {r['evidence_tier']} | {r['smoke_test_status']} | "
            f"{r['scientific_metric']} |")
    return "\n".join(lines) + "\n"


def render_licence_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Licence and access audit", "",
             "| backend | license | class | redistributable | commercial-restricted | academic-only | "
             "web-only | network | default-enabled | optional | replacement |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['backend']} | {r['license']} | {r['license_class']} | {r['redistributable']} | "
            f"{r['commercial_use_restricted']} | {r['academic_only']} | {r['web_only']} | "
            f"{r['network_required']} | {r['default_enabled']} | {r['optional_only']} | "
            f"{r['replacement_backend']} |")
    return "\n".join(lines) + "\n"


def render_summary_metrics_md(metrics: dict[str, Any]) -> str:
    lines = ["# Summary metrics", ""]
    for k, v in metrics.items():
        lines.append(f"- **{k}**: {v}")
    return "\n".join(lines) + "\n"
