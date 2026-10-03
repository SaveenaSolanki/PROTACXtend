#!/usr/bin/env python
"""Repair demonstration, code freeze, and held-out rerun for the closed-48 suite.

Order of operations (matching the requested sequence):

1. Run the repaired, structured path on development cases for each capability
   and one justified abstention.
2. Freeze the code: write a manifest with the git commit, worktree status and
   SHA-256 of every repaired module, plus the route definitions.
3. Rerun the held-out (blind + validation) cases at the matched 120 s budget on
   the frozen path and compare outcomes with the locked original run.
4. Write the paired/diagnostic CSV and square plots. **No scientific score is
   computed** (gold is still pending).

Usage::

    python scripts/repair_closed48.py --workers 8
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from protacxtend.agents.graph import CAPABILITY_NODES  # noqa: E402
from protacxtend.validation.closure_figures import (  # noqa: E402
    apply_style,
    save_square,
    style_axes,
)

CASES = ROOT / "benchmark" / "cases"
SPLITS = ROOT / "benchmark" / "gateC" / "splits.json"
LOCKED = ROOT / "benchmark_results" / "closed48" / "closed48_locked"
OUT = ROOT / "benchmark_results" / "closed48" / "repaired_frozen"

REPAIRED_MODULES = [
    "protacxtend/agents/binder_agent.py",
    "protacxtend/agents/graph.py",
    "protacxtend/agents/supervisor_agent.py",
    "protacxtend/agents/design_planner_agent.py",
    "protacxtend/agents/structured_run.py",
]

#: Complete-run demonstration: development cases for K/R/D and, because all 12
#: DISCOVER cases are held-out, one held-out DISCOVER experiment-plan case.
DEMO_COMPLETE = ["KNOW-04", "REASON-09", "DESIGN-02", "DISCOVER-03"]
#: A genuinely justified abstention: the ranking task's supplied "table"
#: describes columns but contains no candidate rows.
DEMO_ABSTAIN = ["DISCOVER-01"]


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT),
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return ""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_case(task_id: str) -> dict[str, Any]:
    return json.loads((CASES / f"{task_id}.json").read_text(encoding="utf-8"))


def _worker(task_id: str) -> dict[str, Any]:
    from protacxtend.agents.structured_run import run_case

    case = _load_case(task_id)
    return run_case(case, capability=case.get("capability", ""), budget_s=120.0)


def freeze_manifest() -> dict[str, Any]:
    return {
        "schema": "closed48.repaired_freeze.v1",
        "frozen": True,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git(["rev-parse", "HEAD"]),
        "git_status": _git(["status", "--short"]).splitlines(),
        "modules": {m: _sha256(ROOT / m) for m in REPAIRED_MODULES if (ROOT / m).exists()},
        "routes": CAPABILITY_NODES,
        "budget_s": 120,
        "note": "No correctness scoring. Gold remains PENDING_INDEPENDENT_REVIEW.",
    }


def run_demo() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task_id in DEMO_COMPLETE + DEMO_ABSTAIN:
        result = _worker(task_id)
        result["demo_role"] = "justified_abstention" if task_id in DEMO_ABSTAIN else "complete"
        rows.append(result)
    return rows


def run_heldout(case_ids: list[str], workers: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_worker, cid): cid for cid in case_ids}
        for fut in as_completed(futures):
            rows.append(fut.result())
    rows.sort(key=lambda r: r["case_id"])
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _plot_comparison(original: dict[str, str], repaired: list[dict[str, Any]], out: Path) -> None:
    outcomes = ["completed", "abstained", "timeout", "failed"]
    colors = {"completed": "#009E73", "abstained": "#F0E442", "timeout": "#CC79A7", "failed": "#D55E00"}
    orig = Counter(original.values())
    new = Counter(r["outcome"] for r in repaired)
    apply_style()
    fig, ax = plt.subplots()
    width = 0.6
    bottom = np.zeros(2)
    for oc in outcomes:
        vals = np.array([orig.get(oc, 0), new.get(oc, 0)], dtype=float)
        if not vals.any():
            continue
        ax.bar(["locked original", "repaired"], vals, width, bottom=bottom, label=oc, color=colors[oc])
        bottom += vals
    for i, total in enumerate(bottom):
        ax.text(i, total + 0.5, f"n={int(total)}", ha="center", fontsize=9)
    style_axes(ax, xlabel="Run", ylabel="Held-out cases (n = 32)",
               title="Held-out outcomes before/after repair (120 s budget)")
    ax.legend(fontsize=8, ncol=2, frameon=False)
    save_square(fig, out / "fig_repair_heldout.png")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out-dir", type=Path, default=OUT)
    args = parser.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    splits = json.loads(SPLITS.read_text(encoding="utf-8"))["assignment"]
    heldout = [k for k, v in splits.items() if v != "development"]

    manifest = freeze_manifest()
    (out / "FREEZE_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    demo = run_demo()
    (out / "demo_results.json").write_text(json.dumps(demo, indent=2, default=str), encoding="utf-8")
    _write_csv(out / "demo_results.csv", demo)

    repaired = run_heldout(heldout, args.workers)
    (out / "heldout_results.json").write_text(json.dumps(repaired, indent=2, default=str), encoding="utf-8")
    _write_csv(out / "heldout_results.csv", repaired)

    # Original locked outcomes for the same held-out cases.
    preds = [json.loads(l) for l in (LOCKED / "predictions.jsonl").read_text().splitlines() if l.strip()]
    original = {p["case_id"]: p["outcome"] for p in preds if p["arm"] == "protacxtend" and p["case_id"] in heldout}

    _plot_comparison(original, repaired, out)

    demo_ok = [r["case_id"] for r in demo if r.get("demo_role") == "complete" and r["outcome"] == "completed"]
    print(f"frozen: {manifest['frozen']} git={manifest['git_commit'][:10]}")
    print(f"demo complete: {demo_ok}")
    print(f"demo justified abstention: {[r['case_id'] for r in demo if r.get('demo_role')=='justified_abstention']}")
    print(f"held-out repaired: {dict(Counter(r['outcome'] for r in repaired))}")
    print(f"held-out original: {dict(Counter(original.values()))}")
    print(f"artifacts: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
