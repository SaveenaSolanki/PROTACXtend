"""Prepare enriched analysis rows: curated degradation table joined with
cell-line mapping (DepMap), expression availability and POI gene."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from synglue_agent.modules.cell_context_selector import cellline, dataset, omics
from synglue_agent.modules.cell_context_selector.genemap import target_to_gene

DATA_DIR = Path(__file__).resolve().parent / "data"


def gene_vocab() -> set[str]:
    try:
        expr = omics.ensure_curated_expression()
        return set(expr.columns)
    except Exception:
        return set()


def enrich(df: pd.DataFrame | None = None,
           rebuild_mapping: bool = False) -> pd.DataFrame:
    """Return rows + cell context columns (canonical cell, DepMap id, lineage,
    expression availability, POI gene)."""
    if df is None:
        df = dataset.ensure_curated()
    df = df.copy()
    mapping_csv = DATA_DIR / "cell_line_mapping.csv"
    if not mapping_csv.exists() or rebuild_mapping:
        names = sorted(df["cell_line_raw"].dropna().unique())
        mp = cellline.map_cell_lines(names)
        mp.to_csv(mapping_csv, index=False)
    mp = pd.read_csv(mapping_csv)
    expr = omics.ensure_curated_expression()
    expr_ids = set(expr.index)
    mp["has_expression"] = mp["depmap_id"].isin(expr_ids).astype(int)
    out = df.merge(mp[["cell_line_raw", "cell_line", "depmap_id", "lineage",
                       "primary_disease", "mapping_status",
                       "has_expression"]], on="cell_line_raw", how="left")
    vocab = gene_vocab()
    out["target_gene"] = out["target"].map(
        lambda t: target_to_gene(t, vocab) if isinstance(t, str) else None)
    out["has_expression"] = out["has_expression"].fillna(0).astype(int)
    return out
