#!/usr/bin/env python
"""First scored aggregate against the machine-verified / rule-based gold.

Scores every arm in benchmark_results/closed48/closed48_locked plus the
comparator adapters in benchmark_results/first_aggregate against
benchmark/gold_machine_v1/machine_gold.json using the repository grader with
use_overlay=False (the self-derived overlays are never used).

Primary endpoint   : MACHINE_VERIFIED_EXTERNAL tasks (objective, externally checked)
Secondary endpoint : RULE_BASED_RUBRIC tasks (deterministic, pre-registered)
Excluded           : PENDING_HUMAN tasks (reported, not scored)

Writes benchmark_results/first_aggregate/{scores.json,aggregate.csv,predictions.jsonl,RESULTS.md}
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from benchmark_runner.grader import grade_answer  # noqa: E402

GOLD = ROOT / "benchmark/gold_machine_v1/machine_gold.json"
CLOSED = ROOT / "benchmark_results/closed48/closed48_locked/predictions.jsonl"
CLOSED_FIXED = ROOT / "benchmark_results/closed48/protacxtend_fixed/predictions.jsonl"
ADAPTERS = ROOT / "benchmark_results/first_aggregate/adapters_predictions.jsonl"
ADAPTERS_LLM = ROOT / "benchmark_results/first_aggregate/adapters_llm_know.jsonl"
OUT = ROOT / "benchmark_results/first_aggregate"
OUT.mkdir(parents=True, exist_ok=True)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def load_predictions() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if CLOSED.exists():
        for line in CLOSED.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("arm") == "protacxtend" and CLOSED_FIXED.exists():
                    continue  # superseded by the fixed capability-routed arm
                rows.append(row)
    if CLOSED_FIXED.exists():
        for line in CLOSED_FIXED.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    if ADAPTERS.exists():
        for line in ADAPTERS.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    if ADAPTERS_LLM.exists():
        for line in ADAPTERS_LLM.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main() -> int:
    gold_payload = json.loads(GOLD.read_text())
    gold = gold_payload["gold"]
    preds = load_predictions()
    scored: list[dict[str, Any]] = []
    for p in preds:
        tid = p["case_id"]
        g = gold.get(tid)
        if not g or g["gold_class"] == "PENDING_HUMAN":
            scored.append({**p, "gold_class": (g or {}).get("gold_class", "UNKNOWN"),
                           "score": None, "correct": None, "scored": False})
            continue
        rec = grade_answer(tid, p.get("answer") or "", gt=g, use_overlay=False)
        score = rec.get("score")
        threshold = g.get("threshold") or 0.5
        correct = (score is not None and score >= threshold)
        scored.append({**p, "gold_class": g["gold_class"], "score": score,
                       "threshold": threshold, "correct": bool(correct), "scored": True,
                       "grader_status": rec.get("status"), "missing": rec.get("dimensions", {}).get("missing_mandatory")
                       or rec.get("dimensions", {}).get("missing")})

    # aggregate by arm x gold_class
    by_arm: dict[str, dict[str, Any]] = {}
    for row in scored:
        arm = row["arm"]
        bucket = by_arm.setdefault(arm, {
            "arm": arm,
            "MACHINE_VERIFIED_EXTERNAL": {"n": 0, "correct": 0},
            "RULE_BASED_RUBRIC": {"n": 0, "correct": 0},
            "PENDING_HUMAN": {"n": 0, "correct": 0},
        })
        gc = row["gold_class"]
        bucket.setdefault(gc, {"n": 0, "correct": 0})
        bucket[gc]["n"] += 1
        if row.get("correct"):
            bucket[gc]["correct"] += 1

    aggregate = []
    for arm, bucket in sorted(by_arm.items()):
        for gc in ("MACHINE_VERIFIED_EXTERNAL", "RULE_BASED_RUBRIC", "PENDING_HUMAN"):
            b = bucket.get(gc, {"n": 0, "correct": 0})
            acc = (b["correct"] / b["n"]) if b["n"] else None
            lo, hi = wilson(b["correct"], b["n"]) if b["n"] else (None, None)
            aggregate.append({"arm": arm, "gold_class": gc, "n": b["n"],
                              "correct": b["correct"],
                              "accuracy": round(acc, 4) if acc is not None else None,
                              "wilson_lo": lo, "wilson_hi": hi})

    result = {
        "schema": "protacxtend.first_aggregate.v1",
        "gold": str(GOLD.relative_to(ROOT)),
        "gold_sha256": (ROOT / "benchmark/gold_machine_v1/machine_gold.sha256").read_text().strip(),
        "gold_counts": gold_payload["counts"],
        "note": ("Primary endpoint = MACHINE_VERIFIED_EXTERNAL (externally verified). "
                 "Secondary = RULE_BASED_RUBRIC. PENDING_HUMAN excluded and reported. "
                 "Not human adjudication."),
        "n_predictions": len(scored),
        "aggregate": aggregate,
    }
    (OUT / "scores.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (OUT / "predictions.jsonl").write_text("\n".join(json.dumps(r) for r in scored) + "\n", encoding="utf-8")
    with (OUT / "aggregate.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["arm", "gold_class", "n", "correct", "accuracy", "wilson_lo", "wilson_hi"])
        w.writeheader(); w.writerows(aggregate)

    lines = ["# First scored aggregate — 48-case governed benchmark", "",
             f"- gold: `{result['gold']}` (sha256 `{result['gold_sha256'][:16]}…`)",
             f"- gold classes: {gold_payload['counts']}",
             f"- predictions scored: {len(scored)}",
             "- **Primary endpoint**: MACHINE_VERIFIED_EXTERNAL (externally verified against UniProt/RCSB/Crossref/PubChem).",
             "- **Secondary endpoint**: RULE_BASED_RUBRIC (deterministic, pre-registered checklist).",
             "- **PENDING_HUMAN** tasks are excluded from both endpoints and reported for completeness.",
             "- This is machine-verified / rule-based gold, **not human adjudication**.", "",
             "| arm | gold class | n | correct | accuracy | 95% Wilson CI |",
             "|---|---|---|---|---|---|"]
    for a in aggregate:
        ci = f"[{a['wilson_lo']}, {a['wilson_hi']}]" if a["wilson_lo"] is not None else "—"
        lines.append(f"| {a['arm']} | {a['gold_class']} | {a['n']} | {a['correct']} | "
                     f"{a['accuracy'] if a['accuracy'] is not None else '—'} | {ci} |")
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(aggregate, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
