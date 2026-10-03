#!/usr/bin/env python
"""Phase-4 assessment rerun of the 48 closed cases on the structured path.

Runs every case through :func:`protacxtend.agents.structured_run.run_case`,
keeps the run separate from the locked and repaired runs, and reports
case-level entity correctness, question responsiveness, evidence support,
candidate chemical validity, appropriate abstention and latency.

It does **not** compute correctness against gold (gold is still pending); it
reports the auditable execution facts and the new scientific state.

Usage::

    python scripts/rerun_closed48_structured.py --workers 8 --budget 150
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = ROOT / "benchmark" / "cases"
LOCKED = ROOT / "benchmark_results" / "closed48" / "closed48_locked"
OUT_DEFAULT = ROOT / "benchmark_results" / "closed48" / "closed48_v2_structured"


def _worker(task_id: str, budget: float) -> dict[str, Any]:
    import os

    os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")
    from protacxtend.agents.structured_run import run_case

    case = json.loads((CASES / f"{task_id}.json").read_text(encoding="utf-8"))
    return run_case(case, capability=case.get("capability", ""), offline=True, budget_s=budget)


def _validity(smiles: str) -> str:
    try:
        from rdkit import Chem

        return "valid" if Chem.MolFromSmiles(smiles) else "invalid"
    except Exception:  # noqa: BLE001
        return "unchecked"


def _expected_target(case: dict[str, Any]) -> str:
    from protacxtend.agents.entity_resolution import resolve_entities

    return resolve_entities(case).get("target", "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--budget", type=float, default=150.0)
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    case_ids = sorted(p.stem for p in CASES.glob("*.json") if not p.stem.startswith("_"))
    rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(_worker, cid, args.budget): cid for cid in case_ids}
        for fut in as_completed(futures):
            rows.append(fut.result())
    rows.sort(key=lambda r: r["case_id"])

    # Preserve the full result JSON and a flat table.
    with (out / "results.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")

    flat = []
    for r in rows:
        case = json.loads((CASES / f"{r['case_id']}.json").read_text(encoding="utf-8"))
        expected = _expected_target(case)
        resolved = r["resolved_target"]["target_name"]
        entity_ok = (not expected and not resolved) or (expected and resolved.upper() == expected.upper())
        verified = r["verified_candidate_smiles"]
        flat.append({
            "case_id": r["case_id"], "capability": r["capability"],
            "scientific_state": r["scientific_state"], "outcome": r["outcome"],
            "expected_target": expected, "resolved_target": resolved,
            "entity_correct": entity_ok,
            "resolved_e3": r.get("resolved_e3", ""),
            "n_evidence": len(r.get("evidence") or []),
            "n_candidates": r["n_candidates"],
            "n_verified_candidates": r["n_verified_candidates"],
            "n_design_brief_candidates": r["n_design_brief_candidates"],
            "verified_validity": _validity(verified[0]) if verified else "",
            "abstention_justified": r["abstention_justified"],
            "abstention_reason": r["abstention_reason"],
            "latency_s": r["elapsed_s"],
            "routed_nodes": r["routed_nodes"],
            "answer_chars": len(r.get("answer") or ""),
            "route": ">".join(r["route"]),
        })
    with (out / "results_table.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(flat[0].keys()))
        w.writeheader()
        w.writerows(flat)

    # ── assessment summary ────────────────────────────────────────────
    by_cap = Counter((r["capability"], r["scientific_state"]) for r in rows)
    lines = [
        "# Closed-48 Phase-4 assessment — structured path",
        "",
        "Run `closed48_v2_structured`. Gold remains **pending**; no correctness score is claimed.",
        "This run is separate from `closed48_locked` (original) and "
        "`repaired_frozen`/`reproduced_current` (engineering repair).",
        "",
        "## Scientific-state distribution",
        "",
        "| capability | state | n |",
        "|---|---|---|",
    ]
    for (cap, state), n in sorted(by_cap.items()):
        lines.append(f"| {cap} | {state} | {n} |")
    entity_ok = sum(1 for f in flat if f["entity_correct"])
    justified = sum(1 for f in flat if f["abstention_justified"])
    verified_total = sum(f["n_verified_candidates"] for f in flat)
    lines += [
        "",
        f"* entity resolution correct: **{entity_ok}/48**",
        f"* justified abstentions: **{justified}**",
        f"* source-backed verified candidates produced: **{verified_total}**",
        f"* cases with a question-responsive answer (supported/hypothesis/valid/brief): "
        f"**{sum(1 for f in flat if f['scientific_state'] in {'supported_answer','conditional_hypothesis','valid_candidate','design_brief'})}/48**",
        f"* max latency: **{max(f['latency_s'] for f in flat):.1f}s**",
        "",
        "## Per-case table",
        "",
        "| case | cap | state | entity ok | evidence | verified | brief | latency |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for f in flat:
        lines.append(
            f"| {f['case_id']} | {f['capability']} | {f['scientific_state']} | "
            f"{'yes' if f['entity_correct'] else 'no'} | {f['n_evidence']} | "
            f"{f['n_verified_candidates']} | {f['n_design_brief_candidates']} | {f['latency_s']:.1f} |"
        )
    (out / "ASSESSMENT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {out}/results.jsonl, results_table.csv, ASSESSMENT.md")
    print("states:", dict(Counter(r["scientific_state"] for r in rows)))
    print("outcomes:", dict(Counter(r["outcome"] for r in rows)))
    print(f"entity correct: {entity_ok}/48; justified abstentions: {justified}; verified candidates: {verified_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
