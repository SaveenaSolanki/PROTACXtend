"""Curated dataset for Module 4.

Source (real, reproducible): outputs/benchmark/benchmark_predictions.csv — 64
published PROTAC records (name/target/E3/SMILES, published_dc50_nM for all 64,
published_dmax_pct for 32) previously curated from PROTAC-DB primary entries by
the project's own benchmark pipeline. Labels are the PUBLISHED values; no
label is inferred. E3 vocabulary is CRBN/VHL only (2 groups — unseen-E3 folds
are therefore a 2-fold demonstration, not a generalisation claim).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("protacxtend.degradation_data")

DEFAULT_CSV = Path(__file__).resolve().parents[3] / "outputs" / "benchmark" / "benchmark_predictions.csv"


def load_curated(path: str | Path | None = None) -> pd.DataFrame:
    p = Path(path or DEFAULT_CSV)
    if not p.exists():
        raise FileNotFoundError(f"curated degradation records not found: {p}")
    df = pd.read_csv(p)
    df = df.dropna(subset=["smiles", "published_dc50_nM"])
    df["published_dc50_nM"] = pd.to_numeric(df["published_dc50_nM"], errors="coerce")
    df = df[df["published_dc50_nM"] > 0].copy()
    # target label: pDC50 = -log10(DC50/M)
    df["pdc50"] = -np.log10(df["published_dc50_nM"] * 1e-9)
    df["target"] = df["target"].fillna("unknown")
    df["e3"] = df["e3"].fillna("unknown")
    return df


def dataset_report(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "records": int(len(df)),
        "unique_protacs": int(df["name"].nunique()) if "name" in df else 0,
        "named_protacs": int(df["name"].notna().sum()),
        "unique_targets": int(df["target"].nunique()),
        "unique_e3": int(df["e3"].nunique()),
        "pdc50_range": [round(float(df["pdc50"].min()), 3), round(float(df["pdc50"].max()), 3)],
        "dc50_nM_range": [round(float(df["published_dc50_nM"].min()), 4),
                          round(float(df["published_dc50_nM"].max()), 2)],
        "dmax_label_count": int(df["published_dmax_pct"].notna().sum()) if "published_dmax_pct" in df else 0,
        "labels_measured": True,
        "degradation_probability_labels": 0,   # no binary degradation label exists -> task disabled
    }


def curate_split_sets(df: pd.DataFrame) -> dict[str, list[str]]:
    """Split-group definitions used by the evaluator (each value = a group id
    per row so folds never share a series between train/test)."""
    return {
        "random": [f"row{i}" for i in range(len(df))],
        "scaffold": df["smiles"].map(lambda s: _scaffold(s)).tolist(),
        "unseen_target": df["target"].tolist(),
        "unseen_e3": df["e3"].tolist(),
        "unseen_protac": df["name"].fillna(df["smiles"].map(lambda s: _scaffold(s))).tolist(),
    }


def _scaffold(smiles: str) -> str:
    from protacxtend.modules.degradation_ml.features import murcko_group
    return murcko_group(smiles)
