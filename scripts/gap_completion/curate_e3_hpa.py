#!/usr/bin/env python3
"""Curate the E3 expression/context atlas from the Human Protein Atlas (HPA).

Evidence sources (all public, no fabrication):
  * Tissue RNA  : HPA ``t_RNA_<tissue>`` nTPM (consensus HPA/GTEx/FANTOM5).
  * Tissue protein (IHC): HPA ``t_APE_<tissue>`` annotation (not detected/low/
    medium/high) from antibody-based protein profiling.
  * Tissue protein (MS): HPA ``t_ms_<tissue>`` intensity from mass spectrometry.

The HPA search API is queried per gene and the raw JSON is cached under
``outputs/omics_cache/hpa/`` so the atlas is reproducible offline. Only values
returned by HPA are written; missing values stay missing.

Outputs (module data dir):
  * hpa_tissue_rna.csv       gene x tissue nTPM
  * hpa_tissue_protein_ihc.csv  gene x tissue IHC annotation
  * hpa_tissue_protein_ms.csv   gene x tissue MS intensity
  * hpa_tissue_provenance.json  source URLs, retrieval timestamp, tissue list,
                                gene list, HPA version string.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "protacxtend" / "modules" / "e3_opportunity" / "data"
CACHE_DIR = PROJECT_ROOT / "outputs" / "omics_cache" / "hpa"
HELP_URL = "https://www.proteinatlas.org/about/help/dataaccess"
API = "https://www.proteinatlas.org/api/search_download.php"

# E3 genes + CRL core adaptors (matches e3_opportunity.e3_catalog / context)
E3_GENES = [
    "CRBN", "VHL", "DCAF1", "DCAF11", "DCAF15", "DCAF16", "FEM1B", "FBXO22",
    "KEAP1", "KLHDC2", "KLHL20", "MDM2", "RNF114", "RNF4", "UBR1", "BIRC2",
    "BIRC3", "BIRC4", "XIAP", "HUWE1", "NEDD4", "NEDD4L", "WWP1", "UBE3A", "STUB1",
    "PRKN", "RNF8", "RNF168", "TRIM21", "SIAH1", "RNF7",
    # CRL core / adaptor machinery used in the expression axis
    "DDB1", "CUL1", "CUL2", "CUL3", "CUL4A", "CUL4B", "CUL5", "RBX1", "SKP1",
    "TCEB1", "TCEB2", "ELOB", "ELOC",
]


def _get(url: str, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ProtacPilot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _tissue_keys(prefix: str) -> list[str]:
    html = _get(HELP_URL).decode("utf-8", "ignore")
    keys = sorted(set(re.findall(rf"\b{re.escape(prefix)}[a-zA-Z0-9_]+", html)))
    # drop aggregate/summary keys that are not one value per tissue
    drop = {"t_RNA_tissue", "t_RNA_tissue_specificity", "t_RNA_tissue_distribution",
            "t_ms_tissue", "t_APE_tissue"}
    return [k for k in keys if k not in drop]


def _fetch_gene(gene: str, columns: list[str], tag: str) -> dict | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{gene}_{tag}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    # chunk columns to keep the GET URL reasonable
    merged: dict = {}
    for i in range(0, len(columns), 30):
        chunk = columns[i:i + 30]
        params = urllib.parse.urlencode({
            "search": gene, "format": "json",
            "columns": "g,gs," + ",".join(chunk), "compress": "no"})
        url = f"{API}?{params}"
        for attempt in range(4):
            try:
                data = json.loads(_get(url).decode("utf-8"))
                for rec in data:
                    if rec.get("Gene") == gene:
                        merged.update(rec)
                break
            except Exception as exc:  # transient network
                if attempt == 3:
                    print(f"  !! {gene} {tag} chunk {i}: {exc}", file=sys.stderr)
                time.sleep(1.5 * (attempt + 1))
        time.sleep(0.12)
    if not merged:
        return None
    cache.write_text(json.dumps(merged))
    return merged


def _parse_number(value):
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() in {"nan", "none", "null"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _asset(label: str) -> str:
    """'Tissue RNA - liver [nTPM]' -> 'liver'.

    The HPA search API echoes human-readable column *labels* (not the raw
    ``t_RNA_*`` keys), so we parse the tissue out of the label.
    """
    body = re.sub(r"\s*\[[^\]]*\]\s*$", "", str(label)).strip()
    m = re.search(r"-\s*(.*)$", body)
    return (m.group(1) if m else body).strip().replace(" ", "_")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Discovering HPA tissue columns ...")
    rna_keys = _tissue_keys("t_RNA_")
    ihc_keys = _tissue_keys("t_APE_")
    ms_keys = _tissue_keys("t_ms_")
    print(f"  RNA={len(rna_keys)} IHC={len(ihc_keys)} MS={len(ms_keys)}")

    rna_rows, ihc_rows, ms_rows = [], [], []
    for idx, gene in enumerate(E3_GENES, 1):
        print(f"[{idx}/{len(E3_GENES)}] {gene}")
        rec = _fetch_gene(gene, rna_keys + ihc_keys + ms_keys, "tissue")
        if rec is None:
            print(f"  no HPA record for {gene}", file=sys.stderr)
            continue
        rrow, irow, mrow = {"gene": gene}, {"gene": gene}, {"gene": gene}
        for k, v in rec.items():
            if k in ("Gene", "Gene synonym"):
                continue
            if k.startswith("Tissue RNA -"):
                rrow[_asset(k)] = _parse_number(v)
            elif k.startswith("Tissue Annotation (IH) -"):
                irow[_asset(k)] = None if v in (None, "nan") else str(v)
            elif k.startswith("Tissue protein MS -"):
                mrow[_asset(k)] = _parse_number(v)
        rna_rows.append(rrow)
        ihc_rows.append(irow)
        ms_rows.append(mrow)

    rna = pd.DataFrame(rna_rows).set_index("gene")
    ihc = pd.DataFrame(ihc_rows).set_index("gene")
    ms = pd.DataFrame(ms_rows).set_index("gene")
    # order tissues consistently
    rna = rna.reindex(sorted(rna.columns), axis=1)
    ihc = ihc.reindex(sorted(ihc.columns), axis=1)
    ms = ms.reindex(sorted(ms.columns), axis=1)

    rna.to_csv(OUT_DIR / "hpa_tissue_rna.csv")
    ihc.to_csv(OUT_DIR / "hpa_tissue_protein_ihc.csv")
    ms.to_csv(OUT_DIR / "hpa_tissue_protein_ms.csv")

    provenance = {
        "source": "Human Protein Atlas (proteinatlas.org) search_download API",
        "help_url": HELP_URL,
        "api": API,
        "columns": {"rna": "t_RNA_<tissue> [nTPM]",
                    "protein_ihc": "t_APE_<tissue> (Tissue Annotation (IH))",
                    "protein_ms": "t_ms_<tissue> [Intensity]"},
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "genes": sorted(rna.index.tolist()),
        "n_genes": int(rna.shape[0]),
        "tissues_rna": list(rna.columns),
        "tissues_ihc": list(ihc.columns),
        "tissues_ms": list(ms.columns),
        "note": ("Only values returned by HPA are stored; missing values remain "
                 "missing. RNA nTPM is the HPA consensus (HPA/GTEx/FANTOM5). IHC "
                 "is antibody-based annotation; MS is intensity. These are "
                 "expression/context evidence, NOT degradation measurements."),
    }
    (OUT_DIR / "hpa_tissue_provenance.json").write_text(
        json.dumps(provenance, indent=2))
    print(f"wrote {rna.shape} RNA, {ihc.shape} IHC, {ms.shape} MS -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
