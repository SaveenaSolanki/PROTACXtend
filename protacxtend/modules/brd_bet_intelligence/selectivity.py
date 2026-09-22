"""BRD/BET domain-aware selectivity scoring.

Turns the curated evidence into (a) a target/domain landscape and (b) a
per-warhead, per-target selectivity assessment that the evaluator and the
proteome-selectivity tool consume.

Honesty boundary
----------------
* A warhead present in the curated table yields ``evidence_level="measured"``
  with the exact source rows attached.
* An unmatched warhead falls back to a *target-level prior* computed from the
  measured ligands of that target; this is explicitly ``evidence_level="proxy"``
  and ``status="PRIOR_ONLY"``. It is never reported as a measurement for the
  query molecule.
* No target data at all -> ``status="ABSENT"`` and ``score=None``.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from protacxtend.modules.brd_bet_intelligence.data import (
    BET_GENES,
    canonical_gene,
    load_evidence,
    load_pairs,
    load_summary,
)

# affinity types in decreasing order of preference for a potency summary
AFFINITY_PREFERENCE = ("Kd", "Ki", "IC50", "EC50")
POTENCY_FLOOR_P = 4.0   # 10 uM
POTENCY_CEIL_P = 9.0    # 1 nM


def _p(nm: float | None) -> float | None:
    if nm is None or not np.isfinite(nm) or nm <= 0:
        return None
    return 9.0 - math.log10(nm)


def classify_domain_selectivity(fold_bd1_over_bd2: float | None) -> str | None:
    """fold = BD1 value / BD2 value; >1 => BD2 is the more potent domain."""
    if fold_bd1_over_bd2 is None or not np.isfinite(fold_bd1_over_bd2):
        return None
    if fold_bd1_over_bd2 >= 2.0:
        return "BD2-selective"
    if fold_bd1_over_bd2 <= 0.5:
        return "BD1-selective"
    return "pan-BD1/BD2"


def _potency_score(nm_values: list[float]) -> tuple[float | None, float | None]:
    ps = [p for p in (_p(v) for v in nm_values) if p is not None]
    if not ps:
        return None, None
    med_p = float(np.median(ps))
    score = max(0.0, min(1.0, (med_p - POTENCY_FLOOR_P)
                       / (POTENCY_CEIL_P - POTENCY_FLOOR_P)))
    return round(score, 4), round(med_p, 4)


def domain_landscape() -> dict[str, Any]:
    """Target x domain x assay coverage of the curated evidence."""
    ev = load_evidence()
    if ev.empty:
        return {"available": False, "summary": [], "n_rows": 0}
    summ = load_summary()
    return {
        "available": True,
        "n_rows": int(len(ev)),
        "n_ligands": int(ev["ligand_id"].nunique()),
        "targets": sorted(ev["target_gene"].unique().tolist()),
        "domain_assignment_counts": ev["domain_assignment"].value_counts().to_dict(),
        "summary": summ.to_dict(orient="records"),
    }


def _match_ligand(ev: pd.DataFrame, name: str | None,
                  smiles: str | None) -> pd.DataFrame:
    if smiles:
        s = str(smiles).strip()
        m = ev[ev["smiles"].astype(str).str.strip() == s]
        if len(m):
            return m
    if name:
        n = str(name).strip().lower()
        m = ev[ev["ligand_name"].astype(str).str.strip().str.lower() == n]
        if len(m):
            return m
        m = ev[ev["ligand_name"].astype(str).str.lower().str.contains(
            n, regex=False, na=False)]
        if len(m):
            return m
    return ev.iloc[0:0]


def ligand_selectivity_profile(name: str = "", smiles: str = "",
                               target: str | None = None) -> dict[str, Any]:
    """Per-target/domain profile for a named or SMILES-matched ligand."""
    ev = load_evidence()
    if ev.empty:
        return {"status": "NO_DATA", "evidence_level": "absent"}
    sub = _match_ligand(ev, name, smiles)
    if sub.empty:
        return {"status": "NOT_FOUND", "evidence_level": "absent",
                "query": {"name": name, "smiles": smiles},
                "note": "no measured BRD/BET row for this ligand; no value inferred"}
    lig_id = sub["ligand_id"].iloc[0]
    rows = ev[ev["ligand_id"] == lig_id].copy()
    if target:
        tg = canonical_gene(target)
        if tg:
            rows = rows[rows["target_gene"] == tg]
    per_target: dict[str, Any] = {}
    for gene, g in rows.groupby("target_gene"):
        domains = {}
        for dom, d in g.groupby("domain"):
            vals = d["value_nM"].dropna().tolist()
            domains[str(dom)] = {
                "n": int(len(vals)),
                "median_nM": float(np.median(vals)) if vals else None,
                "min_nM": float(np.min(vals)) if vals else None,
                "max_nM": float(np.max(vals)) if vals else None,
                "activity_types": sorted(d["activity_type"].unique().tolist()),
                "assays": sorted(set(d["assay"].dropna().astype(str)))[:4],
            }
        per_target[str(gene)] = domains
    pairs = load_pairs()
    p = pairs[pairs["ligand_id"] == lig_id]
    if target:
        tg = canonical_gene(target)
        if tg:
            p = p[p["target_gene"] == tg]
    bd = []
    for _, r in p.iterrows():
        fold = float(r["BD1"]) / float(r["BD2"]) if r["BD2"] else None
        bd.append({"target_gene": r["target_gene"],
                   "activity_type": r["activity_type"],
                   "BD1_nM": float(r["BD1"]), "BD2_nM": float(r["BD2"]),
                   "fold_BD1_over_BD2": round(fold, 3) if fold else None,
                   "domain_class": classify_domain_selectivity(fold)})
    return {
        "status": "FOUND",
        "evidence_level": "measured",
        "ligand_id": lig_id,
        "ligand_name": rows["ligand_name"].iloc[0],
        "smiles": rows["smiles"].iloc[0],
        "targets": sorted(rows["target_gene"].unique().tolist()),
        "per_target_domain": per_target,
        "bd1_bd2_pairs": bd,
        "sources": {
            "dois": sorted(set(rows["doi"].dropna().astype(str))),
            "chembl_ids": sorted(set(rows["chembl_id"].dropna().astype(str))),
            "source_files": sorted(set(rows["source_file"].astype(str))),
        },
    }


def target_prior(target: str, activity_type: str | None = None) -> dict[str, Any]:
    """Target-level measured affinity prior (explicitly a proxy for new ligands)."""
    tg = canonical_gene(target)
    ev = load_evidence()
    if tg is None or ev.empty:
        return {"available": False}
    sub = ev[ev["target_gene"] == tg]
    if activity_type:
        sub = sub[sub["activity_type"] == activity_type]
    if sub.empty:
        return {"available": False, "target_gene": tg}
    vals = sub["value_nM"].dropna().tolist()
    return {
        "available": True,
        "target_gene": tg,
        "n_measurements": int(len(vals)),
        "n_ligands": int(sub["ligand_id"].nunique()),
        "median_nM": float(np.median(vals)) if vals else None,
        "min_nM": float(np.min(vals)) if vals else None,
        "max_nM": float(np.max(vals)) if vals else None,
        "activity_types": sorted(sub["activity_type"].unique().tolist()),
        "evidence_level": "proxy",
    }


def score_brd_bet(target: str | None, warhead_name: str | None = None,
                  warhead_smiles: str | None = None,
                  domain: str | None = None) -> dict[str, Any]:
    """Domain-aware BRD/BET selectivity assessment for one warhead/target.

    Returns component scores, the matched measured rows, and an explicit
    ``evidence_level`` (measured / proxy / absent).
    """
    tg = canonical_gene(target)
    base: dict[str, Any] = {"target_gene": tg, "query_name": warhead_name,
                            "query_smiles": warhead_smiles,
                            "evidence_level": "absent", "score": None,
                            "components": {}, "measurements": [],
                            "sources": {}, "limitations": []}
    if tg is None:
        base.update({"status": "NOT_BET",
                     "limitations": ["target is not one of BRD2/BRD3/BRD4/BRDT"]})
        return base
    ev = load_evidence()
    if ev.empty:
        base.update({"status": "NO_DATA",
                     "limitations": ["BRD/BET evidence table is empty"]})
        return base

    sub = _match_ligand(ev, warhead_name, warhead_smiles)
    matched = not sub.empty
    if matched:
        lig_id = sub["ligand_id"].iloc[0]
        rows = ev[(ev["ligand_id"] == lig_id) & (ev["target_gene"] == tg)]
        target_rows = rows
        evidence_level = "measured"
        status = "MEASURED"
    else:
        # target-level prior only — no value invented for the query molecule
        prior_ev = ev[ev["target_gene"] == tg]
        target_rows = prior_ev
        evidence_level = "proxy"
        status = "PRIOR_ONLY"

    if target_rows.empty:
        base.update({"status": "ABSENT", "evidence_level": "absent",
                     "limitations": [f"no measured BRD/BET affinity for {tg}"]})
        return base

    # ---- potency ----
    pref = [t for t in AFFINITY_PREFERENCE
            if t in set(target_rows["activity_type"].unique())]
    chosen = pref[0] if pref else target_rows["activity_type"].iloc[0]
    potency_rows = target_rows[target_rows["activity_type"] == chosen]
    vals = potency_rows["value_nM"].dropna().tolist()
    pot_score, med_p = _potency_score(vals)

    # ---- domain selectivity (BD1 vs BD2) ----
    pairs = load_pairs()
    p = pairs[pairs["target_gene"] == tg]
    if matched:
        p = p[p["ligand_id"] == sub["ligand_id"].iloc[0]]
    domain_sel = None
    domain_components = {}
    if not p.empty:
        p2 = p.copy()
        p2["fold"] = p2["BD1"] / p2["BD2"]
        # most potent/pair with strongest separation as the representative
        row = p2.reindex(p2["fold"].map(lambda f: abs(math.log(f))
                                        if f and f > 0 else -1).sort_values(
                                            ascending=False).index).iloc[0]
        fold = float(row["fold"])
        delta_p = (_p(float(row["BD2"])) or 0) - (_p(float(row["BD1"])) or 0)
        domain_sel = {
            "activity_type": row["activity_type"],
            "BD1_nM": float(row["BD1"]), "BD2_nM": float(row["BD2"]),
            "fold_BD1_over_BD2": round(fold, 3),
            "delta_p_BD2_minus_BD1": round(float(delta_p), 3),
            "domain_class": classify_domain_selectivity(fold),
            "n_pairs": int(len(p2)),
            "source": "query_ligand" if matched else "target_population",
        }
        domain_components["domain_specificity"] = round(
            min(1.0, abs(delta_p) / 3.0), 4)

    # ---- BET family selectivity (target vs other BETs) ----
    family = {"target_median_p": None, "other_bet_median_p": None,
              "delta_p": None, "n_other_measurements": 0,
              "source": "query_ligand" if matched else "target_population"}
    other = ev[(ev["target_gene"].isin([g for g in BET_GENES if g != tg]))]
    if matched:
        other = other[other["ligand_id"] == sub["ligand_id"].iloc[0]]
    p_target = [_p(v) for v in target_rows["value_nM"].dropna().tolist()]
    p_other = [_p(v) for v in other["value_nM"].dropna().tolist()]
    p_target = [p for p in p_target if p is not None]
    p_other = [p for p in p_other if p is not None]
    if p_target:
        family["target_median_p"] = round(float(np.median(p_target)), 3)
    if p_other:
        family["other_bet_median_p"] = round(float(np.median(p_other)), 3)
        family["n_other_measurements"] = len(p_other)
    family_components = {}
    if family["target_median_p"] is not None and family["other_bet_median_p"] is not None:
        dp = family["target_median_p"] - family["other_bet_median_p"]
        family["delta_p"] = round(float(dp), 3)
        # positive = more potent on target than other BETs (selective)
        family_components["bet_family_specificity"] = round(
            max(0.0, min(1.0, dp / 2.0)), 4)

    components: dict[str, float] = {}
    if pot_score is not None:
        components["potency"] = pot_score
    components.update(domain_components)
    components.update(family_components)

    weights = {"potency": 0.40, "domain_specificity": 0.30,
               "bet_family_specificity": 0.30}
    present = {k: v for k, v in components.items() if k in weights}
    score = (sum(weights[k] * v for k, v in present.items())
             / sum(weights[k] for k in present)) if present else None

    limitations = []
    if not matched:
        limitations.append("query ligand not found in curated table — "
                           "target-level PROXY prior only, not a measurement; "
                           "domain/family components describe the target's "
                           "ligand population, not this molecule")
    if "domain_specificity" not in components:
        limitations.append("BD1/BD2 selectivity not measured for this "
                           "ligand/target — domain selectivity UNKNOWN")
    if "bet_family_specificity" not in components:
        limitations.append("cross-BET (BRD2/3/BRDT) measurements unavailable "
                           "for this ligand — family selectivity UNKNOWN")
    if domain and domain_sel and domain.upper() not in (
            "BD1", "BD2", "BD1_BD2"):
        limitations.append(f"requested domain '{domain}' not resolved")

    med_nm = float(np.median(vals)) if vals else None
    base.update({
        "status": status,
        "evidence_level": evidence_level,
        "score": None if score is None else round(float(score), 4),
        "components": components,
        "component_weights": weights,
        "potency": {"activity_type": chosen,
                    "median_nM": med_nm,
                    "median_p": med_p,
                    "n_measurements": int(len(vals))},
        "domain_selectivity": domain_sel,
        "bet_family": family,
        "measurements": target_rows[[
            "ligand_name", "target_gene", "domain", "domain_assignment",
            "activity_type", "value_nM", "censored", "assay", "doi",
            "source_file", "evidence_level"]].to_dict(orient="records"),
        "sources": {
            "dois": sorted(set(target_rows["doi"].dropna().astype(str))),
            "source_files": sorted(set(target_rows["source_file"].astype(str))),
        },
        "limitations": limitations,
    })
    return base


def bet_ligand_table(target: str | None = None) -> pd.DataFrame:
    """Pivot of measured affinities (ligand x target/domain) for plotting."""
    ev = load_evidence()
    if ev.empty:
        return ev
    sub = ev
    if target:
        tg = canonical_gene(target)
        if tg:
            sub = ev[ev["target_gene"] == tg]
    # prefer one activity type per ligand/target/domain (Kd>Ki>IC50>EC50)
    order = {t: i for i, t in enumerate(AFFINITY_PREFERENCE)}
    sub = sub.assign(_pref=sub["activity_type"].map(order)).sort_values("_pref")
    sub = sub.drop_duplicates(subset=["ligand_id", "target_gene", "domain"])
    return sub[["ligand_id", "ligand_name", "target_gene", "domain",
                "domain_assignment", "activity_type", "value_nM", "doi"]]
