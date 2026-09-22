#!/usr/bin/env python
"""Build the benchmark scorable manifest.

For every ``benchmark/ground_truth/*.json`` this records the ground-truth type,
the grader path, whether it is automatically gradeable, and (if not) exactly
which fields are missing.  It also cross-checks the case set so missing/extra
tasks are visible.

Writes:
    benchmark/SCORABLE_MANIFEST.json
    benchmark/SCORABLE_REPORT.md

Exit code is non-zero if any case has no ground truth.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark_runner.grader import scorable_status  # noqa: E402

CASES = ROOT / "benchmark" / "cases"
GROUND_TRUTH = ROOT / "benchmark" / "ground_truth"


def build() -> dict:
    case_ids = sorted(p.stem for p in CASES.glob("*.json") if not p.stem.startswith("_"))
    gt_ids = sorted(p.stem for p in GROUND_TRUTH.glob("*.json") if not p.stem.startswith("_"))
    rows = []
    auto = 0
    for task_id in gt_ids:
        gt = json.loads((GROUND_TRUTH / f"{task_id}.json").read_text(encoding="utf-8"))
        status = scorable_status(gt, task_id=task_id)
        auto += 1 if status["scorable"] else 0
        rows.append({
            "task_id": task_id,
            "gt_type": status["gtype"],
            "mode": status["mode"],
            "automatically_scorable": status["scorable"],
            "requires_expert_review": status["gtype"] in ("design_rubric", "mechanistic_rubric"),
            "missing_fields": status["missing_fields"],
            "reason": status["reason"],
            "has_mandatory_checklist": bool(gt.get("mandatory_answer_elements")),
        })
    return {
        "schema_version": "1.0.0",
        "n_cases": len(case_ids),
        "n_ground_truth": len(gt_ids),
        "cases_without_ground_truth": sorted(set(case_ids) - set(gt_ids)),
        "ground_truth_without_case": sorted(set(gt_ids) - set(case_ids)),
        "n_automatically_scorable": auto,
        "n_requires_expert_review": sum(1 for r in rows if r["requires_expert_review"]),
        "n_not_scorable": sum(1 for r in rows if not r["automatically_scorable"]),
        "tasks": rows,
    }


def render_markdown(manifest: dict) -> str:
    lines = [
        "# Benchmark Scorable Manifest",
        "",
        f"- Cases: **{manifest['n_cases']}**",
        f"- Ground truths: **{manifest['n_ground_truth']}**",
        f"- Automatically scorable: **{manifest['n_automatically_scorable']}**",
        f"- Rubric (needs expert review): **{manifest['n_requires_expert_review']}**",
        f"- Not scorable yet: **{manifest['n_not_scorable']}**",
        "",
    ]
    if manifest["cases_without_ground_truth"]:
        lines.append(f"Cases without ground truth: {', '.join(manifest['cases_without_ground_truth'])}")
        lines.append("")
    lines += [
        "| Task | GT type | Grader | Auto | Missing fields |",
        "|---|---|---|---|---|",
    ]
    for row in manifest["tasks"]:
        lines.append(
            f"| {row['task_id']} | {row['gt_type']} | {row['mode']} | "
            f"{'yes' if row['automatically_scorable'] else 'no'} | "
            f"{', '.join(row['missing_fields']) or '-'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=ROOT / "benchmark" / "SCORABLE_MANIFEST.json")
    parser.add_argument("--md-out", type=Path, default=ROOT / "benchmark" / "SCORABLE_REPORT.md")
    args = parser.parse_args()

    manifest = build()
    args.json_out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    args.md_out.write_text(render_markdown(manifest), encoding="utf-8")

    print(f"cases={manifest['n_cases']} gt={manifest['n_ground_truth']} "
          f"auto_scorable={manifest['n_automatically_scorable']} "
          f"rubric={manifest['n_requires_expert_review']} "
          f"not_scorable={manifest['n_not_scorable']}")
    if manifest["cases_without_ground_truth"]:
        print("MISSING GT:", ", ".join(manifest["cases_without_ground_truth"]))
    print(f"wrote {args.json_out} and {args.md_out}")
    return 1 if manifest["cases_without_ground_truth"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
