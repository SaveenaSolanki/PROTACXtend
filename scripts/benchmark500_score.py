#!/usr/bin/env python
"""Score a benchmark500 run on objective dimensions and write results artifacts.

Only dimensions that are objectively checkable from the run are scored. Every
gold-dependent dimension (scientific/mechanistic/quantitative correctness,
uncertainty calibration, final decision quality, future-outcome match, tool
selection correctness) is emitted as null with status `pending_adjudication` —
never invented.

Outputs under benchmark500/results/<run_id>/:
  scores.json               per-case objective scores + aggregates
  scores_by_domain.csv
  scores_by_difficulty.csv
  scores_by_split.csv
And under benchmark500/:
  PROTACXtend_500_Results.xlsx      (per-task + summary sheets)
  ADJUDICATION_QUEUE.xlsx           (blank expert-scoring sheet with evidence)
  REPORT.md
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmark500" / "results"
CASES = ROOT / "benchmark500" / "cases"

# Dimensions that require human adjudication (must be curated against evidence).
ADJUDICATED_DIMENSIONS = [
    "Scientific_Correctness_0_5", "Temporal_Compliance_0_5", "Evidence_Grounding_0_5",
    "Tool_Selection_0_5", "Mechanistic_Correctness_0_5", "Quantitative_Correctness_0_5",
    "Uncertainty_Calibration_0_5", "Final_Decision_Quality_0_5", "Future_Outcome_Match_0_5",
]


def _evidence_score(ev: dict) -> tuple[int, int]:
    items = 0
    if ev.get("target"):
        items += 1
    if ev.get("structures"):
        items += 1
    if ev.get("e3_ligands", 0) > 0:
        items += 1
    if ev.get("binders", 0) > 0:
        items += 1
    if ev.get("warheads", 0) > 0:
        items += 1
    return min(5, items), items


def score_case(p: dict) -> dict:
    ev = p.get("evidence") or {}
    e_items = 0
    if p["status"] == "executed":
        tool_exec = 5 if p.get("valid_output") else 3
    elif p["status"] == "abstained" and p.get("failure_code"):
        tool_exec = 2  # typed abstenion is a valid, non-fabricated outcome
    else:
        tool_exec = 0
    ev_score, e_items = _evidence_score(ev)
    reproducibility = 5 if p.get("run_id") and p.get("execution_mode") else 3
    return {
        "case_id": p["case_id"],
        "suite": p["suite"],
        "domain": p["domain"],
        "difficulty_level": p["difficulty_level"],
        "split": p.get("split", ""),
        "run_status": p["status"],
        "abstention_reason": p.get("abstention_reason", ""),
        "failure_code": p.get("failure_code", ""),
        "capability_attempted": p.get("capability_attempted", ""),
        "tool_executed": bool(p.get("tool_executed")),
        "valid_output": bool(p.get("valid_output")),
        "evidence_items": e_items,
        # ── objective, non-gold scores (0-5) ──
        "Tool_Execution_0_5": tool_exec,
        "Reproducibility_0_5": reproducibility,
        "Evidence_Availability_0_5": ev_score,
        # ── gold-dependent: pending ──
        **{d: None for d in ADJUDICATED_DIMENSIONS},
        "adjudication_status": "pending_adjudication",
    }


def _agg(rows: list[dict], key: str) -> list[dict]:
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    out = []
    for k, g in sorted(groups.items(), key=lambda kv: str(kv[0])):
        n = len(g)
        out.append({
            key: k,
            "n": n,
            "executed": sum(1 for r in g if r["run_status"] == "executed"),
            "abstained": sum(1 for r in g if r["run_status"] == "abstained"),
            "failed": sum(1 for r in g if r["run_status"] == "failed"),
            "execution_rate": round(sum(1 for r in g if r["run_status"] == "executed") / n, 4),
            "abstention_rate": round(sum(1 for r in g if r["run_status"] == "abstained") / n, 4),
            "mean_tool_execution": round(statistics.mean(r["Tool_Execution_0_5"] for r in g), 3),
            "mean_evidence_availability": round(statistics.mean(r["Evidence_Availability_0_5"] for r in g), 3),
            "mean_reproducibility": round(statistics.mean(r["Reproducibility_0_5"] for r in g), 3),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    run_dir = RESULTS / args.run_id
    preds = [json.loads(l) for l in (run_dir / "predictions.jsonl").read_text().splitlines() if l.strip()]
    cases = {}
    for suite in ("temporal_500", "general_500"):
        for l in (CASES / f"{suite}.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                c = json.loads(l)
                cases[c["case_id"]] = c
    for p in preds:
        p["split"] = cases.get(p["case_id"], {}).get("split", "")

    rows = [score_case(p) for p in preds]
    by_domain = _agg(rows, "domain")
    by_diff = _agg(rows, "difficulty_level")
    by_split = _agg(rows, "split")
    by_suite = _agg(rows, "suite")

    funnel = {
        "planned": len(rows),
        "eligible_uncurated": len(rows),
        "executed": sum(1 for r in rows if r["run_status"] == "executed"),
        "valid_output": sum(1 for r in rows if r["valid_output"]),
        "typed_abstention": sum(1 for r in rows if r["run_status"] == "abstained" and r["failure_code"]),
        "adjudicated": 0,
        "gold_curated": 0,
    }
    scores = {
        "run_id": args.run_id,
        "schema_version": "benchmark500.scores.v1",
        "n_cases": len(rows),
        "funnel": funnel,
        "objective_dimensions": ["Tool_Execution_0_5", "Reproducibility_0_5", "Evidence_Availability_0_5"],
        "adjudicated_dimensions": ADJUDICATED_DIMENSIONS,
        "aggregates": {"by_suite": by_suite, "by_domain": by_domain,
                       "by_difficulty": by_diff, "by_split": by_split},
        "limitations": [
            "Gold answers are uncurated in both source workbooks; no scientific-correctness score can be computed.",
            "No LLM provider is authenticated; L4–L6 reasoning tasks cannot be answered.",
            "Temporal-suite runs have no frozen pre-cutoff corpus; temporal compliance is unverifiable.",
            "Execution here measures capability/provenance readiness, not therapeutic correctness.",
        ],
    }
    (run_dir / "scores.json").write_text(json.dumps({"summary": scores, "cases": rows}, indent=2), encoding="utf-8")
    for name, data in (("scores_by_domain.csv", by_domain), ("scores_by_difficulty.csv", by_diff),
                       ("scores_by_split.csv", by_split), ("scores_by_suite.csv", by_suite)):
        with (run_dir / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            w.writeheader(); w.writerows(data)
    print(json.dumps(scores["funnel"], indent=2))
    print("by_suite:", json.dumps(by_suite, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
