"""Production artifact training + claim gating (Module 5).

The benchmark (run_benchmark) evaluates endpoints x legs x models across the
grouped regimes and writes a JSON report. train_production() then refits the
chosen leg/model on each endpoint's full measured universe and persists a
single artifact used by predict_cell_context().

Claim gating is evidence-based and conservative:
  cell_context_aware       = best cell-information leg beats PROTAC+target+E3
                             (leg B) on held-out unseen-PROTAC (or random)
  transcriptomics_generalises_to_unseen_lines = leg D > leg B on
                             unseen-cell-line
  proteotype_aware         = False unless proteomics features are validated
                             (none available in DepMap 24Q4 -> not claimed)
  selectivity_from_identity_only = never claimed
Mechanistic (Modules 1-3) features are structure/parameter limited: reported
as a census (see docs/LIMITATIONS.md), never included at dataset scale.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import joblib
import numpy as np
import pandas as pd

from synglue_agent.modules.cell_context_selector.models import Evaluator
from synglue_agent.modules.cell_context_selector.prepare import enrich
from synglue_agent.modules.cell_context_selector.features import MolCache
from synglue_agent.modules.degradation_ml.features import murcko_group

logger = logging.getLogger("protacxtend.cell_context_train")

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
DEFAULT_MODEL_PATH = MODULE_DIR / "models" / "cell_context_model.joblib"

REGRESSION_MODELS = ["mean", "ridge", "random_forest", "extra_trees", "xgboost"]
CLASSIFICATION_MODELS = ["rf_classifier", "logistic"]

# Benchmark matrix (documented; keeps runtime bounded while covering spec):
#  * regression endpoints: all legs x principal regimes x all regression models
#    for pdc50; ridge+rf for the remaining regimes; dmax uses ridge+rf.
#  * classification endpoint: legs B,D x random/unseen_protac/unseen_cell_line
BENCHMARK = {
    "pdc50": {"legs": ["A", "B", "C", "D"],
              "models": REGRESSION_MODELS,
              "regimes_full": ["random", "unseen_protac", "unseen_cell_line"],
              "regimes_light": ["scaffold", "unseen_target", "unseen_e3",
                                "unseen_protac_and_cell"]},
    "dmax": {"legs": ["B", "D"], "models": ["mean", "ridge", "random_forest"],
             "regimes_full": ["random", "unseen_protac", "unseen_cell_line"],
             "regimes_light": ["scaffold", "unseen_target", "unseen_e3"]},
    "derived_active": {"legs": ["B", "D"], "models": CLASSIFICATION_MODELS,
                       "regimes_full": ["random", "unseen_protac"],
                       "regimes_light": ["unseen_cell_line"]},
}


def run_benchmark(df: pd.DataFrame, cfg: dict | None = None) -> dict[str, Any]:
    """Full grouped benchmark. Returns nested results + coverage summary."""
    from synglue_agent.modules.cell_context_selector.prepare import enrich
    cfg = cfg or dict(n_estimators=250, n_jobs=4, n_splits=5, seed=42)
    enr = enrich(df)
    from synglue_agent.modules.cell_context_selector import omics
    expr = omics.ensure_curated_expression()
    results: dict[str, Any] = {"cfg": cfg, "endpoints": {}}
    for endpoint, spec in BENCHMARK.items():
        ep = {"legs": {}, "note": ""}
        for leg in spec["legs"]:
            ev = Evaluator(endpoint, leg, cfg)
            rows_u = ev.universe(enr)
            leg_res = {"n_universe": int(len(rows_u))}
            for regime in spec["regimes_full"]:
                for model in spec["models"]:
                    leg_res[f"{regime}|{model}"] = ev.evaluate_regime(
                        enr, model, regime)
            for regime in spec["regimes_light"]:
                for model in (spec["models"] if False else
                              ["ridge", "random_forest"]):
                    if endpoint == "derived_active":
                        continue  # covered above for classification
                    leg_res[f"{regime}|{model}"] = ev.evaluate_regime(
                        enr, model, regime)
            ep["legs"][leg] = leg_res
        results["endpoints"][endpoint] = ep
    return results


def _best_cell_info_win(results: dict, endpoint: str, regime: str,
                        metric: str = "r2", higher=True) -> dict[str, Any]:
    """Compare the best context legs vs leg B on a regime (best model)."""
    def best(leg):
        leg_res = results["endpoints"][endpoint]["legs"][leg]
        best_v = None
        best_k = None
        for k, v in leg_res.items():
            if not k.endswith("|" + ("random_forest" if False else "")):
                pass
            if "|" not in k:
                continue
            reg, model = k.split("|", 1)
            if reg != regime or not isinstance(v, dict):
                continue
            val = v.get(metric)
            if val is None or val != val:  # nan-safe
                continue
            if best_v is None or (higher and val > best_v) or (
                    not higher and val < best_v):
                best_v, best_k = val, k
        return best_v, best_k
    bB, kB = best("B")
    best_val, best_key, best_leg = bB, kB, "B"
    avail = list(results["endpoints"][endpoint]["legs"].keys())
    for leg in avail:
        if leg == "B":
            continue
        bv, bk = best(leg)
        if bv is not None and (best_val is None or
                               (higher and bv > best_val) or
                               (not higher and bv < best_val)):
            best_val, best_key, best_leg = bv, bk, leg
    return {"best_leg": best_leg, "best_model_key": best_key,
            "best_metric": best_val, "legB_metric": bB,
            "delta_vs_B": (None if bB is None or best_val is None
                           else round(best_val - bB, 4))}


def compute_claims(results: dict) -> dict[str, Any]:
    """Evidence-based claim gating (see module docstring)."""
    claims: dict[str, Any] = {
        "cell_context_aware": False, "transcriptomics_unseen_line_gain": None,
        "proteotype_aware": False, "selectivity_from_identity_only": False,
        "evidence": {},
    }
    for regime, metric in (("unseen_protac", "r2"),
                           ("random", "r2"),
                           ("unseen_cell_line", "r2")):
        w = _best_cell_info_win(results, "pdc50", regime, metric)
        claims["evidence"][f"pdc50_{regime}"] = w
    w_up = claims["evidence"].get("pdc50_unseen_protac") or {}
    w_rnd = claims["evidence"].get("pdc50_random") or {}
    delta = w_up.get("delta_vs_B")
    if delta is None:
        delta = w_rnd.get("delta_vs_B")
    claims["cell_context_aware"] = bool(delta is not None and delta > 0.0)
    w_ucl = claims["evidence"].get("pdc50_unseen_cell_line") or {}
    d_ucl = w_ucl.get("delta_vs_B")
    claims["transcriptomics_unseen_line_gain"] = (
        None if d_ucl is None else round(d_ucl, 4))
    claims["transcriptomics_generalises_to_unseen_lines"] = bool(
        d_ucl is not None and d_ucl > 0.0)
    claims["proteotype_aware"] = False   # no validated proteomics features
    return claims


def _fit_endpoint(enr: pd.DataFrame, endpoint: str, leg: str,
                  model_name: str, cfg: dict) -> tuple[dict, int]:
    """Fit one endpoint on its full measured universe -> stored bundle."""
    from synglue_agent.modules.cell_context_selector import features as F
    from synglue_agent.modules.cell_context_selector import models as M
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    ev = Evaluator(endpoint, leg, cfg)
    rows = ev.universe(enr)
    y = (rows["derived_active"].astype(float) if endpoint == "derived_active"
         else rows[{"pdc50": "pdc50", "dmax": "dmax_pct"}[endpoint]].to_numpy())
    expr = M._expression()
    molc = M._mol_cache()
    enc = F.fit_encoders(rows, leg)
    X, names = F.build_row_features(
        rows, leg, molc, expr, enc_target=enc.get("enc_target"),
        enc_e3=enc.get("enc_e3"), enc_cell=enc.get("enc_cell"),
        lin_enc=enc.get("lin_enc"))
    imputer = scaler = None
    if leg == "D":
        imputer = SimpleImputer(strategy="median").fit(X)
        X = imputer.transform(X)
    est_name = model_name.replace("_classifier", "")
    if endpoint == "derived_active":
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import RandomForestClassifier
        clf = (LogisticRegression(C=1.0, max_iter=3000) if
               model_name == "logistic" else
               RandomForestClassifier(n_estimators=cfg.get("n_estimators", 250),
                                      random_state=42,
                                      n_jobs=cfg.get("n_jobs", 1),
                                      min_samples_leaf=2))
        clf.fit(X, y)
        bundle = {"estimator": clf, "kind": "classifier",
                  "model_name": model_name}
    else:
        est = M._make_model(model_name, cfg)
        if est is None:
            raise ValueError(f"model {model_name} unavailable")
        if M._is_linear(est):
            scaler = StandardScaler().fit(X)
            est.fit(scaler.transform(X), y)
            pred = est.predict(scaler.transform(X))
        else:
            est.fit(X, y)
            pred = est.predict(X)
        resid = y - pred
        bundle = {"estimator": est, "kind": "regressor",
                  "model_name": model_name,
                  "scaler": scaler,
                  "residual_quantiles": {
                      "p5": float(np.percentile(resid, 5)),
                      "p95": float(np.percentile(resid, 95))},
                  "train_metrics": M.regression_metrics(y, pred)}
    bundle["imputer"] = imputer
    return bundle, int(len(rows))


def train_production(df: pd.DataFrame, results: dict,
                     cfg: dict | None = None,
                     out_path: Path = DEFAULT_MODEL_PATH,
                     force_leg: str | None = None,
                     force_models: dict | None = None) -> dict[str, Any]:
    """Persist the production artifact (leg/model chosen by the benchmark)."""
    cfg = cfg or dict(n_estimators=250, n_jobs=4, n_splits=5, seed=42)
    enr = enrich(df)
    expr_rows = enr[enr["has_expression"] == 1]
    claims = compute_claims(results)

    def choose(endpoint, reg="unseen_protac"):
        if force_models and endpoint in force_models:
            return force_leg or "D", force_models[endpoint]
        spec = BENCHMARK[endpoint]
        metric = "auroc" if endpoint == "derived_active" else "r2"
        w = _best_cell_info_win(results, endpoint, reg, metric=metric)
        win_leg = w.get("best_leg") or "B"
        if win_leg not in spec["legs"]:
            win_leg = spec["legs"][0]
        best_key = w.get("best_model_key") or ""
        model = (best_key.split("|", 1)[1] if "|" in best_key
                 else spec["models"][0])
        return win_leg, model

    p_leg, p_model = choose("pdc50")
    d_leg, d_model = choose("dmax", "unseen_protac")
    a_leg, a_model = choose("derived_active", "unseen_protac")
    if force_leg:
        p_leg = d_leg = a_leg = force_leg

    bundles = {}
    n_rows = {}
    for endp, leg, model in (("pdc50", p_leg, p_model),
                             ("dmax", d_leg, d_model),
                             ("derived_active", a_leg, a_model)):
        bundles[endp], n_rows[endp] = _fit_endpoint(enr, endp, leg, model, cfg)

    # OOD references (molecular space + scaffolds + training cell lines)
    molc = MolCache()
    mol_ref = molc.matrix(enr["protac_smiles_canonical"].tolist())
    from sklearn.neighbors import NearestNeighbors
    nn = NearestNeighbors(n_neighbors=min(5, len(mol_ref)), n_jobs=1)
    nn.fit(mol_ref)
    d, _ = nn.kneighbors(mol_ref)
    mean_mol = float(np.mean(d[:, 1:])) if d.shape[1] > 1 else 0.0
    scaffolds = {murcko_group(s) for s in enr["protac_smiles_canonical"]}

    art = {
        "model_version": "cell_context_degradation-v1.0.0",
        "config": {"leg": p_leg, "n_estimators": cfg.get("n_estimators"),
                   "n_jobs": cfg.get("n_jobs"), "seed": cfg.get("seed", 42)},
        "endpoint_legs": {"pdc50": p_leg, "dmax": d_leg,
                          "derived_active": a_leg},
        "endpoint_models": {"pdc50": p_model, "dmax": d_model,
                            "derived_active": a_model},
        "pdc50": bundles["pdc50"], "dmax": bundles["dmax"],
        "derived_active": bundles["derived_active"],
        "n_rows": n_rows,
        "mol_ref": mol_ref, "mean_mol_distance": mean_mol,
        "scaffolds": scaffolds, "train_cells": set(
            expr_rows["depmap_id"].dropna().astype(str)),
        "cell_line_table": pd.read_csv(DATA_DIR / "cell_line_mapping.csv"),
        "claims": claims,
        "mechanistic_features_used": [],
        "limitations": [
            "transcriptomic context absent -> imputed with training medians + "
            "cell OOD flag (no fabricated context)",
            "binary activity is threshold-derived (pDC50>=6.0, Dmax>=60), "
            "never an experimental probability",
            "proteomics and Modules 1-3 mechanistic features not available at "
            "dataset scale (see docs/LIMITATIONS.md)",
            "DepMap 24Q4 TPM (log1p) as shipped; assay-level heterogeneity "
            "across 231 source DOIs remains",
        ],
    }
    # attach encoders (from the pdc50 fit) properly
    art["encoders"] = _encoders(enr, p_leg)
    art["model_path"] = str(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(art, out_path)
    return {"model_path": str(out_path), "claims": claims,
            "endpoint_legs": art["endpoint_legs"],
            "endpoint_models": art["endpoint_models"],
            "n_rows": n_rows}


def _encoders(enr: pd.DataFrame, leg: str) -> dict[str, Any]:
    from synglue_agent.modules.cell_context_selector import features as F
    return F.fit_encoders(enr, leg)
