"""Recruiter tractability axis (Module 6).

Recruiter evidence comes exclusively from the DOI-cited E3-ligand library
(data layer). Demo-only rows never count as recruiter evidence. A missing
recruiter is reported explicitly (recruiter_available=False/None) — the model
never implies a recruiter exists. Affinity (activity_nM), exit-vector
confidence, stereochemistry validity and attachment-point notes are carried
through as reported by the source; synthetic accessibility is not invented.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from synglue_agent.modules.e3_opportunity.dataset import load_recruiters

_recruiters: pd.DataFrame | None = None


def recruiters() -> pd.DataFrame:
    global _recruiters
    if _recruiters is None:
        _recruiters = load_recruiters()
    return _recruiters


def recruiter_info(e3_gene: str) -> dict[str, Any]:
    rec = recruiters()
    rows = rec[(rec["e3_gene"] == e3_gene) & (rec["demo_only"] == False)]  # noqa
    if len(rows) == 0:
        rows = rec[(rec["e3_gene"] == e3_gene)]
        has_any = len(rows) > 0
        return {"available": None if not has_any else False,
                "demo_only": bool(has_any),
                "n_cited_ligands": 0, "n_demo_ligands": int(has_any),
                "best_affinity_nM": None,
                "max_exit_vector_confidence": None,
                "stereochemistry_valid": None,
                "attachment_points": [],
                "confidence": 0.0,
                "limitations": ["no DOI-cited recruiter ligand in the library "
                                "for this E3"]}
    conf_parts = []
    aff = rows["activity_nM_num"].dropna()
    best_aff = float(aff.min()) if len(aff) else None
    if best_aff is not None:
        # log-scale affinity strength (1 nM ~ 1.0, 10 uM ~ 0)
        conf_parts.append(float(np.clip(1.0 - np.log10(max(best_aff, 1.0)) /
                                        7.0, 0.0, 1.0)))
    ev = pd.to_numeric(rows["exit_vector_confidence"], errors="coerce")
    if ev.notna().any():
        conf_parts.append(float(ev.max()))
    sv = rows["stereochemistry_valid"].astype(str)
    if len(sv):
        frac_ok = float((sv == "true").mean())
        conf_parts.append(frac_ok)
    src_conf = pd.to_numeric(rows["source_confidence"], errors="coerce")
    if src_conf.notna().any():
        conf_parts.append(float(src_conf.max()))
    return {
        "available": True,
        "demo_only": False,
        "n_cited_ligands": int(len(rows)),
        "n_demo_ligands": 0,
        "best_affinity_nM": (None if best_aff is None else round(best_aff, 2)),
        "max_exit_vector_confidence": (None if ev.notna().sum() == 0
                                       else round(float(ev.max()), 3)),
        "stereochemistry_valid": bool((sv == "true").all())
        if len(sv) else None,
        "attachment_points": sorted(set(
            str(a) for a in rows["attachment_point"].dropna()
            if str(a).strip())),
        "confidence": round(float(np.mean(conf_parts)), 4)
        if conf_parts else 0.0,
        "ligand_names": sorted(set(rows["name"].dropna().astype(str)))[:8],
        "limitations": [],
    }
