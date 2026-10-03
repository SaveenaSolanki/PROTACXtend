#!/usr/bin/env python
"""Run the matched comparator baselines over the 48 cases (G04).

Arms: retrieval_only, tool_only, llm_only (local Ollama). Writes
benchmark_results/first_aggregate/adapters_predictions.jsonl. Every failure is
recorded (status + error), never dropped.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from benchmark_runner.adapters import ADAPTERS  # noqa: E402

CASES = ROOT / "benchmark/cases"
OUT = ROOT / "benchmark_results/first_aggregate"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="retrieval_only,tool_only,llm_only")
    ap.add_argument("--model", default="deepseek-r1:14b")
    ap.add_argument("--tasks", default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    wanted = {t.strip() for t in args.tasks.split(",") if t.strip()}

    cases = []
    for f in sorted(CASES.glob("*.json")):
        d = json.loads(f.read_text())
        if wanted and d["task_id"] not in wanted:
            continue
        cases.append(d)
    if args.limit:
        cases = cases[: args.limit]

    OUT.mkdir(parents=True, exist_ok=True)
    out_file = OUT / "adapters_predictions.jsonl"
    rows: list[dict] = []
    for case in cases:
        q = case.get("scientific_question", "")
        for arm in arms:
            fn = ADAPTERS[arm]
            t0 = time.monotonic()
            try:
                if arm == "llm_only":
                    res = fn(q, model=args.model)
                else:
                    res = fn(q)
            except Exception as exc:  # noqa: BLE001
                res = {"answer": "", "status": "engine_error", "error": str(exc)[:200]}
            row = {"case_id": case["task_id"], "capability": case.get("capability", ""),
                   "arm": arm, "answer": res.get("answer", ""), "outcome": res.get("status", ""),
                   "latency_s": res.get("latency_s", round(time.monotonic() - t0, 2)),
                   "error": res.get("error", ""), "correctness": "UNSCORED"}
            rows.append(row)
            print(f"[{arm}] {row['case_id']}: {row['outcome']} {str(row['answer'])[:70]!r}", flush=True)
            out_file.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} predictions -> {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
