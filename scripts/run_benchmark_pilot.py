#!/usr/bin/env python
"""Run a PROTACXtend-only benchmark pilot and grade it.

Two modes:

``--offline-smoke``
    Fast validation of the grading pipeline: grades each task's own authored
    ground-truth answer against its derived criteria.  No scientific pipeline
    is executed.  Use this to verify the scoring engine end-to-end.

default
    Runs the canonical PROTACXtend stack (deterministic engine) for each task
    and grades its emitted ``TherapeuticStrategy``.

Examples::

    python scripts/run_benchmark_pilot.py --offline-smoke
    python scripts/run_benchmark_pilot.py --limit 3 --capability DESIGN
    python scripts/run_benchmark_pilot.py --tasks DESIGN-01,KNOW-01

The full report is written under ``benchmark_results/pilots/``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark_runner.grader import grade_answer, load_ground_truth  # noqa: E402

CASES = ROOT / "benchmark" / "cases"
OUT_DIR = ROOT / "benchmark_results" / "pilots"


def _load_cases() -> List[Dict[str, Any]]:
    cases = []
    for path in sorted(CASES.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        cases.append(json.loads(path.read_text(encoding="utf-8")))
    return cases


def _answer_from_result(result: Dict[str, Any]) -> str:
    """Extract a gradeable answer string from a canonical run result."""
    strategy = result.get("therapeutic_strategy") or {}
    if strategy:
        # A compact but complete rendering of the typed decision artifact.
        return json.dumps(strategy, default=str)
    return json.dumps(result.get("summary") or result, default=str)


def _run_one(case: Dict[str, Any], engine: str) -> Dict[str, Any]:
    from protacxtend.agents.runtime import run_protacpilot

    question = case.get("scientific_question") or case.get("title") or ""
    started = time.monotonic()
    try:
        result = run_protacpilot(question, mode=engine, config={"record_run": False})
        answer = _answer_from_result(result)
        error = ""
        status = "ok"
    except Exception as exc:  # noqa: BLE001 - record, never crash the pilot
        answer = ""
        error = f"{type(exc).__name__}: {exc}"
        status = "failed"
    score = grade_answer(case["task_id"], answer)
    return {
        "task_id": case["task_id"],
        "capability": case.get("capability", ""),
        "run_status": status,
        "error": error,
        "latency_s": round(time.monotonic() - started, 2),
        "score": score,
    }


def _smoke_one(case: Dict[str, Any]) -> Dict[str, Any]:
    gt = load_ground_truth(case["task_id"])
    answer = str(gt.get("expected_answer") or "")
    score = grade_answer(case["task_id"], answer)
    return {
        "task_id": case["task_id"],
        "capability": case.get("capability", ""),
        "run_status": "offline_smoke",
        "error": "",
        "latency_s": 0.0,
        "score": score,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-smoke", action="store_true",
                        help="Grade authored GT answers instead of running the pipeline.")
    parser.add_argument("--engine", choices=["deterministic", "agentic"], default="deterministic")
    parser.add_argument("--capability", default="", help="Filter by capability (KNOW/REASON/DESIGN/DISCOVER).")
    parser.add_argument("--tasks", default="", help="Comma-separated task ids.")
    parser.add_argument("--limit", type=int, default=0, help="Max tasks (0 = all).")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    cases = _load_cases()
    if args.capability:
        cases = [c for c in cases if c.get("capability") == args.capability]
    if args.tasks:
        wanted = {t.strip() for t in args.tasks.split(",") if t.strip()}
        cases = [c for c in cases if c["task_id"] in wanted]
    if args.limit:
        cases = cases[: args.limit]

    results = []
    for case in cases:
        results.append(_smoke_one(case) if args.offline_smoke else _run_one(case, args.engine))

    scored = [r["score"]["score"] for r in results if r["score"].get("score") is not None]
    mean = round(sum(scored) / len(scored), 4) if scored else None
    report = {
        "schema_version": "1.0.0",
        "system": "PROTACXtend",
        "engine": "offline-smoke" if args.offline_smoke else args.engine,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "n_tasks": len(results),
        "n_scored": len(scored),
        "mean_score": mean,
        "results": results,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out_dir / f"pilot_{report['engine']}_{stamp}.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"tasks={report['n_tasks']} scored={report['n_scored']} mean_score={mean}")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
