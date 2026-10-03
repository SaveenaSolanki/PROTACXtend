"""Shared causal evidence record for one target/compound programme.

Chain: cellular target engagement -> E3 recruitment -> ternary formation ->
ubiquitination -> proteasome-dependent loss -> phenotype/selectivity.
Each item is tagged measured | computed | inferred | proposed | missing and
carries, where applicable: compound, target variant, cell, dose, time,
endpoint, source. A tagged item is never upgraded by another item's tag
(e.g. chemical validity never makes 'proteasome loss' measured).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

Tag = Literal["measured", "computed", "inferred", "proposed", "missing"]

STEPS = ("target_engagement", "e3_recruitment", "ternary_formation",
         "ubiquitination", "proteasome_loss", "phenotype_selectivity")
STEP_TITLES = {
    "target_engagement": "Cellular target engagement",
    "e3_recruitment": "E3 recruitment",
    "ternary_formation": "Ternary complex formation",
    "ubiquitination": "Ubiquitination",
    "proteasome_loss": "Proteasome-dependent target loss",
    "phenotype_selectivity": "Phenotype / selectivity",
}


@dataclass
class CausalItem:
    step: str
    tag: Tag = "missing"
    compound: str = ""
    target_variant: str = ""
    cell: str = ""
    dose: str = ""
    time: str = ""
    endpoint: str = ""
    source: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CausalEvidenceRecord:
    target: str = ""
    uniprot_id: str = ""
    items: list[CausalItem] = field(default_factory=list)

    def by_step(self) -> dict[str, CausalItem]:
        return {i.step: i for i in self.items}

    def to_dict(self) -> dict[str, Any]:
        return {"target": self.target, "uniprot_id": self.uniprot_id,
                "items": [i.to_dict() for i in self.items]}


def empty_record(target: str = "", uniprot_id: str = "") -> CausalEvidenceRecord:
    rec = CausalEvidenceRecord(target=target, uniprot_id=uniprot_id)
    for s in STEPS:
        rec.items.append(CausalItem(step=s, tag="missing",
                                    detail=f"{STEP_TITLES[s]}: no evidence on record"))
    return rec


def set_item(rec: CausalEvidenceRecord, step: str, *, tag: Tag, compound: str = "",
             target_variant: str = "", cell: str = "", dose: str = "", time: str = "",
             endpoint: str = "", source: str = "", detail: str = "") -> CausalEvidenceRecord:
    for i in rec.items:
        if i.step == step:
            i.tag = tag; i.compound = compound; i.target_variant = target_variant
            i.cell = cell; i.dose = dose; i.time = time; i.endpoint = endpoint
            i.source = source; i.detail = detail
            return rec
    rec.items.append(CausalItem(step=step, tag=tag, compound=compound, target_variant=target_variant,
                                cell=cell, dose=dose, time=time, endpoint=endpoint, source=source,
                                detail=detail))
    return rec


def summarize(rec: CausalEvidenceRecord) -> str:
    lines = [f"Causal evidence — {rec.target} ({rec.uniprot_id or 'n/a'})"]
    for i in rec.items:
        ctx = " · ".join(x for x in (i.compound, i.target_variant, i.cell, i.dose, i.time, i.endpoint) if x)
        src = f" · source: {i.source}" if i.source else ""
        lines.append(f"  [{i.tag}] {i.step}: {i.detail}{(' (' + ctx + ')' ) if ctx else ''}{src}")
    return "\n".join(lines)


def egfr_strong_binding_no_degradation_case() -> CausalEvidenceRecord:
    """Typed input case: strong biochemical binding (measured, literature)
    with absent cellular degradation (input observation flagged for
    verification). Used by the diagnosis demo; every row keeps its source."""
    rec = empty_record(target="EGFR", uniprot_id="P00533")
    set_item(rec, "target_engagement", tag="measured",
             compound="gefitinib", target_variant="EGFR WT", cell="n/a (biochemical)",
             dose="n/a", time="n/a", endpoint="Kd 0.8 nM",
             source="DOI 10.1021/acs.jmedchem.9b01566 (protacSpace warhead table row; CHEMBL939)",
             detail="Measured sub-nM biochemical Kd for the EGFR kinase domain.")
    set_item(rec, "e3_recruitment", tag="proposed",
             compound="EGFR degrader (gefitinib-derived warhead + recruiter)",
             endpoint="E3 engagement assay", source="proposed, not performed",
             detail="Recruiter chosen on paper; no E3 engagement measured.")
    set_item(rec, "ternary_formation", tag="missing",
             detail="No ternary-engagement or structure measurement on record.")
    set_item(rec, "ubiquitination", tag="missing",
             detail="No ubiquitination assay on record.")
    set_item(rec, "proteasome_loss", tag="missing",
             endpoint="cellular DC50/Dmax",
             detail="Cellular degradation input: reported absent in the tested cell line "
                    "(input observation for the diagnosis demo; assay record to be attached).")
    set_item(rec, "phenotype_selectivity", tag="missing",
             detail="No phenotype/selectivity data on record.")
    return rec