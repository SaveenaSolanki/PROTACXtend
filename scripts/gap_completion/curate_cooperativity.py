#!/usr/bin/env python3
"""Curate experimental ternary-cooperativity records for Module 3.

Source: the in-repo PROTAC-DB-derived table
``data/protac_repos/repos/Protac-invent/data/protac/protacDB/protac.csv``.
This is the *same* DOI-cited corpus the project already uses for degradation
prediction, and it explicitly separates the binary POI affinity, the binary E3
affinity and the ternary-complex affinity, each with its own assay description.

alpha convention (module ``alpha_def.py``):
    alpha = Kd2 / Kd2(ternary)
where Kd2 is the *second* binary interaction. In this corpus the ternary assay
almost always reads "Kd between <E3> and the complex of protac and <POI>", i.e.
it measures the conditional E3-arm affinity, so alpha = kd_binary_e3 /
kd_ternary. When the assay only says e.g. "ITC"/"SPR" the arm is ambiguous; we
still record it (``alpha_arm = assumed_e3``) but flag it, and the calibration
report excludes ambiguous-arm rows from the headline fit (sensitivity only).

Direct binding constants only: Kd preferred, Ki as fallback. IC50/EC50 are NOT
converted to alpha (no Cheng-Prusoff correction of unknown conditions). Paired
values ("33/24") are collapsed with the geometric mean and flagged; the raw
string is retained. Nothing is imputed.
"""
from __future__ import annotations

import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROTAC = (ROOT / "data" / "protac_repos" / "repos" / "Protac-invent" / "data"
          / "protac" / "protacDB" / "protac.csv")
OUT = (ROOT / "protacxtend" / "modules" / "cooperativity_alpha_predictor"
       / "data" / "cooperativity_records.csv")
PROV = (ROOT / "protacxtend" / "modules" / "cooperativity_alpha_predictor"
        / "data" / "cooperativity_provenance.json")

NUM = re.compile(r"^[<>]?\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)$")
DOMAIN_PAIR = re.compile(r"BD1\s*/\s*(?:BD)?2\b", re.I)


def vals(raw) -> list[float]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return []
    out = []
    for tok in str(raw).split("/"):
        m = NUM.match(tok.strip())
        if m:
            out.append(float(m.group(1)))
    return out


def geomean(xs: list[float]) -> float | None:
    xs = [x for x in xs if x > 0]
    if not xs:
        return None
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs)))


def parse_domain(assay: str) -> str:
    a = str(assay or "")
    if DOMAIN_PAIR.search(a):
        return "BD1_BD2"
    if re.search(r"\bBD1\b", a, re.I):
        return "BD1"
    if re.search(r"\bBD2\b", a, re.I):
        return "BD2"
    return ""


def arm_from_ternary_assay(assay: str, e3: str) -> str:
    a = str(assay or "")
    if re.search(r"\bKd between\b", a, re.I) and re.search(
            r"complex of protac", a, re.I):
        head = re.split(r"\band the complex\b", a, flags=re.I)[0]
        if e3 and e3.upper() in head.upper():
            return "e3_assay_described"
        return "poi_assay_described"
    if re.search(r"complex", a, re.I):
        return "ambiguous"
    return "ambiguous"


def build() -> pd.DataFrame:
    p = pd.read_csv(PROTAC)
    rows = []
    seen = set()
    for _, r in p.iterrows():
        e3 = str(r.get("E3 ligase") or "").strip()
        poi = str(r.get("Target") or "").strip()
        if not e3 or e3.lower() == "nan" or not poi or poi.lower() == "nan":
            continue
        for basis in ("Kd", "Ki"):
            ecol = f"{basis} (nM, Protac to E3)"
            tcol = f"{basis} (nM, Ternary complex)"
            pcol = f"{basis} (nM, Protac to Target)"
            if ecol not in p.columns or tcol not in p.columns:
                continue
            bin_e3 = vals(r.get(ecol))
            tern = vals(r.get(tcol))
            if not bin_e3 or not tern:
                continue
            bin_poi = vals(r.get(pcol)) if pcol in p.columns else []
            te_assay = r.get(f"Assay (Ternary complex, {basis})") or ""
            pe_assay = r.get(f"Assay (Protac to E3, {basis})") or ""
            po_assay = r.get(f"Assay (Protac to Target, {basis})") or ""
            arm = arm_from_ternary_assay(te_assay, e3)
            kb_e3, kt = geomean(bin_e3), geomean(tern)
            kb_poi = geomean(bin_poi)
            if arm == "poi_assay_described" and kb_poi:
                alpha = kb_poi / kt if kt else None
                num, den = "kd_binary_poi_nM", "kd_ternary_nM"
            else:  # e3_assay_described or ambiguous -> use E3 arm
                alpha = kb_e3 / kt if kt else None
                num, den = "kd_binary_e3_nM", "kd_ternary_nM"
            if alpha is None or not (alpha > 0):
                continue
            pid = f"{(r.get('Compound ID') or 'NA')}:{poi}:{e3}:{basis}"
            if pid in seen:
                continue
            seen.add(pid)
            paired = len(bin_e3) > 1 or len(tern) > 1
            rows.append({
                "protac_id": str(r.get("Name") or r.get("Compound ID") or pid),
                "protac_smiles": r.get("Smiles"),
                "poi": poi,
                "e3": e3,
                "warhead": "",
                "e3_recruiter": "",
                "linker": "",
                "linker_smiles": "",
                "alpha": round(float(alpha), 5),
                "log_alpha": round(math.log(float(alpha)), 5),
                "kd_binary_poi_nM": round(kb_poi, 4) if kb_poi else np.nan,
                "kd_binary_e3_nM": round(kb_e3, 4) if kb_e3 else np.nan,
                "kd_ternary_nM": round(kt, 4) if kt else np.nan,
                "assay": f"binary_E3={pe_assay}; ternary={te_assay}",
                "temperature_c": np.nan,
                "doi": r.get("Article DOI"),
                "pmid": "",
                "pdb_ids": r.get("PDB") if pd.notna(r.get("PDB")) else "",
                "alpha_definition": f"alpha = {num} / {den}",
                "source": "PROTAC-DB (Protac-invent protac.csv)",
                "notes": (f"affinity_basis={basis}; alpha_arm={arm}; "
                          f"poi_domain={parse_domain(te_assay) or 'unspecified'}; "
                          f"paired_values={paired}; raw E3={r.get(ecol)}; "
                          f"raw ternary={r.get(tcol)}; raw POI={r.get(pcol)}"),
            })
    df = pd.DataFrame(rows)
    return df


def main() -> int:
    df = build()
    if df.empty:
        print("no cooperativity records curated", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    header = ("### EXPERIMENTAL TERNARY COOPERATIVITY RECORDS\n"
              "### Source: PROTAC-DB-derived protac.csv (in-repo, DOI-cited).\n"
              "### alpha = Kd2/Kd2(ternary); direct binding (Kd preferred, Ki fallback).\n"
              "### Row-level notes carry alpha_arm, poi_domain, pairing and raw values.\n")
    with OUT.open("w") as fh:
        fh.write(header)
        df.to_csv(fh, index=False)

    def stats(sub):
        if len(sub) == 0:
            return {}
        return {"n": int(len(sub)), "median_alpha": float(sub["alpha"].median()),
                "mean_log_alpha": float(sub["log_alpha"].mean()),
                "std_log_alpha": float(sub["log_alpha"].std(ddof=1)) if len(sub) > 1 else None,
                "frac_positive": float((sub["alpha"] > 1.25).mean()),
                "frac_neutral": float(((sub["alpha"] >= 0.8) & (sub["alpha"] <= 1.25)).mean()),
                "frac_negative": float((sub["alpha"] < 0.8).mean())}

    prov = {
        "source_file": "data/protac_repos/repos/Protac-invent/data/protac/protacDB/protac.csv",
        "source_description": "PROTAC-DB-derived table with separate binary-POI, binary-E3 and ternary affinity columns and assay descriptions",
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "n_records": int(len(df)),
        "n_unique_protacs": int(df["protac_id"].nunique()),
        "n_pois": int(df["poi"].nunique()),
        "n_e3s": int(df["e3"].nunique()),
        "overall": stats(df),
        "by_arm": {a: stats(df[df["notes"].str.contains(f"alpha_arm={a}")])
                   for a in ("e3_assay_described", "poi_assay_described", "ambiguous")},
        "by_basis": {b: stats(df[df["notes"].str.contains(f"affinity_basis={b}")])
                     for b in ("Kd", "Ki")},
        "by_e3": {e: stats(df[df["e3"] == e]) for e in sorted(df["e3"].unique())},
        "headline_fit_set": "alpha_arm=e3_assay_described (unambiguous E3-arm Kd)",
        "note": ("Values are measured equilibrium constants copied from the source; "
                 "paired values are geometric means (flagged). No IC50->Kd conversion "
                 "and no imputation."),
    }
    import json
    PROV.write_text(json.dumps(prov, indent=2, default=str))
    print(f"wrote {len(df)} cooperativity records -> {OUT}")
    print(json.dumps(prov["overall"], indent=2, default=str))
    print("by arm:", {k: (v.get("n") if v else 0) for k, v in prov["by_arm"].items()})
    print("by e3:", {k: (v.get("n") if v else 0) for k, v in prov["by_e3"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
