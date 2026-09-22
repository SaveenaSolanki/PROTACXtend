"""Paired statistical analysis (Section 22).

Systems solve the same tasks, so every test preserves pairing. Wilcoxon
signed-rank, paired permutation, McNemar, bootstrap CIs, and a mixed-effects
model with a per-task random intercept.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

try:
    import numpy as np
    from scipy import stats as _st
    _HAVE = True
except Exception:  # pragma: no cover
    _HAVE = False


def _require() -> None:
    if not _HAVE:
        raise RuntimeError("stats requires numpy+scipy (not available)")


def wilcoxon_paired(a: Sequence[float], b: Sequence[float]) -> Dict[str, Any]:
    """a, b are paired per-task scores for two systems."""
    _require()
    a_arr, b_arr = np.asarray(a, float), np.asarray(b, float)
    if len(a_arr) != len(b_arr):
        raise ValueError("paired arrays must be equal length")
    diff = a_arr - b_arr
    if np.allclose(diff, 0):
        return {"test": "wilcoxon", "n": len(a_arr), "statistic": 0.0,
                "p_value": 1.0, "median_diff": 0.0, "note": "all differences zero"}
    res = _st.wilcoxon(a_arr, b_arr, zero_method="wilcox", alternative="two-sided")
    return {"test": "wilcoxon", "n": len(a_arr),
            "statistic": float(res.statistic), "p_value": float(res.pvalue),
            "median_diff": float(np.median(diff)),
            "mean_diff": float(np.mean(diff))}


def paired_permutation(a: Sequence[float], b: Sequence[float],
                       n_perm: int = 10000, seed: int = 0) -> Dict[str, Any]:
    """Sign-flip permutation test on the mean paired difference."""
    _require()
    rng = np.random.default_rng(seed)
    diff = np.asarray(a, float) - np.asarray(b, float)
    obs = float(np.mean(diff))
    if np.allclose(diff, 0):
        return {"test": "paired_permutation", "n": len(diff), "observed": 0.0,
                "p_value": 1.0}
    signs = rng.choice([-1.0, 1.0], size=(n_perm, len(diff)))
    perm = (signs * diff).mean(axis=1)
    p = float(np.mean(np.abs(perm) >= abs(obs)))
    return {"test": "paired_permutation", "n": len(diff),
            "observed": obs, "p_value": p, "n_perm": n_perm}


def mcnemar(b_correct: Sequence[bool], c_correct: Sequence[bool],
            exact: Optional[bool] = None) -> Dict[str, Any]:
    """McNemar test for two paired binary correctness vectors (b vs c)."""
    _require()
    b = np.asarray(b_correct, bool)
    c = np.asarray(c_correct, bool)
    if len(b) != len(c):
        raise ValueError("paired arrays must be equal length")
    n01 = int(np.sum(b & ~c))
    n10 = int(np.sum(~b & c))
    n = n01 + n10
    if n == 0:
        return {"test": "mcnemar", "n": len(b), "b_only": 0, "c_only": 0,
                "p_value": 1.0}
    if exact is None:
        exact = n < 25
    if exact:
        p = float(_st.binomtest(min(n01, n10), n, 0.5).pvalue * 2)
        p = min(p, 1.0)
    else:
        stat = (abs(n01 - n10) - 1) ** 2 / n
        p = float(_st.chi2.sf(stat, 1))
    return {"test": "mcnemar", "n": len(b), "b_only": n01, "c_only": n10,
            "p_value": p, "exact": bool(exact)}


def bootstrap_ci(values: Sequence[float], statistic: str = "mean",
                 n_boot: int = 10000, alpha: float = 0.05,
                 seed: int = 0) -> Dict[str, Any]:
    _require()
    arr = np.asarray(values, float)
    if arr.size == 0:
        return {"n": 0, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(seed)
    fn: Callable[[Any], float] = {
        "mean": lambda x: float(np.mean(x)),
        "median": lambda x: float(np.median(x)),
    }[statistic]
    boots = np.array([fn(rng.choice(arr, size=arr.size, replace=True))
                      for _ in range(n_boot)])
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"n": int(arr.size), "statistic": statistic,
            "point": round(fn(arr), 6), "ci_low": round(float(lo), 6),
            "ci_high": round(float(hi), 6), "alpha": alpha, "n_boot": n_boot}


def cohens_d_paired(a: Sequence[float], b: Sequence[float]) -> float:
    _require()
    diff = np.asarray(a, float) - np.asarray(b, float)
    sd = float(np.std(diff, ddof=1)) if diff.size > 1 else 0.0
    return round(float(np.mean(diff) / sd), 4) if sd > 0 else 0.0


def mixed_effects(records: List[Dict[str, Any]],
                  formula: str = "score ~ C(system) + C(domain) + C(difficulty) "
                                 "+ C(system):C(difficulty) + C(system):C(domain)"):
    """Fit a mixed-effects model with a per-task random intercept.

    ``records`` rows: {score, system, domain, difficulty, task_id}. Every task_id
    should be observed by every system (paired design). If the full interaction
    model is singular (common with small/sparse data), fall back to a reduced
    main-effects model and say so.
    """
    try:
        import pandas as pd
        import statsmodels.formula.api as smf
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": f"statsmodels/pandas unavailable: {exc}"}
    df = pd.DataFrame(records)

    def _fit(f: str):
        model = smf.mixedlm(f, df, groups=df["task_id"])
        return model.fit(reml=True, method="lbfgs")

    reduced = "score ~ C(system) + C(domain) + C(difficulty)"
    for f, kind in ((formula, "full_interaction"), (reduced, "reduced_main_effects")):
        try:
            fit = _fit(f)
            return {"available": True, "model": kind, "formula": f,
                    "converged": bool(fit.converged),
                    "params": {k: round(float(v), 5) for k, v in fit.params.items()},
                    "pvalues": {k: round(float(v), 5) for k, v in fit.pvalues.items()}}
        except Exception:
            continue
    # Fallback: OLS with cluster-robust SEs by task_id. Used when the random
    # intercept variance is ~0 (singular) — labelled so it is never mistaken
    # for a mixed model.
    try:
        import statsmodels.formula.api as smf
        ols = smf.ols(reduced, df).fit(cov_type="cluster",
                                       cov_kwds={"groups": df["task_id"]})
        return {"available": True, "model": "ols_cluster_robust_fallback",
                "formula": reduced, "converged": True,
                "params": {k: round(float(v), 5) for k, v in ols.params.items()},
                "pvalues": {k: round(float(v), 5) for k, v in ols.pvalues.items()},
                "note": "random-intercept variance singular; clustered OLS used"}
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": f"both mixed and OLS failed: {exc}",
                "formula": formula}


def holm_bonferroni(p_values: Dict[str, float]) -> Dict[str, float]:
    """Holm-Bonferroni adjusted p-values for the family of comparisons."""
    items = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(items)
    adjusted: Dict[str, float] = {}
    prev = 0.0
    for i, (k, p) in enumerate(items):
        adj = min(1.0, max(prev, (m - i) * p))
        adjusted[k] = round(adj, 6)
        prev = adj
    return adjusted
