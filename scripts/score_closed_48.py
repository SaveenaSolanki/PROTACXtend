#!/usr/bin/env python
"""Gold-gated scoring for the closed 48-case benchmark.

Scoring is impossible until a reviewer-approved gold file exists. Default path:

    benchmark/gateC/reviewed_gold/consensus.json

It must contain::

    {
      "approved": true,
      "approved_by": ["reviewer-A", "reviewer-B"],
      "adjudicator": "reviewer-C",
      "approved_at": "2026-...Z",
      "gold": {
        "KNOW-01": {"type": "exact", "expected_answer": "...",
                    "mandatory_answer_elements": ["O60885"],
                    "acceptable_alternatives": [], "answerability": "answerable"},
        ...
      }
    }

Without an approved file this script writes a `pending_adjudication` record
and exits 0. It never falls back to the self-derived overlays.

With approval it grades each arm, computes per-case correctness, abstention
correctness, and a paired bootstrap CI versus PROTACXtend grouped by
capability, then writes `scores.json`, `scores_by_case.csv` and
`scores_summary.json`.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark_runner.grader import grade_answer  # noqa: E402

DEFAULT_GOLD = ROOT / "benchmark" / "gateC" / "reviewed_gold" / "consensus.json"
RUBRIC_TYPES = {"design_rubric", "mechanistic_rubric"}


def load_predictions(run_dir: Path) -> List[Dict[str, Any]]:
    path = run_dir / "predictions.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_gold(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("approved"):
        return None
    return data


def correctness_for(pred: Dict[str, Any], gold: Dict[str, Any]) -> Dict[str, Any]:
    task_id = pred["case_id"]
    entry = gold.get(task_id)
    if not entry:
        return {"status": "gold_missing", "score": None}
    if str(entry.get("answerability", "answerable")).lower() in {"unanswerable", "no_go", "insufficient"}:
        ok = pred.get("outcome") in {"abstained", "refused", "timeout"}
        return {"status": "abstention", "score": 1.0 if ok else 0.0,
                "expected": "abstain", "observed": pred.get("outcome")}
    gtype = str(entry.get("type", "")).lower()
    if gtype in RUBRIC_TYPES:
        return {"status": "requires_expert_review", "score": None,
                "expected": "rubric", "observed": pred.get("outcome")}
    rec = grade_answer(task_id, pred.get("answer", ""), gt=entry, use_overlay=False)
    return {"status": rec.get("status"), "score": rec.get("score"),
            "expected": entry.get("expected_answer", ""),
            "observed": pred.get("outcome")}


def bootstrap_diff(a: List[float], b: List[float], n: int = 10000, seed: int = 42) -> Dict[str, Any]:
    if not a or len(a) != len(b):
        return {"n": 0, "mean_diff": None, "ci95": [None, None]}
    rng = random.Random(seed)
    diffs = [x - y for x, y in zip(a, b)]
    means = []
    for _ in range(n):
        means.append(sum(rng.choice(diffs) for _ in diffs) / len(diffs))
    means.sort()
    return {
        "n": len(diffs),
        "mean_diff": round(sum(diffs) / len(diffs), 4),
        "ci95": [round(means[int(0.025 * n)], 4), round(means[int(0.975 * n)], 4)],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    ap.add_argument("--baseline-arm", default="protacxtend")
    args = ap.parse_args()

    preds = load_predictions(args.run_dir)
    gold_doc = load_gold(args.gold)

    if gold_doc is None:
        pending = {
            "schema_version": "closed48.scores.v1",
            "run_dir": str(args.run_dir),
            "gold_path": str(args.gold),
            "status": "pending_adjudication",
            "reason": ("No reviewer-approved gold file. The 29 reviewer decisions and all 48 "
                       "gold adjudications are PENDING. No correctness is computed."),
            "benchmark_score": None,
            "n_predictions": len(preds),
            "cases": [{"case_id": p["case_id"], "arm": p["arm"],
                       "correctness": "PENDING_INDEPENDENT_GOLD"} for p in preds],
        }
        (args.run_dir / "scores.json").write_text(json.dumps(pending, indent=2), encoding="utf-8")
        print("PENDING: no reviewer-approved gold. Wrote pending_adjudication record; no score.")
        return 0

    gold = gold_doc["gold"]
    scores: Dict[str, Dict[str, Any]] = defaultdict(dict)
    for p in preds:
        scores[p["case_id"]][p["arm"]] = correctness_for(p, gold)

    arms = sorted({p["arm"] for p in preds})
    per_case_rows = []
    for cid in sorted(scores):
        row = {"case_id": cid}
        for arm in arms:
            rec = scores[cid].get(arm, {})
            row[f"{arm}_score"] = rec.get("score")
            row[f"{arm}_status"] = rec.get("status")
        per_case_rows.append(row)

    summary: Dict[str, Any] = {"n_cases": len(scores), "arms": {}}
    for arm in arms:
        vals = [scores[c][arm]["score"] for c in scores
                if arm in scores[c] and scores[c][arm].get("score") is not None]
        summary["arms"][arm] = {
            "n_scored": len(vals),
            "mean_correctness": round(sum(vals) / len(vals), 4) if vals else None,
        }

    # paired bootstrap vs the baseline arm, grouped by capability
    cap_of: Dict[str, str] = {}
    for p in preds:
        if p.get("capability"):
            cap_of[p["case_id"]] = p["capability"]
    paired: Dict[str, Any] = {}
    for arm in arms:
        if arm == args.baseline_arm:
            continue
        by_cap: Dict[str, List[List[float]]] = defaultdict(lambda: [[], []])
        for cid, recs in scores.items():
            base = recs.get(args.baseline_arm, {}).get("score")
            other = recs.get(arm, {}).get("score")
            if base is None or other is None:
                continue
            by_cap[cap_of.get(cid, "?")][0].append(base)
            by_cap[cap_of.get(cid, "?")][1].append(other)
        paired[arm] = {cap: bootstrap_diff(a, b) for cap, (a, b) in by_cap.items()}

    output = {
        "schema_version": "closed48.scores.v1",
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(args.run_dir),
        "gold_path": str(args.gold),
        "approved_by": gold_doc.get("approved_by"),
        "adjudicator": gold_doc.get("adjudicator"),
        "status": "scored_against_approved_gold",
        "summary": summary,
        "paired_vs_baseline": paired,
        "cases": per_case_rows,
    }
    (args.run_dir / "scores.json").write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    (args.run_dir / "scores_summary.json").write_text(
        json.dumps({"summary": summary, "paired_vs_baseline": paired}, indent=2, default=str),
        encoding="utf-8")
    with (args.run_dir / "scores_by_case.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per_case_rows[0].keys()) if per_case_rows else ["case_id"])
        w.writeheader()
        w.writerows(per_case_rows)
    print(json.dumps({"summary": summary, "paired_vs_baseline": paired}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
