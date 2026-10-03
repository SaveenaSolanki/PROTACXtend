#!/usr/bin/env python
"""Freeze code, data, splits and scoring for the closed 48-case benchmark.

Emits ``benchmark/gateC/CLOSED48_FREEZE.json`` with SHA-256 of every relevant
file plus the git commit and a combined freeze hash. Run after the code and
Gate C artifacts are final::

    python scripts/freeze_closed48.py
    python scripts/freeze_closed48.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmark" / "gateC" / "CLOSED48_FREEZE.json"

CODE = [
    "protacxtend/runtime/modes.py",
    "benchmark_runner/grader.py",
    "scripts/run_closed_48.py",
    "scripts/closed48_worker.py",
    "scripts/score_closed_48.py",
    "scripts/plot_closed_48.py",
    "scripts/make_closed48_report.py",
    "scripts/gateC_pilot.py",
    "tests/test_gate_c_input_contract.py",
]
DATA = [
    "benchmark/SCORABLE_MANIFEST.json",
    "benchmark/benchmark_manifest.csv",
    "benchmark/gateC/CASE_INVENTORY.json",
    "benchmark/gateC/REVIEWER_DECISIONS.tsv",
    "benchmark/gateC/gold_review.tsv",
    "benchmark/gateC/splits.json",
    "benchmark/gateC/pre_registration.md",
    "benchmark/gateC/provenance_manifest.json",
    "benchmark/gateC/reviewed_gold/consensus.template.json",
    "benchmark500/ARCHIVE_NOTICE.md",
    "benchmark500/ARCHIVE_MANIFEST.json",
]
SCORING = ["benchmark/SCORING_RUBRIC.md", "benchmark/BLINDNESS_RULES.md",
           "benchmark/BENCHMARK_PROTOCOL.md", "benchmark/BASELINES.md"]


def sha(p: Path) -> str | None:
    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return ""


def collect(prefix: str, paths) -> list[dict]:
    return [{"group": prefix, "path": p, "sha256": sha(ROOT / p)} for p in paths]


def build() -> dict:
    case_files = sorted((ROOT / "benchmark" / "cases").glob("*.json"))
    gt_files = sorted((ROOT / "benchmark" / "ground_truth").glob("*.json"))
    rubric_files = sorted((ROOT / "benchmark" / "gateC" / "rubrics").glob("*.json"))
    ev_files = sorted((ROOT / "benchmark" / "gateC" / "evidence_packages").glob("*.json"))
    pilot_files = sorted((ROOT / "benchmark" / "gateC" / "pilot").glob("*.json"))
    entries = (
        collect("code", CODE)
        + collect("data", DATA)
        + collect("scoring", SCORING)
        + [{"group": "cases", "path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in case_files]
        + [{"group": "ground_truth", "path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in gt_files]
        + [{"group": "rubrics", "path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in rubric_files]
        + [{"group": "evidence_packages", "path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in ev_files]
        + [{"group": "pilot", "path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in pilot_files]
    )
    core = {
        "schema": "closed48.freeze.v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git(),
        "scope": "existing 48-case benchmark only; 2x500 templates archived uncurated",
        "gold_adjudicated": False,
        "benchmark_score_reported": False,
        "note": ("Code/data/splits/scoring are frozen. Correctness scoring is locked until "
                 "benchmark/gateC/reviewed_gold/consensus.json is approved."),
        "n_entries": len(entries),
        "entries": entries,
    }
    core["freeze_hash"] = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    return core


def check() -> int:
    if not OUT.exists():
        print("no freeze file; run without --check first")
        return 1
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    bad = []
    for e in doc["entries"]:
        got = sha(ROOT / e["path"])
        if got != e["sha256"]:
            bad.append(e["path"])
    if bad:
        print("FROZEN FILES CHANGED:")
        for b in bad:
            print("  ", b)
        return 1
    print(f"OK: {len(doc['entries'])} frozen hashes verified; freeze_hash={doc['freeze_hash'][:16]}…")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        return check()
    doc = build()
    OUT.write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"freeze_hash": doc["freeze_hash"], "n_entries": doc["n_entries"],
                      "git_commit": doc["git_commit"], "gold_adjudicated": False,
                      "benchmark_score_reported": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
