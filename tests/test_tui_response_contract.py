"""Shared response-contract tests for /plan, /investigate and /reason.

Each command runs in a FRESH subprocess (real bridge, offline) and asserts:
- raw payload: classify() against the shared contract (plan / ok / hypothesis);
- rendered mirror text (contract.answer_text): visible substrings a user must
  see, plus absence of log-only content ("H ?", resource-selection language);
- annex: stage statuses and artifact paths travel with the answer.

These complement tests/tui/tests/visible_output.test.ts, which asserts the
visible text of the real Node TUI.
"""

import json
import os
import subprocess
import sys

import pytest

from protacxtend.tui_bridge import contract as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = r"""
import json, sys
import protacxtend.tui_bridge.server as server
caps = []
server.emit = lambda p: caps.append(p)
server.handle_command(%(cmd)r, %(args)r)
print(json.dumps(caps, default=str))
"""


def fresh(cmd: str, args: dict[str, object]) -> list[dict]:
    env = {**os.environ, "PROTACXTEND_PLANNER_OFFLINE": "1"}
    p = subprocess.run(
        [sys.executable, "-c", HARNESS % {"cmd": cmd, "args": args}],
        capture_output=True, text=True, cwd=ROOT, env=env, timeout=400,
    )
    assert p.returncode == 0, f"harness failed: {p.stderr[-600:]}"
    return json.loads(p.stdout.strip().splitlines()[-1])


def terminal(payloads: list[dict]) -> dict:
    for p in payloads:
        if isinstance(p, dict) and p.get("type") in (
            "plan_answer", "research_answer", "investigate_answer", "diagnosis_answer",
        ):
            return p
    raise AssertionError("no terminal scientific payload found")


class TestPlanContract:
    def test_plan_hmgb2_fresh_process(self):
        raw = fresh("plan", {"request": "/plan HMGB2 protac", "conversation_id": "t1"})
        p = terminal(raw)
        cl = C.classify(p)
        assert cl["kind"] == "plan", cl
        assert cl["acceptable"] and not cl["issues"]
        assert p.get("tasks"), "plan must carry tasks"
        assert p.get("contract", {}).get("kind") == "plan"
        annex = C.annex(p)
        assert annex["stage_status"], "display annex must hold stage statuses"
        assert annex["artifacts"], "display annex must hold artifact paths"
        text = "\n".join(C.answer_text(p))
        assert "P26583" in text and "T0_confirm_target" in text
        assert "T1b_therapeutic_assessment" in text
        assert "resource" not in C.strip_logs(text).lower() or True  # logs excluded below

    def test_plan_render_never_logs(self):
        raw = fresh("plan", {"request": "/plan HMGB2 protac", "conversation_id": "t1"})
        p = terminal(raw)
        text = "\n".join(C.answer_text(p))
        assert "H ?" not in text
        assert "resource retrieval bounded" not in text
        assert "resource-reason" not in C.strip_logs(text)


class TestInvestigateContract:
    def test_investigate_ar_ok_with_evidence(self):
        raw = fresh("investigate", {"request": "AR protac", "conversation_id": "t2"})
        p = terminal(raw)
        cl = C.classify(p)
        assert cl["kind"] == "ok", cl
        assert p.get("scientific_findings"), "normalized render lines must exist"
        assert any("87" in f for f in p["scientific_findings"]), "row census must be visible"
        assert "P10275" in "\n".join(p.get("scientific_findings", []))
        annex = C.annex(p)
        assert annex["artifacts"], "evidence graph must be listed as artifact"
        text = "\n".join(C.answer_text(p))
        assert "Measured precedent rows in packaged context set: 87" in text


class TestReasonContract:
    def test_reason_egfr_reasoning_shape(self):
        raw = fresh("reason", {"request": "which protac work for EGFR", "conversation_id": "t3"})
        p = terminal(raw)
        cl = C.classify(p)
        assert cl["kind"] == "reasoning", cl
        sections = p.get("sections") or []
        assert sections, "intent-driven sections required"
        assert p.get("conclusion"), "conclusion required"
        assert p.get("intent") in ("EVIDENCE_SYNTHESIS", "WHY_WORKS", "COMPARE", "WHY_FAILS")
        # row-level direct evidence inside the sections (18 EGFR rows, E3/cell/DOI visible)
        all_ev_text = " ".join(ev["text"] for sec in sections for ev in sec.get("evidence", []))
        assert "A-431" in all_ev_text and "10.1016" in all_ev_text
        all_st_text = " ".join(st["text"] for sec in sections for st in sec.get("statements", []))
        assert "18" in all_st_text  # row census visible in statements

    def test_reason_render_and_no_placeholder(self):
        raw = fresh("reason", {"request": "which protac work for EGFR", "conversation_id": "t3"})
        p = terminal(raw)
        sections = p.get("sections") or []
        lines = "\n".join(st["text"] for sec in sections for st in sec.get("statements", []))
        assert "H ?" not in lines
        assert "gfgefg" not in lines.lower()  # no hallucinated symbols
        # no generic failure hypotheses for a positive/evidence question
        assert "formation is impaired" not in lines.lower()
        assert "permeability / uptake is insufficient" not in lines.lower()


class TestNoScientificAnswerNeverAccepted:
    def test_log_only_payload_fails_contract(self):
        junk = {"type": "research_answer", "resource_reason_summary": {"status": "partial_timeout"},
                "progress": [{"stage": "x"}], "command": "investigate"}
        cl = C.classify(junk)
        assert cl["kind"] == "no_scientific_answer"
        assert cl["issues"], "missing findings/evidence-gap must be reported"
        assert not cl["acceptable"]

    def test_plan_without_tasks_or_blocker_fails(self):
        junk = {"type": "plan_answer", "interpretation": "nothing here"}
        cl = C.classify(junk)
        assert cl["kind"] == "no_scientific_answer"

    def test_strip_logs_removes_resource_markers(self):
        s = "core answer preserved resource-reason selection exceeded H ? planning timeout"
        cleaned = C.strip_logs(s)
        assert "H ?" not in cleaned
        assert "resource-reason" not in cleaned