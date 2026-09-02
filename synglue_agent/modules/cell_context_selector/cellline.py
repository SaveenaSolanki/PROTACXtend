"""Cell-line normalisation + DepMap/CCLE mapping (Module 5).

Normalises the cell-line vocabulary of PROTAC-Degradation-DB and maps each
line to DepMap (CCLE) identifiers using the public DepMap 24Q4 Model.csv
(sample metadata). Coverage is reported per axis: mapped/unmapped, ambiguous,
transcriptomics coverage (expression matrix membership) and proteomics
coverage (none available from DepMap 24Q4 -> reported, not assumed).

The DepMap metadata table is a small, citable download cached under
outputs/omics_cache/depmap_model.csv (DepMap Public 24Q4). Mapping is
deterministic: exact normalised match -> single candidate; >1 candidate ->
ambiguous (reported); none -> normalised fuzzy match (ratio>=0.85); else
unmapped.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
OMICS_CACHE = Path(__file__).resolve().parents[3] / "outputs" / "omics_cache"

DEPMAP_MODEL_CSV = OMICS_CACHE / "depmap_model.csv"
# bundled lookup of the DepMap rows that cover our dataset cell lines
BUNDLED_MODEL_CSV = DATA_DIR / "depmap_model_lookup.csv"

# manual alias fixes (dataset name -> DepMap CellLineName)
ALIASES = {
    "MM1.S": "MM1.S", "MM.1S": "MM1.S", "MM1S": "MM1.S",
    "HCT 116": "HCT116", "HCT-116": "HCT116",
    "RPMI8226": "RPMI-8226", "RPMI 8226": "RPMI-8226",
    "786-O": "786-0", "786O": "786-0",
    "C4-2B": "C4-2B", "HEK293": "HEK293", "HEK 293T": "HEK293T",
    "MOLT4": "MOLT-4", "MOLT-4": "MOLT-4",
    "H1975": "NCI-H1975", "NCI-H1975": "NCI-H1975",
    "H1666": "NCI-H1666", "H23": "NCI-H23", "H322": "NCI-H322",
    "H358": "NCI-H358", "H661": "NCI-H661", "H1299": "NCI-H1299",
    "H3122": "NCI-H3122", "H3255": "NCI-H3255", "H1838": "NCI-H1838",
    "HCC827": "HCC827", "HCC78": "HCC78",
    "HBL-1": "HBL1", "Ba/F3": "BAF3", "BaF3": "BAF3",
    "BaF3 FLT3-ITD": "BAF3",
    "Bel-7402": "BEL-7402", "BEL7402": "BEL-7402",
    "HEK293T": "HEK293T", "293T": "HEK293T",
    "SRD15": None,  # no CCLE line -> unmapped by design (documented)
    "Panc02.13": None,
    # DepMap 24Q4 actual spellings (checked against Model.csv)
    "LNCaP": "LNCaP clone FGC", "LnCaP": "LNCaP clone FGC",
    "LnCap": "LNCaP clone FGC", "LnCaP95": None,
    "U251": "U-251 MG", "U251MG": "U-251 MG", "U87": "U-87 MG",
    "U87MG": "U-87 MG", "MM1.S": "MM1-S", "MM.1S": "MM1-S",
    "MM1S": "MM1-S", "VCaP AR+": "VCaP",
    "MB-MDA-231": "MDA-MB-231",
    "KYSE520 esophageal cancer cell line": "KYSE-520",
    "MOLT-4": "MOLT-4", "MOLT4": "MOLT-4",
}

# suffixes/parentheticals stripped before matching
_DROP_PAREN = __import__("re").compile(r"\s*\(.*?\)\s*")
_DROP_TAIL = __import__("re").compile(
    r"\s+(cancer\s+)?cell\s+line\s*(es)?$", re.I)
# '+'/' AR+' positional variants: 'VCaP AR+' handled by alias; here we only
# drop a trailing '+'
_DROP_PLUS = __import__("re").compile(r"\+$")

# dataset names that are not single cell lines (qualitative assay descriptors)
NON_CELL_LINE_HINTS = ("cell lines", "cells", "neurons", "monocytes",
                       "reporter", "selection", "positive", "fibroblasts")


def normalize_name(name) -> str:
    s = re.sub(r"[^a-z0-9]", "", str(name).lower())
    return s


def _load_depmap_model(path: str | Path | None = None) -> pd.DataFrame:
    p = Path(path) if path else DEPMAP_MODEL_CSV
    if p.exists():
        return pd.read_csv(p)
    if BUNDLED_MODEL_CSV.exists():
        return pd.read_csv(BUNDLED_MODEL_CSV)
    return pd.DataFrame()


def _candidates_index(models: pd.DataFrame) -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = {}
    for _, row in models.iterrows():
        rec = {"depmap_id": row.get("ModelID"),
               "cell_line_name": row.get("CellLineName"),
               "lineage": row.get("OncotreeLineage"),
               "primary_disease": row.get("OncotreePrimaryDisease"),
               "subtype": row.get("OncotreeSubtype"),
               "rrid": row.get("RRID")}
        for field in ("CellLineName", "StrippedCellLineName", "CCLEName"):
            v = row.get(field)
            if isinstance(v, str) and v:
                idx.setdefault(normalize_name(v), []).append(rec)
    return idx


def map_cell_lines(names: list[str], path=None) -> pd.DataFrame:
    """Map dataset cell-line names -> canonical DepMap records.

    Returns a row per input name with status mapped/ambiguous/unmapped.
    """
    models = _load_depmap_model(path)
    idx = _candidates_index(models)
    all_norms = list(idx.keys())
    rows = []
    for raw in names:
        raw_s = str(raw)
        alias = ALIASES.get(raw_s)
        if alias is None and raw_s in ALIASES.values():
            alias = raw_s
        cands = []
        if alias:
            cands = idx.get(normalize_name(alias), [])
        if not cands:
            cands = idx.get(normalize_name(raw_s), [])
        if not cands:
            cleaned = _DROP_PAREN.sub("", raw_s)
            cleaned = _DROP_TAIL.sub("", cleaned)
            cleaned = _DROP_PLUS.sub("", cleaned)
            if cleaned and cleaned != raw_s:
                if cleaned in ALIASES and ALIASES[cleaned]:
                    cands = idx.get(normalize_name(ALIASES[cleaned]), [])
                else:
                    cands = idx.get(normalize_name(cleaned), [])
        if not cands:
            fuzzy = difflib.get_close_matches(normalize_name(raw_s), all_norms,
                                              n=2, cutoff=0.85)
            cands = [c for f in fuzzy for c in idx.get(f, [])]
        seen = []
        for c in cands:
            if c not in seen:
                seen.append(c)
        if len(seen) == 1:
            rec = seen[0]
            rows.append({"cell_line_raw": raw_s,
                         "cell_line": rec["cell_line_name"],
                         "depmap_id": rec["depmap_id"],
                         "lineage": rec["lineage"],
                         "primary_disease": rec["primary_disease"],
                         "subtype": rec["subtype"],
                         "rrid": rec["rrid"],
                         "mapping_status": "mapped",
                         "candidates": 1})
        elif len(seen) > 1:
            rows.append({"cell_line_raw": raw_s,
                         "cell_line": raw_s,
                         "depmap_id": None,
                         "lineage": None, "primary_disease": None,
                         "subtype": None, "rrid": None,
                         "mapping_status": "ambiguous",
                         "candidates": len(seen)})
        else:
            desc = any(h in raw_s.lower() for h in NON_CELL_LINE_HINTS)
            rows.append({"cell_line_raw": raw_s, "cell_line": raw_s,
                         "depmap_id": None, "lineage": None,
                         "primary_disease": None, "subtype": None,
                         "rrid": None, "mapping_status": "unmapped",
                         "candidates": 0,
                         "descriptive_entry": bool(desc)})
    return pd.DataFrame(rows)


def _coverage_report(mapped: pd.DataFrame,
                     expression_models: set | None = None,
                     proteomics_models: set | None = None) -> dict[str, Any]:
    n = len(mapped)
    st = mapped["mapping_status"].value_counts().to_dict()
    has_expr = [0] * n
    if expression_models:
        has_expr = [1 if (r.depmap_id in expression_models) else 0
                    for r in mapped.itertuples()]
    has_prot = [0] * n
    if proteomics_models:
        has_prot = [1 if (r.depmap_id in proteomics_models) else 0
                    for r in mapped.itertuples()]
    return {
        "n": n,
        "mapped": int(st.get("mapped", 0)),
        "unmapped": int(st.get("unmapped", 0)),
        "ambiguous": int(st.get("ambiguous", 0)),
        "transcriptomics_covered": int(sum(has_expr)),
        "proteomics_covered": int(sum(has_prot)),
        "notes": [
            "DepMap 24Q4 Model.csv is the mapping reference",
            "transcriptomics coverage = mapped lines present in the 24Q4 "
            "protein-coding TPM matrix",
            "proteomics coverage = 0: no DepMap 24Q4 quantitative-proteomics "
            "matrix exists; proteotype claims require user-supplied proteomics",
        ],
    }


def coverage_report(df: pd.DataFrame, omics=None) -> dict[str, Any]:
    names = sorted(df["cell_line_raw"].dropna().unique())
    mapped = map_cell_lines(names)
    expr_models = None
    if omics is not None:
        expr_models = set(omics["expression_models"])
    return _coverage_report(mapped, expr_models)
