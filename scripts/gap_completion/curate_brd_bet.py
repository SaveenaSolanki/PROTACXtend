#!/usr/bin/env python3
"""Curate BRD/BET ligand + domain-selectivity evidence.

Primary sources (in-repo PROTAC-DB-derived tables, all DOI-cited):
  * ``protacSpace/data/raw/warhead.csv``  — small-molecule BET warheads with
    IC50/EC50/Kd/Ki + assay text + DOI + ChEMBL/PubChem ids.
  * ``Protac-invent/.../protacDB/protac.csv`` — PROTAC ``Protac-to-Target``
    binary affinities (also domain-annotated).

Secondary source (optional, cached): ChEMBL activities for BRDT
(CHEMBL1795185), which is absent from the local tables. Only rows whose assay
description names BD1/BD2 are retained.

Domain handling — two distinct things are tracked separately:
  * ``evidence_level``   : measured (value copied from source) vs inferred.
  * ``domain_assignment``: how the domain was attributed:
        explicit               — assay names a single domain (e.g. "ITC in BRD2 BD1")
        inferred_pair_order    — assay says "BD1/2" (both) and the source reports a
                                 two-value pair "x/y"; first->BD1, second->BD2.
                                 The VALUES are measured; the domain mapping is inferred
                                 from the source's BD1/BD2 pair convention.
        pan_unspecified        — "BD1/2" assay with a single (pan) value.
        unspecified            — no domain information in the assay text.

No affinity value is ever fabricated or imputed. Censored values ("<1") are
kept with their inequality flag.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WARHEAD = ROOT / "data" / "protac_repos" / "repos" / "protacSpace" / "data" / "raw" / "warhead.csv"
PROTAC = (ROOT / "data" / "protac_repos" / "repos" / "Protac-invent" / "data"
          / "protac" / "protacDB" / "protac.csv")
OUT_DIR = ROOT / "protacxtend" / "modules" / "brd_bet_intelligence" / "data"
CACHE = ROOT / "outputs" / "omics_cache" / "chembl_brdt_activities.json"

BET_GENES = ["BRD2", "BRD3", "BRD4", "BRDT"]
NUM = re.compile(r"^[<>]?\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)$")


def parse_pair(raw) -> list[tuple[float, str]]:
    """'3.1/3.9' -> [(3.1,'='),(3.9,'=')]; '<1' -> [(1.0,'<')]."""
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return []
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none"}:
        return []
    out = []
    for tok in text.split("/"):
        tok = tok.strip()
        if not tok:
            continue
        m = NUM.match(tok)
        if not m:
            continue
        cens = tok[0] if tok[0] in "<>" else "="
        out.append((float(m.group(1)), cens))
    return out


def domain_info(assay: str) -> tuple[list[str], str]:
    """Return (domains, assignment_hint) from an assay string.

    Handles both the explicit ``BD1/BD2`` and the common shorthand ``BD1/2``
    (which literally contains only "BD1").
    """
    a = str(assay or "").upper()
    if re.search(r"BD1\s*/\s*(?:BD)?2\b", a):
        return ["BD1", "BD2"], "pair"
    has1 = bool(re.search(r"\bBD1\b", a))
    has2 = bool(re.search(r"\bBD2\b", a))
    if has1 and has2:
        return ["BD1", "BD2"], "pair"
    if has1:
        return ["BD1"], "single"
    if has2:
        return ["BD2"], "single"
    return [], "none"


def _rows_for(ligand_id, name, smiles, target, molecule_class, act_type, raw,
              assay, doi, chembl, pubchem, source_file):
    vals = parse_pair(raw)
    if not vals:
        return []
    domains, hint = domain_info(assay)
    rows = []
    if len(vals) >= 2 and hint == "pair":
        for i, (v, c) in enumerate(vals[:2]):
            rows.append(dict(
                ligand_id=ligand_id, ligand_name=name, smiles=smiles,
                target_gene=target, molecule_class=molecule_class,
                activity_type=act_type, value_nM=v, value_nM_raw=str(raw),
                censored=c, domain=domains[i],
                domain_assignment="inferred_pair_order", assay=assay, doi=doi,
                chembl_id=chembl, pubchem_id=pubchem, source_file=source_file,
                evidence_level="measured",
                notes="domain order inferred from source BD1/BD2 pair convention"))
    else:
        domain = "BD1_BD2" if hint == "pair" else (domains[0] if hint == "single"
                                                    else "unspecified")
        da = ("pan_unspecified" if hint == "pair"
              else ("explicit" if hint == "single" else "unspecified"))
        for i, (v, c) in enumerate(vals):
            rows.append(dict(
                ligand_id=ligand_id, ligand_name=name, smiles=smiles,
                target_gene=target, molecule_class=molecule_class,
                activity_type=act_type, value_nM=v, value_nM_raw=str(raw),
                censored=c, domain=domain, domain_assignment=da,
                assay=assay, doi=doi, chembl_id=chembl, pubchem_id=pubchem,
                source_file=source_file, evidence_level="measured",
                notes=("replicate value" if len(vals) > 1 else "")))
    return rows


def curate_local() -> list[dict]:
    rows: list[dict] = []
    # ---- warheads -----------------------------------------------------------
    w = pd.read_csv(WARHEAD)
    w = w[w["Target"].isin(BET_GENES)]
    for _, r in w.iterrows():
        for t in ("IC50", "EC50", "Kd", "Ki"):
            vcol, acol = f"{t} (nM)", f"Assay ({t})"
            if vcol in w.columns and pd.notna(r.get(vcol)):
                rows += _rows_for(
                    f"warhead:{r.get('Compound ID')}", r.get("Name"), r.get("Smiles"),
                    r["Target"], "warhead", t, r.get(vcol), r.get(acol),
                    r.get("Article DOI"), r.get("ChEMBL"), r.get("PubChem"),
                    "protacSpace/warhead.csv")
    # ---- PROTAC binary target affinities -----------------------------------
    p = pd.read_csv(PROTAC)
    p = p[p["Target"].isin(BET_GENES)]
    for _, r in p.iterrows():
        for t in ("IC50", "EC50", "Kd", "Ki"):
            vcol, acol = f"{t} (nM, Protac to Target)", f"Assay (Protac to Target, {t})"
            if vcol in p.columns and pd.notna(r.get(vcol)):
                rows += _rows_for(
                    f"protac:{r.get('Compound ID')}", r.get("Name"), r.get("Smiles"),
                    r["Target"], "protac", t, r.get(vcol), r.get(acol),
                    r.get("Article DOI"), None, None,
                    "Protac-invent/protacDB/protac.csv")
    return rows


def curate_chembl_brdt() -> list[dict]:
    """Optional ChEMBL supplement for BRDT (absent from local tables)."""
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE.exists():
        acts = json.loads(CACHE.read_text())
    else:
        acts = []
        url = ("https://www.ebi.ac.uk/chembl/api/data/activity.json"
               "?target_chembl_id=CHEMBL1795185&limit=1000&offset={off}")
        try:
            for off in (0, 1000):
                req = urllib.request.Request(url.format(off=off),
                                             headers={"User-Agent": "ProtacPilot/1.0"})
                with urllib.request.urlopen(req, timeout=40) as resp:
                    acts += json.loads(resp.read().decode())["activities"]
                time.sleep(0.2)
            CACHE.write_text(json.dumps(acts))
        except Exception as exc:
            print(f"  ChEMBL BRDT fetch failed ({exc}); using local tables only",
                  file=sys.stderr)
            return []
    rows = []
    for a in acts:
        desc = a.get("assay_description") or ""
        domains, hint = domain_info(desc)
        if hint == "none":
            continue
        st = a.get("standard_type")
        if st not in ("IC50", "Kd", "Ki", "EC50"):
            continue
        if (a.get("standard_units") or "").lower() != "nm":
            continue
        val = a.get("standard_value")
        if val in (None, ""):
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        rel = a.get("standard_relation") or "="
        row = dict(
            ligand_id=f"chembl:{a.get('molecule_chembl_id')}",
            ligand_name=a.get("molecule_chembl_id"), smiles=a.get("canonical_smiles"),
            target_gene="BRDT", molecule_class="warhead", activity_type=st,
            value_nM=v, value_nM_raw=str(val), censored=rel,
            domain=(domains[0] if hint == "single" else "BD1_BD2"),
            domain_assignment=("explicit" if hint == "single" else "pan_unspecified"),
            assay=desc, doi=(a.get("document_chembl_id") or ""),
            chembl_id=a.get("molecule_chembl_id"), pubchem_id=None,
            source_file="ChEMBL target CHEMBL1795185 (BRDT)",
            evidence_level="measured", notes="ChEMBL supplement")
        rows.append(row)
    return rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = curate_local()
    print(f"local BRD/BET evidence rows: {len(rows)}")
    chembl_rows = curate_chembl_brdt()
    print(f"ChEMBL BRDT supplement rows: {len(chembl_rows)}")
    df = pd.DataFrame(rows + chembl_rows)
    if df.empty:
        print("no BRD/BET evidence curated", file=sys.stderr)
        return 1
    df["p_value"] = df["value_nM"].map(
        lambda v: (9.0 - np.log10(v)) if pd.notna(v) and v > 0 else np.nan)
    df = df.drop_duplicates(subset=["ligand_id", "target_gene", "activity_type",
                                    "value_nM", "domain", "assay"])
    cols = ["ligand_id", "ligand_name", "smiles", "target_gene", "molecule_class",
            "activity_type", "value_nM", "value_nM_raw", "censored", "p_value",
            "domain", "domain_assignment", "assay", "doi", "chembl_id",
            "pubchem_id", "source_file", "evidence_level", "notes"]
    df = df[cols].sort_values(["target_gene", "ligand_name", "activity_type"]
                              ).reset_index(drop=True)
    df.to_csv(OUT_DIR / "brd_bet_ligand_evidence.csv", index=False)

    # per (target, domain, activity_type) coverage summary
    summary = (df.groupby(["target_gene", "domain", "activity_type"], observed=True)
               .agg(n_measurements=("value_nM", "size"),
                    n_ligands=("ligand_id", "nunique"),
                    median_nM=("value_nM", "median"),
                    min_nM=("value_nM", "min"),
                    max_nM=("value_nM", "max"),
                    n_sources=("doi", "nunique")).reset_index())
    summary.to_csv(OUT_DIR / "brd_bet_domain_summary.csv", index=False)

    # BD1/BD2 pairs per ligand/target (for selectivity analysis)
    piv = (df[df["domain"].isin(["BD1", "BD2"])]
           .groupby(["ligand_id", "ligand_name", "target_gene", "activity_type",
                     "domain"], observed=True)["value_nM"].median().unstack("domain"))
    piv = piv.dropna(subset=["BD1", "BD2"]).reset_index()
    if len(piv):
        piv["delta_p_BD2_minus_BD1"] = (9 - np.log10(piv["BD2"])) - (9 - np.log10(piv["BD1"]))
        piv["fold_BD1_over_BD2"] = piv["BD1"] / piv["BD2"]
    piv.to_csv(OUT_DIR / "brd_bet_bd1_bd2_pairs.csv", index=False)

    provenance = {
        "primary_sources": [
            "data/protac_repos/repos/protacSpace/data/raw/warhead.csv",
            "data/protac_repos/repos/Protac-invent/data/protac/protacDB/protac.csv",
        ],
        "secondary_sources": ["ChEMBL BRDT CHEMBL1795185 (optional, cached)"],
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "n_rows": int(len(df)),
        "n_ligands": int(df["ligand_id"].nunique()),
        "targets": sorted(df["target_gene"].unique().tolist()),
        "domains": sorted(df["domain"].unique().tolist()),
        "domain_assignment_counts": df["domain_assignment"].value_counts().to_dict(),
        "note": ("Values are measured affinities copied from DOI-cited sources; "
                 "the only inference is the BD1/BD2 ordering of two-value pairs "
                 "in assays labelled 'BD1/2' (flagged inferred_pair_order). No "
                 "affinity is imputed."),
    }
    (OUT_DIR / "brd_bet_provenance.json").write_text(json.dumps(provenance, indent=2))
    print(f"wrote {len(df)} rows, {summary.shape[0]} summary rows, "
          f"{len(piv)} BD1/BD2 pairs -> {OUT_DIR}")
    print(df["target_gene"].value_counts().to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
