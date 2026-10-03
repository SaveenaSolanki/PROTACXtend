#!/usr/bin/env python
"""Build the versioned local evidence snapshot for pilot KNOW/REASON queries.

Runs the gold-free retrieval path LIVE and persists raw, source-attributed
records into ``data/evidence_snapshots/evidence-snapshot-v1/<tool>/<hash>.json``.
Later offline runs serve these records and label them ``snapshot=True`` with
schema version + fetched_at + live source URL. Nothing here touches ground truth.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from protacxtend.evidence.snapshot import SNAPSHOT_ROOT, save_snapshot  # noqa: E402
from protacxtend.evidence.trace import _TOOLS, build_queries, _normalise_records  # noqa: E402
from protacxtend.agentic.registry import execute_tool  # noqa: E402


def _capture(tool: str, query: str, params: dict) -> tuple:
    res = execute_tool(tool, params)
    recs = _normalise_records(tool, res.data or {}) if res.status.value == "success" else []
    src = {"kind": "live_" + tool, "url": ""}
    return recs, res.status.value, res.summary[:160]


def main() -> int:
    cases_dir = ROOT / "benchmark" / "cases"
    rows = []
    for path in sorted(cases_dir.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        cap = case.get("capability", "")
        if cap not in _TOOLS:
            continue
        q = case.get("scientific_question") or ""
        for query in build_queries(cap, q):
            for tool in _TOOLS[cap]:
                from protacxtend.evidence.trace import _params_for
                recs, status, summary = _capture(tool, query, _params_for(tool, query, cap))
                # Save even zero-hit successes so offline replay can distinguish
                # "snapshot: 0 hits" from "snapshot missing" (never 'unavailable').
                if status == "success":
                    spath = save_snapshot(tool, query, recs, {"kind": "live_" + tool})
                    rows.append({"task": case["task_id"], "tool": tool, "query": query[:60],
                                 "records": len(recs), "snapshot": str(Path(spath).relative_to(ROOT))})
                else:
                    rows.append({"task": case["task_id"], "tool": tool, "query": query[:60],
                                 "records": 0, "status": status, "snapshot": ""})
    print(f"snapshot root: {SNAPSHOT_ROOT}")
    for r in rows:
        print(f"  {r['task']:<12} {r['tool']:<18} recs={r.get('records', 0):<3} {r.get('status','')} {r.get('snapshot','')}")
    Path(ROOT / "outputs" / "evidence_snapshot_build.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())