"""Experimental cooperativity calibration (Module 3, post-curation).

The curated ``data/cooperativity_records.csv`` now contains real, DOI-cited
ternary-cooperativity records (alpha = Kd2/Kd2(ternary); see the curation
script). This module:

  1. reports the alpha distribution and coverage (overall, per E3, per arm,
     per affinity basis);
  2. fits a deliberately small ridge model on the unambiguous E3-arm subset
     and evaluates it with grouped cross-validation (unseen POI / unseen
     PROTAC);
  3. exposes an honest ``empirical_alpha`` lookup with a strict evidence
     hierarchy: measured pair -> E3 prior -> global prior -> gated model.

It never claims experimental calibration for a POI-E3 combination that has no
measured record. Predictions for E3s absent from the curated data are refused.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from protacxtend.modules.cooperativity_alpha_predictor.data import load_records

MODULE_DIR = Path(__file__).resolve().parent
REPORT_JSON = MODULE_DIR / "data" / "calibration_report.json"

FEATURES = ["log10_kd_e3", "is_crbn", "is_ciap1", "is_kd"]
MIN_PAIR_N = 1
MIN_E3_N = 2
MIN_GLOBAL_N = 5


def _featurize(df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    X["log10_kd_e3"] = np.log10(pd.to_numeric(df["kd_binary_e3_nM"], errors="coerce"))
    X["is_crbn"] = (df["e3"].astype(str) == "CRBN").astype(float)
    X["is_ciap1"] = (df["e3"].astype(str) == "cIAP1").astype(float)
    X["is_kd"] = df["notes"].astype(str).str.contains("affinity_basis=Kd").astype(float)
    return X


def _headline(df: pd.DataFrame) -> pd.DataFrame:
    """Unambiguous E3-arm, positive-alpha records used for the headline fit."""
    if df.empty:
        return df
    return df[df["notes"].astype(str).str.contains("alpha_arm=e3_assay_described")]


def _dist(alpha: pd.Series) -> dict[str, Any]:
    a = pd.to_numeric(alpha, errors="coerce").dropna()
    if a.empty:
        return {"n": 0}
    loga = np.log(a[a > 0])
    return {
        "n": int(len(a)),
        "median_alpha": round(float(a.median()), 4),
        "q1_alpha": round(float(a.quantile(0.25)), 4),
        "q3_alpha": round(float(a.quantile(0.75)), 4),
        "min_alpha": round(float(a.min()), 4),
        "max_alpha": round(float(a.max()), 4),
        "mean_log_alpha": round(float(loga.mean()), 4),
        "std_log_alpha": round(float(loga.std(ddof=1)), 4) if len(loga) > 1 else None,
        "frac_positive": round(float((a > 1.25).mean()), 4),
        "frac_neutral": round(float(((a >= 0.8) & (a <= 1.25)).mean()), 4),
        "frac_negative": round(float((a < 0.8).mean()), 4),
    }


def _metrics(y_true, y_pred) -> dict[str, float]:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    m = np.isfinite(yt) & np.isfinite(yp)
    yt, yp = yt[m], yp[m]
    if len(yt) < 2:
        return {"n": int(len(yt)), "r2": float("nan"), "mae": float("nan"),
                "rmse": float("nan"), "spearman": float("nan")}
    ss_res = float(np.sum((yt - yp) ** 2))
    ss_tot = float(np.sum((yt - yt.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))
    mae = float(np.mean(np.abs(yt - yp)))
    sp = float(pd.Series(yt).corr(pd.Series(yp), method="spearman"))
    return {"n": int(len(yt)), "r2": round(r2, 4), "mae": round(mae, 4),
            "rmse": round(rmse, 4), "spearman": round(sp, 4)}


def fit_calibration(df: pd.DataFrame | None = None,
                    save: bool = True) -> dict[str, Any]:
    """Fit/evaluate the calibration and return the full report dict."""
    if df is None:
        df = load_records()
    report: dict[str, Any] = {"n_records": int(len(df))}
    if df.empty:
        report["status"] = "NO_DATA"
        return report

    report["overall_distribution"] = _dist(df["alpha"])
    report["by_e3"] = {e: _dist(g["alpha"]) for e, g in df.groupby("e3")}
    report["by_arm"] = {
        "e3_assay_described": _dist(df[df["notes"].str.contains(
            "alpha_arm=e3_assay_described")]["alpha"]),
        "ambiguous": _dist(df[df["notes"].str.contains(
            "alpha_arm=ambiguous")]["alpha"]),
    }
    report["by_basis"] = {
        b: _dist(df[df["notes"].str.contains(f"affinity_basis={b}")]["alpha"])
        for b in ("Kd", "Ki")}
    report["coverage"] = {
        "n_e3s": int(df["e3"].nunique()),
        "n_pois": int(df["poi"].nunique()),
        "n_poi_e3_pairs": int(df.groupby(["poi", "e3"]).ngroups),
        "e3s_with_ge2": [e for e, g in df.groupby("e3") if len(g) >= MIN_E3_N],
    }

    # ---- model fit on the unambiguous E3-arm subset ----------------------
    head = _headline(df)
    report["headline_n"] = int(len(head))
    if len(head) < 6:
        report["model"] = {"status": "TOO_SMALL",
                           "note": f"n={len(head)} unambiguous records; prior "
                                   "lookup only, no fitted model claimed"}
        if save:
            REPORT_JSON.write_text(json.dumps(report, indent=2, default=str))
        return report

    from sklearn.linear_model import Ridge
    X = _featurize(head).to_numpy(dtype=float)
    y = head["log_alpha"].to_numpy(dtype=float)

    # grouped leave-one-POI-out and leave-one-PROTAC-out CV
    def grouped_cv(groups: list[str]) -> dict[str, Any]:
        preds = np.full(len(y), np.nan)
        for g in sorted(set(groups)):
            te = np.array([i for i, x in enumerate(groups) if x == g])
            tr = np.array([i for i, x in enumerate(groups) if x != g])
            if len(te) == 0 or len(tr) < 4:
                continue
            model = Ridge(alpha=1.0).fit(X[tr], y[tr])
            preds[te] = model.predict(X[te])
        ok = np.isfinite(preds)
        return {
            "n_test": int(ok.sum()),
            "metrics": _metrics(y[ok], preds[ok]),
            "baseline_mean_metrics": _metrics(y[ok], np.full(ok.sum(), y[ok].mean())),
            "n_groups": len(set(groups)),
        }

    poi_cv = grouped_cv(head["poi"].astype(str).tolist())
    protac_cv = grouped_cv(head["protac_id"].astype(str).tolist())

    model = Ridge(alpha=1.0).fit(X, y)
    resid = y - model.predict(X)
    cv_r2 = poi_cv["metrics"].get("r2")
    model_usable = bool(cv_r2 is not None and np.isfinite(cv_r2) and cv_r2 > 0.05)
    report["model"] = {
        "status": "FIT",
        "kind": "ridge_log_alpha",
        "features": FEATURES,
        "n_train": int(len(y)),
        "coefficients": {f: round(float(c), 5)
                         for f, c in zip(FEATURES, model.coef_)},
        "intercept": round(float(model.intercept_), 5),
        "residual_std_log_alpha": round(float(np.std(resid, ddof=1)), 4),
        "train_r2": _metrics(y, model.predict(X))["r2"],
        "cv_unseen_poi": poi_cv,
        "cv_unseen_protac": protac_cv,
        "baseline": {
            "global_mean_log_alpha": round(float(y.mean()), 4),
            "global_std_log_alpha": round(float(y.std(ddof=1)), 4),
        },
        "model_usable": model_usable,
        "claim_gate": ("model is used ONLY for E3s present in the curated data; "
                       "pairs without measured records are reported as prior/"
                       "uncalibrated"),
    }
    report["status"] = "CALIBRATED_LIMITED" if model_usable else "PRIOR_ONLY"
    report["conclusion"] = (
        "A fitted model beats the mean baseline on unseen-POI grouped CV."
        if model_usable else
        "The fitted model does NOT beat the mean baseline on grouped CV; "
        "cooperativity is therefore served as measured-pair / E3-prior / "
        "global-prior lookups, and no trained-model alpha is claimed.")
    if save:
        REPORT_JSON.write_text(json.dumps(report, indent=2, default=str))
    return report


def empirical_alpha(poi: str | None = None, e3: str | None = None,
                    kd_binary_e3_nM: float | None = None,
                    df: pd.DataFrame | None = None) -> dict[str, Any]:
    """Evidence-ordered cooperativity estimate for a POI/E3 combination.

    Hierarchy: measured_pair > e3_prior > global_prior > model_predicted.
    Returns ``available=False`` for E3s with no curated records.
    """
    if df is None:
        df = load_records()
    if df.empty:
        return {"available": False, "reason": "no curated cooperativity records"}
    out: dict[str, Any] = {"poi": poi, "e3": e3, "available": False}
    sub = df
    if poi:
        p = sub[sub["poi"].astype(str).str.upper() == str(poi).upper()]
    else:
        p = sub.iloc[0:0]
    if e3:
        sub = sub[sub["e3"].astype(str).str.upper() == str(e3).upper()]
    if e3 and sub.empty:
        out["reason"] = (f"no measured cooperativity records for E3={e3}; "
                         "no experimental calibration claimed")
        return out
    pair = p[p["e3"].astype(str).str.upper() == str(e3).upper()] if (e3 and poi) else p.iloc[0:0]

    def _pack(d: pd.Series, level: str, note: str) -> dict[str, Any]:
        a = float(d["alpha"])
        loga = math.log(a) if a > 0 else None
        return {"available": True, "evidence_level": level, "alpha": round(a, 4),
                "log_alpha": None if loga is None else round(loga, 4),
                "cooperativity_class": ("positive" if a > 1.25 else
                                        "negative" if a < 0.8 else
                                        "approximately_neutral"),
                "note": note}

    if len(pair) >= MIN_PAIR_N:
        return {"available": True, "evidence_level": "measured_pair",
                "alpha": round(float(pair["alpha"].median()), 4),
                "log_alpha": round(float(pair["log_alpha"].median()), 4),
                "n_measurements": int(len(pair)),
                "confidence": round(min(0.85, 0.45 + 0.025 * len(pair)), 3),
                "distribution": _dist(pair["alpha"]),
                "cooperativity_class": (
                    "positive" if pair["alpha"].median() > 1.25 else
                    "negative" if pair["alpha"].median() < 0.8 else
                    "approximately_neutral"),
                "poi": poi, "e3": e3,
                "sources": sorted(set(pair["doi"].dropna().astype(str)))[:6],
                "note": f"{len(pair)} measured record(s) for this POI-E3 pair"}
    if e3 and len(sub) >= MIN_E3_N:
        return {"available": True, "evidence_level": "e3_prior",
                "alpha": round(float(sub["alpha"].median()), 4),
                "log_alpha": round(float(sub["log_alpha"].median()), 4),
                "n_measurements": int(len(sub)),
                "confidence": round(min(0.6, 0.25 + 0.02 * len(sub)), 3),
                "distribution": _dist(sub["alpha"]),
                "cooperativity_class": (
                    "positive" if sub["alpha"].median() > 1.25 else
                    "negative" if sub["alpha"].median() < 0.8 else
                    "approximately_neutral"),
                "poi": poi, "e3": e3,
                "sources": sorted(set(sub["doi"].dropna().astype(str)))[:6],
                "note": f"{len(sub)} measured records for E3={e3} across POIs; "
                        "POI-specific alpha not measured"}

    # global prior (not calibrated to any E3)
    rep = fit_calibration(df, save=False).get("overall_distribution", {})
    if rep.get("n", 0) >= MIN_GLOBAL_N:
        return {"available": True, "evidence_level": "global_prior",
                "alpha": rep.get("median_alpha"),
                "log_alpha": rep.get("mean_log_alpha"),
                "n_measurements": rep.get("n"),
                "confidence": 0.25,
                "distribution": rep, "poi": poi, "e3": e3,
                "cooperativity_class": (
                    "positive" if (rep.get("median_alpha") or 1) > 1.25 else
                    "negative" if (rep.get("median_alpha") or 1) < 0.8 else
                    "approximately_neutral"),
                "note": "global prior over all measured cooperativity records; "
                        "NOT calibrated to this E3"}
    out["reason"] = "insufficient measured cooperativity records"
    return out


def calibration_summary() -> dict[str, Any]:
    if REPORT_JSON.exists():
        return json.loads(REPORT_JSON.read_text())
    return fit_calibration(save=True)


if __name__ == "__main__":
    import sys
    rep = fit_calibration(save=True)
    print(json.dumps(rep, indent=2, default=str)[:4000])
    sys.exit(0)
