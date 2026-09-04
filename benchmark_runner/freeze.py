"""Benchmark provenance: SHA-256 freeze manifest + fail-closed verification.

Freezes the 48 blinded cases, 48 ground-truth records, manifest, protocol,
blindness rules and scoring rubric. Benchmark execution MUST fail closed
when any frozen file hash changes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]

# Frozen file groups (relative to the benchmark root = repo/benchmark)
CASE_DIR = "cases"
GT_DIR = "ground_truth"
FREEZE_FILES: List[str] = [
    "benchmark_manifest.csv",
    "BENCHMARK_PROTOCOL.md",
    "BLINDNESS_RULES.md",
    "SCORING_RUBRIC.md",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_frozen_paths(benchmark_root: Path):
    """Yield (rel_path) for every frozen file inside benchmark_root."""
    for group, folder in [("case", CASE_DIR), ("ground_truth", GT_DIR)]:
        for p in sorted((benchmark_root / folder).glob("*.json")):
            if p.name == "README.md" or p.name.startswith("_"):
                continue
            yield group, p.relative_to(benchmark_root).as_posix()
    for rel in FREEZE_FILES:
        yield "support", rel


def build_freeze_manifest(benchmark_root: Path) -> Dict[str, Any]:
    entries: List[Dict[str, str]] = []
    for group, rel in iter_frozen_paths(benchmark_root):
        entries.append({
            "group": group,
            "path": rel,
            "sha256": sha256_file(benchmark_root / rel),
        })
    return {
        "freeze_version": "2A.1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "counts": {"cases": sum(1 for e in entries if e["group"] == "case"),
                   "ground_truth": sum(1 for e in entries if e["group"] == "ground_truth"),
                   "total": len(entries)},
        "entries": entries,
    }


def write_freeze_manifest(benchmark_root: Path) -> Dict[str, Any]:
    manifest = build_freeze_manifest(benchmark_root)
    (benchmark_root / "FREEZE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_freeze_manifest(benchmark_root: Path) -> Dict[str, Any]:
    path = benchmark_root / "FREEZE_MANIFEST.json"
    if not path.exists():
        raise FileNotFoundError("FREEZE_MANIFEST.json missing — benchmark cannot run unfrozen")
    return json.loads(path.read_text(encoding="utf-8"))


def check_frozen(benchmark_root: Path) -> Dict[str, Any]:
    """Return {'ok': bool, 'violations': [...]}. Never throws on hash drift."""
    frozen = load_freeze_manifest(benchmark_root)
    expected = {e["path"]: e["sha256"] for e in frozen["entries"]}
    violations: List[Dict[str, str]] = []
    current = dict(expected)
    seen: set[str] = set()
    for group, rel in iter_frozen_paths(benchmark_root):
        seen.add(rel)
        current[rel] = sha256_file(benchmark_root / rel)
        if rel not in expected:
            violations.append({"path": rel, "issue": "not in frozen manifest"})
            continue
        if expected[rel] != current[rel]:
            violations.append({"path": rel, "issue": "hash changed since freeze"})
    for rel in expected:
        if rel not in seen:
            violations.append({"path": rel, "issue": "frozen file missing"})
    return {"ok": not violations, "violations": violations,
            "freeze_version": frozen.get("freeze_version"),
            "frozen_at": frozen.get("frozen_at")}


class FreezeViolation(Exception):
    """Raised when frozen benchmark files differ from the freeze manifest."""


def assert_frozen(benchmark_root: Path) -> None:
    """Fail closed: raise FreezeViolation if any frozen file changed."""
    result = check_frozen(benchmark_root)
    if not result["ok"]:
        raise FreezeViolation(
            f"frozen benchmark drifted ({len(result['violations'])} violation(s)): "
            + "; ".join(f"{v['path']} ({v['issue']})" for v in result["violations"][:5]))
