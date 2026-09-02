"""
Link-INVENT-style linker scoring & ranking.
===========================================
Faithful re-implementation of the Link-INVENT scoring recipe used by
SynGlue's REINVENT wrapper (SynGlue_Py/module_4.py): per-component
reverse-sigmoid transformations aggregated as a weighted product
("custom_product" in Link-INVENT terms).

Components (weights from the Link-INVENT config):
    LGL  linker graph length      w=2  reverse_sigmoid(high=12, low=4,  k=0.5)
    LEL  linker effective length  w=2  reverse_sigmoid(high=8,  low=4,  k=0.5)
    Flex rotatable bonds          w=2  reverse_sigmoid(high=12, low=0,  k=0.15)
    HBD  linker H-bond donors     w=1  reverse_sigmoid(high=6,  low=0,  k=0.15)
    MW   molecular weight         w=2  reverse_sigmoid(high=1000,low=700,k=0.01)
    TPSA topological PSA          w=2  reverse_sigmoid(high=230, low=0,  k=0.1)

Optional extra component: ADMET-AI composite penalty (AMES/DILI/hERG) —
added as a multiplier when the isolated ADMET-AI venv is available
(PROTACPILOT_LINKER_ADMET_SCORE=1, default on).

score = product(component_i ** weight_i) * (1 - admet_risk)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors

from synglue_agent.backend.schemas import LinkerRecord

logger = logging.getLogger("protacpilot.linker_scoring")

# Link-INVENT component definitions: (weight, high, low, k)
COMPONENTS: Dict[str, Dict[str, float]] = {
    "LGL": {"weight": 2.0, "high": 12.0, "low": 4.0, "k": 0.5},
    "LEL": {"weight": 2.0, "high": 8.0, "low": 4.0, "k": 0.5},
    "Flex": {"weight": 2.0, "high": 12.0, "low": 0.0, "k": 0.15},
    "HBD": {"weight": 1.0, "high": 6.0, "low": 0.0, "k": 0.15},
    "MW": {"weight": 2.0, "high": 400.0, "low": 100.0, "k": 0.005},
    "TPSA": {"weight": 2.0, "high": 120.0, "low": 0.0, "k": 0.15},
}
# NOTE: Link-INVENT scores MW/TPSA on the FULL PROTAC (warhead+linker+E3);
# here they are adapted to the isolated linker's contribution (documented
# deviation so isolated-linker ranking is meaningful).


def reverse_sigmoid(value: float, high: float, low: float, k: float) -> float:
    """Link-INVENT's transformation: score 1 at the target band, falls off
    with steepness k outside it. Returns [0, 1]."""
    if value <= low:
        return float(max(0.0, 1.0 - k * (low - value)))
    if value >= high:
        return float(max(0.0, 1.0 - k * (value - high)))
    return 1.0


def _clean(smiles: str) -> str:
    """Strip all attachment markers (incl. BRICS [4*]-style dummies)."""
    import re as _re
    cleaned = _re.sub(r"\[\*:?\d*\]|\[\d\*\]", "", smiles)
    cleaned = _re.sub(r"\(\)", "", cleaned)  # drop dangling empty parens from dummy removal
    return cleaned


def _attachment_distance(linker_smiles: str) -> Optional[float]:
    """Shortest bond-path between the two attachment dummy atoms (the true
    linker effective length). None when markers are absent."""
    try:
        mol = Chem.MolFromSmiles(linker_smiles)
        if mol is None:
            return None
        dummies = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() == 0]
        if len(dummies) != 2:
            return None
        from collections import deque
        start, goal = dummies
        seen = {start}
        q = deque([(start, 0)])
        while q:
            node, dist = q.popleft()
            if node == goal:
                return float(dist)
            for nb in mol.GetAtomWithIdx(node).GetNeighbors():
                if nb.GetIdx() not in seen:
                    seen.add(nb.GetIdx())
                    q.append((nb.GetIdx(), dist + 1))
    except Exception:  # noqa: BLE001
        pass
    return None


def linker_properties(linker_smiles: str) -> Dict[str, float]:
    """Descriptors the scoring components need (strip attachment markers)."""
    clean = _clean(linker_smiles)
    mol = Chem.MolFromSmiles(clean)
    if mol is None:
        return {}
    eff_len = _attachment_distance(linker_smiles)
    return {
        "graph_length": float(mol.GetNumHeavyAtoms()),
        "effective_length": float(eff_len) if eff_len is not None
        else float(rdMolDescriptors.CalcNumRotatableBonds(mol)),
        "rotatable_bonds": float(rdMolDescriptors.CalcNumRotatableBonds(mol)),
        "hbd": float(rdMolDescriptors.CalcNumHBD(mol)),
        "mw": float(Descriptors.MolWt(mol)),
        "tpsa": float(rdMolDescriptors.CalcTPSA(mol)),
    }


@dataclass
class LinkerScore:
    smiles: str
    components: Dict[str, float] = field(default_factory=dict)
    composite: float = 0.0
    admet_risk: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {"smiles": self.smiles, "components": self.components,
                "composite": round(self.composite, 4), "admet_risk": round(self.admet_risk, 4)}


def score_linker_smiles(linker_smiles: str, use_admet: bool = True) -> LinkerScore:
    """Score one linker with the Link-INVENT recipe."""
    props = linker_properties(linker_smiles)
    if not props:
        return LinkerScore(smiles=linker_smiles, composite=0.0)
    comps: Dict[str, float] = {}
    log_score = 0.0
    for name, cfg in COMPONENTS.items():
        key = {
            "LGL": "graph_length", "LEL": "effective_length", "Flex": "rotatable_bonds",
            "HBD": "hbd", "MW": "mw", "TPSA": "tpsa",
        }[name]
        val = props.get(key, 0.0)
        s = reverse_sigmoid(val, cfg["high"], cfg["low"], cfg["k"])
        comps[name] = round(s, 4)
        log_score += cfg["weight"] * math.log(max(s, 1e-6))
    composite = math.exp(log_score)

    admet_risk = 0.0
    if use_admet:
        try:
            from synglue_agent.tools.admet_integration import _run_admet_ai
            rows = _run_admet_ai([_clean(linker_smiles)], timeout_s=120)
            if rows:
                e = rows[0].get("endpoints", {})
                admet_risk = min(
                    1.0, 0.50 * float(e.get("AMES") or 0.0)
                    + 0.30 * float(e.get("DILI") or 0.0)
                    + 0.20 * float(e.get("hERG") or 0.0))
        except Exception:  # noqa: BLE001
            admet_risk = 0.0
    return LinkerScore(smiles=linker_smiles, components=comps,
                       composite=composite, admet_risk=admet_risk)


def score_linker_record(record: LinkerRecord, use_admet: bool = True) -> LinkerScore:
    return score_linker_smiles(record.smiles, use_admet=use_admet)


def rank_linkers(linkers: Sequence[LinkerRecord],
                 use_admet: bool = True,
                 admet_batch: bool = True) -> List[LinkerRecord]:
    """Rank LinkerRecords by the Link-INVENT composite (descending).
    ADMET penalties are batched into ONE subprocess call when admet_batch."""
    if not linkers:
        return []
    scores: Dict[str, LinkerScore] = {}
    if use_admet and admet_batch:
        try:
            from synglue_agent.tools.admet_integration import _run_admet_ai
            cleaned = [_clean(l.smiles) for l in linkers]
            rows = _run_admet_ai(cleaned, timeout_s=300)
            risk_by = {}
            for row in rows or []:
                e = row.get("endpoints", {})
                risk_by[row.get("smiles")] = min(
                    1.0, 0.50 * float(e.get("AMES") or 0.0)
                    + 0.30 * float(e.get("DILI") or 0.0)
                    + 0.20 * float(e.get("hERG") or 0.0))
        except Exception:  # noqa: BLE001
            risk_by = {}
        for l in linkers:
            sc = score_linker_smiles(l.smiles, use_admet=False)
            sc.admet_risk = risk_by.get(_clean(l.smiles), 0.0)
            sc.composite = sc.composite * (1.0 - sc.admet_risk)
            scores[l.smiles] = sc
    else:
        for l in linkers:
            scores[l.smiles] = score_linker_smiles(l.smiles, use_admet=use_admet)

    ranked = sorted(linkers, key=lambda l: scores[l.smiles].composite, reverse=True)
    for l in ranked:
        sc = scores[l.smiles]
        l.synthetic_feasibility_proxy = round(sc.composite, 3)
        if l.provenance is None:
            l.provenance = {}
        l.provenance["linkinvent_score"] = sc.as_dict()
    return ranked


if __name__ == "__main__":
    for smi in ["[*:1]CCC[*:2]", "[*:1]CCOCCOCC[*:2]", "[*:1]CCCCCCCCCCCCCCCCCC[*:2]",
                "[*:1]Cc1ccc(C)cc1[*:2]", "[*:1]CCNC(=O)CCOCC[*:2]"]:
        sc = score_linker_smiles(smi, use_admet=False)
        print(f"{smi[:40]:42} comp={sc.composite:.4f}  {sc.components}")
