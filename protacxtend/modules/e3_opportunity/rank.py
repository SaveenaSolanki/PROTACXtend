"""Evidence-weighted ranking + verdicts (Module 6).

Axis weights (documented):
  cell-context .25 | precedent .20 | recruiter .20 | localization .15 |
  selectivity .05 | structure .10 | lysine .05

Rule: an axis that has no evidence contributes nothing and does not invent a
score; coverage (sum of present-axis weights / total) discounts confidence.
Low E3 expression (context percentile < 0.2) is an explicit cap on the
verdict. Ternary feasibility, recruiter absence, paralog discrimination and
off-target risk are reported as UNKNOWN/absent rather than guessed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from protacxtend.modules.e3_opportunity import (
    context,
    dataset,
    localization,
    lysines,
    recruiters,
    selectivity,
    structure,
    uncertainty,
)
from protacxtend.modules.e3_opportunity.e3_catalog import load_catalog

AXIS_WEIGHTS = {"cell_context": 0.25, "precedent": 0.20, "recruiter": 0.20,
                "localization": 0.15, "selectivity": 0.05, "structure": 0.10,
                "lysine": 0.05}
VERDICTS = ("SUPPORTED", "PROMISING", "EXPLORATORY", "INSUFFICIENT EVIDENCE")
LOW_EXPRESSION_CAP = 0.2


def precedent_stats(poi_gene: str, e3_gene: str) -> dict[str, Any]:
    pairs = dataset.load_benchmark_pairs()
    sub = pairs[(pairs["poi_gene"] == poi_gene) &
                (pairs["e3_gene"] == e3_gene)]
    n = int(len(sub))
    n_measured = int(sub["has_dc50"].sum())
    doi_set = sorted(set(sub["doi"].dropna().astype(str)))
    return {"n_rows": n, "n_dc50_measured": n_measured,
            "dois": doi_set[:4], "known_use": n > 0}


def family_precedent(poi_gene: str, e3_gene: str) -> int:
    fam = selectivity._FAMILY_OF_GENE.get(poi_gene)
    if not fam:
        return 0
    members = selectivity.POI_FAMILIES[fam]
    pairs = dataset.load_benchmark_pairs()
    return int(len(pairs[(pairs["poi_gene"].isin(members)) &
                         (pairs["e3_gene"] == e3_gene)]))


def evaluate_candidate(poi_gene: str, e3_gene: str,
                       cell_line: str | None, tissue: str | None,
                       disease: str | None, warhead: str | None,
                       poi_structure: str | None) -> dict[str, Any]:
    cat = load_catalog()
    row = cat[cat["e3_gene"] == e3_gene]
    family = str(row.iloc[0]["e3_family"]) if len(row) else "?"
    ctx = context.context_scores(poi_gene, cell_line, tissue, e3_gene)
    loc = localization.compatibility(poi_gene, e3_gene)
    rec = recruiters.recruiter_info(e3_gene)
    st = structure.structural_axis(poi_gene, e3_gene, poi_structure)
    prec = precedent_stats(poi_gene, e3_gene)
    fprec = family_precedent(poi_gene, e3_gene)
    prec["family_rows"] = fprec
    sel = selectivity.selectivity_axis(poi_gene, e3_gene)
    lys = None
    if poi_structure and Path(poi_structure).exists():
        lys = lysines.surface_lysines(poi_structure)
    axes = {
        "cell_context": {"score": ctx.get("score"),
                         "confidence": ctx.get("confidence"),
                         "detail": {k: ctx.get(k) for k in (
                             "e3_expression_percentile",
                             "adaptor_expression_percentile",
                             "poi_expression_percentile", "lineage",
                             "context_source", "flags")}},
        "precedent": {"score": (min(1.0, prec["n_rows"] / 3.0) if
                                prec["n_rows"] else None),
                      "confidence": 0.8 if prec["n_rows"] else 0.0,
                      "detail": {**prec, "family_rows": fprec}},
        "recruiter": {"score": (rec["confidence"] if rec["available"] else
                                (0.0 if rec.get("available") is False else
                                 None)),
                      "confidence": rec["confidence"],
                      "detail": {k: rec.get(k) for k in (
                          "available", "demo_only", "n_cited_ligands",
                          "best_affinity_nM",
                          "max_exit_vector_confidence",
                          "stereochemistry_valid", "attachment_points",
                          "ligand_names", "limitations")}},
        "localization": {"score": loc.get("score"),
                         "confidence": loc.get("confidence"),
                         "detail": {k: loc.get(k) for k in (
                             "poi_compartments", "e3_compartments",
                             "missing", "shared")}},
        "selectivity": {"score": sel.get("score"),
                        "confidence": 0.5 if sel.get("score") is not None
                        else 0.0,
                        "detail": {k: sel.get(k) for k in (
                            "expression_restriction_score",
                            "restricted_lineages", "poi_family", "paralogs",
                            "limitations")}},
        "structure": {"score": st["structural_availability_score"],
                      "confidence": (0.8 if st["evidence_level"] else 0.0),
                      "detail": {k: st.get(k) for k in (
                          "e3_complex_pdb_ids", "e3_ternary_example",
                          "poi_monomer_available", "evidence_level",
                          "ternary_feasibility", "limitations")}},
        "lysine": {"score": (lys or {}).get("lysine_opportunity"),
                   "confidence": (0.8 if (lys or {}).get("status")
                                  == "SUPPORTED" else 0.0),
                   "detail": (lys or {"note": "no POI structure provided"})},
    }
    ev = _aggregate(axes, rec, prec)
    ev.update({"e3_gene": e3_gene, "e3_family": family})
    return ev


def _aggregate(axes: dict, rec: dict, prec: dict) -> dict[str, Any]:
    present = {k: v for k, v in axes.items() if v["score"] is not None}
    total_w = sum(AXIS_WEIGHTS.values())
    w_present = sum(AXIS_WEIGHTS[k] for k in present)
    coverage = w_present / total_w
    if present:
        raw = sum(AXIS_WEIGHTS[k] * v["score"] for k, v in present.items()) \
            / w_present
        confs = [v["confidence"] for v in present.values()
                 if v.get("confidence") is not None]
        conf = float(np.mean(confs)) if confs else 0.0
    else:
        raw, conf = 0.0, 0.0
    ctx = axes["cell_context"]
    low_expr = bool(ctx.get("score") is not None and ctx["score"] <
                    LOW_EXPRESSION_CAP)
    # recruiter absent / present
    rec_avail = rec.get("available") if isinstance(rec, dict) else None
    has_precedent = bool(prec.get("n_rows")) if isinstance(prec, dict) else False
    family_rows = int((prec or {}).get("family_rows", 0))
    verdict = _verdict(raw, conf, coverage, rec_avail, has_precedent, low_expr,
                       axes, family_rows)
    return {
        "overall_rank_score": round(raw, 4),
        "overall_confidence": round(conf, 4),
        "coverage": round(coverage, 4),
        "verdict": verdict,
        "limitations": _limitations(axes, rec, low_expr),
        "recommended_next_test": _next_test(axes, rec, low_expr),
        "axes": {k: v for k, v in axes.items()},
        "recruiter_available": rec.get("available")
        if isinstance(rec, dict) else None,
        "known_precedent_n": (prec or {}).get("n_rows", 0),
    }


def _verdict(raw, conf, coverage, rec_avail, has_precedent, low_expr,
             axes, family_precedent: int = 0) -> str:
    # A chemical handle (cited recruiter) or usage signal (direct/family
    # precedent) is required for PROMISING. SUPPORTED additionally requires
    # DIRECT measured precedent for this POI (rows in the curated dataset) —
    # recruiter + context alone never claim POI suitability.
    handle = bool(rec_avail or has_precedent or family_precedent)
    if low_expr:
        return "EXPLORATORY" if (raw > 0.0 or handle) \
            else "INSUFFICIENT EVIDENCE"
    if (raw >= 0.55 and conf >= 0.5 and coverage >= 0.55 and has_precedent):
        return "SUPPORTED"
    if raw >= 0.5 and coverage >= 0.4 and handle:
        return "PROMISING"
    if raw >= 0.35 and coverage >= 0.2:
        return "EXPLORATORY"
    if raw > 0.0 or any(a.get("score") is not None
                        for a in axes.values()):
        return "EXPLORATORY"
    return "INSUFFICIENT EVIDENCE"


def _limitations(axes, rec, low_expr) -> list[str]:
    out = []
    if low_expr:
        out.append("E3 expression percentile is LOW (< 0.2) in this context — "
                   "verdict capped at EXPLORATORY")
    for name, ax in axes.items():
        if ax["score"] is None:
            detail = ax.get("detail") or {}
            if name == "lysine":
                out.append("lysine opportunity UNKNOWN (no POI structure "
                           "provided)")
            elif name == "structure":
                out.append("structural feasibility UNKNOWN for this pair "
                           "(ternary data required)")
            elif name == "selectivity":
                out.append("selectivity/paralog evidence unavailable")
            elif name == "precedent" and not isinstance(detail, dict):
                out.append("no precedent evidence")
    if isinstance(rec, dict) and rec.get("available") is None:
        out.append("no DOI-cited recruiter ligand in the library — absence "
                   "reported, not assumed")
    return out


def _next_test(axes, rec, low_expr) -> str:
    tests = []
    if axes["cell_context"]["score"] is None:
        tests.append("measure E3 + adaptor expression in the target context "
                     "(WB/qPCR/DepMap pull)")
    if low_expr:
        tests.append("confirm E3 protein level before committing (low "
                     "expression)")
    if axes["localization"]["score"] is None:
        tests.append("verify POI/E3 subcellular co-occurrence (IF/imaging)")
    if isinstance(rec, dict) and rec.get("available") is None:
        tests.append("identify/validate a small-molecule recruiter for this E3")
    if axes["structure"]["score"] is None or axes["structure"].get(
            "score") == 0.0:
        tests.append("resolve or dock a ternary complex for this POI:E3")
    if axes["lysine"]["score"] is None:
        tests.append("obtain a POI structure to run the surface-lysine census")
    if not tests:
        tests.append("synthesize a pilot degrader and test degradation + "
                     "selectivity in the target cell line")
    return "; ".join(tests)
