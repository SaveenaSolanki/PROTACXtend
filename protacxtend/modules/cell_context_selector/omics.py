"""DepMap/CCLE transcriptomics curation + context features (Module 5).

Curation: extracts a small (cell line x gene) TPM-log1p matrix from the public
DepMap 24Q4 'OmicsExpressionProteinCodingGenesTPMLogp1' file (cached under
outputs/omics_cache/expression_tpmlogp1.csv; source recorded in the manifest)
for: (i) the ubiquitin-proteasome/E3/transporter panel below and (ii) every
POI gene observed in the curated degradation table. The extracted matrix is
tiny and is committed under data/cell_context_expression.csv for
reproducibility; the 506 MB raw file is not.

Gene set (HGNC symbols):
* E3 machinery / CRL core: CRBN DDB1 CUL4A CUL4B RBX1 CUL1 CUL2 CUL3 SKP1
  VHL TCEB1 TCEB2 KEAP1 RNF7 MDM2 FEM1B RNF114 BIRC2 BIRC3 BIRC4 UBR1 ARIH1
* E2 enzymes: UBE2D1 UBE2D2 UBE2D3 UBE2G1 UBE2G2 UBE2L3 UBE2R1 UBE2R2 UBE2N
  UBE2M UBE2F UBE2K UBE2H UBE2E1 CDC34
* proteasome: PSMA1 PSMB5 PSMB6 PSMB8 PSMB9 PSMC1 PSMC2 PSMD2 PSMD11 PSMD14
  PSME1 PSMB10
* ubiquitin/chain/DUB: UBB UBC UBA52 RPS27A USP7 USP14 USP9X UCHL5 OTUB1
* drug transporters: ABCB1 ABCC1 ABCG2 ABCC3 SLC46A1
All features, never labels. Expression is a cell-state descriptor; it is not
a degradation measurement.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
OMICS_CACHE = Path(__file__).resolve().parents[3] / "outputs" / "omics_cache"
RAW_EXPRESSION = OMICS_CACHE / "expression_tpmlogp1.csv"
CURATED_EXPRESSION_CSV = DATA_DIR / "cell_context_expression.csv"
MANIFEST = DATA_DIR / "omics_provenance.json"

PANEL_GENES = [
    # E3 machinery / CRL core
    "CRBN", "DDB1", "CUL4A", "CUL4B", "RBX1", "CUL1", "CUL2", "CUL3", "SKP1",
    "VHL", "TCEB1", "TCEB2", "KEAP1", "RNF7", "MDM2", "FEM1B", "RNF114",
    "BIRC2", "BIRC3", "BIRC4", "UBR1", "ARIH1",
    # E2 ubiquitin-conjugating enzymes
    "UBE2D1", "UBE2D2", "UBE2D3", "UBE2G1", "UBE2G2", "UBE2L3", "UBE2R1",
    "UBE2R2", "UBE2N", "UBE2M", "UBE2F", "UBE2K", "UBE2H", "UBE2E1", "CDC34",
    # proteasome
    "PSMA1", "PSMB5", "PSMB6", "PSMB8", "PSMB9", "PSMB10", "PSMC1", "PSMC2",
    "PSMD2", "PSMD11", "PSMD14", "PSME1",
    # ubiquitin precursors / DUBs
    "UBB", "UBC", "UBA52", "RPS27A", "USP7", "USP14", "USP9X", "UCHL5",
    "OTUB1",
    # drug transporters
    "ABCB1", "ABCC1", "ABCG2", "ABCC3", "SLC46A1",
]

_GENE_COL = re.compile(r"^([A-Z0-9]+)\s+\(")


def _parse_gene_cols(cols) -> dict[str, str]:
    """map 'GENE (ENTREZ)' -> symbol for the columns we need."""
    out = {}
    for c in cols:
        m = _GENE_COL.match(str(c))
        if m:
            out[m.group(1)] = c
    return out


def build_curated_expression(poi_genes: list[str] | None = None,
                             raw_path=None) -> pd.DataFrame:
    """Extract the (cell line x genes) subset from the raw DepMap file."""
    from protacxtend.modules.cell_context_selector import dataset
    want = list(dict.fromkeys(list(PANEL_GENES) + list(poi_genes or [])))
    raw = pd.read_csv(Path(raw_path) if raw_path else RAW_EXPRESSION, nrows=0)
    gene2col = _parse_gene_cols(raw.columns)
    missing = [g for g in want if g not in gene2col]
    keep_cols = ["Unnamed: 0"] + [gene2col[g] for g in want if g in gene2col]
    df = pd.read_csv(Path(raw_path) if raw_path else RAW_EXPRESSION,
                     usecols=keep_cols)
    df = df.rename(columns={"Unnamed: 0": "depmap_id"})
    df = df.set_index("depmap_id")
    df.columns = [g for g in want if g in gene2col]
    return df, missing


def _gene_vocab_from_header(raw_path=None) -> set[str]:
    raw = pd.read_csv(Path(raw_path) if raw_path else RAW_EXPRESSION, nrows=0)
    gene2col = _parse_gene_cols(raw.columns)
    return set(gene2col.keys())


def ensure_curated_expression(rebuild: bool = False,
                              poi_genes: list[str] | None = None
                              ) -> pd.DataFrame:
    """Load the curated expression matrix; build from the raw cache first use."""
    if CURATED_EXPRESSION_CSV.exists() and not rebuild:
        df = pd.read_csv(CURATED_EXPRESSION_CSV)
        df = df.set_index("depmap_id")
        return df
    if poi_genes is None:
        from protacxtend.modules.cell_context_selector import dataset
        from protacxtend.modules.cell_context_selector.genemap import target_to_gene
        vocab = _gene_vocab_from_header()
        cur, _ = dataset.build_curated()
        poi_genes = sorted({g for g in
                            (target_to_gene(t, vocab)
                             for t in cur["target"].dropna())
                            if g})
    df, missing = build_curated_expression(poi_genes)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CURATED_EXPRESSION_CSV)
    MANIFEST.write_text(json.dumps({
        "source": "DepMap Public 24Q4 OmicsExpressionProteinCodingGenesTPMLogp1"
                  " (figshare file 51065489)",
        "raw_rows_models": int(len(df)),
        "genes": list(df.columns),
        "genes_missing_from_matrix": missing,
        "transform": "TPM log1p as shipped (no rescale)",
        "notes": "expression features only; never degradation labels",
    }, indent=2))
    return df


def load_expression() -> tuple[pd.DataFrame, dict[str, Any]]:
    """(expression matrix indexed by depmap_id, provenance)."""
    df = ensure_curated_expression()
    prov = {}
    if MANIFEST.exists():
        prov = json.loads(MANIFEST.read_text())
    return df, prov
