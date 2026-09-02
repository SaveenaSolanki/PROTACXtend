"""Feature assembly for the E3-opportunity benchmark/rankers (Module 6).

Instance features (per (poi_gene, e3_gene, cell_line)):
  e3_expr_pct, adaptor_expr_pct, poi_expr_pct     (DepMap percentiles)
  loc_score / loc_known / loc_mismatch            (UniProt compartments)
  recruiter_avail, recruiter_conf, log_affinity   (cited library)
  precedent_n (fold-safe counts), family_code
  expr_breadth (restriction), context_known

Missing values are kept NaN and imputed by train-fold medians inside the
benchmark — they are evidence of absence, not zero.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

FEATURE_ORDER = [
    "e3_expr_pct", "adaptor_expr_pct", "poi_expr_pct", "loc_score",
    "recruiter_avail", "recruiter_conf", "log_aff_best", "expr_breadth",
    "precedent_n",
]

# groups used by ablations
FEATURE_GROUPS = {
    "context": ["e3_expr_pct", "adaptor_expr_pct", "poi_expr_pct"],
    "localization": ["loc_score"],
    "recruiter": ["recruiter_avail", "recruiter_conf", "log_aff_best"],
    "selectivity": ["expr_breadth"],
    "precedent": ["precedent_n"],
    # structure & lysine are not numeric at dataset scale (UNKNOWN) -> their
    # ablation is reported as a coverage census, not a model comparison.
}


def build_instances(pairs: pd.DataFrame, cat: pd.DataFrame,
                    context_scores: dict,
                    loc_scores: dict, recruiter_info: dict,
                    breadth: dict, precedent: pd.DataFrame,
                    never_known: dict, n_negatives: int = 4,
                    seed: int = 42) -> pd.DataFrame:
    """Positive (known-working measured) + sampled never-known instances."""
    rows = []
    pos = pairs[pairs["has_dc50"] == 1]
    for _, r in pos.iterrows():
        cs = context_scores.get((r["poi_gene"], r["cell_line"], r["e3_gene"]))
        if cs is None or cs.get("score") is None:
            continue  # no expression context -> cannot build numeric instance
        rows.append(_feats(r["poi_gene"], r["cell_line"], r["e3_gene"], 1,
                           cs, loc_scores, recruiter_info, breadth,
                           precedent, cat))
    # negatives: catalog E3 never used for this POI (all data)
    for (poi_gene, cell), _ in pos.groupby(["poi_gene", "cell_line"]):
        for e3 in never_known.get(poi_gene, [])[:n_negatives]:
            cs = context_scores.get((poi_gene, cell, e3))
            if cs is None or cs.get("score") is None:
                continue
            rows.append(_feats(poi_gene, cell, e3, 0, cs, loc_scores,
                               recruiter_info, breadth, precedent, cat))
    return pd.DataFrame(rows)


def _feats(poi_gene, cell, e3, label, cs, loc_scores, recruiter_info,
           breadth, precedent, cat):
    loc = loc_scores.get((poi_gene, e3), {}) or {}
    rec = recruiter_info.get(e3, {}) or {}
    bd = breadth.get(e3, {}) or {}
    fam = cat[cat["e3_gene"] == e3]["e3_family"]
    fam = str(fam.iloc[0]) if len(fam) else "?"
    prec = precedent.set_index(["poi_gene", "e3_gene"]).get(
        (poi_gene, e3), None) if isinstance(precedent, pd.DataFrame) else 0
    prec_n = int(prec) if prec is not None and not pd.isna(prec) else 0
    aff = rec.get("best_affinity_nM")
    return {
        "poi_gene": poi_gene, "cell_line": cell, "e3_gene": e3, "label": label,
        "e3_family": fam,
        "e3_expr_pct": cs.get("e3_expression_percentile"),
        "adaptor_expr_pct": cs.get("adaptor_expression_percentile"),
        "poi_expr_pct": cs.get("poi_expression_percentile"),
        "loc_score": loc.get("score"),
        "recruiter_avail": int(bool(rec.get("available"))),
        "recruiter_conf": rec.get("confidence"),
        "log_aff_best": (None if aff is None else round(np.log10(aff), 3)),
        "expr_breadth": bd.get("score"),
        "precedent_n": prec_n,
    }


def matrix(inst: pd.DataFrame, drop_groups: Sequence[str] | None = None,
           ) -> tuple[np.ndarray, list[str]]:
    cols = list(FEATURE_ORDER)
    if drop_groups:
        drop = {c for g in drop_groups for c in FEATURE_GROUPS.get(g, [])}
        cols = [c for c in cols if c not in drop]
    X = inst[cols].to_numpy(dtype=float)
    return X, cols
