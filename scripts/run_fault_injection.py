#!/usr/bin/env python
"""Run the fault-injection scenarios and write the results CSV.

Output: ``benchmark_results/closed48_v3/fault_injection_results.csv``
Columns: scenario, kind, detected, recovered, fallback_used, abstained,
hallucinated_continuation, notes.

Usage::

    python scripts/run_fault_injection.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "benchmark_results" / "closed48_v3" / "fault_injection_results.csv"
FIELDS = ["scenario", "kind", "detected", "recovered", "fallback_used",
          "abstained", "hallucinated_continuation", "notes"]


def main() -> int:
    from protacxtend.runtime.fault_injection import all_scenarios, run_fault_scenario

    rows = [run_fault_scenario(sc) for sc in all_scenarios()]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} scenarios)")
    for r in rows:
        print(f"  {r['scenario']:22s} detect={r['detected']} recover={r['recovered']} "
              f"fallback={r['fallback_used']} abstain={r['abstained']} hallu={r['hallucinated_continuation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
