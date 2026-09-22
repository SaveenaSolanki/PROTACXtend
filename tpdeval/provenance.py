"""Run manifests, provenance and temporal-leakage detection (Sections 14, 24, 27).

A run is only admissible if its manifest is complete and leakage-free. Nothing
is silently retained.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from tpdeval.temporal import SourceRecord, leakage_flags


@dataclass
class RunManifest:
    run_id: str
    task_id: str
    system: str
    system_version: str
    condition: str
    model: str
    model_version: str
    provider: str
    seed: int
    temperature: float
    repeat: int
    task_hash: str
    started_at: str
    ended_at: str
    code_commit: str = ""
    environment_hash: str = ""
    tool_versions: Dict[str, str] = field(default_factory=dict)
    db_snapshots: Dict[str, str] = field(default_factory=dict)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def manifest_hash(self) -> str:
        d = self.to_dict()
        d.pop("sources", None)
        return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()
                              ).hexdigest()[:16]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def leakage_from_manifest(manifest: RunManifest, cutoff: str) -> List[Dict[str, Any]]:
    sources = []
    for s in manifest.sources:
        sources.append(SourceRecord(
            source_id=s.get("source_id", ""), kind=s.get("kind", "web"),
            released=s.get("released", ""), retrieved=s.get("retrieved"),
            snapshot=s.get("snapshot")))
    return leakage_flags(sources, cutoff)


def admissible(manifest: RunManifest, cutoff: Optional[str] = None) -> Dict[str, Any]:
    issues: List[str] = []
    for f in ("run_id", "task_id", "system", "condition", "model", "task_hash"):
        if not getattr(manifest, f):
            issues.append(f"manifest missing {f}")
    if manifest.condition not in ("native", "matched_tool"):
        issues.append("manifest condition must be native|matched_tool")
    leaks = leakage_from_manifest(manifest, cutoff) if cutoff else []
    if leaks:
        issues.append(f"{len(leaks)} temporal leakage event(s)")
    return {"admissible": not issues, "issues": issues, "leakage": leaks,
            "status": "CONTAMINATED" if leaks else ("OK" if not issues else "INCOMPLETE")}
