"""Blinded temporal challenge and leakage controls (Sections 13 & 14)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

OUTCOME_CLASSES = ("SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "UNRESOLVED")
UNLOCK_MONTHS = (6, 12, 18, 24)

# Evidence streams that must be frozen at T0 and audited for release date.
FROZEN_STREAMS = ("literature", "databases", "structures", "models", "tools", "web")


@dataclass
class SourceRecord:
    source_id: str
    kind: str                       # publication | database | structure | model | tool | patent | web
    released: str                   # ISO date
    retrieved: Optional[str] = None
    snapshot: Optional[str] = None


def leakage_flags(sources: Sequence[SourceRecord], cutoff: str) -> List[Dict[str, Any]]:
    """Flag any source released or retrieved after the T0 cutoff."""
    flags: List[Dict[str, Any]] = []
    for s in sources:
        if s.released and s.released > cutoff:
            flags.append({"source_id": s.source_id, "kind": s.kind,
                          "released": s.released, "cutoff": cutoff,
                          "issue": "TEMPORAL_LEAKAGE (released after T0)"})
        if s.retrieved and s.retrieved > cutoff:
            flags.append({"source_id": s.source_id, "kind": s.kind,
                          "retrieved": s.retrieved, "cutoff": cutoff,
                          "issue": "TEMPORAL_LEAKAGE (retrieved after T0)"})
    return flags


def classify_outcome(prediction: Dict[str, Any],
                     later_evidence: Dict[str, Any]) -> str:
    """Classify one prediction against post-T0 evidence.

    ``later_evidence`` must carry explicit per-aspect verdicts; we never infer
    them from free text.
    """
    aspects = [k for k in prediction
               if later_evidence.get(k, {}).get("verdict") in OUTCOME_CLASSES]
    if not aspects:
        return "UNRESOLVED"
    verdicts = [later_evidence[k]["verdict"] for k in aspects]
    if all(v == "SUPPORTED" for v in verdicts):
        return "SUPPORTED"
    if all(v == "CONTRADICTED" for v in verdicts):
        return "CONTRADICTED"
    if any(v == "CONTRADICTED" for v in verdicts):
        return "PARTIALLY_SUPPORTED"
    if any(v == "SUPPORTED" for v in verdicts):
        return "PARTIALLY_SUPPORTED"
    return "UNRESOLVED"


def temporal_summary(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    from collections import Counter
    counts = Counter(r.get("classification", "UNRESOLVED") for r in records)
    n = len(records) or 1
    return {
        "n": len(records),
        "counts": dict(counts),
        "supported_rate": round(counts.get("SUPPORTED", 0) / n, 4),
        "contradicted_rate": round(counts.get("CONTRADICTED", 0) / n, 4),
        "leakage_events": sum(len(r.get("leakage", [])) for r in records),
        "per_aspect": _per_aspect(records),
    }


def _per_aspect(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    aspects = ["target_prediction", "e3_prediction", "warhead_strategy",
               "mechanism", "ternary_prediction", "experimental_recommendation"]
    out: Dict[str, Any] = {}
    for a in aspects:
        verdicts = [r.get("aspects", {}).get(a) for r in records]
        verdicts = [v for v in verdicts if v in OUTCOME_CLASSES]
        out[a] = {"n": len(verdicts),
                  "supported": sum(1 for v in verdicts if v == "SUPPORTED"),
                  "contradicted": sum(1 for v in verdicts if v == "CONTRADICTED")}
    return out
