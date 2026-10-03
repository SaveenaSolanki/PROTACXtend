#!/usr/bin/env python
"""Trace selected resources -> evidence -> claim -> answer for audited benchmark cases."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from protacxtend.agents.structured_run import run_case
from protacxtend.workflows.resource_audit import build_resource_registry, shortlist_resources

CASES = ["KNOW-06", "REASON-03", "REASON-05"]
OUT = ROOT / "outputs/priority_agent_audit/case_resource_claim_traces"


def _case(task_id: str) -> dict[str, Any]:
    return json.loads((ROOT / "benchmark/cases" / f"{task_id}.json").read_text(encoding="utf-8"))


def _claims_from_answer(answer: dict[str, Any]) -> list[dict[str, Any]]:
    claims = []
    if answer.get("answer"):
        claims.append({"claim_type": "final_answer", "text": answer["answer"], "support": "scientific_answer.evidence"})
    for key in ("literature_precedent", "identifier_comparison", "evidence_cards"):
        if answer.get(key):
            claims.append({"claim_type": key, "text": json.dumps(answer[key], default=str)[:1200], "support": key})
    return claims


def trace_one(task_id: str, registry: dict[str, Any]) -> dict[str, Any]:
    case = _case(task_id)
    question = case.get("scientific_question", "")
    shortlist = shortlist_resources(question, registry=registry, offline=True)
    run = run_case(case, capability=case.get("capability", ""), budget_s=60)
    answer = run.get("scientific_answer") or {}
    trace = {
        "task_id": task_id,
        "capability": case.get("capability", ""),
        "question": question,
        "resource_reason_summary": shortlist.get("resource_reason_summary", {}),
        "selected_resources": shortlist.get("selected", [])[:16],
        "retrieved_evidence": answer.get("evidence", []),
        "claims": _claims_from_answer(answer),
        "answer": answer.get("answer", ""),
        "scientific_state": run.get("scientific_state", ""),
        "route": run.get("route", []),
        "routing": run.get("routing", {}),
        "outcome": run.get("outcome", ""),
        "denominator_note": "1 audited case; provisional machine diagnostic, not formal matched-48 evaluation",
    }
    (OUT / f"{task_id}.json").write_text(json.dumps(trace, indent=2, default=str), encoding="utf-8")
    return trace


def render(traces: list[dict[str, Any]]) -> str:
    lines = ["# KNOW/REASON Resource-to-Claim Trace", "", "Formal matched-48 evaluation remains `PENDING_HUMAN`; these are machine diagnostics for 3 audited cases.", ""]
    for t in traces:
        lines += [f"## {t['task_id']}", "", f"State: `{t['scientific_state']}` · Outcome: `{t['outcome']}`", "", "Selected resources:"]
        for r in t["resource_reason_summary"].get("selected", [])[:8]:
            lines.append(f"- {r.get('name')}: {r.get('reason')}")
        lines += ["", "Evidence:"]
        for ev in t.get("retrieved_evidence", [])[:8]:
            lines.append(f"- {ev.get('source','')}: {ev.get('summary','')}")
        lines += ["", "Claims:"]
        for c in t.get("claims", []):
            lines.append(f"- {c['claim_type']}: {c['text']}")
        lines += ["", "Answer:", t.get("answer", "") or "(no answer)", ""]
    return "\n".join(lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    registry = build_resource_registry()
    traces = [trace_one(t, registry) for t in CASES]
    summary = {
        "schema_version": "resource-claim-traces.v1",
        "formal_evaluation_status": "PENDING_HUMAN",
        "case_count": len(traces),
        "supported_answer_count": sum(1 for t in traces if t["scientific_state"] == "supported_answer"),
        "conditional_hypothesis_count": sum(1 for t in traces if t["scientific_state"] == "conditional_hypothesis"),
        "traces": traces,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (OUT / "report.md").write_text(render(traces), encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT), "cases": CASES}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
