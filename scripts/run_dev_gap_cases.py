#!/usr/bin/env python
"""Run the repaired structured path on the DEVELOPMENT cases where direct_tool
succeeded but the original agent failed (E3 gap closure on visible cases)."""
from __future__ import annotations
import argparse, json, os, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
CASES = ROOT / "benchmark" / "cases"
OUT = ROOT / "results" / "closure"

def _worker(cid):
    from protacxtend.agents.structured_run import run_case
    case = json.loads((CASES / f"{cid}.json").read_text(encoding="utf-8"))
    return run_case(case, capability=case.get("capability", ""), budget_s=120.0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True, help="comma-separated case ids")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    ids = [c for c in args.cases.split(",") if c]
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(_worker, c): c for c in ids}
        for f in as_completed(futs):
            rows.append(f.result())
    rows.sort(key=lambda r: r["case_id"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dev_gap_repaired.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    import collections
    print("dev gap repaired:", dict(collections.Counter(r["outcome"] for r in rows)))
    for r in rows:
        print(f"  {r['case_id']:12} {r['outcome']:10} {r.get('stop_reason') or r.get('error','')[:60]}")

if __name__ == "__main__":
    main()
