#!/usr/bin/env python
"""Gate-C four-system pilot runner (S1/S2/S3/S4).

Runs the four frozen Gate-C pilot cases through four real systems, one
replicate each (16 intended runs), preserving raw outputs, tool traces, typed
outcomes, latency/cost and infrastructure errors. It emits **no correctness
score** — gold is PENDING independent review — only execution/validation
evidence.

Systems
    S1  LLM+RAG          benchmark_runner.live_systems.RetrievalRAGLiveAdapter
    S2  LLM+flat-tools   benchmark_runner.live_systems.LLMFlatToolsLiveAdapter
    S3  PROTACXtend      benchmark_runner.live.PROTACXtendLiveAdapter
    S4  Biomni           benchmark_runner.live_systems.BiomniLiveAdapter

Usage
    python scripts/gateC_four_system.py --online
    python scripts/gateC_four_system.py --systems S1,S2,S3 --resume <run_dir>

Never overwrites an existing run directory. Each (case, system, replicate) has
an immutable JSON result; reruns create a new run_id.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# NOTE: PROTACXTEND_EXECUTION_MODE is set inside main(), NOT at import time.
# Importing this module must not mutate process-global state (a test importing
# it for _classify/_behavior_match previously leaked 'scientific' mode into the
# rest of the pytest process).

PILOT_DIR = ROOT / "benchmark" / "gateC" / "pilot"
CASES_DIR = ROOT / "benchmark" / "cases"
DEFAULT_OUT = ROOT / "benchmark_results" / "gateC_four_system"

# Adapter-level retry policy (declared): retry once on transport/infra errors
# only, never on a typed abstention or a valid/invalid answer.
MAX_INFRA_RETRIES = 1

SYSTEMS = {
    "S1": ("LLM+RAG", "benchmark_runner.live_systems", "RetrievalRAGLiveAdapter"),
    "S2": ("LLM+flat-tools", "benchmark_runner.live_systems", "LLMFlatToolsLiveAdapter"),
    "S3": ("PROTACXtend", "benchmark_runner.live", "PROTACXtendLiveAdapter"),
    "S4": ("Biomni", "benchmark_runner.live_systems", "BiomniLiveAdapter"),
}

OUTCOME_CLASSES = ("answered", "abstained", "errored", "timed_out", "unavailable")


def _git() -> Dict[str, str]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                                         stderr=subprocess.DEVNULL).decode().strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=str(ROOT),
                                        stderr=subprocess.DEVNULL).decode().strip()
        return {"commit": commit, "dirty": "yes" if dirty else "no"}
    except Exception:  # noqa: BLE001
        return {"commit": "", "dirty": ""}


def _adapter(key: str, allow_real: bool = True):
    import importlib
    name, module, cls_name = SYSTEMS[key]
    cls = getattr(importlib.import_module(module), cls_name)
    return cls(name, allow_real=allow_real)


def _classify(result: Dict[str, Any]) -> str:
    status = str(result.get("status", "")).lower()
    blob = " ".join(str(result.get(k) or "") for k in ("error", "answer", "failure_code")).lower()
    abstention_markers = ("missing_scientific_input", "missingscientificinput",
                          "clarification_required", "clarification needed",
                          "syntheticinputnotallowed", "fixtureusageerror",
                          "no_local_evidence", "llm_unavailable")
    if status == "unavailable":
        return "unavailable"
    if status == "timeout":
        return "timed_out"
    if status == "abstained" or any(m in blob for m in abstention_markers):
        return "abstained"
    if status in {"failed", "error"}:
        return "errored"
    if status in {"ok", "partial"} and (result.get("answer") or "").strip():
        return "answered"
    return "errored"


def _behavior_match(expected: str, outcome: str, answer: str) -> Any:
    """Pipeline-integrity check of the pilot's declared expected behaviour.

    This is NOT a correctness grade. ``None`` means the behaviour is not
    objectively checkable here (expert/rubric pending).
    """
    if not expected:
        return None
    text = (answer or "").lower()
    if expected == "typed_abstention_MISSING_SCIENTIFIC_INPUT":
        return outcome == "abstained"
    if expected == "resolved_reviewed_human_accession":
        return ("o60885" in text) or (outcome == "answered" and "brd4" in text)
    return None


def _load_pilot_cases() -> List[Dict[str, Any]]:
    out = []
    for p in sorted(PILOT_DIR.glob("*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def _task_input(pilot: Dict[str, Any]):
    from benchmark_runner.runner import TaskInput
    case_path = CASES_DIR / f"{pilot['source_task']}.json"
    task = TaskInput.from_case(case_path)
    task.raw["pilot_id"] = pilot["pilot_id"]
    task.raw["expected_behavior"] = pilot.get("expected_behavior", "")
    return task


def main() -> int:
    os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--systems", default="S1,S2,S3,S4")
    ap.add_argument("--online", action="store_true", help="permit network retrieval")
    ap.add_argument("--replicates", type=int, default=1)
    ap.add_argument("--run-id", default="")
    ap.add_argument("--resume", type=Path, default=None,
                    help="resume an existing run dir (skips completed (case,system,rep))")
    ap.add_argument("--timeout-s", type=int, default=900)
    args = ap.parse_args()

    if args.resume:
        run_dir = args.resume
    else:
        rid = args.run_id or datetime.now(timezone.utc).strftime("gateC_4sys_%Y%m%dT%H%M%SZ")
        run_dir = args.out_dir / rid
        if run_dir.exists():
            print(f"refusing to overwrite existing run: {run_dir}", file=sys.stderr)
            return 2
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)
    (run_dir / "traces").mkdir(parents=True, exist_ok=True)

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    pilots = _load_pilot_cases()
    rows: List[Dict[str, Any]] = []

    manifest = {
        "run_id": run_dir.name,
        "schema": "gateC.four_system_run.v1",
        "git": _git(),
        "python": platform.python_version(),
        "host": socket.gethostname(),
        "execution_mode": os.environ.get("PROTACXTEND_EXECUTION_MODE", ""),
        "online": args.online,
        "systems": systems,
        "n_pilot_cases": len(pilots),
        "replicates": args.replicates,
        "max_infra_retries": MAX_INFRA_RETRIES,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "gold_status": "PENDING_INDEPENDENT_REVIEW",
        "score_note": "No correctness score: eligible gold is pending independent adjudication.",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    for pilot in pilots:
        task = _task_input(pilot)
        for key in systems:
            name, _mod, _cls = SYSTEMS[key]
            for rep in range(1, args.replicates + 1):
                result_file = run_dir / "raw" / f"{key}_{task.task_id}_r{rep}.json"
                if args.resume and result_file.exists():
                    rows.append(json.loads(result_file.read_text(encoding="utf-8")))
                    continue
                ctx = {"online": args.online, "artifact_dir": str(run_dir / "raw"),
                       "timeout_s": args.timeout_s}
                started = datetime.now(timezone.utc).isoformat()
                attempts = 0
                outcome = ""
                result: Dict[str, Any] = {}
                last_error = ""
                while attempts <= MAX_INFRA_RETRIES:
                    attempts += 1
                    try:
                        adapter = _adapter(key, allow_real=True)
                        result = adapter.execute(task, ctx)
                    except Exception as exc:  # noqa: BLE001
                        result = {"status": "failed", "answer": None,
                                  "error": f"{type(exc).__name__}: {exc}",
                                  "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                                  "tool_calls": 0, "latency_s": 0.0}
                    outcome = _classify(result)
                    last_error = str(result.get("error") or "")
                    if outcome not in {"errored", "timed_out"}:
                        break
                    # only transport/infra failures are retried; never abstentions
                    if "adapter" in last_error.lower() and attempts <= MAX_INFRA_RETRIES:
                        continue
                    if attempts > MAX_INFRA_RETRIES:
                        break
                    break

                row = {
                    "system_key": key,
                    "system_id": name,
                    "task_id": task.task_id,
                    "pilot_id": pilot["pilot_id"],
                    "capability": task.capability,
                    "replicate": rep,
                    "config_version": result.get("version") or "",
                    "provider": result.get("provider") or "",
                    "model": result.get("model") or "",
                    "started_at": started,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "status": result.get("status", ""),
                    "outcome_class": outcome,
                    "answer": (result.get("answer") or ""),
                    "evidence": result.get("retrieval") or result.get("tool_trace") or [],
                    "tool_trace": result.get("tool_trace") or [],
                    "tool_calls": result.get("tool_calls", 0),
                    "typed_abstention": outcome == "abstained",
                    "infra_error": last_error if outcome in {"errored", "timed_out", "unavailable"} else "",
                    "latency_s": result.get("latency_s", 0.0),
                    "tokens_in": result.get("tokens_in", 0),
                    "tokens_out": result.get("tokens_out", 0),
                    "cost_usd": result.get("cost_usd", 0.0),
                    # Telemetry honesty: Biomni's real go() interface exposes no
                    # token usage, so its cost is unavailable (never zero-filled).
                    "tokens_available": key != "S4",
                    "cost_available": key != "S4",
                    "cost_source": ("published_rate:deepseek usd/1M in=0.14 out=0.28"
                                    if key != "S4" else "not_reported_by_biomni"),
                    "attempts": attempts,
                    "expected_behavior": pilot.get("expected_behavior", ""),
                    "expected_behavior_met": _behavior_match(
                        pilot.get("expected_behavior", ""), outcome, result.get("answer") or ""),
                    "raw_file": str(result_file.relative_to(run_dir)),
                }
                result_file.write_text(json.dumps({"row": row, "raw": result}, indent=1, default=str),
                                       encoding="utf-8")
                (run_dir / "traces" / f"{key}_{task.task_id}_r{rep}.json").write_text(
                    json.dumps(result.get("llm_log") or {}, indent=1, default=str), encoding="utf-8")
                rows.append(row)
                print(f"[{key} {name}] {task.task_id} r{rep}: {outcome} "
                      f"({result.get('latency_s', 0)}s, {attempts} attempt)")

    _write_results(run_dir, rows, manifest)
    return 0


def _write_results(run_dir: Path, rows: List[Dict[str, Any]], manifest: Dict[str, Any]) -> None:
    import csv
    # CSV
    cols = ["system_key", "system_id", "task_id", "pilot_id", "capability", "replicate",
            "status", "outcome_class", "tool_calls", "typed_abstention", "latency_s",
            "tokens_in", "tokens_out", "tokens_available", "cost_usd", "cost_available",
            "cost_source", "attempts", "infra_error",
            "expected_behavior", "expected_behavior_met", "raw_file"]
    with (run_dir / "task_level_results.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    # Parquet
    try:
        import pandas as pd
        pd.DataFrame(rows).to_parquet(run_dir / "task_level_results.parquet", index=False)
    except Exception as exc:  # noqa: BLE001
        (run_dir / "PARQUET_ERROR.txt").write_text(str(exc), encoding="utf-8")

    # Summary + report
    from collections import Counter
    by_system = {}
    for key in sorted({r["system_key"] for r in rows}):
        sub = [r for r in rows if r["system_key"] == key]
        by_system[key] = {
            "n": len(sub),
            "outcomes": dict(Counter(r["outcome_class"] for r in sub)),
            "answered": sum(1 for r in sub if r["outcome_class"] == "answered"),
            "abstained": sum(1 for r in sub if r["outcome_class"] == "abstained"),
            "errored": sum(1 for r in sub if r["outcome_class"] == "errored"),
            "timed_out": sum(1 for r in sub if r["outcome_class"] == "timed_out"),
            "unavailable": sum(1 for r in sub if r["outcome_class"] == "unavailable"),
            "total_cost_usd": round(sum(r["cost_usd"] or 0 for r in sub), 6),
            "mean_latency_s": round(sum(r["latency_s"] or 0 for r in sub) / max(1, len(sub)), 3),
        }
    summary = {"run_id": run_dir.name, "n_rows": len(rows), "by_system": by_system,
               "gold_status": "PENDING_INDEPENDENT_REVIEW",
               "correctness": "NOT_SCORED (eligible gold pending)"}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    lines = [f"# Gate-C four-system pilot — {run_dir.name}", "",
             "Execution/validation evidence only. **No correctness score** — eligible gold is "
             "`PENDING_INDEPENDENT_REVIEW`.", "",
             f"- git: `{manifest['git']['commit'][:9]}` (dirty={manifest['git']['dirty']})",
             f"- online retrieval: {manifest['online']}",
             f"- rows: {len(rows)}", "",
             "## Outcomes by system", "",
             "| system | n | answered | abstained | errored | timed_out | unavailable | cost USD | mean latency s |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for key, s in by_system.items():
        lines.append(f"| {key} | {s['n']} | {s['answered']} | {s['abstained']} | {s['errored']} | "
                     f"{s['timed_out']} | {s['unavailable']} | {s['total_cost_usd']} | {s['mean_latency_s']} |")
    lines += ["", "## Per-run", "", "| system | task | outcome | behavior_met | tool_calls | latency s | attempts |",
              "|---|---|---|---|---:|---:|---:|"]
    for r in sorted(rows, key=lambda x: (x["system_key"], x["task_id"])):
        lines.append(f"| {r['system_key']} | {r['task_id']} | {r['outcome_class']} | "
                     f"{r.get('expected_behavior_met')} | "
                     f"{r['tool_calls']} | {r['latency_s']} | {r['attempts']} |")
    lines += ["", "## Not established by this run", "",
              "- Correctness/accuracy (gold pending).",
              "- Superiority of any system (4-case smoke, not a powered study).",
              "- Scientific validity of any answer.",
              "- S4 resource-matching to S1–S3 (declared difference: Biomni uses native tools/data lake)."]
    (run_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
