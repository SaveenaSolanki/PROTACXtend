"""rank_e3_ligases — public Module 6 API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from protacxtend.modules.cell_context_selector.genemap import target_to_gene
from protacxtend.modules.e3_opportunity import context
from protacxtend.modules.e3_opportunity import rank as rank_mod
from protacxtend.modules.e3_opportunity.e3_catalog import CATALOG, candidate_universe
from protacxtend.modules.e3_opportunity.schemas import MODEL_VERSION


def resolve_poi_gene(poi: str) -> str | None:
    """POI -> gene symbol (deterministic; None = unresolved -> honest gate)."""
    if not poi:
        return None
    p = str(poi).strip()
    up = p.upper()
    try:
        vocab = set(context.lookup().genes())
    except Exception:
        vocab = set()
    if up in vocab or up in {"AR", "BRD4", "BTK", "EGFR", "KRAS", "MDM2",
                             "ABL1", "ESR1", "STAT3", "TTK", "CDK6", "CDK4",
                             "CDK2", "BRAF", "PTK2", "PARP1", "ALK", "FLT3",
                             "JAK2", "HDAC1", "HDAC6", "HMGCR", "HPGDS"}:
        return up
    return target_to_gene(p, vocab)


def rank_e3_ligases(poi: str, cell_line: str | None = None,
                    tissue: str | None = None, disease: str | None = None,
                    warhead: str | None = None,
                    poi_structure: str | None = None,
                    top_k: int = 10) -> dict[str, Any]:
    """Rank candidate E3 ligases for a POI (evidence-gated; see SPEC.md)."""
    poi_gene = resolve_poi_gene(poi)
    if poi_gene is None:
        return _empty_response(poi, cell_line, tissue, disease,
                               "POI could not be resolved to a gene symbol — "
                               "no evidence axes can be evaluated")
    rows = []
    for e3 in candidate_universe():
        ev = rank_mod.evaluate_candidate(
            poi_gene, e3, cell_line, tissue, disease, warhead, poi_structure)
        rows.append(ev)
    df = pd.DataFrame(rows)
    order = {"SUPPORTED": 0, "PROMISING": 1, "EXPLORATORY": 2,
             "INSUFFICIENT EVIDENCE": 3}
    df["_tier"] = df["verdict"].map(order).fillna(3)
    df = df.sort_values(["_tier", "overall_rank_score",
                         "overall_confidence"],
                        ascending=[True, False, False]).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    out = _to_response(poi, poi_gene, cell_line, tissue, disease, df, top_k)
    return out


def _empty_response(poi, cell_line, tissue, disease, note) -> dict[str, Any]:
    return {
        "model": MODEL_VERSION, "poi": poi, "poi_gene": None,
        "cell_line": cell_line, "tissue": tissue, "disease": disease,
        "candidates": [], "ood": {"hard_ood": ["target_unseen"]},
        "claims": {}, "notes": [note], "status": "INSUFFICIENT EVIDENCE",
    }


def _to_response(poi, poi_gene, cell_line, tissue, disease, df,
                 top_k) -> dict[str, Any]:
    cands = []
    for _, r in df.head(top_k).iterrows():
        ax = r.get("axes", {}) or {}
        def s(name, ax=ax):
            return ax.get(name, {}).get("score")
        def d(name, ax=ax):
            return ax.get(name, {}) or {}
        rec = d("recruiter").get("detail", {})
        resist = CATALOG.get(str(r["e3_gene"]), {}).get("resistance", "")
        cands.append({
            "rank": int(r["rank"]),
            "e3_gene": str(r["e3_gene"]),
            "e3_family": str(r["e3_family"]),
            "cell_context_score": s("cell_context"),
            "cell_context_confidence": d("cell_context").get("confidence"),
            "localization_score": s("localization"),
            "recruiter_available": r.get("recruiter_available"),
            "recruiter_confidence": d("recruiter").get("confidence"),
            "structural_feasibility": None,   # UNKNOWN by design
            "structural_confidence": d("structure").get("confidence"),
            "lysine_opportunity": s("lysine"),
            "selectivity_opportunity": s("selectivity"),
            "known_precedent": (None if r.get("known_precedent_n", 0) == 0
                                else round(min(1.0, r["known_precedent_n"]
                                               / 3.0), 3)),
            "resistance_risk": (0.7 if resist else None),
            "resistance_note": resist or None,
            "overall_rank_score": float(r["overall_rank_score"]),
            "overall_confidence": float(r["overall_confidence"]),
            "verdict": str(r["verdict"]),
            "supporting_evidence": {
                "e3_expression_percentile": d("cell_context").get(
                    "detail", {}).get("e3_expression_percentile"),
                "adaptor_percentile": d("cell_context").get(
                    "detail", {}).get("adaptor_expression_percentile"),
                "poi_expression_percentile": d("cell_context").get(
                    "detail", {}).get("poi_expression_percentile"),
                "context_flags": d("cell_context").get("detail", {}).get(
                    "flags"),
                "ligands": rec.get("ligand_names"),
                "best_affinity_nM": rec.get("best_affinity_nM"),
                "precedent_rows": r.get("known_precedent_n", 0),
                "e3_pdb_ids": d("structure").get("detail", {}).get(
                    "e3_complex_pdb_ids"),
                "restricted_lineages": d("selectivity").get(
                    "detail", {}).get("restricted_lineages"),
            },
            "limitations": r.get("limitations", []),
            "recommended_next_test": str(r.get("recommended_next_test", "")),
        })
    return {
        "model": MODEL_VERSION, "poi": poi, "poi_gene": poi_gene,
        "cell_line": cell_line, "tissue": tissue, "disease": disease,
        "candidates": cands,
        "ood": {"candidates_scored": int(len(df))},
        "claims": {},
        "notes": [
            "structural_feasibility is deliberately UNKNOWN for every pair "
            "without resolved/docked ternary data",
            "degradation-probability style claims are never made from "
            "expression alone",
        ],
        "status": "SUPPORTED",
    }
def np_(x):
    return x
