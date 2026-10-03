"""/reason — competing mechanistic explanations and discriminating tests.

Input: a candidate with measured (or strongly predicted) binary binding but
no cellular degradation (or any claim/outcome mismatch). Output: competing
hypotheses mapped to mechanistic axes, each with evidence for/against and
discriminating tests; all hypotheses are labelled inferred/computed — never
observed — and every degradation statement stays 'predicted' unless a
wet-lab record is supplied.
"""

from __future__ import annotations

import os, time
from dataclasses import dataclass, field
from typing import Any, Optional

from protacxtend.evidence.graph import EvidenceGraph, make_claim


@dataclass
class Hypothesis:
    hypothesis_id: str = ""
    axis: str = ""                    # dimension name
    statement: str = ""
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    discriminating_tests: list[str] = field(default_factory=list)
    expected_if_true: str = ""


_DIM_MAP = {"degradation_kinetics": "degradation", "e3_recruitment": "e3_recruitment",
           "exposure": "exposure", "ternary_formation": "ternary_formation",
           "ubiquitination": "ubiquitination", "cellular_context": "cellular_context",
           "target_engagement": "target_engagement"}

HYPOTHESIS_BANK: list[dict[str, Any]] = [
    {"axis": "exposure", "statement": "Cellular permeability/efflux limits intracellular concentration below the degradation threshold",
     "tests": ["PAMPA/Caco-2 permeability", "efflux ratio (MDCK-MDR1)", "cellular uptake (LC-MS/MS) at 1 and 24 h"],
     "expected": "low Papp / high efflux ratio -> exposure hypothesis supported"},
    {"axis": "ternary_formation", "statement": "Binary binding is strong but the ternary complex fails to form productively (geometry/cooperativity)",
     "tests": ["ternary complex formation assay (AlphaScreen/AlphaLISA or ITC with E3)", "cooperativity alpha measurement", "ternary co-crystal or mutagenesis on the E3-interface"],
     "expected": "no ternary signal / alpha<1 -> ternary hypothesis supported"},
    {"axis": "ubiquitination", "statement": "Ternary forms but the lysine geometry on the POI is unproductive (no ubiquitination)",
     "tests": ["in vitro ubiquitination assay (E1/E2/E3+ligase)", "surface-lysine mutagenesis scan", "K48/K63 ubiquitin linkage analysis"],
     "expected": "no POI ubiquitination despite ternary -> ubiquitination hypothesis supported"},
    {"axis": "e3_recruitment", "statement": "E3 is engaged biochemically but not in the cellular context (expression/accessibility)",
     "tests": ["E3 expression by cell line (qPCR/western)", "E3 knockdown/knockout control", "competitor-ligand displacement in cells"],
     "expected": "low E3 in the tested line -> recruitment-in-context hypothesis supported"},
    {"axis": "degradation_kinetics", "statement": "Degradation is real but below assay resolution (rate/duration mismatch)",
     "tests": ["time-course degradation (0.5/2/6/24 h)", "proteasome control (MG-132)", "label-free HiBiT titration"],
     "expected": "slow kdeg -> kinetics hypothesis supported"},
    {"axis": "cellular_context", "statement": "Cell context (signaling/neosubstrate competition) masks degradation of this POI",
     "tests": ["same compound in 2+ cell lines", "transcriptomic context comparison (module M5)", "target expression stability control"],
     "expected": "context-dependent degradation -> context hypothesis supported"},
]


def reason_about(candidate_smiles: str, *,
                 binding_claim: Optional[dict[str, Any]] = None,
                 degradation_claim: Optional[dict[str, Any]] = None,
                 supplied_axis: str = "") -> tuple[list[Hypothesis], EvidenceGraph, dict[str, Any]]:
    """Generate competing explanations for 'binding without degradation'."""
    graph = EvidenceGraph()
    binding_claim = binding_claim or {"statement": "compound shows strong binary binding (biochemical)",
                                      "value": None}
    graph.add(make_claim(command="reason", dimension="target_engagement", kind="observed" if binding_claim.get("source_ids") else "computed",
                         statement=binding_claim.get("statement", "binary binding"),
                         value=binding_claim.get("value"), unit=binding_claim.get("unit", ""),
                         tool=binding_claim.get("tool", "user-supplied claim"),
                         source_ids=binding_claim.get("source_ids", []) if binding_claim.get("observed", False) else [],
                         assay=binding_claim.get("assay", "")))
    graph.add(make_claim(command="reason", dimension="degradation", kind="computed",
                         statement=degradation_claim.get("statement", "no cellular degradation observed/measured"),
                         value=degradation_claim.get("value"), unit=degradation_claim.get("unit", ""),
                         tool=degradation_claim.get("tool", "user-supplied claim")))

    hypotheses: list[Hypothesis] = []
    for i, h in enumerate(HYPOTHESIS_BANK, 1):
        # binding-based filter: exposure/kinetics/context hypotheses apply broadly
        hyp = Hypothesis(hypothesis_id=f"H{i}", axis=h["axis"], statement=h["statement"],
                         evidence_for=[h["statement"] + " (consistent with: strong binary binding, no degradation)"],
                         evidence_against=[],
                         discriminating_tests=h["tests"],
                         expected_if_true=h["expected"])
        graph.add(make_claim(command="reason", dimension=_DIM_MAP.get(h["axis"], "degradation"), kind="inferred",
                             statement=h["statement"], tool="reasoner",
                             params={"candidate": candidate_smiles[:40]}))
        hypotheses.append(hyp)

    summary = {
        "candidate": candidate_smiles,
        "n_hypotheses": len(hypotheses),
        "axes": [h.axis for h in hypotheses],
        "label": "hypotheses are inferred; degradation statements remain predictions unless a wet-lab record is supplied",
    }
    return hypotheses, graph, summary