"""Deterministic scoring (Sprint 2B).

- exact            -> normalized exact match
- categorical      -> predefined categorical scoring (mandatory + alternatives)
- ranked           -> rank-correlation / top-k metrics

Deterministic scoring never uses an LLM judge.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

# ── exact ────────────────────────────────────────────────────────────────

def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v).strip().lower())


def exact_score(predicted: Any, expected: Any) -> float:
    """1.0 if normalized equal else 0.0."""
    return 1.0 if _norm(predicted) == _norm(expected) else 0.0


# ── categorical ──────────────────────────────────────────────────────────

def categorical_score(
    predicted: Any,
    expected_set: Sequence[Any],
    mandatory: Optional[Sequence[str]] = None,
    alternatives: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Score against a predefined set. 1.0 when every mandatory element is
    present and no fabricated element appears; partial otherwise."""
    text = _norm(predicted)
    exp = [_norm(e) for e in expected_set]
    man = [_norm(m) for m in (mandatory or expected_set)]
    alt = [_norm(a) for a in (alternatives or [])]

    present = {e for e in exp if e in text}
    mandatory_missing = [m for m in man if m not in present and m not in alt]
    present_mandatory = len(man) - len(mandatory_missing)
    coverage = present_mandatory / len(man) if man else 0.0
    return {
        "score": coverage,
        "present": sorted(present),
        "missing_mandatory": mandatory_missing,
        "method": "categorical",
    }


# ── ranked ───────────────────────────────────────────────────────────────

def _rank(values: Sequence[Any]) -> List[float]:
    # standard competition ranking (averaged)
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def rank_correlation(predicted: Sequence[Any], expected: Sequence[Any]) -> float:
    """Spearman rank correlation between predicted and expected orderings."""
    n = len(predicted)
    if n != len(expected) or n == 0:
        return 0.0
    rp = _rank(list(predicted))
    rexp = _rank(list(expected))
    mp = sum(rp) / n
    me = sum(rexp) / n
    num = sum((a - mp) * (b - me) for a, b in zip(rp, rexp))
    dp = sum((a - mp) ** 2 for a in rp) ** 0.5
    de = sum((b - me) ** 2 for b in rexp) ** 0.5
    if dp == 0 or de == 0:
        return 1.0 if rp == rexp else 0.0
    return round(num / (dp * de), 4)


def topk_agreement(predicted_ids: Sequence[str], expected_ids: Sequence[str],
                   k: Optional[int] = None) -> Dict[str, Any]:
    """Fraction of expected top-k ids that appear in the predicted top-k."""
    k = k or min(len(expected_ids), len(predicted_ids))
    expected_top = list(expected_ids)[:k]
    predicted_top = set(predicted_ids[:k])
    hits = [e for e in expected_top if e in predicted_top]
    return {"k": k, "hits": hits, "expected_top": expected_top,
            "topk": round(len(hits) / len(expected_top), 4) if expected_top else 1.0}


def rank_score(predicted: Sequence[Any], expected: Sequence[Any]) -> Dict[str, Any]:
    return {"method": "ranked",
            "spearman": rank_correlation(predicted, expected),
            "score": max(0.0, (rank_correlation(predicted, expected) + 1) / 2)}


def score(gt_type: str, predicted: Any, expected: Any, **kw: Any) -> Dict[str, Any]:
    """Dispatch on ground-truth type (never an LLM)."""
    if gt_type == "exact":
        return {"method": "exact", "score": exact_score(predicted, expected)}
    if gt_type == "categorical":
        return categorical_score(predicted, expected, **kw)
    if gt_type in ("ranked", "ranking"):
        return rank_score(predicted, expected)
    raise ValueError(f"deterministic scoring not defined for gt_type {gt_type!r} "
                     "(rubric types use rubric scoring)")
