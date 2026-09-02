"""Structural availability / ternary feasibility axis (Module 6).

Rules (no fabrication):
* E3 structural evidence comes from the curated catalog facts (e.g.,
  CRBN-DDB1 4CI2, BRD4-CRBN 6BN7; VHL-ElonginBC 4W9O, BRD4-VHL 5T35). Other
  E3s list no curated complex -> structural_evidence=UNKNOWN (None).
* Ternary-complex feasibility for THIS POI:E3 pair is never asserted from
  monomer availability: without a resolved/docked ternary complex it stays
  None with an explicit limitation (requires ternary modelling/assay).
* When a POI structure file is provided, its format/parseability is verified
  and monomer availability is recorded (used by the lysine axis).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from synglue_agent.modules.e3_opportunity.e3_catalog import load_catalog

_PDB_ID = re.compile(r"\b([0-9][A-Za-z0-9]{3})\b")


def catalog_row(e3_gene: str) -> dict[str, Any]:
    cat = load_catalog()
    row = cat[cat["e3_gene"] == e3_gene]
    if len(row) == 0:
        return {"structure_facts": "", "resistance": ""}
    return {"structure_facts": str(row.iloc[0]["structure_facts"]),
            "resistance": str(row.iloc[0]["resistance"])}


def pdb_ids(facts: str) -> list[str]:
    return list(dict.fromkeys(_PDB_ID.findall(facts)))


def e3_structural_evidence(e3_gene: str) -> dict[str, Any]:
    row = catalog_row(e3_gene)
    facts = row["structure_facts"]
    ids = pdb_ids(facts)
    has_ternary = any(k in facts for k in ("ternary",))
    return {"e3_complex_pdb_ids": ids,
            "has_curated_complex": bool(ids),
            "has_curated_ternary_example": bool(ids and has_ternary),
            "facts": facts}


def poi_structure_available(poi_structure: str | None) -> dict[str, Any]:
    """Verify a provided POI structure file/PDB id (best-effort, offline for
    files; network PDB fetch is opt-in)."""
    if not poi_structure:
        return {"poi_structure_provided": False, "poi_monomer_available": None,
                "note": "no POI structure provided"}
    p = Path(poi_structure)
    if p.exists():
        try:
            from synglue_agent.modules.lysine_ubiquitination_feasibility.core import (
                read_pdb,
            )
            atoms = read_pdb(p)
            return {"poi_structure_provided": True,
                    "poi_monomer_available": len(atoms) > 0,
                    "atom_count": len(atoms), "source": str(p)}
        except Exception as exc:
            return {"poi_structure_provided": True,
                    "poi_monomer_available": False, "note": f"parse failed: {exc}"}
    # a 4-char PDB id: only claim availability if the file is locally cached
    return {"poi_structure_provided": True, "poi_monomer_available": None,
            "note": "PDB id given; download/caching not performed offline — "
                    "no structural claim made"}


def structural_axis(poi_gene: str, e3_gene: str,
                    poi_structure: str | None) -> dict[str, Any]:
    e3 = e3_structural_evidence(e3_gene)
    poi = poi_structure_available(poi_structure)
    evidence_level = []
    if e3["has_curated_complex"]:
        evidence_level.append("e3_complex_pdb")
    if e3["has_curated_ternary_example"]:
        evidence_level.append("e3_ternary_example")
    if poi["poi_structure_provided"] and poi.get("poi_monomer_available"):
        evidence_level.append("poi_monomer")
    limitations = []
    if not e3["has_curated_complex"]:
        limitations.append("no curated E3 complex PDB — structural feasibility "
                           "UNKNOWN")
    limitations.append("ternary-complex feasibility for this POI:E3 pair "
                       "requires resolved/docked ternary data — not asserted "
                       "from monomers")
    return {
        # availability is real; pair feasibility is deliberately None
        "e3_complex_pdb_ids": e3["e3_complex_pdb_ids"],
        "e3_ternary_example": e3["has_curated_ternary_example"],
        "poi_monomer_available": poi.get("poi_monomer_available"),
        "evidence_level": evidence_level,
        "structural_availability_score": round(
            min(1.0, len(evidence_level) * 0.33), 4),
        "ternary_feasibility": None,   # UNKNOWN — never fabricated
        "limitations": limitations,
    }
