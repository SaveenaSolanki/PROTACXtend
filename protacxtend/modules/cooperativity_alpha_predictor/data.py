"""Dataset audit + leakage-safe evaluation helpers (Module 3, steps 1 & 6).

Policy: experimental alpha values are only ever taken from primary literature
measurements in a single assay system (alpha = Kd2/Kd2_ternary, see alpha_def);
alpha is NEVER inferred from qualitative statements. The shipped curation
template contains zero records until trusted/manual curation; the audit report
below therefore reports real (currently zero/limited) statistics and stops
supervised training accordingly (surrogate mode).
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("protacxtend.cooperativity_data")

RECORD_FIELDS = [
    "protac_id", "protac_smiles", "poi", "e3", "warhead", "e3_recruiter",
    "linker", "linker_smiles", "alpha", "log_alpha", "kd_binary_poi_nM",
    "kd_binary_e3_nM", "kd_ternary_nM", "assay", "temperature_c", "doi",
    "pmid", "pdb_ids", "alpha_definition", "source", "notes",
]

DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "cooperativity_records.csv"


def load_records(path: str | Path | None = None) -> pd.DataFrame:
    p = Path(path or DEFAULT_DATA_PATH)
    if not p.exists():
        raise FileNotFoundError(f"cooperativity records not found: {p}")
    df = pd.read_csv(p, comment="#", dtype=str)
    df = df.dropna(how="all")
    if df.empty:
        return df
    for col in ("alpha", "log_alpha", "temperature_c",
                "kd_binary_poi_nM", "kd_binary_e3_nM", "kd_ternary_nM"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # enforce single convention: ln(alpha) stored, never mix log bases
    if "alpha" in df.columns and "log_alpha" in df.columns:
        df["log_alpha"] = df["alpha"].map(
            lambda a: math.log(a) if pd.notna(a) and a > 0 else np.nan)
    return df


def audit_records(df: pd.DataFrame) -> dict[str, Any]:
    """Report every dataset statistic required before modelling."""
    if df is None or df.empty:
        return {
            "records": 0, "unique_protacs": 0, "unique_pois": 0, "unique_e3s": 0,
            "with_structures": 0, "with_alpha": 0,
            "alpha_distribution": {}, "assay_distribution": {},
            "missingness": {}, "duplicates": [], "conflicts": [],
            "conclusion": "NO MACHINE-READABLE EXPERIMENTAL alpha RECORDS CURATED "
                          "YET -> supervised training NOT run; structural surrogate "
                          "mode retained (no fabricated labels).",
            "definition": "alpha = Kd2 / Kd2(ternary) measured in the SAME assay "
                          "system; model target log_alpha = ln(alpha); classes: "
                          "alpha>1 positive, 0.8<=alpha<=1.25 approximately "
                          "non-cooperative, alpha<0.8 negative.",
        }
    alpha = pd.to_numeric(df["alpha"], errors="coerce") if "alpha" in df else pd.Series(dtype=float)
    dups = []
    if "doi" in df.columns:
        dups = df[df["doi"].notna() & df["doi"].duplicated(keep=False)]["doi"].unique().tolist()
    conflicts = []
    if "alpha" in df.columns and "log_alpha" in df.columns:
        derived = df["alpha"].map(lambda a: math.log(a) if pd.notna(a) and a > 0 else np.nan)
        bad = (df["log_alpha"] - derived).abs() > 1e-6
        conflicts = df.loc[bad.fillna(False), "protac_id"].tolist()
    return {
        "records": int(len(df)),
        "unique_protacs": int(df["protac_id"].nunique()) if "protac_id" in df else 0,
        "unique_pois": int(df["poi"].nunique()) if "poi" in df else 0,
        "unique_e3s": int(df["e3"].nunique()) if "e3" in df else 0,
        "with_structures": int(df["pdb_ids"].notna().sum()) if "pdb_ids" in df else 0,
        "with_alpha": int(alpha.notna().sum()),
        "alpha_distribution": {"min": float(alpha.min()) if alpha.notna().any() else None,
                               "median": float(alpha.median()) if alpha.notna().any() else None,
                               "max": float(alpha.max()) if alpha.notna().any() else None,
                               "positive_frac": float((alpha > 1).mean()) if alpha.notna().any() else None},
        "assay_distribution": dict(df["assay"].value_counts()) if "assay" in df else {},
        "missingness": {c: int(df[c].isna().sum()) for c in RECORD_FIELDS if c in df},
        "duplicates": list(dups)[:10],
        "conflicts": list(conflicts)[:10],
        "conclusion": "curation policy enforced; alpha only from measured values.",
    }


# ── leakage-safe splitting (step 6) ─────────────────────────────────────────

def grouped_train_test_indices(groups: list[Any], test_group: Any):
    """Split indices so that no record from ``test_group`` is in train.

    Use to build unseen-PROTAC / unseen-POI / unseen-E3 / linker-scaffold and
    leave-one-series-out folds.
    """
    groups = list(groups)
    test_idx = [i for i, g in enumerate(groups) if g == test_group]
    train_idx = [i for i, g in enumerate(groups) if g != test_group]
    if not test_idx or not train_idx:
        raise ValueError("both a non-empty train and test group are required")
    return train_idx, test_idx


def grouped_kfold(groups: list[Any], n_splits: int = 5):
    """Yield (train_idx, test_idx) folds grouped by series (no intra-series leak)."""
    unique = sorted(set(groups))
    if len(unique) < 2:
        return
    for i in range(min(n_splits, len(unique))):
        test_set = {unique[i]} if i < len(unique) else set()
        if not test_set:
            continue
        yield grouped_train_test_indices(groups, next(iter(test_set)))
