"""Module 5 — baseline models, grouped-split evaluation and ablations.

Endpoints (each trained on its own measured rows; missing endpoints never
fabricated, they just don't contribute to that task):
  * pdc50  (log10 DC50 molar)     rows with measured DC50
  * dmax   (percent)              rows with measured Dmax
  * derived_active (0/1)          rows where the documented AND rule decides
                                  (threshold-derived; classification metrics
                                  AUROC/AUPRC only, never "measured prob")

Split regimes (all grouped; encoders fit on train folds only):
  random, unseen_protac, scaffold, unseen_target, unseen_e3, unseen_cell_line,
  unseen_protac_and_cell (where sample size permits)

Model order: global mean -> cell-line mean -> ridge -> elastic net ->
RandomForest -> ExtraTrees -> XGBoost (CatBoost when importable).

Evaluators return pooled metrics over test folds: R2/MAE/RMSE/Spearman/Pearson
for regression and AUROC/AUPRC for classification, plus per-split n.
"""

from __future__ import annotations

import itertools
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, KFold

logger = logging.getLogger("protacxtend.cell_context_models")


# ---------------------------------------------------------------- metrics ----
def _pearson(x, y) -> float:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def regression_metrics(y_true, y_pred) -> dict[str, Any]:
    yt = np.asarray(y_true, float)
    yp = np.asarray(y_pred, float)
    m = np.isfinite(yt) & np.isfinite(yp)
    yt, yp = yt[m], yp[m]
    if len(yt) < 2:
        return {"r2": np.nan, "mae": np.nan, "rmse": np.nan,
                "spearman": np.nan, "pearson": np.nan, "n": int(len(yt))}
    ss_res = float(np.sum((yt - yp) ** 2))
    ss_tot = float(np.sum((yt - yt.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    from scipy.stats import spearmanr
    sp = float(spearmanr(yt, yp).statistic) if len(yt) > 2 else float("nan")
    return {"r2": round(r2, 4), "mae": round(float(np.mean(np.abs(yt - yp))), 4),
            "rmse": round(float(np.sqrt(np.mean((yt - yp) ** 2))), 4),
            "spearman": round(sp, 4), "pearson": round(_pearson(yt, yp), 4),
            "n": int(len(yt))}


def classification_metrics(y_true, y_score) -> dict[str, Any]:
    yt = np.asarray(y_true, int)
    ys = np.asarray(y_score, float)
    m = np.isfinite(ys) & (yt >= 0)
    yt, ys = yt[m], ys[m]
    if len(np.unique(yt)) < 2 or len(yt) < 5:
        return {"auroc": np.nan, "auprc": np.nan, "n": int(len(yt)),
                "pos": int(yt.sum())}
    from sklearn.metrics import average_precision_score, roc_auc_score
    return {"auroc": round(float(roc_auc_score(yt, ys)), 4),
            "auprc": round(float(average_precision_score(yt, ys)), 4),
            "n": int(len(yt)), "pos": int(yt.sum())}


# -------------------------------------------------------------- models ------
def _make_model(name: str, cfg: dict):
    if name == "mean":
        return None
    if name == "cell_mean":
        return None  # handled specially
    if name == "ridge":
        from sklearn.linear_model import Ridge
        return Ridge(alpha=cfg.get("ridge_alpha", 1.0))
    if name == "elasticnet":
        from sklearn.linear_model import ElasticNet
        return ElasticNet(alpha=cfg.get("en_alpha", 0.01),
                          l1_ratio=cfg.get("en_l1", 0.5),
                          max_iter=2000, random_state=42)
    if name == "random_forest":
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor(
            n_estimators=cfg.get("n_estimators", 250), random_state=42,
            n_jobs=cfg.get("n_jobs", 1), min_samples_leaf=cfg.get("min_leaf", 2))
    if name == "extra_trees":
        from sklearn.ensemble import ExtraTreesRegressor
        return ExtraTreesRegressor(
            n_estimators=cfg.get("n_estimators", 250), random_state=42,
            n_jobs=cfg.get("n_jobs", 1), min_samples_leaf=cfg.get("min_leaf", 2))
    if name == "xgboost":
        try:
            from xgboost import XGBRegressor
            return XGBRegressor(n_estimators=cfg.get("n_estimators", 250),
                                max_depth=cfg.get("xgb_depth", 5),
                                learning_rate=cfg.get("xgb_lr", 0.05),
                                random_state=42, n_jobs=cfg.get("n_jobs", 1),
                                verbosity=0)
        except Exception:
            return None
    if name == "catboost":
        try:
            from catboost import CatBoostRegressor
            return CatBoostRegressor(iterations=cfg.get("n_estimators", 250),
                                     depth=6, learning_rate=0.05,
                                     random_seed=42, verbose=False,
                                     thread_count=cfg.get("n_jobs", 1))
        except Exception:
            return None
    if name == "logistic":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(C=1.0, max_iter=2000)
    if name == "rf_classifier":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            n_estimators=cfg.get("n_estimators", 250), random_state=42,
            n_jobs=cfg.get("n_jobs", 1), min_samples_leaf=2)
    return None


def _is_linear(est) -> bool:
    return est.__class__.__name__ in ("Ridge", "ElasticNet",
                                      "LogisticRegression")


# ------------------------------------------------------------ splits ---------
def split_folds(rows: pd.DataFrame, regime: str, n_splits: int,
                seed: int = 42) -> list[tuple[np.ndarray, np.ndarray]]:
    """Deterministic grouped fold index pairs for a regime.

    Returns list of (train_idx, test_idx). For LOO regimes (unseen_e3) returns
    one fold per group value. For unseen_protac_and_cell uses cells as the
    held-out axis and excludes the test compounds from training.
    """
    rng = np.random.RandomState(seed)
    idx = np.arange(len(rows))
    if regime == "random":
        kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
        return [(tr, te) for tr, te in kf.split(idx)]
    groups = {
        "unseen_protac": rows["protac_smiles_canonical"].fillna("unknown"),
        "scaffold": rows["protac_smiles_canonical"].fillna("unknown").map(
            lambda s: murcko(s)),
        "unseen_target": rows["target"].fillna("unknown"),
        "unseen_cell_line": rows["cell_line_raw"].fillna("unknown"),
    }
    if regime in groups:
        g = groups[regime].to_numpy()
        gkf = GroupKFold(n_splits=n_splits)
        return [(tr, te) for tr, te in gkf.split(idx, groups=g)]
    if regime == "unseen_e3":
        vals = sorted(set(rows["e3"].tolist()))
        folds = []
        for v in vals:
            te = np.where(rows["e3"].to_numpy() == v)[0]
            tr = np.where(rows["e3"].to_numpy() != v)[0]
            if len(tr) > 0 and len(te) > 0:
                folds.append((tr, te))
        return folds
    if regime == "unseen_protac_and_cell":
        return _dual_unseen_folds(rows, n_splits, rng)
    raise ValueError(f"unknown regime {regime}")


def murcko(smiles: str) -> str:
    from synglue_agent.modules.degradation_ml.features import murcko_group
    try:
        return murcko_group(smiles)
    except Exception:
        return "na"


def _dual_unseen_folds(rows: pd.DataFrame, n_splits: int,
                       rng: np.random.RandomState):
    """Test rows have unseen cell lines AND their compounds never appear in
    train (sample-size permitting). Cells with >=8 rows are candidates."""
    cells = rows["cell_line_raw"].value_counts()
    cands = [c for c, n in cells.items() if n >= 8]
    if len(cands) < 2:
        return []
    rng.shuffle(cands)
    folds = []
    per_fold = max(1, int(np.ceil(len(cands) / n_splits)))
    for i in range(0, len(cands), per_fold):
        test_cells = cands[i:i + per_fold]
        te_mask = rows["cell_line_raw"].isin(test_cells)
        te_compounds = set(rows.loc[te_mask, "protac_smiles_canonical"])
        tr_mask = (~te_mask) & (~rows["protac_smiles_canonical"].isin(
            te_compounds))
        te = np.where(te_mask.to_numpy())[0]
        tr = np.where(tr_mask.to_numpy())[0]
        if len(te) >= 20 and len(tr) >= 50:
            folds.append((tr, te))
    return folds


# ------------------------------------------------------------ pipeline ------
class Evaluator:
    """Grouped-split evaluator for one endpoint + one feature leg."""

    def __init__(self, endpoint: str, leg: str, cfg: dict | None = None) -> None:
        self.endpoint = endpoint
        self.leg = leg
        self.cfg = cfg or dict(n_estimators=200, n_jobs=4, n_splits=5)

    # -- row universe for the endpoint ---------------------------------------
    def universe(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.endpoint == "pdc50":
            out = df[df["has_dc50"] == 1].copy()
        elif self.endpoint == "dmax":
            out = df[df["has_dmax"] == 1].copy()
        elif self.endpoint == "derived_active":
            out = df[df["derived_active_defined"] == 1].copy()
        else:
            raise ValueError(self.endpoint)
        # expression legs are only meaningful where a transcriptomic profile
        # exists for the cell line (no fabricated context)
        if self.leg == "D":
            out = out[out["has_expression"] == 1]
        return out.reset_index(drop=True)

    def _fit_predict(self, model_name: str, Xtr, ytr, Xte,
                     cell_tr, cell_te) -> np.ndarray:
        if model_name == "mean":
            return np.full(len(Xte), float(np.mean(ytr)))
        if model_name == "cell_mean":
            return _cell_mean_predict(ytr, cell_tr, cell_te)
        est = _make_model(model_name, self.cfg)
        if est is None:
            return np.full(len(Xte), float(np.nan))
        if _is_linear(est):
            from sklearn.preprocessing import StandardScaler
            sc = StandardScaler().fit(Xtr)
            Xtr_s, Xte_s = sc.transform(Xtr), sc.transform(Xte)
            if self.endpoint == "derived_active":
                est.fit(Xtr_s, ytr)
                return est.predict_proba(Xte_s)[:, 1]
            est.fit(Xtr_s, ytr)
            return est.predict(Xte_s)
        if self.endpoint == "derived_active":
            est.fit(Xtr, ytr)
            return est.predict_proba(Xte)[:, 1]
        est.fit(Xtr, ytr)
        return est.predict(Xte)

    def evaluate_regime(self, df: pd.DataFrame, model: str,
                        regime: str) -> dict[str, Any]:
        rows = self.universe(df)
        folds = split_folds(rows, regime, self.cfg.get("n_splits", 5))
        if not folds:
            return {"unavailable": "no valid folds", "n": 0}
        preds, trues = [], []
        y = (rows["derived_active"].astype(float) if
             self.endpoint == "derived_active" else
             rows[{"pdc50": "pdc50", "dmax": "dmax_pct"}[self.endpoint]]
             .to_numpy())
        expr = _expression()
        molc = _mol_cache()
        from synglue_agent.modules.cell_context_selector import features as F
        for tr, te in folds:
            tr_df = rows.iloc[tr]
            te_df = rows.iloc[te]
            enc = F.fit_encoders(tr_df, self.leg)
            Xtr, _ = F.build_row_features(
                tr_df, self.leg, molc, expr,
                enc_target=enc.get("enc_target"), enc_e3=enc.get("enc_e3"),
                enc_cell=enc.get("enc_cell"), lin_enc=enc.get("lin_enc"))
            Xte, _ = F.build_row_features(
                te_df, self.leg, molc, expr,
                enc_target=enc.get("enc_target"), enc_e3=enc.get("enc_e3"),
                enc_cell=enc.get("enc_cell"), lin_enc=enc.get("lin_enc"))
            if self.leg == "D":
                Xtr, Xte = _impute(Xtr, Xte)
            ytr = y[tr]
            yte = y[te]
            p = self._fit_predict(model, Xtr, ytr, Xte,
                                  tr_df["cell_line_raw"].tolist(),
                                  te_df["cell_line_raw"].tolist())
            preds.extend(p.tolist())
            trues.extend(yte.tolist())
        if self.endpoint == "derived_active":
            m = classification_metrics(np.array(trues), np.array(preds))
        else:
            m = regression_metrics(np.array(trues), np.array(preds))
        m["folds"] = len(folds)
        return m


def _cell_mean_predict(ytr, cell_tr, cell_te) -> np.ndarray:
    means = {}
    for c, v in zip(cell_tr, ytr, strict=False):
        means.setdefault(c, []).append(v)
    out = []
    for c in cell_te:
        if c in means and len(means[c]) >= 2:
            out.append(float(np.mean(means[c])))
        else:
            out.append(float(np.mean(ytr)))
    return np.array(out)


_cell_mean_cache: dict = {}


def _expression():
    global _cell_mean_cache
    if "expr" not in _cell_mean_cache:
        from synglue_agent.modules.cell_context_selector import omics
        _cell_mean_cache["expr"] = omics.ensure_curated_expression()
    return _cell_mean_cache["expr"]


def _mol_cache():
    global _cell_mean_cache
    if "mol" not in _cell_mean_cache:
        from synglue_agent.modules.cell_context_selector.features import MolCache
        _cell_mean_cache["mol"] = MolCache()
    return _cell_mean_cache["mol"]


def _impute(Xtr, Xte) -> tuple[np.ndarray, np.ndarray]:
    from sklearn.impute import SimpleImputer
    imp = SimpleImputer(strategy="median")
    imp.fit(Xtr)
    return imp.transform(Xtr), imp.transform(Xte)


# ------------------------------------------------------------ ablations -----
def run_ablation(df: pd.DataFrame, endpoint: str = "pdc50",
                 legs: Sequence[str] = ("A", "B", "C", "D"),
                 regimes: Sequence[str] = ("random", "unseen_protac",
                                           "unseen_cell_line"),
                 models: Sequence[str] = ("ridge", "random_forest"),
                 cfg: dict | None = None) -> dict[str, Any]:
    """Incremental-value ablation on the matched D-eligible universe."""
    rows = prepare_rows(df)
    elig = rows[rows["has_expression"] == 1].copy()
    out = {"endpoint": endpoint, "universe": "rows with transcriptomic context",
           "n": int(len(elig)), "regimes": list(regimes), "legs": list(legs),
           "results": {}}
    for leg in legs:
        if leg not in ("A", "B", "C", "D"):
            continue
        ev = Evaluator(endpoint, leg, cfg)
        leg_rows = elig if leg == "D" else elig  # matched universe for fairness
        for regime in regimes:
            for model in models:
                key = f"{leg}|{regime}|{model}"
                m = ev.evaluate_regime(leg_rows, model, regime)
                out["results"][key] = m
    return out


def prepare_rows(df: pd.DataFrame) -> pd.DataFrame:
    from synglue_agent.modules.cell_context_selector import prepare
    return prepare.enrich(df)
