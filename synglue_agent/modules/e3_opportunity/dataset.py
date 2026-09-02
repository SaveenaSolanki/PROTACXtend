"""Module 6 — data layer: cited recruiters + retrospective POI-E3 dataset.

Recruiters: DOI-cited E3-ligand library (synglue_agent/data/
curated_e3_ligands.csv). Local-demo rows (no DOI/UniProt/activity) are kept
but flagged `demo_only` and never count as cited recruiter evidence.

Retrospective pairs: PROTAC-Degradation-DB rows curated by Module 5 give real
(poi_gene, cell_line, e3) measurements; positives for retrieval benchmarking =
the E3(s) actually used for that POI in the training fold (never 'known
inactive' — absence of a record is only absence of evidence).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from synglue_agent.modules.cell_context_selector import dataset as m5ds
from synglue_agent.modules.cell_context_selector import omics
from synglue_agent.modules.cell_context_selector.genemap import target_to_gene
from synglue_agent.modules.e3_opportunity.e3_catalog import alias_to_genes

logger = logging.getLogger("protacxtend.e3_dataset")

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
LIGAND_LIBRARY = (Path(__file__).resolve().parents[3] / "synglue_agent"
                  / "data" / "curated_e3_ligands.csv")


def load_recruiters(path=None) -> pd.DataFrame:
    """DOI-cited recruiter library, canonical E3 genes expanded."""
    p = Path(path) if path else LIGAND_LIBRARY
    df = pd.read_csv(p)
    df["demo_only"] = df["source"].astype(str).str.startswith("local_demo")
    out = []
    for _, r in df.iterrows():
        genes = alias_to_genes(r.get("e3_ligase"))
        for g in genes or [str(r.get("e3_ligase"))]:
            out.append({**r.to_dict(), "e3_gene": g})
    rec = pd.DataFrame(out)
    if len(rec):
        rec["activity_nM_num"] = pd.to_numeric(rec["activity_nM"],
                                               errors="coerce")
    return rec


_benchmark_pairs_cache: pd.DataFrame | None = None


def load_benchmark_pairs() -> pd.DataFrame:
    """(poi_gene, cell_line, e3_gene, measured dc50/dmax) real pairs."""
    global _benchmark_pairs_cache
    if _benchmark_pairs_cache is not None:
        return _benchmark_pairs_cache.copy()
    cur, _ = m5ds.build_curated()
    try:
        expr = omics.ensure_curated_expression()
        vocab = set(expr.columns)
    except Exception:
        vocab = set()
    cur = cur.copy()
    cur["poi_gene"] = cur["target"].map(
        lambda t: target_to_gene(t, vocab) if isinstance(t, str) else None)
    rows = []
    for _, r in cur.iterrows():
        if pd.isna(r.get("poi_gene")):
            continue
        for g in alias_to_genes(r["e3"]) or []:
            rows.append({"poi_gene": r["poi_gene"], "cell_line": r["cell_line_raw"],
                         "e3_gene": g, "e3_label": r["e3"],
                         "dc50_nM": r["dc50_nM"], "pdc50": r["pdc50"],
                         "dmax_pct": r["dmax_pct"],
                         "has_dc50": int(bool(r.get("has_dc50"))),
                         "has_dmax": int(bool(r.get("has_dmax"))),
                         "doi": r["doi"], "protac_name": r["protac_name"]})
    out = pd.DataFrame(rows)
    _benchmark_pairs_cache = out
    return out.copy()


def known_pair_counts(pairs: pd.DataFrame) -> pd.DataFrame:
    """Precedent counts per (poi_gene, e3_gene) over real measured rows."""
    return (pairs[pairs["has_dc50"] == 1]
            .groupby(["poi_gene", "e3_gene"], observed=True)
            .size().reset_index(name="n_rows"))
