#!/usr/bin/env python
"""Closed 48-case benchmark orchestrator (PROTACXtend + two baselines).

Runs every case under three arms in isolated subprocesses with hard per-arm
wall-time budgets. Records per-case outcome, abstention, failure code, evidence
count, tool calls and runtime.

It does **not** compute correctness: the 48-case gold is
``PENDING_INDEPENDENT_REVIEW``. Use ``scripts/score_closed_48.py`` once a
reviewer-approved gold file exists.

Usage::

    python scripts/run_closed_48.py --workers 12
    python scripts/run_closed_48.py --arms direct_tool,fixed_workflow
    python scripts/run_closed_48.py --arms protacxtend --timeout-protacxtend 120
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmark" / "cases"
GATESPLITS = ROOT / "benchmark" / "gateC" / "splits.json"
WORKER = ROOT / "scripts" / "closed48_worker.py"
DEFAULT_OUT = ROOT / "benchmark_results" / "closed48"

TIMEOUTS = {"protacxtend": 180, "direct_tool": 60, "fixed_workflow": 120}


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return ""


def load_cases() -> List[str]:
    return sorted(p.stem for p in CASES.glob("*.json") if not p.stem.startswith("_"))


def run_one(case_id: str, arm: str, timeout: int, workdir: Path) -> Dict[str, Any]:
    out = workdir / f"{case_id}.{arm}.json"
    started = time.time()
    capability = ""
    case_path = CASES / f"{case_id}.json"
    if case_path.exists():
        capability = json.loads(case_path.read_text(encoding="utf-8")).get("capability", "")
    cmd = [sys.executable, str(WORKER), "--case", case_id, "--arm", arm, "--out", str(out)]
    env = dict(os.environ)
    env.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")
    try:
        subprocess.run(cmd, cwd=str(ROOT), env=env, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except subprocess.TimeoutExpired:
        return {"case_id": case_id, "capability": capability, "arm": arm, "outcome": "timeout",
                "status": "timeout", "failure_code": "WALL_TIME_EXCEEDED",
                "error": f"exceeded {timeout}s budget", "latency_s": round(time.time() - started, 3),
                "n_evidence_refs": 0, "tool_calls": None,
                "correctness": "PENDING_INDEPENDENT_GOLD", "score": None,
                "scientific_conclusion": "PENDING_INDEPENDENT_REVIEW"}
    if not out.exists():
        return {"case_id": case_id, "capability": capability, "arm": arm, "outcome": "failed",
                "status": "no_output", "failure_code": "WORKER_NO_OUTPUT",
                "error": "worker produced no result", "latency_s": round(time.time() - started, 3),
                "n_evidence_refs": 0, "tool_calls": None,
                "correctness": "PENDING_INDEPENDENT_GOLD", "score": None,
                "scientific_conclusion": "PENDING_INDEPENDENT_REVIEW"}
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arms", default="protacxtend,direct_tool,fixed_workflow")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout-protacxtend", type=int, default=TIMEOUTS["protacxtend"])
    ap.add_argument("--timeout-direct", type=int, default=TIMEOUTS["direct_tool"])
    ap.add_argument("--timeout-fixed", type=int, default=TIMEOUTS["fixed_workflow"])
    ap.add_argument("--run-id", default="")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    timeouts = {"protacxtend": args.timeout_protacxtend,
                "direct_tool": args.timeout_direct, "fixed_workflow": args.timeout_fixed}
    case_ids = load_cases()
    run_id = args.run_id or f"closed48_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out = args.out_dir / run_id
    work = out / "raw"
    work.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc).isoformat()
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(run_one, cid, arm, timeouts[arm], work): (cid, arm)
                   for cid in case_ids for arm in arms}
        for fut in as_completed(futures):
            cid, arm = futures[fut]
            try:
                results.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                results.append({"case_id": cid, "arm": arm, "outcome": "failed",
                                "failure_code": type(exc).__name__, "error": str(exc),
                                "correctness": "PENDING_INDEPENDENT_GOLD", "score": None})

    results.sort(key=lambda r: (r.get("case_id", ""), r.get("arm", "")))
    with (out / "predictions.jsonl").open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    with (out / "tool_runs.jsonl").open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps({"case_id": r.get("case_id"), "arm": r.get("arm"),
                                 "tool_calls": r.get("tool_calls"),
                                 "outcome": r.get("outcome"),
                                 "failure_code": r.get("failure_code"),
                                 "latency_s": r.get("latency_s")}, default=str) + "\n")
    failures = [r for r in results if r.get("outcome") in {"failed", "timeout", "refused"}]
    with (out / "failures.jsonl").open("w", encoding="utf-8") as fh:
        for r in failures:
            fh.write(json.dumps({"case_id": r.get("case_id"), "arm": r.get("arm"),
                                 "outcome": r.get("outcome"),
                                 "failure_code": r.get("failure_code", ""),
                                 "error": r.get("error", "")}, default=str) + "\n")

    splits = json.loads(GATESPLITS.read_text(encoding="utf-8"))["assignment"] if GATESPLITS.exists() else {}
    with (out / "results_table.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "capability", "split", "arm", "outcome", "failure_code",
                    "n_evidence_refs", "latency_s", "correctness", "scientific_conclusion"])
        for r in results:
            w.writerow([r.get("case_id"), r.get("capability"), splits.get(r.get("case_id"), ""),
                        r.get("arm"), r.get("outcome"), r.get("failure_code", ""),
                        r.get("n_evidence_refs", 0), r.get("latency_s"),
                        "PENDING_INDEPENDENT_GOLD", "PENDING_INDEPENDENT_REVIEW"])

    counts: Dict[str, Dict[str, int]] = {}
    for arm in arms:
        counts[arm] = {}
        for r in results:
            if r.get("arm") == arm:
                counts[arm][r.get("outcome", "?")] = counts[arm].get(r.get("outcome", "?"), 0) + 1
    manifest = {
        "run_id": run_id,
        "schema_version": "closed48.run.v1",
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "host": socket.gethostname(),
        "execution_mode": os.environ.get("PROTACXTEND_EXECUTION_MODE", "scientific"),
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "n_cases": len(case_ids),
        "arms": arms,
        "timeouts_s": timeouts,
        "outcome_counts": counts,
        "benchmark_score": None,
        "correctness_status": "PENDING_INDEPENDENT_GOLD",
        "score_note": ("No correctness is computed. The 29 reviewer decisions and all 48 gold "
                       "adjudications are PENDING. Run scripts/score_closed_48.py after approval."),
        "artifacts": ["predictions.jsonl", "tool_runs.jsonl", "failures.jsonl", "results_table.csv"],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "n_cases": len(case_ids), "arms": arms,
                      "outcome_counts": counts, "benchmark_score": None,
                      "correctness_status": "PENDING_INDEPENDENT_GOLD"}, indent=2))
    print(f"artifacts: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
