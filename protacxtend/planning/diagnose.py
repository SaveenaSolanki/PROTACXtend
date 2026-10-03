"""Mechanistic diagnosis for a candidate with strong biochemical binding but
absent cellular degradation.

Decision rule (hard): a linker change is NEVER recommended before the
discriminating measurement identifies the bottleneck. The diagnosis offers
competing explanations with evidence for/against each, one discriminating
measurement, and per-result next actions. Flipping an observation must flip
the recommended action (tested).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from protacxtend.planning.causal import CausalEvidenceRecord, egfr_strong_binding_no_degradation_case


@dataclass
class Hypothesis:
    id: str
    title: str
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    to_dict = lambda self: self.__dict__.copy()  # noqa: E731


@dataclass
class DiscriminatingMeasurement:
    experiment: str = ""
    tool: str = ""
    inputs: str = ""
    expected_artifact: str = ""
    controls: list[str] = field(default_factory=list)
    outcomes: dict[str, str] = field(default_factory=dict)  # result -> next action


@dataclass
class Diagnosis:
    case: str
    observations: dict[str, str] = field(default_factory=dict)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    discriminating_measurement: DiscriminatingMeasurement = field(default_factory=DiscriminatingMeasurement)
    recommended_action: str = ""
    gated: list[str] = field(default_factory=list)   # actions explicitly withheld until diagnosis

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case, "observations": self.observations,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "discriminating_measurement": self.discriminating_measurement.__dict__,
            "recommended_action": self.recommended_action, "gated": self.gated,
        }


def diagnose(rec: CausalEvidenceRecord) -> Diagnosis:
    """Run the diagnosis for a causal record. Observations taken from the
    record's tags/endpoints; the decision tree reacts to observations."""
    items = rec.by_step()
    binding = items.get("target_engagement")
    deg_state = ("absent" if (items.get("proteasome_loss") or items.get("phenotype_selectivity")).tag == "missing"
                 and "absent" in ((items.get("proteasome_loss") or items.get("phenotype_selectivity")).detail or "")
                 else "present" if any(i.tag == "measured" for i in rec.items
                                        if i.step in ("proteasome_loss", "phenotype_selectivity"))
                 else "unmeasured")
    obs = {
        "target_engagement": binding.tag if binding else "missing",
        "binding_endpoint": binding.endpoint if binding else "",
        "cellular_degradation": deg_state,
        "ternary": items.get("ternary_formation").tag if items.get("ternary_formation") else "missing",
        "ubiquitination": items.get("ubiquitination").tag if items.get("ubiquitination") else "missing",
    }
    diag = Diagnosis(case=f"{rec.target} ({rec.uniprot_id or 'n/a'})", observations=obs)

    strong_binding = binding is not None and binding.tag == "measured"
    absent_deg = deg_state == "absent"

    if strong_binding and absent_deg:
        diag.hypotheses = [
            Hypothesis(id="H1", title="Ternary formation is impaired",
                       evidence_for=["Strong binary binding of the warhead is measured (biochemical Kd).",
                                     "No ternary-engagement or structure measurement exists on record."],
                       evidence_against=["Ternary feasibility was not tested; geometry may be adequate.",
                                         "PDB-level ternary evidence for other degraders does not transfer without a model."]),
            Hypothesis(id="H2", title="Cellular permeability / uptake is insufficient",
                       evidence_for=["Degraders are beyond-Rule-of-5; permeability is the documented bottleneck.",
                                     "Cellular degradation absent despite potent biochemical Kd is the classic signature."],
                       evidence_against=["Neither permeability nor intracellular concentration was measured here."]),
            Hypothesis(id="H3", title="E3 recruitment or ubiquitination is not productive in the cell",
                       evidence_for=["Recruiter chosen on paper; no E3-engagement assay on record.",
                                     "No ubiquitination data on record."],
                       evidence_against=["E3 literature precedent exists for this target family; recruitment is plausible."]),
        ]
        dm = DiscriminatingMeasurement(
            experiment=("Parallel (a) ternary-engagement by SPR/BLI or cellular proximity (e.g. TriCEPS/nanoBRET) and "
                        "(b) cellular uptake: PAMPA/Caco-2 + intracellular compound concentration by LC-MS"),
            tool="SPR/BLI or TriCEPS/nanoBRET; PAMPA/Caco-2 + LC-MS",
            inputs=f"degreater (gefitinib-derived warhead + recruiter); cell line with reported absent degradation",
            expected_artifact="(a) ternary engagement yes/no + apparent affinity; (b) intracellular concentration vs free level",
            controls=["probe-only warhead (no recruiter) as ternary negative", "permeability reference (e.g. danazol/atenolol)",
                      "known-permeable degrader positive control"],
            outcomes={
                "ternary_ok_and_uptake_low": "next action = permeability-focused optimization (prodrug / polarity reduction); NO linker geometry change yet",
                "ternary_low": "next action = linker/E3-geometry redesign or E3 switch, with a ternary assay repeat",
                "ternary_ok_uptake_ok": "next action = ubiquitination/E3-engagement assay (E3 knockdown/mutant + ubiquitin blot)",
                "both_ok": "next action = re-check degradation assay protocol (dose/time/proteasome control) before any design change",
            },
        )
        diag.discriminating_measurement = dm
        diag.recommended_action = ("Run the discriminating measurement (ternary engagement + cellular uptake). "
                                   "Do NOT change the linker before the bottleneck is identified.")
        diag.gated = ["linker change", "E3 switch", "warhead change"]
        return diag

    if strong_binding and deg_state == "present":
        diag.recommended_action = ("Degradation is observed: proceed to dose/time/hook characterization and "
                                   "selectivity checks; optimization is potency/selectivity-driven, not bottleneck-driven.")
        return diag

    if binding is None or binding.tag != "measured":
        diag.recommended_action = "Binding is not measured: obtain a biochemical binding measurement before any cellular diagnosis."
        diag.gated = ["cellular degradation interpretation"]
        return diag

    diag.recommended_action = "Insufficient observations for a bottleneck diagnosis; record binding and degradation endpoints first."
    return diag


def egfr_diagnosis_demo() -> Diagnosis:
    return diagnose(egfr_strong_binding_no_degradation_case())