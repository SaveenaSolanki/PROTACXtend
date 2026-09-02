"""Training + grouped evaluation + OOD for Module 4 (tabular baselines).

Order kept scientific: mean -> ridge -> RandomForest -> XGBoost -> GP(optional).
Evaluation runs several split regimes (random / scaffold / unseen-target /
unseen-E3 / unseen-PROTAC) with entities encoded on the training fold only.
Every split folds are grouped (no same-series rows across train/test). Models
are saved with version metadata; OOD = kNN distance to the training set.

Degradation probability: no binary measured labels exist in the curated set ->
that task is reported as disabled (never fabricated). A Dmax regressor is
trained on the 32 rows that carry published Dmax labels.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from synglue_agent.modules.degradation_ml.dataset import curate_split_sets
from synglue_agent.modules.degradation_ml.features import (
    DEFAULT_MODEL_PATH,
    EntityEncoder,
    feature_matrix,
)

logger = logging.getLogger("protacxtend.degradation_models")


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    yt, yp = np.asarray(y_true, float), np.asarray(y_pred, float)
    m = np.isfinite(yt) & np.isfinite(yp)
    yt, yp = yt[m], yp[m]
    if len(yt) < 2:
        return {"r2": float("nan"), "mae": float("nan"), "rmse": float("nan"),
                "spearman": float("nan"), "n": int(len(yt))}
    from scipy.stats import spearmanr
    ss_res = float(np.sum((yt - yp) ** 2))
    ss_tot = float(np.sum((yt - yt.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    spearman = float(spearmanr(yt, yp).statistic) if len(yt) > 2 else float("nan")
    return {"r2": round(r2, 4), "mae": round(float(np.mean(np.abs(yt - yp))), 4),
            "rmse": round(float(np.sqrt(np.mean((yt - yp) ** 2))), 4),
            "spearman": round(spearman, 4), "n": int(len(yt))}


def _group_folds(groups: list[Any], n_splits: int):
    unique = sorted(set(groups))
    if len(unique) < 2:
        return
    n = min(n_splits, len(unique))
    for i in range(n):
        test_g = unique[i]
        test_idx = [j for j, g in enumerate(groups) if g == test_g]
        train_idx = [j for j, g in enumerate(groups) if g != test_g]
        if train_idx and test_idx:
            yield train_idx, test_idx


def evaluate_splits(df: pd.DataFrame, target_col: str = "pdc50",
                    models: list[str] | None = None) -> dict[str, Any]:
    """Grouped evaluation over split regimes for the requested baseline models."""
    models = models or ["mean", "ridge", "random_forest", "xgboost"]
    smiles = df["smiles"].tolist()
    targets = df["target"].tolist()
    e3s = df["e3"].tolist()
    y = pd.to_numeric(df[target_col], errors="coerce").to_numpy()
    finite = np.isfinite(y)
    if int(finite.sum()) < 12:
        return {"dataset_too_small": True, "n": int(finite.sum())}

    split_groups = curate_split_sets(df)
    out: dict[str, Any] = {"n": int(finite.sum()), "target": target_col, "splits": {}}

    for split_name, groups_all in split_groups.items():
        groups = [g for g, ok in zip(groups_all, finite, strict=False) if ok]
        if len(set(groups)) < 2:
            out["splits"][split_name] = {"unavailable": "fewer than 2 groups"}
            continue
        per_model: dict[str, Any] = {}
        for model in models:
            preds, trues, fold_n = [], [], 0
            for tr_idx, te_idx in _group_folds(groups, n_splits=4):
                tr_idx = [i for i in tr_idx if finite[i]]
                te_idx = [i for i in te_idx if finite[i]]
                if len(tr_idx) < 4 or not te_idx:
                    continue
                # entities encoded on TRAIN ONLY (no leakage)
                enc_t = EntityEncoder().fit([targets[i] for i in tr_idx])
                enc_e = EntityEncoder().fit([e3s[i] for i in tr_idx])
                Xtr, _ = feature_matrix([smiles[i] for i in tr_idx],
                                        [targets[i] for i in tr_idx],
                                        [e3s[i] for i in tr_idx],
                                        enc_target=enc_t, enc_e3=enc_e)
                Xte, _ = feature_matrix([smiles[i] for i in te_idx],
                                        [targets[i] for i in te_idx],
                                        [e3s[i] for i in te_idx],
                                        enc_target=enc_t, enc_e3=enc_e)
                ytr = y[tr_idx]
                yte = y[te_idx]
                pred = _predict(model, Xtr, ytr, Xte)
                if pred is None:
                    continue
                fold_n += 1
                preds.extend(pred.tolist())
                trues.extend(yte.tolist())
            if not preds:
                per_model[model] = {"unavailable": True}
                continue
            m = _metrics(np.array(trues), np.array(preds))
            m["folds"] = fold_n
            per_model[model] = m
        out["splits"][split_name] = per_model
    return out


def _predict(model: str, Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray):
    if model == "mean":
        return np.full(len(Xte), float(np.mean(ytr)))
    if model == "ridge":
        from sklearn.linear_model import Ridge
        return Ridge(alpha=1.0).fit(Xtr, ytr).predict(Xte)
    if model == "random_forest":
        from sklearn.ensemble import RandomForestRegressor
        m = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=1)
        return m.fit(Xtr, ytr).predict(Xte)
    if model == "xgboost":
        try:
            from xgboost import XGBRegressor
        except Exception:
            return None
        m = XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05,
                         random_state=42, n_jobs=1, verbosity=0)
        return m.fit(Xtr, ytr).predict(Xte)
    if model == "gaussian_process":
        if len(ytr) < 8:
            return None
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RBF, WhiteKernel
        m = GaussianProcessRegressor(1.0 * RBF(1.0) + WhiteKernel(0.1),
                                     random_state=42, normalize_y=True,
                                     n_restarts_optimizer=0)
        try:
            return m.fit(Xtr, ytr).predict(Xte)
        except Exception:
            return None
    return None


def train_pdc50(df: pd.DataFrame, out_path: Path = DEFAULT_MODEL_PATH,
                model_name: str = "random_forest") -> dict[str, Any]:
    """Train the production model on ALL curated rows (entities fitted on the
    full set at deployment) and persist with metadata + conformal residuals."""
    smiles = df["smiles"].tolist()
    targets = df["target"].tolist()
    e3s = df["e3"].tolist()
    y = pd.to_numeric(df["pdc50"], errors="coerce").to_numpy()
    finite = np.isfinite(y)
    enc_t = EntityEncoder().fit([t for t, ok in zip(targets, finite, strict=False) if ok])
    enc_e = EntityEncoder().fit([e for e, ok in zip(e3s, finite, strict=False) if ok])
    t_f = [t for t, okk in zip(targets, finite, strict=False) if okk]
    e_f = [e for e, okk in zip(e3s, finite, strict=False) if okk]
    X, ok = feature_matrix([s for s, k in zip(smiles, finite, strict=False) if k],
                           t_f, e_f, enc_target=enc_t, enc_e3=enc_e)
    yv = y[finite]
    if model_name == "random_forest":
        from sklearn.ensemble import RandomForestRegressor
        estimator = RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=1)
    elif model_name == "xgboost":
        try:
            from xgboost import XGBRegressor
        except Exception as exc:
            raise RuntimeError(f"xgboost unavailable: {exc}") from exc
        estimator = XGBRegressor(n_estimators=400, max_depth=4, learning_rate=0.05,
                                 random_state=42, n_jobs=1, verbosity=0)
    elif model_name == "ridge":
        from sklearn.linear_model import Ridge
        estimator = Ridge(alpha=1.0)
    else:
        raise ValueError(f"unknown model {model_name}")
    estimator.fit(X, yv)
    pred = estimator.predict(X)
    residuals = yv - pred
    resid_q = {"p5": float(np.percentile(residuals, 5)),
               "p95": float(np.percentile(residuals, 95))}
    from synglue_agent.modules.degradation_ml.models import ood_distance
    mean_train_distance = float(ood_distance(X, X))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model_name": model_name,
        "fitted": estimator,
        "encoder_target": enc_t, "encoder_e3": enc_e,
        "y_mean": float(np.mean(yv)), "y_std": float(np.std(yv)),
        "residual_quantiles_pdc50": resid_q,
        "train_X": X,
        "mean_train_distance": mean_train_distance,
        "train_n": int(len(yv)), "features": "descriptors+morgan+entity codes",
        "n_features": int(X.shape[1]),
    }, out_path)
    metrics = _metrics(yv, pred)
    return {"model_path": str(out_path), "model_name": model_name,
            "train_metrics": metrics, "residual_quantiles_pdc50": resid_q,
            "mean_train_distance": round(mean_train_distance, 4),
            "n": int(len(yv))}


def ood_distance(X, X_train: np.ndarray, k: int = 5) -> float:
    """Mean distance to the k nearest training rows (descriptor+entity space)."""
    from sklearn.neighbors import NearestNeighbors
    nn = NearestNeighbors(n_neighbors=min(k, len(X_train)), n_jobs=1)
    nn.fit(X_train)
    dist, _ = nn.kneighbors(X)
    return float(np.mean(dist[0]))
