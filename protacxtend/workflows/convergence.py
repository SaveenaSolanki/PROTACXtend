"""Trajectory convergence assessment.

A finished MD trajectory is **not** automatically converged. This module scores
plateau/stationarity of running observables, block-average uncertainty and
replica agreement, and returns one of:

``CONVERGED`` · ``PARTIALLY_CONVERGED`` · ``NOT_CONVERGED`` ·
``INSUFFICIENT_TRAJECTORY``

The evidence tier must not be escalated above TIER_3 when convergence fails.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

MIN_FRAMES = 20


def _block_sem(series: np.ndarray, nblocks: int = 5) -> float:
    if len(series) < 2:
        return float("nan")
    nblocks = max(2, min(nblocks, len(series) // 2))
    blocks = [series[i::nblocks].mean() for i in range(nblocks)]
    return float(np.std(blocks) / np.sqrt(len(blocks)))


def _plateau(series: Sequence[float], tol_frac: float = 0.15) -> dict[str, Any]:
    arr = np.asarray([x for x in series if x is not None], dtype=float)
    if len(arr) < MIN_FRAMES:
        return {"ok": False, "reason": "insufficient frames", "n": int(len(arr))}
    half = len(arr) // 2
    first, second = float(arr[:half].mean()), float(arr[half:].mean())
    span = max(abs(first), abs(second), 1e-6)
    drift = abs(second - first) / span
    return {
        "ok": drift <= tol_frac,
        "first_half_mean": round(first, 4),
        "second_half_mean": round(second, 4),
        "relative_drift": round(drift, 4),
        "block_sem": round(_block_sem(arr), 4),
        "n": int(len(arr)),
    }


def assess_convergence(
    *,
    rmsd: Sequence[float] | None = None,
    bsa: Sequence[float] | None = None,
    contact_occupancy: Sequence[float] | None = None,
    interaction_energy: Sequence[float] | None = None,
    replica_means: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Return a structured convergence verdict with the evidence behind it."""
    checks: dict[str, Any] = {}
    if rmsd is not None:
        checks["rmsd_plateau"] = _plateau(rmsd)
    if bsa is not None:
        checks["bsa_plateau"] = _plateau(bsa)
    if contact_occupancy is not None:
        checks["contact_plateau"] = _plateau(contact_occupancy)
    if interaction_energy is not None:
        checks["energy_plateau"] = _plateau(interaction_energy)

    replica_check: dict[str, Any] = {}
    if replica_means and len(replica_means) > 1:
        vals = np.asarray(list(replica_means.values()), dtype=float)
        spread = float(np.std(vals))
        mean = float(np.mean(vals))
        rel = spread / max(abs(mean), 1e-6)
        replica_check = {"ok": rel <= 0.25, "spread": round(spread, 4),
                         "relative_spread": round(rel, 4),
                         "n_replicas": len(vals)}
        checks["replica_agreement"] = replica_check

    if "rmsd_plateau" in checks and not checks["rmsd_plateau"].get("n", 0) >= MIN_FRAMES:
        if all(not c.get("ok") for c in checks.values() if isinstance(c, dict)):
            return {"verdict": "INSUFFICIENT_TRAJECTORY", "checks": checks}

    n_ok = sum(1 for c in checks.values() if isinstance(c, dict) and c.get("ok"))
    n_total = sum(1 for c in checks.values() if isinstance(c, dict))
    if n_total == 0:
        verdict = "INSUFFICIENT_TRAJECTORY"
    elif n_ok == n_total and n_total >= 2:
        verdict = "CONVERGED"
    elif n_ok >= 1:
        verdict = "PARTIALLY_CONVERGED"
    else:
        verdict = "NOT_CONVERGED"
    return {
        "verdict": verdict,
        "n_checks_ok": n_ok,
        "n_checks": n_total,
        "checks": checks,
        "tier_escalation_allowed": verdict == "CONVERGED",
    }


def convergence_csv_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for name, check in (result.get("checks") or {}).items():
        rows.append({"check": name, "ok": check.get("ok"), **{k: v for k, v in check.items() if k != "ok"}})
    return rows
