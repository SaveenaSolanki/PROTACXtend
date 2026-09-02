#!/usr/bin/env python3
"""Build the multi-E3 ligand library from SynGlue_Py/data/e3_ligand.csv.

Merges the 117-row cited E3-ligand dataset (Target, Name, Smiles, DOI,
Uniprot, activity) into synglue_agent/data/curated_e3_ligands.csv in the
toolbox's schema. SMILES are RDKit-validated; only valid rows are kept.
Attachment points are NOT baked in (construction adds [*:1] with an
approximate position; provenance records this limitation).

Usage: python scripts/build_e3_library.py [--dry-run]
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from rdkit import Chem

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "synglue" / "data" / "e3_ligand.csv"
DST = ROOT / "synglue_agent" / "data" / "curated_e3_ligands.csv"

# e3_ligand.csv Target → canonical E3 key (toolbox _norm_name style)
E3_SYNONYMS = {
    "crbn": "CRBN", "cereblon": "CRBN",
    "vhl": "VHL", "pvh1": "VHL",
    "ciap1": "cIAP1", "birc2": "cIAP1", "iap1": "cIAP1",
    "ciap2": "cIAP2", "birc3": "cIAP2",
    "xiap": "XIAP", "birc4": "XIAP",
    "iap": "IAP",
    "mdm2": "MDM2",
    "dcaf15": "DCAF15", "dcaf16": "DCAF16", "dcaf11": "DCAF11", "dcaf1": "DCAF1",
    "keap1": "KEAP1",
    "rnf114": "RNF114", "znf313": "RNF114", "rnf4": "RNF4", "rnf126": "RNF126",
    "klhl20": "KLHL20", "klhdc2": "KLHDC2",
    "fem1b": "FEM1B", "fbxo22": "FBXO22", "ahr": "AhR", "skp1": "SKP1",
}


def canonical_e3(raw: str) -> str:
    key = raw.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    return E3_SYNONYMS.get(key, raw.strip())


def main() -> int:
    dry = "--dry-run" in sys.argv
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    out_rows = []
    seen_smiles = set()
    for r in rows:
        smiles = (r.get("Smiles") or "").strip()
        target = (r.get("Target") or "").strip()
        if not smiles or not target:
            continue
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue
        canon = Chem.MolToSmiles(mol)
        if canon in seen_smiles:
            continue
        seen_smiles.add(canon)
        name = (r.get("Name") or "").strip() or f"{target}_ligand_{len(out_rows)}"
        doi = (r.get("Article DOI") or "").strip()
        act = r.get("Kd (nM)") or r.get("IC50 (nM)") or r.get("Ki (nM)") or ""
        out_rows.append({
            "name": name,
            "e3_ligase": canonical_e3(target),
            "smiles": canon,
            "ligand_class": "literature_e3_ligand",
            "source": f"e3_ligand.csv (DOI {doi})" if doi else "e3_ligand.csv",
            "exit_vector_confidence": 0.75,
            "stereochemistry_valid": "true",
            "source_confidence": 0.7,
            "diversity_score": 0.5,
            "known_degrader_usage": "",
            "article_doi": doi,
            "uniprot": r.get("Uniprot", ""),
            "activity_nM": act,
            "attachment_point": "approximate (construction appends [*:1])",
        })

    # merge with existing rows (keep the 7 hand-curated with markers first)
    existing = []
    if DST.exists():
        existing = list(csv.DictReader(open(DST, encoding="utf-8")))
    merged = existing + out_rows

    if dry:
        from collections import Counter
        print("existing rows:", len(existing))
        print("new valid rows:", len(out_rows), "| total:", len(merged))
        print("E3 coverage:", dict(Counter(r["e3_ligase"] for r in merged)))
        return 0

    fieldnames = list(dict.fromkeys(k for r in merged for k in r))
    with open(DST, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)
    print(f"wrote {len(merged)} rows -> {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
