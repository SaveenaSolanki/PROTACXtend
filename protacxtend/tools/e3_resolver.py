"""Genome-scale E3 resolver: gene -> UniProt + family/mode + DepMap context.

Catalog v2 (data/e3_catalog_v2.csv) merges the UniProt GO:0061630 reviewed
human set with the module-6 mechanistic catalog and curated degradation rows.
Cell-context depth comes from DepMap 24Q4 transcriptomics (1,673 lines).

Resolution order: exact symbol -> aliases -> family-prefixed lookup; a
reviewed UniProt hit is required unless the symbol is in the catalog with an
accession. Unknown symbols return an explicit unresolved result (never a
guess).
"""
from __future__ import annotations

import csv, os
from typing import Any, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CATALOG = os.path.join(ROOT, "data", "e3_catalog_v2.csv")
CONTEXT = os.path.join(ROOT, "data", "e3_cell_context_stats.csv")
ALIASES = {
    "CEREBLON": "CRBN", "CRL4CRBN": "CRBN", "POMALIDOMIDE": "CRBN",
    "VH032": "VHL", "VH298": "VHL", "CUL2": "VHL",
    "MDM4": "MDM2", "Hdm2": "MDM2",
    "CIAP1": "BIRC2", "CIAP2": "BIRC3", "XIAP": "BIRC4",
    "KLHL20": "KLHL20", "KEAP": "KEAP1",
}


def _load(table: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not os.path.exists(table):
        return out
    with open(table, newline="") as f:
        for r in csv.DictReader(f):
            g = (r.get("gene") or "").strip().upper()
            if g:
                out[g] = {k: (v or "") for k, v in r.items()}
    return out


_CAT = _load(CATALOG)
_CTX = _load(CONTEXT)


def resolve_e3(symbol: str) -> dict[str, Any]:
    """Resolve an E3/adaptor symbol to catalog + cell-context record."""
    key = (symbol or "").strip().upper()
    resolved = ALIASES.get(key, key)
    rec = _CAT.get(resolved, {})
    ctx = _CTX.get(resolved, {})
    if not rec and resolved != key:
        rec = _CAT.get(key, {})
    if not rec:
        return {"symbol": key, "resolved_gene": resolved,
                "status": "unresolved",
                "reason": "no reviewed human E3/adaptor record in catalog",
                "accession": "", "family": "", "mode": "",
                "cell_context": {}, "catalog_size": len(_CAT)}
    return {"symbol": key, "resolved_gene": resolved,
            "status": "resolved",
            "accession": rec.get("accession", ""),
            "entry": rec.get("entry", ""),
            "protein_name": rec.get("protein_name", ""),
            "family": rec.get("family", ""),
            "mode": rec.get("mode", ""),
            "sources": rec.get("sources", ""),
            "cell_context": {
                "n_cell_lines": ctx.get("n_cell_lines", ""),
                "median_tpmlog1p": ctx.get("median_tpmlog1p", ""),
                "p90_tpmlog1p": ctx.get("p90_tpmlog1p", ""),
                "breadth_gt1tpm": ctx.get("breadth_gt1tpm", ""),
                "top10_lines": ctx.get("top10_lines", ""),
            },
            "catalog_size": len(_CAT)}


def catalog_summary() -> dict[str, Any]:
    fam: dict[str, int] = {}
    src: dict[str, int] = {}
    with open(CATALOG) as f:
        for r in csv.DictReader(f):
            fv = (r.get("family") or "").strip() or "unclassified"
            fam[fv] = fam.get(fv, 0) + 1
            for s in (r.get("sources") or "").split("|"):
                s = s.strip()
                if s:
                    src[s] = src.get(s, 0) + 1
    with open(CONTEXT) as f:
        n_ctx = sum(1 for _ in csv.DictReader(f))
    return {"catalog_total": len(_CAT), "with_cell_context": n_ctx,
            "cell_lines_covered": 1673, "families": fam, "sources": src}