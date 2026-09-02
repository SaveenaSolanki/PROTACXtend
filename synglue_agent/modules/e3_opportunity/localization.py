"""Subcellular localization axis (Module 6).

Compartments come from UniProt (reviewed human) annotations cached offline in
data/uniprot_localization.csv (source: REST search, gene_exact + organism
9606, SUBCELLULAR LOCATION comment). Both POI and E3 entries are looked up by
gene; any gene without an annotation returns UNKNOWN (score None) — never a
guessed compartment.

Compartment compatibility is defined on shared keywords (nucleus, cytosol,
membrane, er, golgi, mitochondrion, secreted, chromosome). Membrane-cytosol
proteins (e.g., EGFR, BTK) are treated as compatible with cytosol/membrane
machinery. None of this is a substitute for experimental colocalization.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
UNIPROT_CSV = DATA_DIR / "uniprot_localization.csv"

_KEYWORDS = {
    "nucleus": ["nucleus", "nucleoplasm", "chromosome", "nucleolus", "nuclear"],
    "cytosol": ["cytoplasm", "cytosol"],
    "membrane": ["membrane", "cell membrane", "plasma"],
    "er": ["endoplasmic reticulum"],
    "golgi": ["golgi"],
    "mitochondrion": ["mitochondrion", "mitochondrial"],
    "secreted": ["secreted", "extracellular"],
}


def _load() -> pd.DataFrame:
    if not UNIPROT_CSV.exists():
        return pd.DataFrame(columns=["gene", "uniprot", "locations", "ok"])
    return pd.read_csv(UNIPROT_CSV)


_table: pd.DataFrame | None = None


def table() -> pd.DataFrame:
    global _table
    if _table is None:
        _table = _load()
    return _table


def compartments(gene: str) -> list[str]:
    t = table()
    hit = t[t["gene"].astype(str).str.upper() == str(gene).upper()]
    if len(hit) == 0 or not str(hit.iloc[0].get("locations", "")):
        return []
    return [s for s in str(hit.iloc[0]["locations"]).split("|") if s]


def _classes(loc_texts: list[str]) -> set[str]:
    out = set()
    for lt in loc_texts:
        low = lt.lower()
        for cls, kws in _KEYWORDS.items():
            if any(k in low for k in kws):
                out.add(cls)
    return out


def compatibility(poi_gene: str, e3_gene: str) -> dict[str, Any]:
    """0..1 compatibility; None when either annotation is missing."""
    poi = compartments(poi_gene)
    e3 = compartments(e3_gene)
    if not poi or not e3:
        return {"score": None, "poi_compartments": poi,
                "e3_compartments": e3, "confidence": 0.0,
                "missing": [g for g, v in ((poi_gene, poi), (e3_gene, e3))
                            if not v]}
    pcls, ecls = _classes(poi), _classes(e3)
    # membrane/cytosol reachability: many signalling proteins cycle
    shared = pcls & ecls
    if shared:
        return {"score": 1.0, "poi_compartments": poi,
                "e3_compartments": e3, "confidence": 0.9,
                "shared": sorted(shared)}
    # cytosol is permissive for membrane/secreted machinery
    permissive = {"cytosol", "membrane"}
    if (pcls & permissive) and (ecls & permissive) and not (
            pcls - permissive) and not (ecls - permissive):
        return {"score": 0.7, "poi_compartments": poi,
                "e3_compartments": e3, "confidence": 0.6,
                "shared": sorted(shared)}
    return {"score": 0.15, "poi_compartments": poi, "e3_compartments": e3,
            "confidence": 0.7, "shared": sorted(shared)}
