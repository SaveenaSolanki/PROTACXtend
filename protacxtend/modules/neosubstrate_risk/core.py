"""Core neosubstrate/off-target degradation risk functions."""
from __future__ import annotations
from typing import Any, Dict, List, Optional

KNOWN_NEOSUBSTRATES: Dict[str, List[str]] = {
    "CRBN": [
        "IKZF1", "IKZF3", "CK1α", "SALL4", "GSPT1",
        "PARK2", "RBM39", "NBEAL2"
    ],
    "VHL": [],
    "cIAP1": ["RIPK1", "CASP8"],
}

def risk_score(e3_ligase: str, warhead_smiles: str = "", ontology: Optional[Dict] = None) -> Dict[str, Any]:
    e3 = e3_ligase.upper()
    subs = KNOWN_NEOSUBSTRATES.get(e3, [])
    risk = len(subs) / 10.0 if e3 == "CRBN" else len(subs) / 5.0
    return {
        "neosubstrate_risk_score": round(min(risk, 1.0), 3),
        "neosubstrate_hit": len(subs) > 0,
        "neosubstrate_targets": subs,
        "e3_ligase": e3,
        "source": "curated_known_neosubstrates",
    }

def flag_offtarget(e3_ligase: str, warhead_smiles: str = "", ontology: Optional[Dict] = None) -> Dict[str, Any]:
    r = risk_score(e3_ligase, warhead_smiles, ontology)
    return {**r, "action": "flag" if r["neosubstrate_hit"] else "none"}
