"""alpha definitions, classification and conversions (Module 3).

Thermodynamic interpretation (exact sign, used for reasoning)
-------------------------------------------------------------
    alpha > 1  -> positive cooperativity
    alpha = 1  -> non-cooperative
    alpha < 1  -> negative cooperativity

Practical reporting categories (non-overlapping reporting bands)
----------------------------------------------------------------
    alpha <  0.8                      -> negative
    0.8 <= alpha <= 1.25              -> approximately neutral
    alpha >  1.25                     -> positive

The bands are mutually exclusive: 0.8 and 1.25 belong to "approximately
neutral"; 0.7999 is negative; 1.2501 is positive. Model target is
log_alpha = ln(alpha) (natural log, single convention; do not mix log10/ln).

Definition: alpha = Kd2 / Kd2(ternary) — the factor by which the SECOND binary
interaction (E3-PROTAC) strengthens when the first arm (POI-PROTAC) is bound
(consistent with Module 1). Only same-assay measured constants may enter.
"""

from __future__ import annotations

import math
from typing import Optional

ALPHA_NONCOOP_LOW = 0.8
ALPHA_NONCOOP_HIGH = 1.25

THERMODYNAMIC_NOTE = ("Thermodynamic classes are exact-sign statements: "
                      "alpha>1 positive, alpha=1 non-cooperative, alpha<1 negative.")


def alpha_to_log(alpha: float) -> float:
    """ln(alpha)."""
    if alpha < 0:
        raise ValueError("alpha cannot be negative")
    if alpha == 0:
        return -math.inf
    return math.log(alpha)


def log_to_alpha(log_alpha: float) -> float:
    """exp(log_alpha); accepts -inf -> 0."""
    if log_alpha is None or log_alpha == -math.inf:
        return 0.0
    return math.exp(float(log_alpha))


def cooperativity_class_thermodynamic(alpha: float | None, *,
                                      eps: float = 1e-9) -> str:
    """Exact-sign thermodynamic class. alpha==1 (within eps) -> non_cooperative."""
    if alpha is None:
        return "not_assessed"
    if alpha > 1.0 + eps:
        return "positive"
    if alpha < 1.0 - eps:
        return "negative"
    return "non_cooperative"


def cooperativity_class(alpha: float | None, *,
                        low: float = ALPHA_NONCOOP_LOW,
                        high: float = ALPHA_NONCOOP_HIGH) -> str:
    """Non-overlapping PRACTICAL reporting category (defaults 0.8 / 1.25)."""
    if alpha is None:
        return "not_assessed"
    if alpha < low:
        return "negative"
    if alpha > high:
        return "positive"
    return "approximately_neutral"


def class_from_log(log_alpha: float | None, **kw) -> str:
    if log_alpha is None:
        return "not_assessed"
    return cooperativity_class(log_to_alpha(log_alpha), **kw)


def class_edges(*, low: float = ALPHA_NONCOOP_LOW,
                high: float = ALPHA_NONCOOP_HIGH) -> dict[str, float]:
    """Reporting-band edges: [0, low) negative; [low, high] approx neutral;
    (high, inf) positive."""
    return {"negative_lt": low, "approximately_neutral": (low, high),
            "positive_gt": high, "note": THERMODYNAMIC_NOTE}
