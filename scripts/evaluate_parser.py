#!/usr/bin/env python
"""Evaluate the natural-language front door against the parser validation set.

Usage::

    python scripts/evaluate_parser.py [--json-out outputs/parser_eval.json]

Exit code is non-zero when target-extraction accuracy falls below the 98%
acceptance threshold.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from protacxtend.nlp.entity_extraction import extract_entities  # noqa: E402

VALIDATION_SET = REPO_ROOT / "protacxtend" / "data" / "parser_validation_set.json"
TARGET_ACCURACY_THRESHOLD = 0.98


def evaluate() -> dict:
    data = json.loads(VALIDATION_SET.read_text(encoding="utf-8"))
    rows = data["prompts"]

    target_correct = 0
    e3_correct = e3_total = 0
    disease_correct = disease_total = 0
    task_correct = task_total = 0
    failures: list[dict] = []

    for row in rows:
        result = extract_entities(row["prompt"])
        if result.target_gene == row["target_gene"]:
            target_correct += 1
        else:
            failures.append(
                {
                    "id": row["id"],
                    "prompt": row["prompt"],
                    "expected_target": row["target_gene"],
                    "predicted_target": result.target_gene,
                }
            )
        if "e3_preference" in row:
            e3_total += 1
            e3_correct += int(result.e3_preference == row["e3_preference"])
        if "disease_context" in row:
            disease_total += 1
            disease_correct += int(result.disease_context == row["disease_context"])
        if "task_type" in row:
            task_total += 1
            task_correct += int(result.task_type == row["task_type"])

    n = len(rows)
    report = {
        "validation_set": str(VALIDATION_SET.relative_to(REPO_ROOT)),
        "n_prompts": n,
        "target_accuracy": round(target_correct / n, 4),
        "target_threshold": TARGET_ACCURACY_THRESHOLD,
        "target_passed": (target_correct / n) >= TARGET_ACCURACY_THRESHOLD,
        "e3_accuracy": round(e3_correct / e3_total, 4) if e3_total else None,
        "disease_accuracy": round(disease_correct / disease_total, 4) if disease_total else None,
        "task_type_accuracy": round(task_correct / task_total, 4) if task_total else None,
        "failures": failures,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=REPO_ROOT / "outputs" / "parser_eval.json",
        help="Where to write the machine-readable report.",
    )
    args = parser.parse_args()

    report = evaluate()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"prompts:            {report['n_prompts']}")
    print(f"target accuracy:    {report['target_accuracy']:.4f} "
          f"(threshold {report['target_threshold']:.2f})")
    print(f"e3 accuracy:        {report['e3_accuracy']}")
    print(f"disease accuracy:   {report['disease_accuracy']}")
    print(f"task type accuracy: {report['task_type_accuracy']}")
    print(f"report written to:  {args.json_out}")
    if report["failures"]:
        print("failures:")
        for failure in report["failures"]:
            print(f"  {failure['id']}: {failure['prompt']!r} "
                  f"expected {failure['expected_target']!r} got {failure['predicted_target']!r}")
    return 0 if report["target_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
