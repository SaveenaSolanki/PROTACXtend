#!/usr/bin/env python
"""pilot_gold_free_report.py — provenance chains + fixed-denominator buckets.

For every case in a pilot report JSON, render the chain:

    raw source record -> relevant passage / chemical structure
                       -> supported claim -> final answer

and the mutually-exclusive outcome buckets (answered / source_unavailable /
no_relevant_evidence / answer_failed) over the FIXED denominator n_cases.
Optionally gold-gates the completed traces with
protacxtend.evidence.evaluate (post-run only) when a report includes
``gold_eval`` or when --gold-dir is given.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from protacxtend.evidence.evaluate import (  # noqa: E402
    classify_outcome,
    evaluate_trace,
    fixed_denominator_report,
)


def _chain_for(result: dict) -> list[str]:
    trace = result.get("evidence_trace") or {}
    lines = [f"### {result.get('task_id')} — outcome {result.get('outcome')}"
             f" (run_status={result.get('run_status')}, abstained={result.get('abstained')})", ""]
    for r in trace.get("results") or []:
        for t in r.get("top_results") or []:
            src = "snapshot" if t.get("snapshot") else "live"
            ident = t.get("doi") or t.get("pmid") or t.get("id") or "?"
            lines.append(f"- **raw record** [{src}] tool={r.get('tool')} id={t.get('id')} "
                         f"doi/pmid={ident} year={t.get('year')} title={t.get('title')}")
            if t.get("abstract"):
                lines.append(f"  - **passage:** {t['abstract'][:200]}")
            if t.get("structure"):
                lines.append(f"  - **chemical structure:** `{t['structure'][:120]}`")
    for c in trace.get("answer_claims") or []:
        lines.append(f"- **supported claim:** {c.get('claim')} [source_ids={c.get('source_ids')}] "
                     f"(snapshot={c.get('snapshot')})\n    passage: {(c.get('passage') or '')[:200]}")
    if not (trace.get("results") or []):
        lines.append("- no retrieval rows (no tool results produced)")
    if not (trace.get("answer_claims") or []):
        lines.append("- **no supported claims** → abstain / no_relevant_evidence")
    lines.append("")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pilot_json")
    ap.add_argument("--gold-dir", default=str(ROOT / "benchmark" / "ground_truth"),
                    help="ground-truth dir used ONLY by the post-run gold evaluator")
    ap.add_argument("--out", default="outputs/pilot_gold_free_report.md")
    args = ap.parse_args()

    report = json.loads(Path(args.pilot_json).read_text(encoding="utf-8"))
    results = report.get("results") or []

    fd = fixed_denominator_report([
        {"task_id": r["task_id"], "trace": r.get("evidence_trace") or {},
         "error": r.get("error") or "", "status": r.get("run_status")} for r in results])
    report.setdefault("fixed_denominator_outcomes", fd)

    lines = [
        "# Gold-free pilot — provenance chains + fixed-denominator outcomes",
        "",
        f"Pilot: `{args.pilot_json}` · engine={report.get('engine')} · n_cases={fd['n_cases']}",
        "",
        "**Gold access:** execution=" + str(report.get("gold_access", {}).get("during_execution", "n/a"))
        + " — ground truth consumed only by the post-run grader/evaluator.",
        "",
        "## Fixed-denominator outcomes",
        "",
        "| bucket | count | fraction of all cases |",
        "|---|---|---|",
    ]
    for k, v in fd["buckets"].items():
        lines.append(f"| {k} | {v['count']} | {v['fraction_of_all']} |")
    lines += ["", "## Per-case provenance chains", ""]

    for r in results:
        # post-run gold-gated audit (evaluator only; cannot affect the answer)
        gt_path = Path(args.gold_dir) / f"{r['task_id']}.json"
        gold_eval = None
        if gt_path.exists():
            gt = json.loads(gt_path.read_text(encoding="utf-8"))
            gold_eval = evaluate_trace(r.get("evidence_trace"), gt, r.get("capability", ""))
        lines += _chain_for(r)
        if gold_eval:
            lines += [
                f"*gold-gated (post-run): concepts matched={len(gold_eval['gold_concepts_matched'])}/"
                f"{gold_eval['gold_concepts_total']}; "
                f"gold refs cited={len(gold_eval['gold_evidence_refs_cited'])}/"
                f"{gold_eval['gold_evidence_refs_total']}*",
                "",
            ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} (n_cases={fd['n_cases']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())