"""Reproducibility and efficiency experiments (Sections 17 & 18)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

try:
    from scipy.stats import spearmanr  # type: ignore
    _HAVE_SCIPY = True
except Exception:  # pragma: no cover
    _HAVE_SCIPY = False


def repeat_agreement(runs: Sequence[Dict[str, Any]], field: str) -> Dict[str, Any]:
    """Fraction of repeats agreeing on a categorical/numeric decision field."""
    vals = [r.get(field) for r in runs if r.get(field) is not None]
    if not vals:
        return {"field": field, "n": 0, "agreement": None}
    from collections import Counter
    c = Counter(map(str, vals))
    top = c.most_common(1)[0][1]
    return {"field": field, "n": len(vals), "agreement": round(top / len(vals), 4),
            "distribution": dict(c)}


def numeric_variance(runs: Sequence[Dict[str, Any]], field: str) -> Dict[str, Any]:
    vals = [float(r[field]) for r in runs if isinstance(r.get(field), (int, float))]
    if not vals:
        return {"field": field, "n": 0}
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    return {"field": field, "n": len(vals), "mean": round(mean, 6),
            "variance": round(var, 8), "std": round(var ** 0.5, 6),
            "min": min(vals), "max": max(vals)}


def ranking_agreement(runs: Sequence[Sequence[str]]) -> Dict[str, Any]:
    """Pairwise Spearman of candidate rankings across repeats (by rank position)."""
    if len(runs) < 2 or not _HAVE_SCIPY:
        return {"n_repeats": len(runs), "mean_spearman": None}
    universe = list(dict.fromkeys([x for r in runs for x in r]))
    vecs = []
    for r in runs:
        pos = {c: i for i, c in enumerate(r)}
        vecs.append([pos.get(c, len(r) + universe.index(c)) for c in universe])
    cors = []
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            rho = spearmanr(vecs[i], vecs[j]).correlation
            if rho == rho:
                cors.append(rho)
    return {"n_repeats": len(runs),
            "mean_spearman": round(sum(cors) / len(cors), 4) if cors else None}


def replay_success(tool_calls_a: Sequence[Dict[str, Any]],
                   tool_calls_b: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Deterministic tools should replay to the same output digest."""
    def digests(calls):
        return [c.get("output_digest") for c in calls if c.get("output_digest")]
    a, b = digests(tool_calls_a), digests(tool_calls_b)
    if not a and not b:
        return {"n": 0, "replay_exact": None}
    same = sum(1 for x, y in zip(a, b) if x == y)
    return {"n": max(len(a), len(b)),
            "replay_exact": round(same / max(len(a), len(b)), 4),
            "explainable": a == b}


# ---- efficiency (Section 18) ------------------------------------------------

EFFICIENCY_FIELDS = ("wall_clock_s", "llm_calls", "tokens_in", "tokens_out",
                     "tool_calls", "failed_tool_calls", "retrieved_sources",
                     "compute_s", "api_cost_usd", "peak_memory_mb")


def efficiency_record(**kw: Any) -> Dict[str, Any]:
    return {f: kw.get(f) for f in EFFICIENCY_FIELDS}


def efficiency_summary(runs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"n_runs": len(runs)}
    for f in EFFICIENCY_FIELDS:
        vals = [float(r[f]) for r in runs if isinstance(r.get(f), (int, float))]
        if vals:
            out[f] = {"mean": round(sum(vals) / len(vals), 4),
                      "total": round(sum(vals), 4), "n": len(vals)}
    # cost / acceptable answer is reported, not inferred
    out["note"] = "report raw measurements; no single composite efficiency metric"
    return out
