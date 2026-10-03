#!/usr/bin/env python
"""Prepare a matched 48-case evaluation packet without promoting pending gold.

The packet exists so downstream closeout/reporting can show exactly why the
matched evaluation remains blocked. It never computes accuracy or passes an
evaluation while expert gold is pending.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARMS = ["full_agent", "deterministic", "retrieval_only", "llm_only", "tool_only"]


def _read_gold(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_packet(gold_path: Path | str = ROOT / "gold_answers_v1.jsonl") -> dict[str, Any]:
    path = Path(gold_path)
    rows = _read_gold(path)
    pending = [r for r in rows if r.get("status") == "AWAITING_EXPERT_REVIEW" or not r.get("acceptable_answer")]
    status = "PENDING_HUMAN" if pending else "READY_FOR_SCORING"
    capability_counts = Counter(str(r.get("capability") or "") for r in rows)
    arms = [{
        "arm": arm,
        "status": "blocked_pending_expert_gold" if status == "PENDING_HUMAN" else "ready",
        "required_artifact": "gold_answers_v1.jsonl with non-empty acceptable_answer and adjudicator decision for all 48 cases",
        "passing_criterion": "task-level exact/rubric scoring with uncertainty after independent adjudication",
        "current_evidence": f"{len(pending)} of {len(rows)} cases lack reviewed acceptable_answer",
    } for arm in ARMS]
    return {
        "schema_version": "matched48-gold-pending-packet.v1",
        "case_count": len(rows),
        "gold_path": str(path),
        "gold_status": status,
        "pending_cases": [r.get("case_id") for r in pending],
        "capability_counts": dict(sorted(capability_counts.items())),
        "evaluation_arms": arms,
        "task_level_results": [] if status == "PENDING_HUMAN" else "not_computed_by_packet",
        "uncertainty": "not_computable_until_gold_adjudicated",
        "abstention_handling": "abstentions retained; PENDING_HUMAN is not a pass",
        "passed_evaluation": False,
        "claim_gate": "matched 48-case performance claims remain blocked until expert adjudication",
    }


def write_packet(out_dir: str | Path = ROOT / "outputs/priority_agent_audit/matched48_gold_pending",
                 gold_path: Path | str = ROOT / "gold_answers_v1.jsonl") -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    packet = build_packet(gold_path)
    status_path = out / "status.json"
    arms_path = out / "evaluation_arms.json"
    report_path = out / "packet.md"
    status_path.write_text(json.dumps(packet, indent=2, default=str), encoding="utf-8")
    arms_path.write_text(json.dumps(packet["evaluation_arms"], indent=2, default=str), encoding="utf-8")
    lines = [
        "# Matched 48-Case Evaluation Packet",
        "",
        f"Gold status: **{packet['gold_status']}**",
        f"Cases: {packet['case_count']}",
        f"Pending cases: {len(packet['pending_cases'])}",
        "",
        "`PENDING_HUMAN` is an abstention/blocking state, not a passed evaluation.",
        "",
        "## Arms",
        "",
        "| Arm | Status | Current evidence |",
        "| --- | --- | --- |",
    ]
    for arm in packet["evaluation_arms"]:
        lines.append(f"| {arm['arm']} | {arm['status']} | {arm['current_evidence']} |")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": str(status_path), "arms": str(arms_path), "report": str(report_path)}


def main() -> int:
    out = write_packet()
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
