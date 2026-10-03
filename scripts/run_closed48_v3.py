#!/usr/bin/env python
"""Frozen closed-48 v3 benchmark with three seeds and reproducibility stats.

Produces under ``benchmark_results/closed48_v3/``:
  * ``results.jsonl``            — one record per (case, seed)
  * ``results_table.csv``        — per-case median/IQR/p95/max latency + states
  * ``reproducibility_results.csv`` — seed-to-seed stability
  * ``claim_evidence_matrix.csv``   — each claim mapped to its evidence + boundary

Usage::

    python scripts/run_closed48_v3.py --seeds 0,1,2 --workers 10 --budget 150
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = ROOT / "benchmark" / "cases"
OUT = ROOT / "benchmark_results" / "closed48_v3"


def _worker(task_id: str, seed: int, budget: float) -> dict[str, Any]:
    import os

    os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")
    from protacxtend.agents.structured_run import run_case

    case = json.loads((CASES / f"{task_id}.json").read_text(encoding="utf-8"))
    return run_case(case, capability=case.get("capability", ""), offline=True,
                    budget_s=budget, seed=seed)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def _iqr(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.quantiles(values, n=4)[2] - statistics.quantiles(values, n=4)[0]


def _claim_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for r in records:
        answer = (r.get("answer") or "")[:300]
        if not answer:
            continue
        state = r.get("scientific_state", "")
        sources = sorted({e.get("source", "") for e in (r.get("evidence") or []) if e.get("source")})
        claim_type = {
            "supported_answer": "evidence_backed_fact",
            "conditional_hypothesis": "conditional_hypothesis",
            "valid_candidate": "source_backed_reference",
            "design_brief": "design_brief",
            "justified_no_go": "refusal",
        }.get(state, "unknown")
        # Boundary checks: never present a hypothesis/reference as measured.
        boundary = []
        low = answer.lower()
        asserted_measurement = bool(
            re.search(r"(dc50|dmax|ic50|ki|kd)\s*[=:]\s*\d", low)
            or "confirmed experimentally" in low
            or "measured experimentally" in low
        )
        if claim_type == "conditional_hypothesis" and asserted_measurement:
            boundary.append("hypothesis_labelled_as_measured")
        if claim_type == "source_backed_reference" and "newly discovered" in low:
            boundary.append("reference_labelled_as_new")
        if claim_type == "design_brief" and "final protac" in low:
            boundary.append("design_brief_labelled_final")
        rows.append({
            "case_id": r["case_id"], "seed": r.get("seed", 0), "capability": r["capability"],
            "claim_type": claim_type, "scientific_state": state,
            "claim": answer, "n_evidence": len(r.get("evidence") or []),
            "sources": ";".join(sources), "evidence_backed": bool(r.get("evidence")),
            "boundary_respected": not boundary,
            "boundary_violations": ";".join(boundary),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--budget", type=float, default=150.0)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    case_ids = sorted(p.stem for p in CASES.glob("*.json") if not p.stem.startswith("_"))
    records: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(_worker, cid, seed, args.budget): (cid, seed)
                   for cid in case_ids for seed in seeds}
        for fut in as_completed(futures):
            records.append(fut.result())
    records.sort(key=lambda r: (r["case_id"], r.get("seed", 0)))

    with (out / "results.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, default=str) + "\n")

    # ── per-case latency + state table ────────────────────────────────
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_case[r["case_id"]].append(r)
    table_rows = []
    for cid in case_ids:
        rs = sorted(by_case[cid], key=lambda r: r.get("seed", 0))
        latencies = [r["elapsed_s"] for r in rs]
        states = [r["scientific_state"] for r in rs]
        table_rows.append({
            "case_id": cid, "capability": rs[0]["capability"],
            "n_seeds": len(rs),
            "state_seed0": states[0] if len(states) > 0 else "",
            "state_seed1": states[1] if len(states) > 1 else "",
            "state_seed2": states[2] if len(states) > 2 else "",
            "latency_median_s": round(statistics.median(latencies), 3),
            "latency_iqr_s": round(_iqr(latencies), 3),
            "latency_p95_s": round(_percentile(latencies, 0.95), 3),
            "latency_max_s": round(max(latencies), 3),
            "n_verified_candidates": max(r["n_verified_candidates"] for r in rs),
            "n_evidence": max(len(r.get("evidence") or []) for r in rs),
            "route_nodes": rs[0]["routed_nodes"],
            "scientific_state_median": Counter(states).most_common(1)[0][0] if states else "",
        })
    with (out / "results_table.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table_rows[0].keys()))
        w.writeheader()
        w.writerows(table_rows)

    # ── reproducibility ───────────────────────────────────────────────
    repro_rows = []
    for cid in case_ids:
        rs = sorted(by_case[cid], key=lambda r: r.get("seed", 0))
        states = [r["scientific_state"] for r in rs]
        verified = [r["n_verified_candidates"] for r in rs]
        candidates = [r["n_candidates"] for r in rs]
        brief = [r["n_design_brief_candidates"] for r in rs]
        # hash the emitted answer/state for a stable-output check
        hashes = [hashlib.sha256(
            json.dumps({"state": r["scientific_state"], "answer": r.get("answer", ""),
                        "verified": r["verified_candidate_smiles"]}, sort_keys=True).encode()
        ).hexdigest()[:12] for r in rs]
        repro_rows.append({
            "case_id": cid, "capability": rs[0]["capability"],
            "states": "|".join(states), "state_stable": len(set(states)) == 1,
            "verified_counts": "|".join(map(str, verified)),
            "verified_stable": len(set(verified)) == 1,
            "candidate_counts": "|".join(map(str, candidates)),
            "candidate_count_stable": len(set(candidates)) == 1,
            "design_brief_counts": "|".join(map(str, brief)),
            "output_hashes": "|".join(hashes), "output_stable": len(set(hashes)) == 1,
        })
    with (out / "reproducibility_results.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(repro_rows[0].keys()))
        w.writeheader()
        w.writerows(repro_rows)

    # ── claim/evidence matrix ─────────────────────────────────────────
    claim_rows = _claim_rows(records)
    with (out / "claim_evidence_matrix.csv").open("w", newline="", encoding="utf-8") as fh:
        if claim_rows:
            w = csv.DictWriter(fh, fieldnames=list(claim_rows[0].keys()))
            w.writeheader()
            w.writerows(claim_rows)

    # ── summary ───────────────────────────────────────────────────────
    lat = [r["elapsed_s"] for r in records]
    states = Counter(r["scientific_state"] for r in records)
    summary = {
        "n_records": len(records), "seeds": seeds,
        "latency_median_s": round(statistics.median(lat), 3),
        "latency_iqr_s": round(_iqr(lat), 3),
        "latency_p95_s": round(_percentile(lat, 0.95), 3),
        "latency_max_s": round(max(lat), 3),
        "states": dict(states),
        "state_stable_cases": sum(1 for r in repro_rows if r["state_stable"]),
        "output_stable_cases": sum(1 for r in repro_rows if r["output_stable"]),
        "evidence_complete_cases": sum(1 for r in table_rows if r["n_evidence"] > 0),
        "boundary_violations": sum(1 for r in claim_rows if not r["boundary_respected"]),
        "verified_candidates_total": sum(r["n_verified_candidates"] for r in table_rows),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out}/results.jsonl, results_table.csv, reproducibility_results.csv, "
          f"claim_evidence_matrix.csv, summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
