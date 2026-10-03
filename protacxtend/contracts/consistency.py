"""Cross-artifact consistency checks for a persisted controlled run.

Every artifact must describe the same run: same run_id, same funnel counts,
same candidate set, same decision count. ``verify_run_dir`` returns a list of
human-readable problems (empty means consistent).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def verify_run_dir(out_dir: Path) -> list[str]:
    out_dir = Path(out_dir)
    issues: list[str] = []
    run_path = out_dir / "run.json"
    if not run_path.exists():
        return [f"missing run.json in {out_dir}"]
    run = json.loads(run_path.read_text())
    run_id = run.get("run_id", "")

    # trace must carry one entry per stage and the same run_id
    trace = _read_jsonl(out_dir / "trace.jsonl")
    stages = run.get("stages", [])
    if len(trace) != len(stages):
        issues.append(f"trace entries ({len(trace)}) != stages ({len(stages)})")
    for row in trace:
        if row.get("run_id") != run_id:
            issues.append(f"trace run_id {row.get('run_id')!r} != run.json {run_id!r}")
            break

    # decisions must match stages one-to-one
    decisions = _read_jsonl(out_dir / "decisions.jsonl")
    if len(decisions) != len(stages):
        issues.append(f"decisions ({len(decisions)}) != stages ({len(stages)})")

    # funnel.json must equal the embedded funnel
    fun_path = out_dir / "funnel.json"
    if fun_path.exists():
        funnel = json.loads(fun_path.read_text())
        if funnel != run.get("funnel"):
            issues.append("funnel.json disagrees with run.json funnel")

    # candidate table must match the record's candidate ids
    cand_path = out_dir / "candidates.csv"
    if cand_path.exists():
        with cand_path.open(newline="", encoding="utf-8") as fh:
            ids = {r["candidate_id"] for r in csv.DictReader(fh)}
        record_ids = {c.get("candidate_id") for c in run.get("candidates", [])}
        if ids != record_ids:
            issues.append(f"candidates.csv ids {ids} != run.json ids {record_ids}")

    # predictions count
    preds = _read_jsonl(out_dir / "predictions.jsonl")
    if len(preds) != len(run.get("predictions", [])):
        issues.append(f"predictions.jsonl ({len(preds)}) != run.json ({len(run.get('predictions', []))})")

    # funnel reconciliation notes, if any, are themselves a problem
    notes = run.get("consistency_notes", [])
    if notes:
        issues.append("run consistency_notes non-empty: " + "; ".join(notes))

    return issues
