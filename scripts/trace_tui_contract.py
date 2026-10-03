#!/usr/bin/env python3
"""Fresh-process transcripts for the TUI response contract (AFTER state).

For each command: spawns a fresh python bridge process, captures the raw
terminal payload (producer JSON), renders the visible text via the shared
contract mirror (protacxtend.tui_bridge.contract), and writes:
- docs/architecture/tui_contract/transcripts/<slug>.raw.json
- docs/architecture/tui_contract/transcripts/<slug>.rendered.txt
- docs/architecture/tui_contract/raw_vs_displayed.md   (diff summary)
- docs/architecture/tui_contract/transcripts/manifest.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "architecture", "tui_contract", "transcripts")

HARNESS = r"""
import json, sys
import protacxtend.tui_bridge.server as server
caps = []
server.emit = lambda p: caps.append(p)
server.handle_command(%r, %s)
print(json.dumps(caps, default=str))
"""

COMMANDS = [
    ("plan_hmgb2", "plan", {"request": "/plan HMGB2 protac", "conversation_id": "t1"}),
    ("investigate_ar", "investigate", {"request": "AR protac", "conversation_id": "t2"}),
    ("reason_egfr", "reason", {"request": "which protac work for EGFR", "conversation_id": "t3"}),
]


def main() -> None:
    from protacxtend.tui_bridge import contract as C

    os.makedirs(OUT, exist_ok=True)
    rows: list[dict] = []
    diff_lines: list[str] = [
        "# Raw response vs displayed output — /plan, /investigate, /reason",
        "",
        "Fresh subprocess per command (`python -m protacxtend.tui_bridge.server`), "
        "offline (`PROTACXTEND_PLANNER_OFFLINE=1`). Raw = terminal payload as emitted "
        "by the producer; displayed = visible text via the shared contract mirror "
        "(`protacxtend/tui_bridge/contract.py`), which the Node TUI implements.",
        "",
        "| command | raw terminal payload | contract kind | displayed lines | annex (stages/artifacts) |",
        "|---|---|---|---|---|",
    ]
    for slug, cmd, args in COMMANDS:
        code = HARNESS % (cmd, json.dumps(args))
        p = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            cwd=ROOT, env={**os.environ, "PROTACXTEND_PLANNER_OFFLINE": "1"}, timeout=400,
        )
        assert p.returncode == 0, p.stderr[-800:]
        payloads = json.loads(p.stdout.strip().splitlines()[-1])
        term = next(pp for pp in payloads if isinstance(pp, dict) and pp.get("type") in (
            "plan_answer", "research_answer", "investigate_answer", "diagnosis_answer"))
        cl = C.classify(term)
        an = C.annex(term)
        text = C.answer_text(term)
        with open(os.path.join(OUT, f"{slug}.raw.json"), "w") as f:
            json.dump(term, f, indent=1, default=str)
        with open(os.path.join(OUT, f"{slug}.rendered.txt"), "w") as f:
            f.write("\n".join(text) + "\n")
        rows.append({
            "slug": slug, "command": cmd, "request": (args.get("request") or args.get("query")),
            "type": term.get("type"), "kind": cl["kind"], "issues": cl["issues"],
            "n_answer_lines": len(text), "stage_status": an["stage_status"],
            "artifacts": an["artifacts"], "raw_file": f"{slug}.raw.json",
            "rendered_file": f"{slug}.rendered.txt",
        })
        diff_lines.append(
            f"| `{cmd}` `{args.get('request') or args.get('query')}` | `{term.get('type')}` "
            f"(kind `{cl['kind']}`, issues `{cl['issues'] or 'none'}`) | "
            f"`{cl['kind']}` | {len(text)} lines: `{text[0][:60] if text else '(empty)'}` | "
            f"{len(an['stage_status'])} stages / {len(an['artifacts'])} artifacts |"
        )
        diff_lines.append("")
        diff_lines.append(f"### {slug} — payload fields consumed by the renderer")
        diff_lines.append("")
        diff_lines.append("| field | in raw payload | rendered? |")
        diff_lines.append("|---|---|---|")
        for key in ("interpretation", "tasks", "open_questions", "stage_timeline", "artifact_paths",
                    "scientific_findings", "findings", "evidence_gap_conclusion",
                    "scientific_direct_answer", "case_source", "hypotheses", "tests",
                    "recommended_action", "gated", "resource_reason_summary"):
            present = key in term
            rendered = key in {
                "interpretation", "tasks", "open_questions", "stage_timeline", "artifact_paths",
                "scientific_findings", "evidence_gap_conclusion", "scientific_direct_answer",
                "case_source", "hypotheses", "tests", "recommended_action", "gated",
            } and present
            note = ""
            if key == "resource_reason_summary" and present:
                note = " — excluded (never a scientific answer)"
            diff_lines.append(f"| {key} | {'yes' if present else 'no'} | {'yes' if rendered else 'no'}{note} |")
        diff_lines.append("")

    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump({"commands": rows, "contract_version": "v1",
                   "generated_by": "scripts/trace_tui_contract.py"}, f, indent=1)
    with open(os.path.join(ROOT, "docs", "architecture", "tui_contract", "raw_vs_displayed.md"), "w") as f:
        f.write("\n".join(diff_lines))
    print("\n".join(f"{r['slug']}: raw={r['raw_file']} rendered={r['rendered_file']} kind={r['kind']}" for r in rows))


if __name__ == "__main__":
    main()