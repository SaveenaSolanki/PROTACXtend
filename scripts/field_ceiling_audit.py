"""Field-ceiling audit slice (B3): pDC50 regression on the public TACK DC50
subset with scaffold-cluster grouped CV, mirroring the published evaluation
design (TACK: scaffold 5x5 CV; ceiling pDC50 R2 ~0.66 / hold-out RMSE 0.633).

This is an executable slice of the full audit: single seed, subsampled rows,
one scaffold-CV split; multi-seed + LOTO across the full 6,561 endpoints is
the follow-up (commands documented at the bottom).
"""
import json, os, sys, time

import numpy as np
import pandas as pd

from rdkit import Chem
from rdkit.Chem import AllChem

ROOT = "/storage/saveena/protacxtend"
sys.path.insert(0, ROOT)

def morgan(smiles: str, radius: int = 2, nbits: int = 1024) -> np.ndarray:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return np.zeros(nbits)
    return np.array(AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=nbits))

def main() -> int:
    df = pd.read_parquet(os.path.join(ROOT, "data/tack/tack_dc50.parquet"))
    df = df[(df["Value_Unit"] == "nM") & (df["Value"].notna()) & (df["Value"] > 0)]
    df = df[(df["Value_Operator"].fillna("=").isin(["<", "=", ">"]))]
    df = df.copy()
    df["dc50_nM"] = df["Value"].clip(upper=10000.0)
    df["pdc50"] = -np.log10(df["dc50_nM"] * 1e-9)
    # dedupe by (SMILES, POI, ligase, cell) keep max pDC50
    df = df.sort_values("pdc50", ascending=False).drop_duplicates(
        subset=["SMILES", "POI_Name", "Ligase_Name", "Cell_Line"])
    # subsample for the slice budget (deterministic)
    rng = np.random.RandomState(42)
    keep = df["SMILES"].value_counts(sort=False)
    target = keep[keep >= 1].index
    if len(df) > 3000:
        chosen = set(rng.choice(target, 3000, replace=False)) if len(target) >= 3000 else set(target)
        df = df[df["SMILES"].isin(chosen)]

    X_mol = np.stack(df["SMILES"].map(morgan).values)
    # entity codes: train-only encoding with OOV sentinel
    ents = df.assign(poi=df["POI_Name"], lig=df["Ligase_Name"], cell=df["Cell_Line"])
    from sklearn.preprocessing import LabelEncoder
    encoders = {}
    feat_cols = []
    for col, nbits in [("poi", 8), ("lig", 4), ("cell", 12)]:
        le = LabelEncoder()
        le.fit(ents[col])
        vec = le.transform(ents[col]).astype(float)[:, None] / max(1, len(le.classes_))
        feat_cols.append(vec)
    X = np.hstack([X_mol, *feat_cols])
    y = df["pdc50"].values
    groups = df["SMILES_Scaffold_Cluster"].values

    from sklearn.model_selection import GroupKFold
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

    n_folds = 5
    gkf = GroupKFold(n_splits=n_folds)
    out = {"n_rows": int(len(df)), "n_folds": n_folds, "seed": 0, "folds": []}
    y_true_all, y_pred_all = [], []
    t0 = time.time()
    for fold, (tr, te) in enumerate(gkf.split(X, y, groups=groups)):
        rf = RandomForestRegressor(n_estimators=200, random_state=0, n_jobs=4)
        rf.fit(X[tr], y[tr])
        pred = rf.predict(X[te])
        y_true_all.extend(y[te]); y_pred_all.extend(pred)
        out["folds"].append({
            "fold": fold,
            "n_train": int(len(tr)), "n_test": int(len(te)),
            "r2": round(float(r2_score(y[te], pred)), 4),
            "mae": round(float(mean_absolute_error(y[te], pred)), 4),
            "rmse": round(float(mean_squared_error(y[te], pred) ** 0.5), 4),
            "spearman": round(float(pd.Series(y[te]).corr(pd.Series(pred), method="spearman")), 4),
        })
    out["total_s"] = round(time.time() - t0, 1)
    out["aggregate_unseen_cluster_pdc50"] = {
        "r2": round(float(r2_score(np.array(y_true_all), np.array(y_pred_all))), 4),
        "mae": round(float(mean_absolute_error(y_true_all, y_pred_all)), 4),
        "rmse": round(float(mean_squared_error(y_true_all, y_pred_all) ** 0.5), 4),
    }
    out["comparison"] = {
        "tack_paper_scaffold_cv": {"pdc50_R2": 0.66, "holdout_RMSE": 0.633, "n_endpoints": 4184},
        "protacxtend_M5_unseen_PROTAC": {"R2": 0.605, "context": "with DepMap transcriptomics; n=1181"},
    }
    out["limitations"] = (
        "slice: single seed, n<=3000 rows, single scaffold-CV; full audit requires multi-seed, "
        "all 6,561 endpoints, LOTO and per-fold CIs; operators <,> treated as point values (censoring"
    )
    out["followup_commands"] = [
        "python scripts/field_ceiling_audit.py --full --seeds 10 --regimes scaffold,loto,temporal",
    ]
    with open(os.path.join(ROOT, "outputs/manuscript_strategy/closeout/field_ceiling_audit.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: v for k, v in out.items() if k not in ("folds",)}, indent=1, default=str)[:1600])
    for fold in out["folds"]:
        print(fold)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())