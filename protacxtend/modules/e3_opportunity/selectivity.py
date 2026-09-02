"""Selectivity-opportunity axis (Module 6).

* tissue/context restriction: real expression specificity across DepMap
  lineages (context.expression_breadth) — a restricted E3 gives a higher
  selectivity opportunity (real, not inferred).
* paralog discrimination: only reported for POI families in the curated map
  below (kinases/BET/HDAC/…); otherwise UNKNOWN. It describes the *existence*
  of close paralogs to discriminate, not that any E3 achieves it.
* off-target degradation risk: no fabricated risk. When no curated evidence
  exists for the pair it stays None and is listed as a limitation; curated
  catalog resistance notes are surfaced in rank.py (not a selectivity number).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from protacxtend.modules.e3_opportunity import context

# curated POI-family map (documented; paralogs are real, well-known families)
POI_FAMILIES: dict[str, list[str]] = {
    "kinase": ["BTK", "EGFR", "ALK", "FLT3", "JAK2", "PTK2", "FGFR1", "BRAF",
               "AURKA", "CDK2", "CDK4", "CDK6", "CDK9", "MAP2K1", "RIPK2",
               "IRAK1", "IRAK4", "TTK", "ABL1", "SRC", "SYK", "CSF1R"],
    "bet": ["BRD2", "BRD3", "BRD4", "BRDT"],
    "hdac": ["HDAC1", "HDAC2", "HDAC3", "HDAC6", "HDAC8"],
    "parp": ["PARP1", "PARP2", "PARP14"],
    "e3": ["MDM2", "MDM4", "RNF114", "RNF4"],
    "bcl2": ["BCL2", "BCL2L1", "MCL1"],
    "smarca": ["SMARCA2", "SMARCA4"],
}

_FAMILY_OF_GENE = {}
for fam, genes in POI_FAMILIES.items():
    for g in genes:
        _FAMILY_OF_GENE[g] = fam


def selectivity_axis(poi_gene: str, e3_gene: str) -> dict[str, Any]:
    breadth = context.expression_breadth(e3_gene)
    fam = _FAMILY_OF_GENE.get(poi_gene)
    paralogs = POI_FAMILIES.get(fam, []) if fam else []
    paralogs = [p for p in paralogs if p != poi_gene]
    # paralog discrimination opportunity: paralogs exist and E3 restricted
    score_parts = []
    if breadth.get("score") is not None:
        score_parts.append(float(breadth["score"]))
    if paralogs:
        score_parts.append(0.5)  # opportunity exists; magnitude is assay-level
    score = float(np.mean(score_parts)) if score_parts else None
    limitations = []
    if not paralogs:
        limitations.append("no curated paralog family map for this POI — "
                           "paralog discrimination UNKNOWN")
    if breadth.get("score") is None:
        limitations.append("E3 expression breadth unavailable — restriction "
                           "UNKNOWN")
    return {
        "score": None if score is None else round(score, 4),
        "expression_restriction_score": breadth.get("score"),
        "restricted_lineages": breadth.get("restricted_lineages"),
        "poi_family": fam, "paralogs": paralogs or None,
        "off_target_degradation_risk": None,   # never fabricated
        "limitations": limitations,
    }
