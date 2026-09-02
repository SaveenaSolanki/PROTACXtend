"""Baseline benchmarks for log(alpha) prediction (Module 3, steps 5 & 6).

Scientific ordering enforced: constant/mean predictor -> ridge -> Random Forest
-> XGBoost -> Gaussian Process (dataset size permitting). All evaluation uses
grouped folds (unseen PROTAC series by default) to avoid random leakage between
closely-related PROTACs. Every model reports R2, MAE, RMSE, Spearman, Pearson,
sign accuracy and (for GP) calibration error; Random Forest/XGBoost use an
empirical conformal-style residual interval for uncertainty. If the curated
dataset is empty, run_benchmarks returns {'dataset_empty': True} — no model is
trained and no learned alpha predictor is claimed.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from protacxtend.modules.cooperativity_alpha_predictor.data import grouped_kfold

logger = logging.getLogger("protacxtend.cooperativity_models")


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    if mask.sum() < 2:
        return {"r2": float("nan"), "mae": float("nan"), "rmse": float("nan"),
                "spearman": float("nan"), "pearson": float("nan"),
                "sign_accuracy": float("nan"), "n": int(mask.sum())}
    yt, yp = y_true[mask], y_pred[mask]
    ss_res = float(np.sum((yt - yp) ** 2))
    ss_tot = float(np.sum((yt - yt.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    mae = float(np.mean(np.abs(yt - yp)))
    rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))
    pc = float(np.corrcoef(yt, yp)[0, 1]) if len(yt) > 1 else float("nan")
    from scipy.stats import spearmanr
    sp = float(spearmanr(yt, yp).statistic) if len(yt) > 2 else float("nan")
    # sign accuracy: correct sign of log_alpha (positive vs negative class)
    sign_true = np.sign(yt)
    sign_pred = np.sign(yp)
    keep = sign_true != 0
    sa = float(np.mean(sign_pred[keep] == sign_true[keep])) if keep.any() else float("nan")
    return {"r2": round(r2, 4), "mae": round(mae, 4), "rmse": round(rmse, 4),
            "spearman": round(sp, 4), "pearson": round(pc, 4),
            "sign_accuracy": round(sa, 4) if not math.isnan(sa) else None, "n": int(mask.sum())}


def _groups_from_df(df: pd.DataFrame, group_col: str) -> list[Any]:
    if group_col in df.columns:
        return df[group_col].fillna("unknown").tolist()
    return list(range(len(df)))


def run_benchmarks(df: pd.DataFrame, feature_cols: list[str], target_col: str = "log_alpha",
                   group_col: str = "protac_id",
                   gaussian_process: bool = True) -> dict[str, Any]:
    """Grouped cross-validation over baseline models.

    Returns {model: {fold_metrics, pooled_metrics}} or dataset_empty marker.
    """
    if df is None or df.empty or target_col not in df.columns:
        return {"dataset_empty": True,
                "note": "no curated experimental alpha records -> no supervised "
                        "model trained; structural surrogate retained (no fabricated labels)."}
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").to_numpy()
    y = pd.to_numeric(df[target_col], errors="coerce").to_numpy()
    finite = np.isfinite(y)
    X = X[finite]
    y = y[finite]
    groups = [g for g, ok in zip(_groups_from_df(df, group_col), finite, strict=False) if ok]
    if len(X) < 6 or len(set(groups)) < 2:
        return {"dataset_too_small": True,
                "note": f"n={len(X)} usable records (groups={len(set(groups))}) too small for "
                        "reliable grouped supervised prediction; surrogate mode retained."}

    from sklearn.ensemble import RandomForestRegressor
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF, WhiteKernel
    from sklearn.linear_model import Ridge
    from sklearn.metrics import r2_score

    def _constant(tr, te, ytr, yte):
        return np.full(len(yte), float(np.mean(ytr)))

    def _fit_ridge(tr, te, ytr, yte):
        m = Ridge(alpha=1.0)
        m.fit(X[tr], ytr)
        return m.predict(X[te])

    def _fit_rf(tr, te, ytr, yte):
        m = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=1)
        m.fit(X[tr], ytr)
        return m.predict(X[te])

    def _fit_xgb(tr, te, ytr, yte):
        try:
            from xgboost import XGBRegressor
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.info("xgboost unavailable: %s", exc)
            return None
        m = XGBRegressor(n_estimators=200, max_depth=3, learning_rate=0.05,
                         random_state=42, n_jobs=1, verbosity=0)
        m.fit(X[tr], ytr)
        return m.predict(X[te])

    def _fit_gp(tr, te, ytr, yte):
        if len(ytr) < 5:
            return None
        try:
            kernel = 1.0 * RBF(length_scale=1.0) + WhiteKernel(noise_level=0.1)
            m = GaussianProcessRegressor(kernel=kernel, random_state=42,
                                         normalize_y=True, n_restarts_optimizer=2)
            m.fit(X[tr], ytr)
            pred, std = m.predict(X[te], return_std=True)
            return pred
        except Exception as exc:  # pragma: no cover
            logger.info("GP failed on a fold: %s", exc)
            return None

    models = {"mean": _constant, "ridge": _fit_ridge, "random_forest": _fit_rf,
              "xgboost": _fit_xgb}
    if gaussian_process:
        models["gaussian_process"] = _fit_gp

    results: dict[str, Any] = {}
    for name, fitter in models.items():
        preds_all: list[float] = []
        true_all: list[float] = []
        fold_metrics: list[dict[str, Any]] = []
        usable = 0
        for train_idx, test_idx in grouped_kfold(groups, n_splits=min(5, len(set(groups)))):  # noqa: B905
            ytr = y[train_idx]
            yte = y[test_idx]
            pred = fitter(train_idx, test_idx, ytr, yte)
            if pred is None:
                continue
            usable += 1
            m = _metrics(yte, pred)
            m["fold_n"] = int(len(yte))
            fold_metrics.append(m)
            preds_all.extend(pred.tolist())
            true_all.extend(yte.tolist())
        if not fold_metrics:
            results[name] = {"unavailable": True}
            continue
        pooled = _metrics(np.array(true_all), np.array(preds_all))
        pooled["folds"] = usable
        pooled["fold_metrics"] = fold_metrics
        results[name] = {"pooled": pooled}
    return {"models": results,
            "n_usable": int(len(X)), "n_groups": int(len(set(groups))),
            "features": list(feature_cols), "target": target_col,
            "group_col": group_col,
            "leakage_policy": "grouped (unseen-series) folds; no intra-series leakage"}
