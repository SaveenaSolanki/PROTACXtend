"""E3 ligase candidate catalog (Module 6).

Curated, evidence-based table of E3 candidates for PROTAC development.
Every row carries a family, mechanism mode, CRL adaptor components (when the
E3 is a substrate receptor), canonical gene(s), and curated structural/
resistance facts with sources. Rows never assert that a novel E3 is usable
solely from expression — that is the ranker's job under its evidence gate.

Sources
-------
* family/mode: ubiquitin-system literature classification (RING/HECT/RBR/
  U-box; CRL adaptor or standalone).
* ligand/recruiter facts: in-repo cited E3-ligand library
  (synglue_agent/data/curated_e3_ligands.csv; DOI-cited rows only) — joined in
  recruiters.py, not duplicated here.
* curated ternary/complex PDB facts: retained from the project's evidence
  engine (CRBN-DDB1 4CI2 / BRD4-CRBN 6BN7; VHL-ELOB/ELOC 4W9O / BRD4-VHL
  5T35); other E3s list no curated complex PDB (structural evidence UNKNOWN).
* resistance notes: well-documented mechanisms only (CRBN loss/mutation under
  IMiD/lenalidomide selection; VHL loss-of-function in ccRCC) — no inference.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
CATALOG_CSV = DATA_DIR / "e3_catalog.csv"

# canonical gene -> row
# mode: 'crl4_adapter','crl2_adapter','crl3_adapter','scf_fbox','ring',
#       'hect','rbr','ubox','iap_ring'
CATALOG: dict[str, dict[str, Any]] = {
    "CRBN": {"family": "CRL4", "mode": "crl4_adapter",
             "adaptor_genes": ["DDB1", "CUL4A", "CUL4B", "RBX1"],
             "uniprot": "Q96SW2",
             "structure_facts": "CRBN-DDB1 PDB 4CI2; BRD4-CRBN ternary 6BN7 (curated)",
             "resistance": "CRBN loss/mutation selected under IMiD treatment "
                           "(multiple-myeloma literature, curated)"},
    "VHL": {"family": "CRL2", "mode": "crl2_adapter",
            "adaptor_genes": ["TCEB1", "TCEB2", "CUL2", "RBX1"],
            "uniprot": "P40337",
            "structure_facts": "VHL-ElonginBC PDB 4W9O; BRD4-VHL ternary 5T35 (curated)",
            "resistance": "VHL loss-of-function in clear-cell RCC (curated)"},
    "DCAF1": {"family": "CRL4", "mode": "crl4_adapter",
              "adaptor_genes": ["DDB1", "CUL4A", "CUL4B", "RBX1"],
              "uniprot": "Q9Y4B6", "structure_facts": "", "resistance": ""},
    "DCAF11": {"family": "CRL4", "mode": "crl4_adapter",
               "adaptor_genes": ["DDB1", "CUL4A", "CUL4B", "RBX1"],
               "uniprot": "Q8TEB1", "structure_facts": "", "resistance": ""},
    "DCAF15": {"family": "CRL4", "mode": "crl4_adapter",
               "adaptor_genes": ["DDB1", "CUL4A", "CUL4B", "RBX1"],
               "uniprot": "Q66K64", "structure_facts": "", "resistance": ""},
    "DCAF16": {"family": "CRL4", "mode": "crl4_adapter",
               "adaptor_genes": ["DDB1", "CUL4A", "CUL4B", "RBX1"],
               "uniprot": "Q9NXF7", "structure_facts": "", "resistance": ""},
    "FEM1B": {"family": "CRL2", "mode": "crl2_adapter",
              "adaptor_genes": ["TCEB1", "TCEB2", "CUL2", "RBX1"],
              "uniprot": "Q9UK73", "structure_facts": "", "resistance": ""},
    "FBXO22": {"family": "SCF", "mode": "scf_fbox",
               "adaptor_genes": ["SKP1", "CUL1", "RBX1"],
               "uniprot": "Q8NEZ5", "structure_facts": "", "resistance": ""},
    "KEAP1": {"family": "CRL3", "mode": "crl3_adapter",
              "adaptor_genes": ["CUL3", "RBX1"],
              "uniprot": "Q14145", "structure_facts": "", "resistance": ""},
    "KLHDC2": {"family": "CRL2", "mode": "crl2_adapter",
               "adaptor_genes": ["TCEB1", "TCEB2", "CUL2", "RBX1"],
               "uniprot": "Q9Y2U9", "structure_facts": "", "resistance": ""},
    "KLHL20": {"family": "CRL3", "mode": "crl3_adapter",
               "adaptor_genes": ["CUL3", "RBX1"],
               "uniprot": "Q9Y2M5", "structure_facts": "", "resistance": ""},
    "MDM2": {"family": "RING", "mode": "ring",
             "adaptor_genes": [],
             "uniprot": "Q00987", "structure_facts": "", "resistance": ""},
    "RNF114": {"family": "RING", "mode": "ring", "adaptor_genes": [],
               "uniprot": "Q9Y508", "structure_facts": "", "resistance": ""},
    "RNF4": {"family": "RING", "mode": "ring", "adaptor_genes": [],
             "uniprot": "P78317", "structure_facts": "", "resistance": ""},
    "UBR1": {"family": "RING", "mode": "ring", "adaptor_genes": [],
             "uniprot": "Q8IWV8", "structure_facts": "", "resistance": ""},
    "BIRC2": {"family": "IAP", "mode": "iap_ring", "adaptor_genes": [],
              "uniprot": "Q13490", "structure_facts": "", "resistance": ""},
    "BIRC3": {"family": "IAP", "mode": "iap_ring", "adaptor_genes": [],
              "uniprot": "Q13489", "structure_facts": "", "resistance": ""},
    "BIRC4": {"family": "IAP", "mode": "iap_ring", "adaptor_genes": [],
              "uniprot": "P98170", "structure_facts": "", "resistance": ""},
    # --- additional candidates (no curated recruiter) -----------------------
    "HUWE1": {"family": "HECT", "mode": "hect", "adaptor_genes": [],
              "uniprot": "Q7Z6Z7", "structure_facts": "", "resistance": ""},
    "NEDD4": {"family": "HECT", "mode": "hect", "adaptor_genes": [],
              "uniprot": "P46934", "structure_facts": "", "resistance": ""},
    "NEDD4L": {"family": "HECT", "mode": "hect", "adaptor_genes": [],
               "uniprot": "Q96PU5", "structure_facts": "", "resistance": ""},
    "WWP1": {"family": "HECT", "mode": "hect", "adaptor_genes": [],
             "uniprot": "Q9H0M0", "structure_facts": "", "resistance": ""},
    "UBE3A": {"family": "HECT", "mode": "hect", "adaptor_genes": [],
              "uniprot": "Q05086", "structure_facts": "", "resistance": ""},
    "STUB1": {"family": "U-box", "mode": "ubox", "adaptor_genes": [],
              "uniprot": "Q9UNE7", "structure_facts": "", "resistance": ""},
    "PRKN": {"family": "RBR", "mode": "rbr", "adaptor_genes": [],
             "uniprot": "O60260", "structure_facts": "", "resistance": ""},
    "RNF8": {"family": "RING", "mode": "ring", "adaptor_genes": [],
             "uniprot": "O76064", "structure_facts": "", "resistance": ""},
    "RNF168": {"family": "RING", "mode": "ring", "adaptor_genes": [],
               "uniprot": "Q9H6Y3", "structure_facts": "", "resistance": ""},
    "TRIM21": {"family": "TRIM", "mode": "ring", "adaptor_genes": [],
               "uniprot": "P19474", "structure_facts": "", "resistance": ""},
    "SIAH1": {"family": "RING", "mode": "ring", "adaptor_genes": [],
              "uniprot": "Q8IUQ4", "structure_facts": "", "resistance": ""},
    "RNF7": {"family": "CRL", "mode": "ring", "adaptor_genes": ["CUL5", "ELOB", "ELOC"],
             "uniprot": "Q9UBF6", "structure_facts": "", "resistance": ""},
}

# canonical names for database/legacy labels -> catalog gene(s)
E3_ALIASES = {
    "CRBN": ["CRBN"], "VHL": ["VHL"], "PVHL": ["VHL"],
    "MDM2": ["MDM2"], "FEM1B": ["FEM1B"], "RNF114": ["RNF114"],
    "Ubr1": ["UBR1"], "UBR1": ["UBR1"], "UBR box": ["UBR1"],
    "IAP": ["BIRC2", "BIRC3"], "cIAP1": ["BIRC2"], "XIAP": ["BIRC4"],
    "DCAF1": ["DCAF1"], "DCAF11": ["DCAF11"], "DCAF15": ["DCAF15"],
    "DCAF16": ["DCAF16"], "FBXO22": ["FBXO22"], "KEAP1": ["KEAP1"],
    "KLHDC2": ["KLHDC2"], "KLHL20": ["KLHL20"], "RNF4": ["RNF4"],
    "AhR": [],  # transcription-factor adapter, not a ubiquitin ligase
}

FAMILIES = {v["family"] for v in CATALOG.values()}


def load_catalog() -> pd.DataFrame:
    if CATALOG_CSV.exists():
        return pd.read_csv(CATALOG_CSV)
    rows = []
    for gene, d in CATALOG.items():
        rows.append({"e3_gene": gene, "e3_family": d["family"],
                     "mode": d["mode"], "uniprot": d["uniprot"],
                     "adaptor_genes": "|".join(d["adaptor_genes"]),
                     "structure_facts": d["structure_facts"],
                     "resistance": d["resistance"]})
    cat = pd.DataFrame(rows)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cat.to_csv(CATALOG_CSV, index=False)
    return cat


def candidate_universe() -> list[str]:
    return list(CATALOG.keys())


def alias_to_genes(label) -> list[str]:
    s = str(label)
    return E3_ALIASES.get(s, [s] if s in CATALOG else [])
