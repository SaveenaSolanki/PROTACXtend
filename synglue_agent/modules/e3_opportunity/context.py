"""Cell-context expression axis (Module 6).

Reuses Module 5's DepMap infrastructure (cell-line mapping + 24Q4
TPM-log1p). An extended expression matrix covering catalog E3 genes, their
CRL adaptor components and POI genes is built from the same cached raw file
(outputs/omics_cache/expression_tpmlogp1.csv) and cached under this module's
data dir. Values are TPM-log1p percentiles over the full DepMap 24Q4 line
panel; a low percentile is a real low-expression penalty.

Missing context is NEVER fabricated: unmapped cell lines / missing genes /
missing tissue mapping produce None + explicit flags + low confidence.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from synglue_agent.modules.cell_context_selector import cellline, omics
from synglue_agent.modules.e3_opportunity.e3_catalog import CATALOG, load_catalog

logger = logging.getLogger("protacxtend.e3_context")

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
CACHE_CSV = DATA_DIR / "context_expression_matrix.csv"

# extra adaptor genes beyond catalog adaptor lists (CRL cores used broadly)
CORE_GENES = ["DDB1", "CUL1", "CUL2", "CUL3", "CUL4A", "CUL4B", "CUL5",
              "RBX1", "RBX2", "SKP1", "TCEB1", "TCEB2", "ELOB", "ELOC"]

TISSUE_LINEAGE_KEYWORDS = {
    "blood": ["Myeloid", "Lymphoid"], "haematopoietic": ["Myeloid", "Lymphoid"],
    "breast": ["Breast"], "lung": ["Lung"], "prostate": ["Prostate"],
    "colon": ["Colon/Colorectal"], "colorectal": ["Colon/Colorectal"],
    "skin": ["Skin"], "melanoma": ["Skin"], "liver": ["Liver"],
    "pancreas": ["Pancreas"], "kidney": ["Kidney"], "renal": ["Kidney"],
    "brain": ["Nervous System"], "cns": ["Nervous System"],
    "ovary": ["Ovary/Fallopian Tube"], "ovarian": ["Ovary/Fallopian Tube"],
    "stomach": ["Stomach"], "gastric": ["Stomach"], "esophagus": ["Esophagus"],
    "bone": ["Bone"], "soft tissue": ["Soft Tissue"], "uterus": ["Uterine"],
    "bladder": ["Bladder/Urinary Tract"], "thyroid": ["Thyroid"],
}


class ExpressionLookup:
    """Percentile-scaled DepMap expression (offline after build)."""

    def __init__(self) -> None:
        self.matrix: pd.DataFrame | None = None
        self.model_meta: pd.DataFrame | None = None

    def _ensure(self) -> pd.DataFrame:
        if self.matrix is None:
            self.matrix = _build_or_load()
        return self.matrix

    def percentile(self, gene: str, depmap_id: Any) -> float | None:
        m = self._ensure()
        if gene not in m.columns or depmap_id not in m.index:
            return None
        v = float(m.at[depmap_id, gene])
        col = m[gene].dropna()
        if len(col) < 5 or np.isnan(v):
            return None
        return float((col <= v).mean())  # percentile 0..1, low = low expression

    def genes(self) -> list[str]:
        return list(self._ensure().columns)


def _gene_set() -> list[str]:
    genes = set(CORE_GENES)
    cat = load_catalog()
    for _, r in cat.iterrows():
        genes.add(str(r["e3_gene"]))
        for a in str(r["adaptor_genes"]).split("|"):
            if a:
                genes.add(a)
    return sorted(genes)


def _build_or_load() -> pd.DataFrame:
    if CACHE_CSV.exists():
        df = pd.read_csv(CACHE_CSV)
        return df.set_index("depmap_id")
    genes = _gene_set()
    if not omics.RAW_EXPRESSION.exists():
        logger.warning("DepMap raw expression cache missing; expression axis "
                       "will be unavailable (no fabricated context)")
        return pd.DataFrame(columns=["depmap_id"])
    try:
        df, missing = omics.build_curated_expression(poi_genes=genes)
        # widen: use the full 24Q4 line panel (already 1673 rows)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(CACHE_CSV)
        logger.info("wrote context expression matrix %d x %d (%d genes "
                    "missing from DepMap)", df.shape[0], df.shape[1],
                    len(missing))
        return df
    except Exception as exc:  # pragma: no cover
        logger.warning("could not build context expression: %s", exc)
        return pd.DataFrame()


_lookup: ExpressionLookup | None = None


def lookup() -> ExpressionLookup:
    global _lookup
    if _lookup is None:
        _lookup = ExpressionLookup()
    return _lookup


def map_cell(cell_line: str) -> dict[str, Any]:
    """DepMap mapping for one cell-line name (deterministic, offline)."""
    names = [cell_line]
    try:
        mp = cellline.map_cell_lines(names)
    except Exception as exc:
        return {"cell_line": cell_line, "depmap_id": None, "lineage": None,
                "mapped": False, "error": str(exc)}
    row = mp.iloc[0]
    return {"cell_line": row["cell_line"], "depmap_id": row["depmap_id"],
            "lineage": row["lineage"],
            "mapped": row["mapping_status"] == "mapped"}


def tissue_to_lineages(tissue: str | None) -> list[str] | None:
    if not tissue:
        return None
    t = str(tissue).lower()
    for k, lineages in TISSUE_LINEAGE_KEYWORDS.items():
        if k in t:
            return lineages
    return None


def context_scores(poi_gene: str | None, cell_line: str | None,
                   tissue: str | None, e3_gene: str
                   ) -> dict[str, Any]:
    """Per-E3 cell-context axis for a query.

    Returns score/confidence and rich flags. score=None when no real
    expression context can be established.
    """
    lu = lookup()
    m = lu._ensure() if lu.matrix is None else lu.matrix
    if m is None or len(m) == 0:
        return {"score": None, "confidence": 0.0, "flags": ["no_expression_db"],
                "e3_expression_percentile": None,
                "adaptor_expression_percentile": None,
                "poi_expression_percentile": None,
                "context_source": "unavailable"}
    cat = load_catalog()
    row = cat[cat["e3_gene"] == e3_gene]
    adaptors = (str(row.iloc[0]["adaptor_genes"]).split("|")
                if len(row) else [])
    adaptors = [a for a in adaptors if a]

    if cell_line:
        cm = map_cell(cell_line)
        did = cm["depmap_id"]
        lineage = cm["lineage"]
        if not cm["mapped"] or did not in m.index:
            return {"score": None, "confidence": 0.0,
                    "flags": ["cell_unmapped_or_no_expression"],
                    "cell_line": cell_line,
                    "e3_expression_percentile": None,
                    "adaptor_expression_percentile": None,
                    "poi_expression_percentile": None,
                    "context_source": "depmap24q4",
                    "lineage": lineage}
        e3p = lu.percentile(e3_gene, did)
        ap = ([p for p in (lu.percentile(a, did) for a in adaptors)
               if p is not None] if adaptors else [])
        adaptor_p = float(np.mean(ap)) if ap else None
        poi_p = lu.percentile(poi_gene, did) if poi_gene else None
        e3v = None if e3p is None else e3p
        # expression sufficiency: E3 percentile and (when CRL) adaptors
        parts = [p for p in (e3v, adaptor_p) if p is not None]
        if not parts:
            return {"score": None, "confidence": 0.0,
                    "flags": ["gene_missing_from_depmap"],
                    "e3_expression_percentile": None,
                    "adaptor_expression_percentile": adaptor_p,
                    "poi_expression_percentile": poi_p,
                    "context_source": "depmap24q4", "lineage": lineage}
        score = float(np.mean(parts))
        # low E3 expression is penalised naturally (percentile)
        missing = int(e3p is None) + int((adaptor_p is None) and bool(adaptors))
        conf = 0.9 * (1.0 - 0.25 * missing)
        return {"score": round(score, 4), "confidence": round(conf, 4),
                "flags": [],
                "e3_expression_percentile": (None if e3p is None
                                             else round(e3p, 4)),
                "adaptor_expression_percentile": (None if adaptor_p is None
                                                  else round(adaptor_p, 4)),
                "poi_expression_percentile": (None if poi_p is None
                                              else round(poi_p, 4)),
                "context_source": "depmap24q4_tpm", "lineage": lineage,
                "depmap_id": did}

    if tissue:
        lineages = tissue_to_lineages(tissue)
        if not lineages or len(m) == 0:
            return {"score": None, "confidence": 0.0,
                    "flags": ["tissue_not_mapped"],
                    "e3_expression_percentile": None, "context_source": "none"}
        # aggregate DepMap lines of matching lineages (real median of lines)
        meta = _model_meta()
        keep = meta[meta["lineage"].isin(lineages)]
        ids = [x for x in keep["depmap_id"] if x in m.index]
        if len(ids) < 3:
            return {"score": None, "confidence": 0.0,
                    "flags": ["too_few_lines_for_tissue"],
                    "context_source": "depmap24q4"}
        e3v = m.loc[ids, e3_gene].dropna() if e3_gene in m.columns else None
        if e3v is None or len(e3v) < 3:
            return {"score": None, "confidence": 0.0,
                    "flags": ["gene_missing_from_depmap"],
                    "context_source": "depmap24q4"}
        # percentile of the line-median within the full panel
        med = float(np.median(e3v))
        col = m[e3_gene].dropna()
        score = float((col <= med).mean()) if len(col) else None
        ap = None
        if adaptors:
            vals = [m.loc[ids, a].dropna() for a in adaptors if a in m.columns]
            if vals:
                amed = float(np.mean([float(np.median(v)) for v in vals]))
                acol = np.concatenate(
                    [m[a].dropna().to_numpy() for a in adaptors
                     if a in m.columns])
                ap = float((acol <= amed).mean()) if len(acol) else None
        parts = [p for p in (score, ap) if p is not None]
        return {"score": (round(float(np.mean(parts)), 4) if parts else None),
                "confidence": round(0.7 if parts else 0.0, 4),
                "flags": [],
                "e3_expression_percentile": (None if score is None
                                             else round(score, 4)),
                "adaptor_expression_percentile": (None if ap is None
                                                  else round(ap, 4)),
                "poi_expression_percentile": None,
                "context_source": "depmap24q4_lineage_median",
                "lineages": lineages}

    return {"score": None, "confidence": 0.0,
            "flags": ["no_cell_line_or_tissue"],
            "e3_expression_percentile": None,
            "adaptor_expression_percentile": None,
            "poi_expression_percentile": None, "context_source": "none"}


def _model_meta() -> pd.DataFrame:
    if not hasattr(_model_meta, "_cache"):
        try:
            mp = cellline._load_depmap_model()
            _model_meta._cache = pd.DataFrame({
                "depmap_id": mp["ModelID"], "lineage": mp["OncotreeLineage"]})
        except Exception:
            _model_meta._cache = pd.DataFrame(columns=["depmap_id", "lineage"])
    return _model_meta._cache


def expression_breadth(e3_gene: str) -> dict[str, Any]:
    """Expression restriction across DepMap lineages (real specificity)."""
    m = lookup()._ensure()
    if e3_gene not in m.columns:
        return {"score": None, "restricted_lineages": None,
                "expressed_lineages": None}
    col = m[e3_gene].dropna()
    if len(col) == 0:
        return {"score": None, "restricted_lineages": None,
                "expressed_lineages": None}
    meta = _model_meta()
    joined = meta.join(col.rename("v"), on="depmap_id", how="inner")
    joined = joined[joined["v"] >= 0.5 * col.quantile(0.5)]
    expressed = sorted(joined["lineage"].dropna().unique()) if len(joined) else []
    total = meta["lineage"].nunique()
    frac = len(expressed) / total if total else None
    # higher score = more restricted (fewer lineages express it)
    score = 1.0 - frac if frac is not None else None
    return {"score": (None if score is None else round(float(score), 4)),
            "restricted_lineages": expressed if len(expressed) <= 4 else None,
            "expressed_lineages": expressed}
