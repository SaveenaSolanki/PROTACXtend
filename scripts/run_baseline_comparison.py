#!/usr/bin/env python
"""Run the matched-compute baseline comparison over the frozen benchmark.

Baselines (all deterministic unless the LLM baseline has credentials):

* ``retrieval-only``   — identity/retrieval tools only;
* ``tool-only``        — every offline permitted adapter, no orchestration;
* ``Base-LLM-control`` — same provider/model, no tools (skipped without a key);
* ``PROTACXtend-offline`` — the full canonical stack (opt-in, expensive).

Every answer is graded by the deterministic scoring engine
(:mod:`benchmark_runner.grader`) and the report preserves tool calls, status,
latency and failure classes. Output goes to
``benchmark_results/baselines/``.

Examples::

    python scripts/run_baseline_comparison.py --limit 8
    python scripts/run_baseline_comparison.py --systems retrieval-only,tool-only
    python scripts/run_baseline_comparison.py --include-protacxtend --tasks DESIGN-01,KNOW-01
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark_runner.baselines import build_baseline  # noqa: E402
from benchmark_runner.grader import grade_answer  # noqa: E402
from benchmark_runner.matched_tools import coverage, match_task  # noqa: E402
from benchmark_runner.runner import TaskInput  # noqa: E402

CASES = ROOT / "benchmark" / "cases"
OUT_DIR = ROOT / "benchmark_results" / "baselines"

DEFAULT_SYSTEMS = ["retrieval-only", "tool-only", "Base-LLM-control"]


def _load_tasks() -> list[TaskInput]:
    tasks: list[TaskInput] = []
    for path in sorted(CASES.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        tasks.append(TaskInput.from_case(path))
    return tasks


class _Timeout(Exception):
    pass


def _run_with_timeout(fn, timeout_s: float):
    if timeout_s <= 0 or not hasattr(signal, "SIGALRM"):
        return fn()

    def _handler(signum, frame):  # noqa: ANN001
        raise _Timeout()

    previous = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_s)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _run_system(system_id: str, tasks: list[TaskInput], *, offline_only: bool,
                timeout_s: float) -> dict[str, Any]:
    baseline = build_baseline(system_id)
    rows: list[dict[str, Any]] = []
    for task in tasks:
        started = time.monotonic()
        try:
            answer = _run_with_timeout(
                lambda t=task: baseline.run(t, offline_only=offline_only), timeout_s
            )
            answer_dict = answer.to_dict()
            error = ""
        except _Timeout:
            answer_dict = {"system": system_id, "task_id": task.task_id, "status": "timeout",
                           "answer": "", "tool_calls": [], "errors": ["task timeout"]}
            error = "timeout"
        except Exception as exc:  # noqa: BLE001
            answer_dict = {"system": system_id, "task_id": task.task_id, "status": "error",
                           "answer": "", "tool_calls": [], "errors": [str(exc)]}
            error = f"{type(exc).__name__}: {exc}"
        latency = round(time.monotonic() - started, 3)
        if answer_dict.get("status") == "skipped_no_credentials":
            score = {"status": "skipped_no_credentials", "score": None, "gt_type": ""}
        else:
            score = grade_answer(task.task_id, answer_dict.get("answer") or "")
        rows.append({
            "task_id": task.task_id,
            "capability": task.capability,
            "status": answer_dict.get("status"),
            "error": error or "; ".join(answer_dict.get("errors") or []),
            "latency_s": latency,
            "n_tool_calls": len(answer_dict.get("tool_calls") or []),
            "score": score,
        })
    scored = [r["score"]["score"] for r in rows if r["score"].get("score") is not None]
    by_capability: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row["score"].get("score") is not None:
            by_capability[row["capability"]].append(row["score"]["score"])
    return {
        "system": system_id,
        "n_tasks": len(rows),
        "n_scored": len(scored),
        "n_abstained": sum(1 for r in rows if r["status"] == "abstained"),
        "n_skipped": sum(1 for r in rows if r["status"] == "skipped_no_credentials"),
        "n_errors": sum(1 for r in rows if r["status"] in {"error", "timeout"}),
        "mean_score": round(sum(scored) / len(scored), 4) if scored else None,
        "by_capability": {k: round(sum(v) / len(v), 4) for k, v in sorted(by_capability.items())},
        "results": rows,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Baseline comparison",
        "",
        f"- generated: {report['timestamp_utc']}",
        f"- tasks: {report['n_tasks']}",
        f"- offline_only: {report['offline_only']}",
        "",
        "| system | scored | abstained | skipped | errors | mean score |",
        "|---|---|---|---|---|---|",
    ]
    for system in report["systems"]:
        lines.append(
            f"| {system['system']} | {system['n_scored']} | {system['n_abstained']} | "
            f"{system['n_skipped']} | {system['n_errors']} | {system['mean_score']} |"
        )
    lines += ["", "## Match coverage", "", f"- distinct permitted ids: {report['coverage']['n_distinct_permitted']}",
              f"- distinct matched: {report['coverage']['n_distinct_matched']}",
              f"- distinct unmatched: {report['coverage']['n_distinct_unmatched']}",
              f"- unmatched ids: {report['coverage']['unmatched_ids']}", ""]
    lines += ["## Per-capability mean score", "", "| system | KNOW | REASON | DESIGN | DISCOVER |",
              "|---|---|---|---|---|"]
    for system in report["systems"]:
        caps = system["by_capability"]
        lines.append(
            f"| {system['system']} | {caps.get('KNOW', '—')} | {caps.get('REASON', '—')} | "
            f"{caps.get('DESIGN', '—')} | {caps.get('DISCOVER', '—')} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--systems", default=",".join(DEFAULT_SYSTEMS))
    parser.add_argument("--include-protacxtend", action="store_true",
                        help="Also run the (expensive) canonical deterministic stack.")
    parser.add_argument("--allow-network", action="store_true",
                        help="Allow network-backed permitted tools (default offline).")
    parser.add_argument("--capability", default="")
    parser.add_argument("--tasks", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-task timeout (s).")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    if args.include_protacxtend and "PROTACXtend-offline" not in systems:
        systems.append("PROTACXtend-offline")

    tasks = _load_tasks()
    if args.capability:
        tasks = [t for t in tasks if t.capability == args.capability]
    if args.tasks:
        wanted = {t.strip() for t in args.tasks.split(",") if t.strip()}
        tasks = [t for t in tasks if t.task_id in wanted]
    if args.limit:
        tasks = tasks[: args.limit]

    offline_only = not args.allow_network
    system_reports = [
        _run_system(system, tasks, offline_only=offline_only, timeout_s=args.timeout)
        for system in systems
    ]
    report = {
        "schema_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "n_tasks": len(tasks),
        "offline_only": offline_only,
        "systems": system_reports,
        "coverage": coverage(tasks),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = args.out_dir / f"baseline_comparison_{stamp}.json"
    md_path = args.out_dir / f"baseline_comparison_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    for system in system_reports:
        print(f"{system['system']:24s} mean={system['mean_score']} "
              f"scored={system['n_scored']} abstained={system['n_abstained']} skipped={system['n_skipped']}")
    print(f"report: {json_path}")
    print(f"summary: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
