"""E3 tissue/cell-line expression & context atlas (Module 6 extension).

Adds a *separately inspectable* tissue-level expression component derived from
the Human Protein Atlas (HPA) to complement the existing DepMap cell-line
component. Three independent measurements are kept distinct:

  * ``rna_ntpm``       — HPA consensus tissue RNA (HPA/GTEx/FANTOM5 nTPM)
  * ``protein_ihc``    — HPA antibody-based tissue annotation
                         (not detected / low / medium / high)
  * ``protein_ms``     — HPA tissue mass-spectrometry intensity

Design constraints (honesty):
  * Every value is copied from HPA; missing values stay ``None``.
  * The per-component score and the combined score are reported separately.
  * A combined ``tissue_score`` renormalises over the *available* components;
    ``confidence`` is discounted when components are missing.
  * HPA tissue names are mapped from common query terms; an unmapped tissue
    produces an explicit flag, never a guessed value.
  * This is expression/context evidence, NOT a degradation measurement.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
RNA_CSV = DATA_DIR / "hpa_tissue_rna.csv"
IHC_CSV = DATA_DIR / "hpa_tissue_protein_ihc.csv"
MS_CSV = DATA_DIR / "hpa_tissue_protein_ms.csv"
PROV_JSON = DATA_DIR / "hpa_tissue_provenance.json"

# component weights (renormalised over what is present)
COMPONENT_WEIGHTS = {"rna": 0.50, "ihc": 0.30, "ms": 0.20}
# canonical catalog symbol -> symbol used by HPA / DepMap
GENE_ALIASES = {"BIRC4": "XIAP", "TCEB1": "ELOC", "TCEB2": "ELOB"}
IHC_SCALE = {"not detected": 0.0, "low": 0.33, "medium": 0.66, "high": 1.0,
             "negative": 0.0, "weak": 0.33, "moderate": 0.66, "strong": 1.0}

# common query term -> HPA tissue column key
TISSUE_ALIASES = {
    "blood": "bone_marrow", "bone marrow": "bone_marrow",
    "haematopoietic": "bone_marrow", "hematopoietic": "bone_marrow",
    "myeloma": "bone_marrow", "leukemia": "bone_marrow",
    "lymphoma": "lymph_node", "lymph": "lymph_node",
    "colon": "colon", "colorectal": "colon", "crc": "colon",
    "lung": "lung", "nsclc": "lung", "breast": "breast",
    "prostate": "prostate", "kidney": "kidney", "renal": "kidney",
    "liver": "liver", "hepatocellular": "liver", "pancreas": "pancreas",
    "brain": "cerebral_cortex", "cns": "cerebral_cortex",
    "glioma": "cerebral_cortex", "skin": "skin", "melanoma": "skin",
    "ovary": "ovary", "ovarian": "ovary", "stomach": "stomach",
    "gastric": "stomach", "esophagus": "esophagus", "testis": "testis",
    "thymus": "thymus", "spleen": "spleen", "thyroid": "thyroid_gland",
    "bladder": "urinary_bladder", "uterus": "endometrium",
    "endometrium": "endometrium", "cervix": "cervix",
    "adipose": "adipose_tissue", "muscle": "skeletal_muscle",
    "heart": "heart_muscle", "adrenal": "adrenal_gland",
}


class HPAAtlas:
    """Lazy loader over the curated HPA tables (offline)."""

    def __init__(self) -> None:
        self.rna: pd.DataFrame | None = None
        self.ihc: pd.DataFrame | None = None
        self.ms: pd.DataFrame | None = None
        self.provenance: dict | None = None

    def _ensure(self) -> None:
        if self.rna is None:
            self.rna = (pd.read_csv(RNA_CSV, index_col=0)
                        if RNA_CSV.exists() else pd.DataFrame())
        if self.ihc is None:
            self.ihc = (pd.read_csv(IHC_CSV, index_col=0)
                        if IHC_CSV.exists() else pd.DataFrame())
        if self.ms is None:
            self.ms = (pd.read_csv(MS_CSV, index_col=0)
                       if MS_CSV.exists() else pd.DataFrame())
        if self.provenance is None:
            self.provenance = (json.loads(PROV_JSON.read_text())
                               if PROV_JSON.exists() else {})

    # -- basic access -------------------------------------------------------
    def available(self) -> bool:
        self._ensure()
        return self.rna is not None and not self.rna.empty

    def genes(self) -> list[str]:
        self._ensure()
        return [] if self.rna is None else list(self.rna.index)

    def tissues(self) -> list[str]:
        self._ensure()
        return [] if self.rna is None else list(self.rna.columns)

    def resolve_tissue(self, tissue: str | None) -> str | None:
        self._ensure()
        if not tissue or self.rna is None:
            return None
        t = str(tissue).strip().lower().replace("-", " ").replace("_", " ")
        cols = {c.lower().replace("_", " "): c for c in self.rna.columns}
        if t in cols:
            return cols[t]
        for k, v in TISSUE_ALIASES.items():
            if k in t and v in self.rna.columns:
                return v
        # last resort: token overlap
        for c in self.rna.columns:
            cl = c.lower().replace("_", " ")
            if any(tok and tok in cl for tok in t.split()):
                return c
        return None

    def _rna_percentile(self, gene: str, tissue: str) -> float | None:
        gene = GENE_ALIASES.get(gene, gene)
        if self.rna is None or gene not in self.rna.index or tissue not in self.rna.columns:
            return None
        row = pd.to_numeric(self.rna.loc[gene], errors="coerce").dropna()
        if len(row) < 3:
            return None
        v = self.rna.at[gene, tissue]
        if pd.isna(v):
            return None
        return float((row <= float(v)).mean())

    def _ms_percentile(self, gene: str, tissue: str) -> float | None:
        gene = GENE_ALIASES.get(gene, gene)
        if self.ms is None or gene not in self.ms.index or tissue not in self.ms.columns:
            return None
        row = pd.to_numeric(self.ms.loc[gene], errors="coerce").dropna()
        if len(row) < 3:
            return None
        v = self.ms.at[gene, tissue]
        if pd.isna(v):
            return None
        return float((row <= float(v)).mean())

    def expression(self, gene: str, tissue: str) -> dict[str, Any]:
        """Raw per-component values for one gene/tissue (no interpretation)."""
        self._ensure()
        raw_gene = gene
        gene = GENE_ALIASES.get(gene, gene)
        col = self.resolve_tissue(tissue)
        out: dict[str, Any] = {"gene": raw_gene, "resolved_gene": gene,
                               "tissue_query": tissue,
                               "tissue_resolved": col}
        if col is None:
            out.update({"rna_ntpm": None, "protein_ihc": None,
                        "protein_ms": None, "flags": ["tissue_not_mapped"]})
            return out
        rna = ihc = ms = None
        if self.rna is not None and gene in self.rna.index and col in self.rna.columns:
            v = self.rna.at[gene, col]
            rna = None if pd.isna(v) else float(v)
        if self.ihc is not None and gene in self.ihc.index and col in self.ihc.columns:
            v = self.ihc.at[gene, col]
            ihc = None if (pd.isna(v) or str(v).lower() in {"nan", "none"}) else str(v)
        if self.ms is not None and gene in self.ms.index and col in self.ms.columns:
            v = self.ms.at[gene, col]
            ms = None if pd.isna(v) else float(v)
        out.update({"rna_ntpm": rna, "protein_ihc": ihc, "protein_ms": ms,
                    "flags": []})
        return out

    # -- scoring ------------------------------------------------------------
    def tissue_score(self, gene: str, tissue: str,
                     adaptor_genes: list[str] | None = None) -> dict[str, Any]:
        """Combined, component-separated tissue expression score in [0,1]."""
        self._ensure()
        expr = self.expression(gene, tissue)
        col = expr["tissue_resolved"]
        if col is None:
            return {"score": None, "confidence": 0.0,
                    "components": {}, "expression": expr,
                    "flags": ["tissue_not_mapped"],
                    "context_source": "hpa_tissue"}

        comps: dict[str, float] = {}
        raw: dict[str, Any] = {}
        rna_p = self._rna_percentile(gene, col) if expr["rna_ntpm"] is not None else None
        if rna_p is not None:
            comps["rna"] = rna_p
            raw["rna_percentile"] = round(rna_p, 4)
        if expr["protein_ihc"] is not None:
            key = str(expr["protein_ihc"]).strip().lower()
            if key in IHC_SCALE:
                comps["ihc"] = IHC_SCALE[key]
                raw["ihc_label"] = expr["protein_ihc"]
        ms_p = self._ms_percentile(gene, col) if expr["protein_ms"] is not None else None
        if ms_p is not None:
            comps["ms"] = ms_p
            raw["ms_percentile"] = round(ms_p, 4)

        adaptor_p = None
        if adaptor_genes:
            aps = [p for p in (self._rna_percentile(a, col) for a in adaptor_genes)
                   if p is not None]
            if aps:
                adaptor_p = float(np.mean(aps))
                comps["adaptors"] = adaptor_p
                raw["adaptor_rna_percentile"] = round(adaptor_p, 4)

        if not comps:
            return {"score": None, "confidence": 0.0, "components": {},
                    "expression": expr,
                    "flags": ["no_hpa_measurement_for_gene_tissue"],
                    "context_source": "hpa_tissue"}

        # renormalise component weights over the present components
        present = {k: v for k, v in comps.items() if k in COMPONENT_WEIGHTS}
        if present:
            wsum = sum(COMPONENT_WEIGHTS[k] for k in present)
            score = sum(COMPONENT_WEIGHTS[k] * v for k, v in present.items()) / wsum
        else:  # only adaptors present
            score = adaptor_p
        n_total = 3 + (1 if adaptor_genes else 0)
        conf = min(0.9, 0.35 + 0.2 * len(comps)) * (1.0 if len(comps) >= 2 else 0.85)
        return {
            "score": round(float(score), 4),
            "confidence": round(float(conf), 4),
            "components": {k: round(float(v), 4) for k, v in comps.items()},
            "component_weights": COMPONENT_WEIGHTS,
            "expression": expr,
            "raw": raw,
            "n_components_present": len(comps),
            "n_components_possible": n_total,
            "context_source": "hpa_tissue",
            "flags": [],
            "cell_line_component": "see DepMap cell_context axis",
        }

    def profile(self, gene: str) -> dict[str, Any]:
        """Whole-tissue RNA profile + specificity (tau-like) for one gene."""
        self._ensure()
        gene = GENE_ALIASES.get(gene, gene)
        if self.rna is None or gene not in self.rna.index:
            return {"gene": gene, "available": False, "profile": {},
                    "tissue_specificity": None}
        row = pd.to_numeric(self.rna.loc[gene], errors="coerce").dropna()
        if row.empty:
            return {"gene": gene, "available": False, "profile": {},
                    "tissue_specificity": None}
        mx = float(row.max())
        tau = (float((1 - row / mx).sum()) / (len(row) - 1)) if mx > 0 and len(row) > 1 else None
        top = row.sort_values(ascending=False)
        return {
            "gene": gene, "available": True,
            "profile": {str(k): float(v) for k, v in row.items()},
            "top_tissues": {str(k): float(v) for k, v in top.head(5).items()},
            "max_ntpm": mx,
            "tissue_specificity": None if tau is None else round(1 - tau, 4),
            "median_ntpm": float(row.median()),
        }

    def top_e3s_for_tissue(self, tissue: str, e3_genes: list[str],
                           top_k: int = 10) -> list[dict[str, Any]]:
        """Rank E3 genes by combined tissue expression in one tissue."""
        out = []
        for g in e3_genes:
            s = self.tissue_score(g, tissue)
            if s.get("score") is not None:
                out.append({"e3_gene": g, **s})
        out.sort(key=lambda d: d["score"], reverse=True)
        return out[:top_k]


_atlas: HPAAtlas | None = None


def atlas() -> HPAAtlas:
    global _atlas
    if _atlas is None:
        _atlas = HPAAtlas()
    return _atlas


def tissue_expression(gene: str, tissue: str) -> dict[str, Any]:
    return atlas().expression(gene, tissue)


def tissue_score(gene: str, tissue: str,
                 adaptor_genes: list[str] | None = None) -> dict[str, Any]:
    return atlas().tissue_score(gene, tissue, adaptor_genes)


def gene_tissue_profile(gene: str) -> dict[str, Any]:
    return atlas().profile(gene)


def atlas_summary() -> dict[str, Any]:
    a = atlas()
    a._ensure()
    prov = a.provenance or {}
    return {
        "available": a.available(),
        "n_genes": 0 if a.rna is None else int(a.rna.shape[0]),
        "n_rna_tissues": 0 if a.rna is None else int(a.rna.shape[1]),
        "n_ihc_tissues": 0 if a.ihc is None else int(a.ihc.shape[1]),
        "n_ms_tissues": 0 if a.ms is None else int(a.ms.shape[1]),
        "source": prov.get("source"),
        "retrieved_utc": prov.get("retrieved_utc"),
    }
