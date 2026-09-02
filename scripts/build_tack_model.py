#!/usr/bin/env python3
"""Train TACK-style degradation models on the TACK dataset.

TACK (TArgeting Chimeras Knowledge, Ribes/Dunlop/Mercado 2026) combines
TPDdb + PROTAC-DB + PROTACpedia: 6,561 degradation endpoints. This script
reproduces the TACK feature philosophy (Morgan fingerprints + descriptors +
E3/cell-line/POI metadata) with OUR stack (scikit-learn) and a statistically
honest scaffold split.

Outputs (data/tack/):
  tack_dc50_model.joblib  -- HistGradientBoostingRegressor on log10(DC50 nM)
  tack_dmax_model.joblib  -- HistGradientBoostingRegressor on Dmax (%)
  tack_bin_model.joblib   -- HistGradientBoostingClassifier (DC50<100 nM)
  tack_meta.joblib        -- feature vocabularies + metrics
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import accuracy_score, roc_auc_score
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "data" / "tack" / "tack_bin.parquet"
OUT = ROOT / "data" / "tack"

TOP_LIGASES = ["CRBN", "VHL", "IAP", "cIAP1", "MDM2", "XIAP", "FEM1B"]


def mol_features(smiles: str, top_cells, top_pois, ligase="", cell="", poi=""):
    mol = Chem.MolFromSmiles(smiles)
    fp = np.zeros(1024)
    descs = np.zeros(6)
    if mol is not None:
        fp = np.array(AllChem.GetMorganFingerprintAsBitVect(mol, 2, 1024), dtype=float)
        descs = np.array([Descriptors.MolWt(mol), rdMolDescriptors.CalcTPSA(mol),
                          rdMolDescriptors.CalcNumHBD(mol), rdMolDescriptors.CalcNumHBA(mol),
                          rdMolDescriptors.CalcNumRotatableBonds(mol), Descriptors.MolLogP(mol)])
    one_hot = np.zeros(len(TOP_LIGASES) + len(top_cells) + len(top_pois))
    if ligase in TOP_LIGASES:
        one_hot[TOP_LIGASES.index(ligase)] = 1.0
    if cell in top_cells:
        one_hot[len(TOP_LIGASES) + top_cells.index(cell)] = 1.0
    if poi in top_pois:
        one_hot[len(TOP_LIGASES) + len(top_cells) + top_pois.index(poi)] = 1.0
    return np.concatenate([fp, descs, one_hot])


def main() -> int:
    df = pd.read_parquet(BIN)
    top_cells = [c for c, _ in df["Cell_Line"].value_counts().head(20).items()]
    top_pois = [p for p, _ in df["POI_Name"].value_counts().head(50).items()]

    dc = df[df["Value_Type"] == "DC50"].copy()
    dc = dc[dc["Value"] > 0]
    dc["y"] = np.log10(dc["Value"])

    dm = df[df["Value_Type"] == "Dmax"].copy()

    def build_X(sub):
        return np.vstack([mol_features(s, top_cells, top_pois, l, c, p)
                          for s, l, c, p in zip(sub["SMILES"], sub["Ligase_Name"],
                                                sub["Cell_Line"], sub["POI_Name"])])

    # scaffold split (Murcko) — TACK-style statistical honesty
    def split(df_):
        scaffolds = {i: MurckoScaffold.MurckoScaffoldSmilesFromSmiles(s)
                     for i, s in enumerate(df_["SMILES"]) if Chem.MolFromSmiles(s)}
        keys = sorted(set(scaffolds.values()))
        rng = np.random.RandomState(42)
        rng.shuffle(keys)
        test_keys = set(keys[: max(1, len(keys) // 5)])
        test_idx = [i for i, k in scaffolds.items() if k in test_keys]
        mask = np.zeros(len(df_), dtype=bool)
        mask[test_idx] = True
        return ~mask, mask

    tr_dc, te_dc = split(dc)
    Xdc = build_X(dc)
    ydc = dc["y"].values
    m_dc = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_depth=5, random_state=42)
    m_dc.fit(Xdc[tr_dc], ydc[tr_dc])
    pred_dc = m_dc.predict(Xdc[te_dc])
    rho_dc = spearmanr(ydc[te_dc], pred_dc).statistic

    # Dmax model (rows with Dmax % values)
    tr_dm, te_dm = split(dm)
    Xdm = build_X(dm)
    ydm = dm["Value"].values.astype(float)
    m_dm = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_depth=5, random_state=42)
    m_dm.fit(Xdm[tr_dm], ydm[tr_dm])
    pred_dm = m_dm.predict(Xdm[te_dm])
    rho_dm = spearmanr(ydm[te_dm], pred_dm).statistic

    # binary: active = DC50 < 100 nM (TACK bin definition, DC50 part)
    ybin = (dc["Value"].values < 100).astype(int)
    m_bin = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_depth=5, random_state=42)
    m_bin.fit(Xdc[tr_dc], ybin[tr_dc])
    pbin = m_bin.predict(Xdc[te_dc])
    acc = accuracy_score(ybin[te_dc], pbin)
    try:
        auc = roc_auc_score(ybin[te_dc], m_bin.predict_proba(Xdc[te_dc])[:, 1])
    except Exception:
        auc = float("nan")

    OUT.mkdir(parents=True, exist_ok=True)
    joblib.dump(m_dc, OUT / "tack_dc50_model.joblib")
    joblib.dump(m_dm, OUT / "tack_dmax_model.joblib")
    joblib.dump(m_bin, OUT / "tack_bin_model.joblib")
    joblib.dump({"top_cells": top_cells, "top_pois": top_pois, "top_ligases": TOP_LIGASES,
                 "metrics": {"dc50_rho": float(rho_dc), "dmax_rho": float(rho_dm),
                             "bin_acc": float(acc), "bin_auc": float(auc)},
                 "n_dc50": int(len(dc)), "n_dmax": int(len(dm))},
                OUT / "tack_meta.joblib")
    print(f"TACK-style models trained -> {OUT}")
    print(f"  DC50: rho={rho_dc:.3f} (val n={te_dc.sum()}) | Dmax: rho={rho_dm:.3f} | "
          f"bin: acc={acc:.3f} auc={auc:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
