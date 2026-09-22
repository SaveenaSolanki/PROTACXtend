#!/usr/bin/env python3
"""Sprint 2C — execute the frozen 48-task KNOW→REASON→DESIGN→DISCOVER benchmark.

Systems executed live (same model/provider: deepseek / deepseek-v4-flash):
  PROTACXtend · Base-LLM-control · AI-Co-Scientist-compatible

Biomni and the live Google AI Co-Scientist service are formally marked
UNAVAILABLE (external services, not present/licensed in this environment) —
see benchmark_results/raw/biomni/UNAVAILABLE.json and configs/*.json.

Blindness: adapters only ever see benchmark/cases/*.json (supplied inputs).
Ground truth (benchmark/ground_truth/) is never opened during execution.
Every raw response is persisted under benchmark_results/raw/<system>/<task_id>.json
BEFORE any scoring runs.

Usage:
  python3 scripts/sprint2_execute.py [--systems a,b] [--tasks KNOW-01,...]
                                     [--force] [--timeout 660]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from benchmark_runner import freeze  # noqa: E402
from benchmark_runner.runner import BenchmarkRunner, RunConfig, TaskInput  # noqa: E402

BENCH = REPO / "benchmark"
OUT = REPO / "benchmark_results"

SYSTEM_DIR = {
    "PROTACXtend": "protacxtend",
    "Biomni": "biomni",
    "AI-Co-Scientist-compatible": "ai_coscientist",
    "Base-LLM-control": "base_llm",
    "DeepSeek-Flash-control": "deepseek_flash",
    "Local-Ollama-control": "local_ollama",
}

UNAVAILABLE = {
    "Biomni": ("external scientific-agent workflow (per benchmark/BASELINES.md: "
               "'Run only when licensed/available'). No Biomni code, binary, license or "
               "credentials exist in this environment; installing an unlicensed external "
               "workflow was not possible, so all 48 Biomni rows are marked UNAVAILABLE."),
    "AI-Co-Scientist": ("Google AI Co-Scientist is a closed external service. No API access, "
                        "credentials or deployment are available in this environment. The "
                        "locally-runnable 'AI-Co-Scientist-compatible' workflow shape defined in "
                        "benchmark/BASELINES.md WAS executed instead (48 tasks) and is stored "
                        "under raw/ai_coscientist/."),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="PROTACXtend,Base-LLM-control,AI-Co-Scientist-compatible")
    ap.add_argument("--tasks", default="", help="comma list of task ids (default: all 48 from manifest)")
    ap.add_argument("--force", action="store_true", help="rerun even if raw output exists")
    ap.add_argument("--timeout", type=float, default=660.0, help="hard wall-clock per task-system (s)")
    args = ap.parse_args()

    # 1. fail closed on freeze drift
    freeze.assert_frozen(BENCH)
    frozen = freeze.load_freeze_manifest(BENCH)
    print(f"[execute] freeze OK: {frozen['freeze_version']} frozen {frozen['frozen_at']} "
          f"({frozen['counts']['total']} files)")

    rows = list(csv.DictReader(open(BENCH / "benchmark_manifest.csv", encoding="utf-8")))
    if args.tasks:
        wanted = {t.strip() for t in args.tasks.split(",") if t.strip()}
        rows = [r for r in rows if r["task_id"] in wanted]
    tasks = [TaskInput.from_case(BENCH / "cases" / f"{r['task_id']}.json") for r in rows]
    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    print(f"[execute] {len(tasks)} tasks x {len(systems)} systems")

    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    (OUT / "configs").mkdir(parents=True, exist_ok=True)
    (OUT / "scored").mkdir(parents=True, exist_ok=True)

    # 2. system configuration snapshots
    cfg = {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "temperature": 0.0,
        "seed": 42,
        "num_ctx": 16384,
        "timeout_s": args.timeout,
        "usage_estimate": "tokens estimated as chars/4; cost = tokens x published per-1M rates "
                          "(in $0.14, out $0.28) labelled estimated",
        "repeat": 1,
        "date": datetime.now(timezone.utc).isoformat(),
    }
    for sid in ["protacxtend", "base_llm", "biomni", "ai_coscientist"]:
        name = {"protacxtend": "PROTACXtend", "base_llm": "Base-LLM-control",
                "ai_coscientist": "AI-Co-Scientist-compatible",
                "biomni": "Biomni"}[sid]
        payload = dict(cfg)
        payload["system"] = name
        payload["status"] = "UNAVAILABLE" if name == "Biomni" else (
            "executed (AI-Co-Scientist-compatible local workflow; live Google "
            "AI Co-Scientist service UNAVAILABLE)" if sid == "ai_coscientist"
            else "executed")
        if name in UNAVAILABLE:
            payload["reason_unavailable"] = UNAVAILABLE[name]
        payload["system_version"] = _system_version(name)
        payload["freeze"] = {"freeze_version": frozen["freeze_version"],
                             "frozen_at": frozen["frozen_at"]}
        (OUT / "configs" / f"{sid}_config.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    # biomni + ai_coscientist UNAVAILABLE marker files
    (OUT / "raw" / "biomni").mkdir(parents=True, exist_ok=True)
    (OUT / "raw" / "biomni" / "UNAVAILABLE.json").write_text(json.dumps({
        "system": "Biomni", "status": "UNAVAILABLE",
        "reason": UNAVAILABLE["Biomni"],
        "tasks_attempted": 0, "recorded_at": datetime.now(timezone.utc).isoformat()},
        indent=2) + "\n", encoding="utf-8")
    (OUT / "raw" / "ai_coscientist").mkdir(parents=True, exist_ok=True)
    (OUT / "raw" / "ai_coscientist" / "SERVICE_NOTE.json").write_text(json.dumps({
        "live_google_ai_coscientist": "UNAVAILABLE",
        "reason": UNAVAILABLE["AI-Co-Scientist"],
        "executed_instead": "AI-Co-Scientist-compatible local workflow (BASELINES.md)",
        "recorded_at": datetime.now(timezone.utc).isoformat()}, indent=2) + "\n",
        encoding="utf-8")

    # 3. run loop (resumable, deterministic order, one process per pair)
    log_path = OUT / "execution_log.csv"
    log_fields = ["task_id", "stage", "system", "model", "provider", "input",
                  "raw_output", "parsed_output", "tool_calls", "runtime_seconds",
                  "success", "error", "timestamp", "run_seed_config", "envelope_file"]
    new_log = not log_path.exists()
    log_fh = open(log_path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(log_fh, fieldnames=log_fields)
    if new_log:
        writer.writeheader()
    done = 0
    failed = 0
    for task in tasks:
        stage = task.capability
        for system in systems:
            sysdir = SYSTEM_DIR[system]
            env_file = OUT / "raw" / sysdir / f"{task.task_id}.json"
            if env_file.exists() and not args.force:
                print(f"[skip ] {task.task_id} {system} (exists)")
                done += 1
                continue
            env = _run_pair(task, system, args.timeout)
            env_file.parent.mkdir(parents=True, exist_ok=True)
            env_file.write_text(json.dumps(env, indent=1, default=str), encoding="utf-8")
            ok = env.get("status") == "ok"
            if not ok:
                failed += 1
            writer.writerow({
                "task_id": task.task_id, "stage": stage, "system": system,
                "model": env.get("model"), "provider": env.get("provider"),
                "input": json.dumps({"question": task.question,
                                     "supplied_inputs": task.supplied_inputs},
                                    default=str),
                "raw_output": env_file.as_posix(),
                "parsed_output": str(env.get("answer"))[:2000],
                "tool_calls": (env.get("run") or {}).get("tool_calls"),
                "runtime_seconds": (env.get("run") or {}).get("runtime_s"),
                "success": "success" if ok else env.get("status"),
                "error": "; ".join(env.get("errors") or env.get("warnings") or []),
                "timestamp": (env.get("run") or {}).get("started_at"),
                "run_seed_config": json.dumps({"seed": (env.get("run") or {}).get("seed"),
                                               "temperature": (env.get("run") or {}).get("temperature"),
                                               "model": env.get("model"),
                                               "provider": env.get("provider")}),
                "envelope_file": env_file.as_posix(),
            })
            log_fh.flush()
            done += 1
            print(f"[done ] {task.task_id} {system} -> {env.get('status')} "
                  f"({(env.get('run') or {}).get('runtime_s')} s)")
    log_fh.close()
    print(f"[execute] completed {done} task-system runs; {failed} non-ok. "
          f"log: {log_path}")
    return 0


def _run_pair(task: TaskInput, system: str, timeout: float) -> dict:
    """Run one task-system pair in a child process so a hung run cannot stall the batch."""
    import multiprocessing as mp
    q = mp.Queue()
    p = mp.Process(target=_child_run, args=(q, task, system, timeout))
    p.start()
    p.join(timeout + 30.0)
    if p.is_alive():
        p.terminate()
        p.join(5)
        return {"benchmark_envelope_version": "1.0.0", "base_schema_version": "1.0.0",
                "status": "failed", "task_id": task.task_id, "capability": task.capability,
                "system": system, "workflow": "KNOW-REASON-DESIGN-DISCOVER",
                "metadata": {"run_id": uuid.uuid4().hex[:12], "attempts": 1,
                             "fixture_only": False, "frozen_at": None},
                "provider": "deepseek", "model": "deepseek-v4-flash",
                "provider_model_version": "deepseek-v4-flash",
                "answer": None, "summary": f"wall-clock timeout after {timeout}s",
                "evidence": [], "tools": [], "artifacts": [], "warnings": ["wall-clock timeout"],
                "errors": [f"process killed after {timeout}s"], "provenance": [],
                "run": {"seed": 42, "repeat": 1, "tool_calls": 0, "runtime_s": timeout,
                        "tokens_in": None, "tokens_out": None, "api_cost_usd": None,
                        "provider_model_version": "deepseek-v4-flash", "blinded": True,
                        "started_at": None, "ended_at": None},
                "raw_response": "", "scoring": None}
    if q.empty():
        return {"status": "failed", "task_id": task.task_id, "capability": task.capability,
                "system": system, "answer": None, "errors": ["child produced no envelope"],
                "warnings": ["child produced no envelope"], "run": {}}
    return q.get()


def _child_run(q, task: TaskInput, system: str, timeout: float) -> None:
    try:
        budget = int((task.raw.get("budget") or {}).get("runtime_s") or 600)
        config = RunConfig(
            provider="deepseek", model="deepseek-v4-flash", version="deepseek-v4-flash",
            seed=int((task.raw.get("budget") or {}).get("seed") or 42),
            temperature=0.0, timeout_s=min(float(budget), timeout),
            allow_real=True, system_id=system,
        )
        runner = BenchmarkRunner(config, benchmark_root=BENCH, check_freeze=False)
        env = runner.run(task)
        q.put(env)
    except Exception as exc:  # record the failure, never rerun
        q.put({"status": "failed", "task_id": task.task_id, "capability": task.capability,
               "system": system, "answer": None, "errors": [f"adapter exception: {exc}"],
               "warnings": [f"adapter exception: {exc}"], "run": {},
               "provider": "deepseek", "model": "deepseek-v4-flash"})


def _system_version(system: str) -> str:
    try:
        import protacxtend
        return f"protacxtend-{getattr(protacxtend, '__version__', '0.3.0')}"
    except Exception:
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
