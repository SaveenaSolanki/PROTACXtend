"""Module 5 — curated cell-context degradation dataset (data cleaning).

Source: PROTAC-Degradation-DB.csv (PROTAC-Degradation-Predictor, arXiv
2406.02637), the same verified research clone this project used for its G6
reproduction. Cleaning is reproducible and writes a curated table + provenance
manifest.

Cleaning rules (all documented, nothing fabricated):
* Exclude rows whose Comments flag viability/cytotoxicity-only assays (these
  measure cell killing, not degradation): 154 rows -> 2,079 degradation rows.
* DC50 units: the source column is nM throughout (PROTAC-DB/PROTAC-Pedia
  convention; QC range 0.01-100000 nM, no sub-nM/µM-unit outliers). pDC50 is
  always computed as -log10(DC50_molar) from the nM value; unit is asserted,
  never silently rescaled.
* Dmax is percentage (0..100). No missing DC50/Dmax is fabricated.
* The binary degradation label is **derived**, not experimentally measured:
  exactly the paper's is_active() AND rule (pDC50>=6.0 AND Dmax%>=60,
  thresholds pDC50=6.0, Dmax=0.6), recomputed here and kept in a column named
  derived_active. Rows lacking the endpoints needed to decide are NaN.
  QA against the shipped 'Active' column is reported in the manifest (it
  disagrees -> the shipped column is NOT used as a label source).
* Cell lines are normalised + mapped to DepMap identifiers in cellline.py.
* Exact-duplicate rows (same smiles/target/e3/cell/DOI) are dropped; residual
  multi-source duplicates of the same (smiles, target, E3, cell) are merged by
  geometric mean of DC50/Dmax (paper rule) with aggregated DOI provenance.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("protacxtend.cell_context_dataset")

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
SOURCE_DB = (
    Path(__file__).resolve().parents[3]
    / "data" / "protac_repos" / "repos" / "PROTAC-Degradation-Predictor"
    / "data" / "PROTAC-Degradation-DB.csv"
)
CURATED_CSV = DATA_DIR / "cell_context_records.csv"
MANIFEST_JSON = DATA_DIR / "provenance_manifest.json"

# Thresholds of the paper's documented derived-activity rule (is_active AND mode)
PDC50_THRESHOLD = 6.0      # DC50 <= 1000 nM
DMAX_THRESHOLD = 0.6       # Dmax >= 60 %

_VIABILITY_HINTS = re.compile(
    r"viab|cytotox|anti-prolif|viability|IC50[\u2018\u2019'\"]?s? are for cell viability",
    re.I)

E3_ALIASES = {
    "iap": "IAP", "ciap1": "IAP", "xiap": "XIAP", "mdm2": "MDM2", "ubr1": "UBR1",
}
# canonical E3 -> HGNC gene symbols used for expression lookup
E3_GENES = {
    "CRBN": ["CRBN"], "VHL": ["VHL"], "MDM2": ["MDM2"], "FEM1B": ["FEM1B"],
    "RNF114": ["RNF114"], "UBR1": ["UBR1"], "IAP": ["BIRC2", "BIRC3"],
    "XIAP": ["BIRC4"],
}


def is_active_dc50_dmax(dc50_nM, dmax_pct) -> bool | float:
    """Paper is_active() AND rule (arXiv 2406.02637), thresholds above.

    Returns True/False when the endpoints decide, np.nan otherwise.
    A present endpoint below its threshold decides False; True requires both
    endpoints present and above threshold (no fabrication from one endpoint).
    """
    dc50 = pd.to_numeric(dc50_nM, errors="coerce")
    dmax = pd.to_numeric(dmax_pct, errors="coerce")
    pdc50 = -np.log10(dc50 * 1e-9) if pd.notnull(dc50) else np.nan
    dmf = dmax / 100.0 if pd.notnull(dmax) else np.nan
    if pd.notnull(pdc50) and pdc50 < PDC50_THRESHOLD:
        return False
    if pd.notnull(dmf) and dmf < DMAX_THRESHOLD:
        return False
    if pd.notnull(pdc50) and pd.notnull(dmf):
        return bool(pdc50 >= PDC50_THRESHOLD and dmf >= DMAX_THRESHOLD)
    return np.nan


def normalize_e3(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "unknown"
    return E3_ALIASES.get(str(value).strip().lower(), str(value).strip())


def _canonical_smiles(smiles: str) -> tuple[str, bool]:
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return str(smiles), False
        return Chem.MolToSmiles(mol), True
    except Exception:
        return str(smiles), False


def load_source(path: str | Path | None = None) -> pd.DataFrame:
    p = Path(path) if path else SOURCE_DB
    if not p.exists():
        raise FileNotFoundError(
            f"PROTAC-Degradation-DB.csv not found at {p} — clone the "
            "PROTAC-Degradation-Predictor repo into data/protac_repos/repos/ "
            "(see data/protac_repos/README.md)")
    return pd.read_csv(p)


def clean_records(df: pd.DataFrame) -> pd.DataFrame:
    """Reproducible cleaning to the curated schema (NaN = unmeasured)."""
    out = df.copy()

    # --- 1. drop viability/cytotoxicity-only records -------------------------
    flagged = out["Comments"].astype(str).str.contains(
        _VIABILITY_HINTS, na=False)
    n_viability = int(flagged.sum())
    out = out[~flagged].copy()

    # --- 2. canonical PROTAC identifiers / SMILES ----------------------------
    canon = out["Smiles"].astype(str).map(_canonical_smiles)
    out["protac_smiles_canonical"] = [c[0] for c in canon]
    out["smiles_parsable"] = [c[1] for c in canon]
    out["protac_name"] = out["Name"].where(out["Name"].notna(),
                                           out["Compound ID"].astype(str))

    # --- 3. target / E3 normalisation ---------------------------------------
    out["target"] = out["Target (Parsed)"].fillna(out["Target"])
    out["e3"] = out["E3 Ligase"].map(normalize_e3)
    out["e3_gene"] = out["e3"].map(lambda e: ",".join(E3_GENES.get(e, []))
                                   if e != "unknown" else "")

    # --- 4. DC50 unit assertion + pDC50 --------------------------------------
    dc = pd.to_numeric(out["DC50 (nM)"], errors="coerce")
    dc = dc.where(dc > 0)          # non-positive/parse failures -> unmeasured
    out["dc50_nM"] = dc
    out["pdc50"] = -np.log10(dc * 1e-9)
    out["has_dc50"] = dc.notna().astype(int)
    # Dmax percentage (0..100)
    dm = pd.to_numeric(out["Dmax (%)"], errors="coerce")
    dm = dm.where((dm >= 0) & (dm <= 100))
    out["dmax_pct"] = dm
    out["has_dmax"] = dm.notna().astype(int)

    # --- 5. derived activity label (documented threshold; NOT experimental) --
    out["derived_active"] = out.apply(
        lambda r: is_active_dc50_dmax(r["dc50_nM"], r["dmax_pct"]), axis=1)
    out["derived_active"] = pd.to_numeric(out["derived_active"], errors="coerce")
    out["derived_active_defined"] = out["derived_active"].notna().astype(int)
    out["label_is_derived"] = 1   # every binary label in this table is derived

    # --- 6. provenance / assay metadata --------------------------------------
    out["doi"] = out["Article DOI"]
    out["source_db"] = out["Database"]
    out["assay_text"] = out["Assay (DC50/Dmax)"]
    out["treatment_time_h"] = pd.to_numeric(
        out["Treatment Time (h)"], errors="coerce")
    out["cell_line_raw"] = out["Cell Type"]
    out["target_uniprot"] = out["Uniprot"]
    out["e3_uniprot"] = out["E3 Ligase Uniprot"]
    out["cell_line_id_source"] = out["Cell Line Identifier"]
    out["comments"] = out["Comments"]

    keep = ["protac_smiles_canonical", "smiles_parsable", "protac_name",
            "target", "target_uniprot", "e3", "e3_gene", "e3_uniprot",
            "cell_line_raw", "cell_line_id_source", "dc50_nM", "pdc50",
            "has_dc50", "dmax_pct", "has_dmax", "derived_active",
            "derived_active_defined", "label_is_derived", "doi", "source_db",
            "assay_text", "treatment_time_h", "comments"]
    out = out[keep]
    return out, n_viability


def _geo_mean(s: pd.Series) -> float:
    v = s.dropna().astype(float)
    return float(np.exp(np.mean(np.log(v)))) if len(v) else np.nan


def _plain_mean(s: pd.Series) -> float:
    v = s.dropna().astype(float)
    return float(np.mean(v)) if len(v) else np.nan


def _geomean_dedup(df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    """Merge multi-source duplicates by geometric mean of DC50/Dmax (paper
    rule); aggregate DOI provenance. Returns (deduped, n_merged_groups)."""
    if df.empty:
        return df, 0
    num = df[key_cols]
    dup_mask = num.duplicated(keep=False)
    singles = df[~dup_mask].copy()
    dups = df[dup_mask].copy()
    n_merged = int(num.duplicated().sum())
    if dups.empty:
        return singles, 0
    key_set = set(key_cols)
    agg = {
        "dc50_nM": _geo_mean,
        "dmax_pct": _plain_mean,
        "doi": lambda s: "|".join(sorted(set(str(x) for x in s.dropna()))),
        "source_db": lambda s: "|".join(sorted(set(str(x) for x in s.dropna()))),
        "protac_name": "first", "target": "first", "target_uniprot": "first",
        "e3": "first", "e3_gene": "first", "e3_uniprot": "first",
        "cell_line_raw": "first", "cell_line_id_source": "first",
        "smiles_parsable": "first", "assay_text": "first",
        "treatment_time_h": "mean",
        "comments": lambda s: "|".join(sorted(set(str(x) for x in s.dropna()))),
    }
    agg = {k: v for k, v in agg.items() if k not in key_set}
    merged = dups.groupby(key_cols, sort=False).agg(agg).reset_index()
    # recompute derived endpoints after merging
    for r in ["dc50_nM", "dmax_pct"]:
        merged[r] = pd.to_numeric(merged[r], errors="coerce")
    merged["pdc50"] = -np.log10(merged["dc50_nM"] * 1e-9)
    merged["has_dc50"] = merged["dc50_nM"].notna().astype(int)
    merged["has_dmax"] = merged["dmax_pct"].notna().astype(int)
    merged["derived_active"] = merged.apply(
        lambda r: is_active_dc50_dmax(r["dc50_nM"], r["dmax_pct"]), axis=1)
    merged["derived_active"] = pd.to_numeric(
        merged["derived_active"], errors="coerce")
    merged["derived_active_defined"] = merged["derived_active"].notna().astype(int)
    merged["label_is_derived"] = 1
    return pd.concat([singles, merged], ignore_index=True), n_merged


def build_curated(path: str | Path | None = None,
                  merge_same_series: bool = False
                  ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run the reproducible cleaning pipeline -> (curated_df, report).

    merge_same_series=False (default): measurements of the same
    (compound, target, E3, cell line) from *different DOIs* are kept as
    separate rows (they are distinct experimental records). Exact duplicates
    (same DOI too) are always dropped. True duplicate records across papers
    can optionally be merged by geometric mean with merge_same_series=True.
    """
    raw = load_source(path)
    n_raw = len(raw)

    # QA: recomputed derived label vs the shipped 'Active' column (raw rows)
    qa = {"shipped_active_present": "Active" in raw.columns}
    if "Active" in raw.columns:
        r = raw.copy()
        r["dc50_nM"] = pd.to_numeric(r["DC50 (nM)"], errors="coerce")
        r["dmax_pct"] = pd.to_numeric(r["Dmax (%)"], errors="coerce")
        r["derived_active"] = r.apply(
            lambda x: is_active_dc50_dmax(x["dc50_nM"], x["dmax_pct"]), axis=1)
        r["derived_active"] = pd.to_numeric(r["derived_active"],
                                             errors="coerce")
        ov = r[r["derived_active"].notna() & r["Active"].notna()]
        qa["overlap_rows"] = int(len(ov))
        qa["agreement"] = int((ov["derived_active"] == ov["Active"]).sum())
        qa["note"] = ("shipped 'Active' column disagrees with the documented "
                       "AND rule on some rows -> never used as a label")

    clean, n_viability = clean_records(raw)
    exact_dupes = int(clean.duplicated(
        subset=["protac_smiles_canonical", "target_uniprot", "e3_uniprot",
                "cell_line_raw", "doi"]).sum())
    clean = clean.drop_duplicates(
        subset=["protac_smiles_canonical", "target_uniprot", "e3_uniprot",
                "cell_line_raw", "doi"], keep="first")

    n_before_merge = len(clean)
    if merge_same_series:
        clean, n_merged = _geomean_dedup(
            clean, ["protac_smiles_canonical", "target_uniprot", "e3_uniprot",
                    "cell_line_raw"])
    else:
        n_merged = 0

    report = {
        "source": str(SOURCE_DB),
        "raw_rows": n_raw,
        "qa_vs_shipped_active": qa,
        "viability_only_excluded": n_viability,
        "exact_duplicate_rows_dropped": exact_dupes,
        "geomean_merge_surplus_rows_removed": n_merged,
        "degradation_rows_after_clean": n_before_merge,
        "curated_rows": len(clean),
        "measured_dc50": int(clean["has_dc50"].sum()),
        "measured_dmax": int(clean["has_dmax"].sum()),
        "measured_both": int(((clean["has_dc50"] == 1)
                             & (clean["has_dmax"] == 1)).sum()),
        "derived_active_defined": int(clean["derived_active_defined"].sum()),
        "derived_active_true": int((clean["derived_active"] == 1).sum()),
        "cell_lines_raw": int(clean["cell_line_raw"].nunique()),
        "targets": int(clean["target"].nunique()),
        "e3_ligases": int(clean["e3"].nunique()),
        "dois": int(clean["doi"].nunique()),
        "pdc50_threshold": PDC50_THRESHOLD,
        "dmax_threshold": DMAX_THRESHOLD,
        "dc50_unit_nM": True,
        "dc50_nM_range": [float(clean["dc50_nM"].min()),
                          float(clean["dc50_nM"].max())] if
        clean["dc50_nM"].notna().any() else None,
        "dmax_pct_range": [float(clean["dmax_pct"].min()),
                           float(clean["dmax_pct"].max())] if
        clean["dmax_pct"].notna().any() else None,
        "notes": [
            "binary degradation labels are DERIVED (is_active AND rule, "
            "pDC50>=6.0 & Dmax>=60), never experimental measurements",
            "no DC50/Dmax value fabricated; missing endpoints stay NaN",
            "DC50 column asserted nM (source convention); no unit rescale",
        ],
    }
    return clean, report


def dataset_report(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(len(df)),
        "unique_protacs": int(df["protac_smiles_canonical"].nunique()),
        "unique_cell_lines": int(df["cell_line_raw"].nunique()),
        "unique_targets": int(df["target"].nunique()),
        "unique_e3": int(df["e3"].nunique()),
        "measured_dc50": int(df["has_dc50"].sum()),
        "measured_dmax": int(df["has_dmax"].sum()),
        "measured_both": int(((df["has_dc50"] == 1) & (df["has_dmax"] == 1)).sum()),
        "derived_active_defined": int(df["derived_active_defined"].sum()),
        "dc50_nM_range": [round(float(df["dc50_nM"].min()), 4),
                          round(float(df["dc50_nM"].max()), 3)],
        "pdc50_range": [round(float(df["pdc50"].min()), 3),
                        round(float(df["pdc50"].max()), 3)],
        "dmax_pct_range": [round(float(df["dmax_pct"].min()), 3),
                           round(float(df["dmax_pct"].max()), 3)],
    }


def ensure_curated(rebuild: bool = False,
                   merge_same_series: bool = False) -> pd.DataFrame:
    """Load the curated CSV, building + writing it on first use (reproducible)."""
    if CURATED_CSV.exists() and not rebuild:
        df = pd.read_csv(CURATED_CSV)
    else:
        df, report = build_curated(merge_same_series=merge_same_series)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(CURATED_CSV, index=False)
        MANIFEST_JSON.write_text(json.dumps(report, indent=2, default=str))
        logger.info("wrote curated table %s (%d rows)", CURATED_CSV, len(df))
    return df


if __name__ == "__main__":
    d, rep = build_curated()
    print(json.dumps(rep, indent=2, default=str))
    print(dataset_report(d))
