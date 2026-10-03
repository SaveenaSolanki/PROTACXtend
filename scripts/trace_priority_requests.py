"""Trace priority PROTACXtend requests through TUI/API/control-plane surfaces."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from protacxtend.request.controller import RequestController
from protacxtend.workflows.contracts import build_goal_plan
from protacxtend.workflows.api import run_command
from protacxtend.workflows.resource_audit import build_resource_registry, shortlist_resources

OUT = Path("outputs/priority_agent_audit")

CASES = [
    {"id": "plan_egfr", "tui_input": "/plan EGFR protac", "command": "plan", "text": "/plan EGFR protac"},
    {"id": "run_brd4_crbn", "tui_input": "/run Design and evaluate CRBN-recruiting PROTACs for BRD4", "command": "run", "text": "/run Design and evaluate CRBN-recruiting PROTACs for BRD4"},
    {"id": "investigate_kras_g12c", "tui_input": "Investigate allele-specific degradation options for KRAS G12C", "command": "investigate", "text": "Investigate allele-specific degradation options for KRAS G12C"},
]


def _write(path: Path, obj: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str))
    return str(path)


def _type(obj: Any) -> str:
    if obj is None:
        return "None"
    return type(obj).__name__


def trace_case(case: dict[str, str], registry: dict[str, Any]) -> dict[str, Any]:
    cid = case["id"]
    cdir = OUT / "traces" / cid
    cdir.mkdir(parents=True, exist_ok=True)
    command = case["command"]
    text = case["text"]
    ctl = RequestController(offline=True)
    u = ctl.understand(text, default_action=command)
    understanding_path = _write(cdir / "understanding.json", u.to_snapshot())
    target = u.primary_target.__dict__ if u.primary_target else None
    transitions = [
        {
            "transition": "TUI input",
            "code_location": "protacxtend/tui_bridge/server.py:handle_command",
            "input_type": "JSONL event or slash command text",
            "input": case["tui_input"],
            "output_type": "command + request text",
            "selected_resources": ["TUI bridge command router"],
            "artifact": "",
            "status": "ok",
            "first_failure": "",
        },
        {
            "transition": "parse + target resolution",
            "code_location": "protacxtend/request/controller.py:RequestController.understand -> request/resolver.py:resolve_target",
            "input_type": "str",
            "output_type": "RequestUnderstanding",
            "selected_resources": ["curated_targets.csv", "supplemental resolver", "UniProt cache/live when enabled"],
            "artifact": understanding_path,
            "status": "clarification_needed" if u.clarification.pending else "ok",
            "first_failure": u.clarification.question if u.clarification.pending else "",
            "target": target,
            "intent": u.action,
            "mutation": u.mutation,
            "e3": u.e3.__dict__,
        },
    ]
    plan_payload = None
    if not u.clarification.pending:
        try:
            plan = build_goal_plan(u)
            plan_payload = {
                "goal_type": plan.goal_type,
                "signature": plan.signature,
                "nodes": [n.__dict__ for n in plan.nodes],
                "gates": plan.gates,
                "evidence_needed": plan.evidence_needed,
                "artifacts": plan.artifacts,
            }
            transitions.append({
                "transition": "intent -> capability plan",
                "code_location": "protacxtend/workflows/contracts.py:build_goal_plan",
                "input_type": "RequestUnderstanding",
                "output_type": "GoalPlan",
                "selected_resources": [n["capability"] for n in plan_payload["nodes"]],
                "artifact": _write(cdir / "goal_plan.json", plan_payload),
                "status": "ok",
                "first_failure": "",
            })
        except Exception as exc:  # noqa: BLE001
            transitions.append({"transition": "intent -> capability plan", "code_location": "build_goal_plan", "input_type": "RequestUnderstanding", "output_type": "GoalPlan", "selected_resources": [], "artifact": "", "status": "failed", "first_failure": str(exc)})
    shortlist = shortlist_resources(text, registry=registry, offline=True)
    transitions.append({
        "transition": "eligible resource retrieval",
        "code_location": "protacxtend/workflows/resource_audit.py:shortlist_resources",
        "input_type": "target + intent + mutation + environment",
        "output_type": "eligible-resource-shortlist.v1",
        "selected_resources": [r["name"] for r in shortlist["selected"][:12]],
        "artifact": _write(cdir / "eligible_resources.json", shortlist),
        "status": "ok",
        "first_failure": "",
    })
    execution_payload = None
    if command in {"plan", "investigate"}:
        try:
            execution_payload = run_command(command, text, offline=True)
            transitions.append({
                "transition": "tool execution + evidence graph",
                "code_location": "protacxtend/workflows/api.py:run_command",
                "input_type": "command:str + text:str",
                "output_type": "dict payload",
                "selected_resources": [command, "EvidenceGraph"],
                "artifact": _write(cdir / "workflow_payload.json", execution_payload),
                "status": execution_payload.get("status", "unknown"),
                "first_failure": execution_payload.get("question") or execution_payload.get("error") or "",
            })
        except Exception as exc:  # noqa: BLE001
            transitions.append({"transition": "tool execution + evidence graph", "code_location": "workflows.api:run_command", "input_type": "command/text", "output_type": "dict", "selected_resources": [command], "artifact": "", "status": "failed", "first_failure": str(exc)})
    elif command == "run":
        transcript = OUT.parent / "workflows" / "demo_tui_run" / "tui_transcript.jsonl"
        summary = OUT.parent / "workflows" / "demo_tui_run" / "tui_transcript_summary.json"
        transitions.append({
            "transition": "tool execution + evidence graph + candidate state",
            "code_location": "protacxtend/tui_bridge/server.py:_handle_design_run_via_workflows_api -> workflows.api.run_command -> workflows.designer.run_design -> agents.runtime.run_protacpilot",
            "input_type": "TUI JSONL /run event",
            "output_type": "TUI JSONL transcript + research_answer payload",
            "selected_resources": ["workflows.api", "run_protacpilot", "deterministic DESIGN graph"],
            "artifact": str(transcript if transcript.exists() else summary),
            "status": "ok" if transcript.exists() else "not_run_in_this_trace_script",
            "first_failure": "",
        })
    first_failure = next((t for t in transitions if t.get("first_failure")), None)
    return {
        "case_id": cid,
        "tui_input": case["tui_input"],
        "command": command,
        "target": target,
        "intent": u.action,
        "mutation": u.mutation,
        "transitions": transitions,
        "first_failure": first_failure,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Priority request trace report", "", "This report traces real request understanding, capability selection, execution surfaces, artifacts, and first failures. It is an audit map, not a scientific claim.", ""]
    lines.append("## Registry counts")
    for k, v in report["registry_counts"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    for case in report["cases"]:
        lines += [f"## {case['case_id']}", f"Input: `{case['tui_input']}`", f"Intent: `{case['intent']}` · Target: `{(case.get('target') or {}).get('symbol')}` · Mutation: `{case.get('mutation') or ''}`", "", "| transition | code | output | status | artifact | first failure |", "|---|---|---|---|---|---|"]
        for t in case["transitions"]:
            lines.append(f"| {t['transition']} | `{t['code_location']}` | `{t['output_type']}` | {t['status']} | `{t.get('artifact','')}` | {t.get('first_failure','')} |")
        if not case.get("first_failure"):
            lines.append("\nFirst failure: none in traced available stages.")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    registry = build_resource_registry()
    traces = [trace_case(c, registry) for c in CASES]
    report = {
        "schema_version": "priority-request-traces.v1",
        "registry_counts": registry["counts"],
        "registry_status_counts": registry["status_counts"],
        "cases": traces,
    }
    _write(OUT / "priority_request_traces.json", report)
    (OUT / "priority_request_trace_report.md").write_text(render_markdown(report))
    print(json.dumps({"out_dir": str(OUT), "cases": [c["case_id"] for c in traces]}, indent=2))


if __name__ == "__main__":
    main()
