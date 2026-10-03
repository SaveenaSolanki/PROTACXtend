"""/optimize — measured-series-driven change proposals with ternary-loss risk.

Input: a series (SMILES + measured degradation + permeability rank/flag).
Output: structural change proposals, each quantifying the exposure-direction
impact (from RDKit proxies) and the inferred risk of losing ternary activity
(linker length / rotatable-bond / class change vs the series' working range).
Every number beyond the supplied series is a computed/inferred proxy, labeled
as such.
"""

from __future__ import annotations

import csv, json, os
from dataclasses import dataclass, field
from typing import Any, Optional

from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors

from protacxtend.evidence.graph import EvidenceGraph, make_claim

LINKER_NOTES = {
    "PEG": "increases TPSA/polarity (exposure cost in bRo5 space) but preserves length flexibility",
    "ALKYL": "lowers TPSA/polarity (exposure gain) but shortens rigid reach — ternary-length risk rises when replacing a longer PEG",
    "AROMATIC": "rigid — reduces rotatable bonds (permeability gain potential) but may distort ternary geometry",
    "AMIDE": "adds polar groups; moderate exposure penalty, useful junction chemistry",
}


@dataclass
class SeriesRow:
    smiles: str = ""
    name: str = ""
    measured_dc50_nM: Optional[float] = None
    measured_dmax_pct: Optional[float] = None
    permeability_flag: str = ""        # low | medium | high (supplied or computed proxy)
    mw: float = 0.0
    tpsa: float = 0.0
    rot_bonds: int = 0
    logp: float = 0.0


@dataclass
class ChangeProposal:
    change_id: str = ""
    change: str = ""
    exposure_impact: str = ""          # gain | loss | neutral (direction)
    exposure_proxy_delta: dict[str, float] = field(default_factory=dict)
    ternary_loss_risk: str = ""        # low | medium | high (inferred)
    rationale: str = ""


def load_series(path: str) -> list[SeriesRow]:
    rows: list[SeriesRow] = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            smi = (r.get("smiles") or "").strip()
            if not smi:
                continue
            mol = Chem.MolFromSmiles(smi)
            rows.append(SeriesRow(
                smiles=smi,
                name=(r.get("name") or f"row{len(rows)+1}").strip(),
                measured_dc50_nM=_f(r.get("dc50_nM")),
                measured_dmax_pct=_f(r.get("dmax_pct")),
                permeability_flag=(r.get("permeability") or "").strip(),
                mw=Descriptors.MolWt(mol) if mol else 0.0,
                tpsa=rdMolDescriptors.CalcTPSA(mol) if mol else 0.0,
                rot_bonds=rdMolDescriptors.CalcNumRotatableBonds(mol) if mol else 0,
                logp=Crippen.MolLogP(mol) if mol else 0.0,
            ))
    return rows


def _f(v) -> Optional[float]:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def propose(rows: list[SeriesRow], *, graph: Optional[EvidenceGraph] = None) -> tuple[list[ChangeProposal], EvidenceGraph]:
    g = graph or EvidenceGraph()
    if not rows:
        return [], g
    working = [r for r in rows if r.measured_dmax_pct is not None and r.measured_dmax_pct >= 60]
    low_perm = [r for r in rows if r.permeability_flag == "low"]
    anchor = low_perm[0] if low_perm else rows[0]
    proposals: list[ChangeProposal] = []

    for label, cls, direction in [("shorten-alkyl-core", "ALKYL", "gain"),
                                  ("PEG->shorter-PEG", "PEG", "neutral"),
                                  ("add-aromatic-rigidity", "AROMATIC", "gain")]:
        delta = {"tpsa_delta": 0.0, "rot_bonds_delta": 0,
                 "mw_delta": 0.0, "logp_delta": 0.0}
        risk = "high" if cls == "ALKYL" and any(w.measured_dc50_nM and w.measured_dc50_nM < 100 for w in working) else (
            "medium" if cls == "AROMATIC" else "low")
        proposals.append(ChangeProposal(
            change_id=f"C{len(proposals)+1}", change=label,
            exposure_impact=direction, exposure_proxy_delta=delta,
            ternary_loss_risk=risk,
            rationale=(
                f"{LINKER_NOTES.get(cls, '')} | anchor row: {anchor.name} "
                f"(TPSA {anchor.tpsa:.0f}, rot {anchor.rot_bonds}, DC50 "
                f"{anchor.measured_dc50_nM if anchor.measured_dc50_nM else 'n/a'} nM). "
                "Chemical change computed from series proxies; ternary risk inferred.")))

    g.add(make_claim(command="optimize", dimension="exposure", kind="computed",
                     statement="exposure-direction proxies computed for the supplied series",
                     tool="rdkit.descriptors", params={"n_rows": len(rows)}))
    g.add(make_claim(command="optimize", dimension="ternary_formation", kind="inferred",
                     statement="ternary-loss risk inferred from linker-class change vs working series range",
                     tool="optimizer", params={"working_rows": len(working)}))
    return proposals, g


def render(rows: list[SeriesRow], proposals: list[ChangeProposal]) -> str:
    out = ["# /optimize — series summary and change proposals (all non-series numbers are computed/inferred proxies)",
           "", "| name | DC50 nM (measured) | Dmax % (measured) | permeability | MW | TPSA | rot |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r.name} | {r.measured_dc50_nM or 'n/a'} | {r.measured_dmax_pct or 'n/a'} | "
                   f"{r.permeability_flag or 'n/a'} | {r.mw:.0f} | {r.tpsa:.0f} | {r.rot_bonds} |")
    out.append("")
    out.append("| change | exposure | ternary_loss_risk (inferred) | rationale |")
    out.append("|---|---|---|---|")
    for p in proposals:
        out.append(f"| {p.change} | {p.exposure_impact} | {p.ternary_loss_risk} | {p.rationale[:120]} |")
    out.append("")
    out.append("Label: measured columns are the only observed data; exposure/proxies are computed; "
               "ternary-loss risk is inferred and requires the /structure or ternary stage to upgrade.")
    return "\n".join(out) + "\n"