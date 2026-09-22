#!/usr/bin/env python
"""Derive machine-checkable scoring criteria for every benchmark task.

The frozen ``benchmark/ground_truth/*.json`` files are immutable and are NOT
modified.  Instead this writes an overlay under ``benchmark/scoring/<task>.json``
that the grading engine merges at score time.  The overlay contains the
explicit requirement checklist derived from the authored ground truth so every
task is automatically gradeable, while the subjective dimensions remain flagged
for blind expert review.

Usage::

    python scripts/derive_scoring_criteria.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GROUND_TRUTH = ROOT / "benchmark" / "ground_truth"
SCORING_DIR = ROOT / "benchmark" / "scoring"

RUBRIC_TYPES = {"design_rubric", "mechanistic_rubric"}
_PREFIX_RE = re.compile(r"^\s*(rubric\s*\+?\s*exact\s*checks?\s*:?|rubric\s*:?)\s*", re.IGNORECASE)


def _split_requirements(text: str) -> List[str]:
    """Split an authored expected-answer sentence into checkable requirements."""
    cleaned = _PREFIX_RE.sub("", (text or "").strip())
    if not cleaned:
        return []
    parts: List[str] = []
    for chunk in re.split(r"[;\n]+", cleaned):
        chunk = chunk.strip(" .")
        if not chunk:
            continue
        # Split long run-on clauses on commas only when the pieces stay short.
        pieces = re.split(r",\s+", chunk) if len(chunk) > 90 else [chunk]
        for piece in pieces:
            piece = piece.strip(" .")
            if piece:
                parts.append(piece)
    return parts


def derive(gt: dict) -> dict:
    gtype = str(gt.get("type") or gt.get("gt_type") or "").strip()
    mandatory = list(gt.get("mandatory_answer_elements") or [])
    derived = False
    if not mandatory:
        mandatory = _split_requirements(str(gt.get("expected_answer") or ""))
        derived = bool(mandatory)
    overlay: dict[str, Any] = {
        "schema_version": "1.0.0",
        "task_id": gt.get("task_id", ""),
        "gt_type": gtype,
        "mandatory_elements": mandatory,
        "acceptable_alternatives": list(gt.get("acceptable_alternatives") or []),
        "derived": derived,
        "requires_expert_review": gtype in RUBRIC_TYPES,
        "source": "benchmark/ground_truth/" + str(gt.get("task_id", "")) + ".json",
    }
    # Preserve any real structured expectation already authored.
    for key in ("expected_value", "expected_set", "expected_ranking", "tolerance",
                "constraints", "causal_graph", "decision_trajectory"):
        if gt.get(key) is not None:
            overlay[key] = gt[key]
    return overlay


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=SCORING_DIR)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    count = 0
    derived_count = 0
    for path in sorted(GROUND_TRUTH.glob("*.json")):
        gt = json.loads(path.read_text(encoding="utf-8"))
        overlay = derive(gt)
        if overlay["derived"]:
            derived_count += 1
        (args.out / f"{path.stem}.json").write_text(
            json.dumps(overlay, indent=2), encoding="utf-8")
        count += 1
    print(f"wrote {count} scoring overlays ({derived_count} derived from expected_answer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
