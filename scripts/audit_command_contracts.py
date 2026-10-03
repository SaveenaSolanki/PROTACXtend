#!/usr/bin/env python3
"""User-facing command contract audit for /design, /run, /optimize, /experiment,
/validate, /compare.

Each command runs through the real TUI bridge (fresh process) with a
representative query. For each: routed handler, contract classification
(protacxtend.tui_bridge.contract), structured result presence, sections,
evidence rows, abstention honesty (typed abstention instead of fabrication),
and pass/fail with reason. No fixes are applied during the audit.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "audits" / "command_contracts"
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PROTACXTEND_PLANNER_OFFLINE", "1")

HARNESS = r"""
import json, sys, warnings
warnings.filterwarnings("ignore")
import protacxtend.tui_bridge.server as server
caps = []
server.emit = lambda p: caps.append(p)
for msg in sys.stdin:
    if not msg.strip():
        continue
    m = json.loads(msg)
    server.handle_command(m.pop("type"), m)
print(json.dumps(caps, default=str))
"""


def bridge(seq: list[dict], timeout: int = 420) -> list[dict]:
    inp = "\n".join(json.dumps(m) for m in seq) + "\n"
    p = subprocess.run([sys.executable, "-c", HARNESS], input=inp, capture_output=True,
                       text=True, cwd=ROOT, env={**os.environ, "PROTACXTEND_PLANNER_OFFLINE": "1"},
                       timeout=timeout)
    if p.returncode != 0 or not p.stdout.strip():
        return [{"type": "harness_error", "stderr": p.stderr[-400:]}]
    lines = [json.loads(ln) for ln in p.stdout.strip().splitlines() if ln.strip()]
    # protocol-level prints (tool_call/tool_result) appear as raw JSONL lines;
    # the mocked emit() events are in the final caps list (if a list).
    raw = lines[:-1] if lines else []
    caps = lines[-1] if lines and isinstance(lines[-1], list) else []
    merged: list[dict] = []
    seen: set[tuple] = set()
    for e in raw + caps:
        if not isinstance(e, dict):
            continue
        key = (e.get("type"), e.get("tool"), e.get("ts"), str(e.get("status") or e.get("plan_id") or "")[:24])
        if key not in seen:
            seen.add(key)
            merged.append(e)
    return merged


TERMINAL_TYPES = {
    "plan": ["plan_answer"],
    "design": ["research_answer", "scientific_result"],
    "run": ["run_answer", "research_answer", "error"],
    "optimize": ["diagnosis_answer", "research_answer", "error"],
    "experiment": ["diagnosis_answer", "research_answer", "error"],
    "validate": ["tool_result", "error"],
    "compare": ["research_answer", "compare_result", "error"],
}


def audit() -> list[dict]:
    from protacxtend.tui_bridge.contract import classify

    rows: list[dict] = []
    # 1) plan first so /run has a persisted plan
    plan_evs = bridge([{"type": "plan", "request": "EGFR protac with CRBN", "conversation_id": "cmd-audit"}])
    plan_payload = next((e for e in plan_evs if isinstance(e, dict) and e.get("type") == "plan_answer"), {})
    plan_id = plan_payload.get("plan_id", "")

    cases = [
        ("/design", "design", {"request": "design BRD4 CRBN PROTAC", "conversation_id": "cmd-audit"}, 420),
        ("/run", "run", {"request": plan_id, "conversation_id": "cmd-audit"}, 120),
        ("/optimize", "optimize", {"request": "optimize MT-802 series for BRD4", "conversation_id": "cmd-audit"}, 120),
        ("/experiment", "experiment", {"request": "experiment MZ1 in MOLM-13", "conversation_id": "cmd-audit"}, 120),
        ("/validate", "validate", {"smiles": "Cc1nsc(C)c1c1ccc(Cl)cc1", "conversation_id": "cmd-audit"}, 120),
        ("/validate (no input)", "validate", {"smiles": "", "conversation_id": "cmd-audit"}, 60),
        ("/compare (case file)", "compare", {"path": "outputs/case_study_brd4_vhl_result.json", "conversation_id": "cmd-audit"}, 180),
        ("/compare (bare)", "compare", {"request": "BRD4 vs GSPT1", "conversation_id": "cmd-audit"}, 90),
    ]
    for label, cmd, args, timeout in cases:
        evs = bridge([{"type": cmd, **args}], timeout=timeout)
        terminal = next((e for e in evs if isinstance(e, dict) and e.get("type") in TERMINAL_TYPES.get(cmd, [])), None)
        if terminal is None:
            kinds = [e.get("type") for e in evs if isinstance(e, dict)][:4]
            herr = next((e.get("stderr", "") for e in evs if isinstance(e, dict) and e.get("type") == "harness_error"), "")
            rows.append(_row(label, cmd, "no_terminal_payload", "", kinds, 0, "FAIL",
                             f"no terminal payload; events: {kinds}" + (f"; stderr: {herr[-200:]}" if herr else "")))
            continue
        cl = classify(terminal)
        secs = terminal.get("sections") or []
        structured = terminal.get("structured") or {}
        evidence_rows = sum(1 for s in secs for _ in s.get("evidence", [])) if secs else 0
        answer = terminal.get("interpretation") or terminal.get("answer") or ""
        if not answer and isinstance(terminal.get("conclusion"), dict):
            answer = terminal["conclusion"].get("rationale", "")
        if not answer and terminal.get("scientific_findings"):
            answer = "; ".join(str(x) for x in terminal["scientific_findings"][:2])
        # validate surfaces tool_result (RDKit calculated properties), a different contract surface
        if cmd == "validate":
            res = terminal.get("result") or {}
            ev = res.get("evidence") or []
            cl = {"kind": "tool_result_calculated", "issues": [], "acceptable": True}
            secs, structured, evidence_rows = [], {}, len(ev)
            answer = str(ev[0])[:160] if ev else str(res.get("summary") or res)[:160]
        honest = cl["acceptable"] or (terminal.get("type") in ("error",) )
        abstain = bool(cl["issues"]) or terminal.get("status") in ("clarification_needed", "unsupported", "blocked", "partial")
        ok = (cl["acceptable"] and not abstain) if terminal.get("type") not in ("error",) else False
        note = (f"contract={cl['kind']}; issues={cl['issues'] or 'none'}; "
                f"sections={len(secs)}; evidence={evidence_rows}; answer={str(answer)[:90]}")
        if cmd in ("optimize", "experiment") and terminal.get("type") == "diagnosis_answer":
            note += " [SEMANTIC FINDING: legacy canned diagnose (query-agnostic scenario); not sectioned]"
        if cmd == "compare":
            note += " [compare returns research contract; sectioned synthesis not implemented for compare]"
        if cmd == "design" and "0 valid PROTAC candidate" in str(answer):
            note += " [offline: 0 candidates (evidence-bounded abstention); P1 offline-recall]"
        rows.append(_row(label, cmd, terminal.get("type", ""), cl["kind"], len(secs) if secs else None,
                         evidence_rows, "PASS" if ok else "MIXED" if (honest and abstain) else "FAIL", note))
    return rows


def _row(label, cmd, terminal_type, contract_kind, sections, evidence, verdict, note) -> dict:
    return {"command": label, "handler_cmd": cmd, "terminal_payload_type": terminal_type,
            "contract_kind": contract_kind, "sections": sections, "evidence_rows": evidence,
            "verdict": verdict, "note": note}


def main() -> None:
    rows = audit()
    with open(OUT / "command_contract_audit.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (OUT / "report.md").write_text(
        "# User-facing command contract audit — /design /run /optimize /experiment /validate /compare\n\n"
        "Method: each command through the real TUI bridge (fresh process), contract classified with "
        "protacxtend.tui_bridge.contract; verdict PASS = acceptable contract with no abstention-only outcome, "
        "MIXED = honest abstention/typed limitation, FAIL = no terminal payload or unacceptable contract.\n\n"
        "| command | terminal | contract | sections | evidence | verdict | note |\n|---|---|---|---|---|---|---|\n"
        + "\n".join(f"| {r['command']} | {r['terminal_payload_type']} | {r['contract_kind']} | {r['sections']} | "
                    f"{r['evidence_rows']} | {r['verdict']} | {r['note']} |" for r in rows)
        + "\n\nFindings and follow-ups are itemized in the companion summary; this audit applies no fixes.",
        encoding="utf-8")
    for r in rows:
        print(f"{r['command']:<28} {r['terminal_payload_type']:<18} {str(r['contract_kind']):<20} "
              f"{r['verdict']:<7} {r['note'][:110]}")


if __name__ == "__main__":
    main()