"""Lysine-opportunity axis (Module 6).

Surface-lysine census computed from a PROVIDED POI structure file only
(reuses Module 2's PDB reader + numeric Shrake-Rupley SASA). Without a POI
structure the axis is UNKNOWN (None) — no sequence-heuristic lysine claim.
CRL/E2 accessibility requires a ternary/E2 context and is reported None here
(see Module 2 for full geometric scoring with an E2 proxy).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

LYSINE_SIDECHAIN = {"CG", "CD", "CE", "NZ"}
_RADII = {"C": 1.7, "N": 1.55, "O": 1.52, "S": 1.8, "H": 1.2}
_NZ_SASA_CUTOFF = 10.0   # A^2; exposed NZ threshold (Module 2 convention)


def surface_lysines(poi_structure: str) -> dict[str, Any]:
    from protacxtend.modules.lysine_ubiquitination_feasibility.core import (
        Atom,
        read_pdb,
        shrake_rupley_sasa,
    )
    try:
        atoms = read_pdb(Path(poi_structure))
    except Exception as exc:
        return {"status": "UNKNOWN", "error": str(exc),
                "n_lysines": None, "surface_lysines": None,
                "lysine_opportunity": None,
                "note": "structure unparseable — no lysine claim"}
    if not atoms:
        return {"status": "UNKNOWN", "error": "no atoms parsed",
                "n_lysines": None, "surface_lysines": None,
                "lysine_opportunity": None}
    # full-structure SASA (context for burial)
    sasa = shrake_rupley_sasa(atoms, probe=1.4, n_dots=64, radii=_RADII)
    lys = {}
    for i, a in enumerate(atoms):
        if a.resname.strip().upper() == "LYS" and a.name.strip() == "NZ":
            lys.setdefault(a.chain, {}).setdefault(a.resseq, {})["nz_sasa"] = \
                sasa.get(i, 0.0)
        if a.resname.strip().upper() == "LYS" and a.name.strip() == "CA":
            lys.setdefault(a.chain, {}).setdefault(a.resseq, {})["ca"] = i
    n_lys = sum(len(v) for v in lys.values())
    surface = []
    for ch, resids in lys.items():
        for resseq, d in resids.items():
            nz = d.get("nz_sasa")
            if nz is not None and nz >= _NZ_SASA_CUTOFF:
                surface.append({"chain": ch, "resseq": resseq,
                                "nz_sasa_A2": round(float(nz), 2)})
    # opportunity: exposed-lysine richness (0..1); None when zero lysines are
    # observed (no fabricated claim). Saturated at >=5 exposed NZ.
    if n_lys == 0:
        opp = None
    else:
        opp = float(np.clip(len(surface) / 5.0, 0.0, 1.0))
    return {
        "status": "SUPPORTED" if n_lys else "UNKNOWN",
        "n_lysines": n_lys,
        "n_surface_lysines": len(surface),
        "surface_lysines": sorted(surface, key=lambda x: -x["nz_sasa_A2"])[:10],
        "lysine_opportunity": (None if opp is None else round(opp, 4)),
        "note": ("static surface census only; CRL/E2 accessibility needs a "
                 "ternary/E2 geometry (Module 2) — not claimed here"),
    }
