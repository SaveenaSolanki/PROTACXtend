"""/experiment — select assays that discriminate competing hypotheses.

Takes hypotheses (from /reason or /optimize risk notes) and returns an assay
sequence where every hypothesis gets at least one discriminating test with
mandatory controls, effort and expected outcomes. Nothing is executed; the
output is a protocol with provenance.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

from protacxtend.evidence.graph import EvidenceGraph, make_claim


@dataclass
class ExperimentTest:
    test_id: str = ""
    hypothesis_id: str = ""
    hypothesis_axis: str = ""
    assay: str = ""
    readout: str = ""
    controls: list[str] = field(default_factory=list)
    discriminator: str = ""
    effort: str = "M"
    expected_if_hypothesis_true: str = ""
    expected_if_false: str = ""


def design(hypotheses: list[Any], *, graph: Optional[EvidenceGraph] = None) -> tuple[list[ExperimentTest], EvidenceGraph]:
    """Map each hypothesis to a discriminating assay sequence with controls."""
    g = graph or EvidenceGraph()
    tests: list[ExperimentTest] = []
    for i, hyp in enumerate(hypotheses, 1):
        axis = getattr(hyp, "axis", "") or (hyp.get("axis", "") if isinstance(hyp, dict) else "")
        h_id = getattr(hyp, "hypothesis_id", "") or f"H{i}"
        discrim = (getattr(hyp, "discriminating_tests", None) or
                   (hyp.get("discriminating_tests", []) if isinstance(hyp, dict) else []) or [])
        assay = discrim[0] if discrim else f"{axis}-diagnostic assay"
        controls = ["vehicle", "E3-null or competitor-ligand control",
                    "proteasome control (MG-132)"] if axis in ("ubiquitination", "degradation_kinetics") else \
                   ["vehicle", "positive control compound", "negative structural analogue"]
        tests.append(ExperimentTest(
            test_id=f"T{i}", hypothesis_id=h_id, hypothesis_axis=axis, assay=assay,
            readout="quantitative readout per assay protocol; replicate >= 3",
            controls=controls,
            discriminator=f"outcome differs across hypotheses H-set (axis {axis})",
            effort="M" if "screen" not in assay.lower() else "L",
            expected_if_hypothesis_true=getattr(hyp, "expected_if_true", "") or "signal consistent with the hypothesis",
            expected_if_false="alternative hypothesis retains support"))
        _dim = {"degradation_kinetics": "degradation"}.get(axis, axis)
        g.add(make_claim(command="experiment", dimension=_dim if _dim in (
            "exposure", "ternary_formation", "ubiquitination", "e3_recruitment",
            "degradation", "cellular_context", "target_engagement",
            "selectivity", "synthesis") else "cellular_context", kind="proposed",
            statement=f"discriminating assay proposed: {assay}", tool="experimenter",
            params={"hypothesis": h_id}))
    return tests, g


def render(tests: list[ExperimentTest]) -> str:
    out = ["# /experiment — discriminating test plan (protocol; nothing executed)", "",
           "| test | hypothesis | assay | readout | controls | discriminator | effort |",
           "|---|---|---|---|---|---|---|"]
    for t in tests:
        out.append(f"| {t.test_id} | {t.hypothesis_id} ({t.hypothesis_axis}) | {t.assay} | "
                   f"{t.readout[:40]} | {', '.join(t.controls[:2])}... | {t.discriminator[:44]} | {t.effort} |")
    out.append("")
    out.append("Label: proposed protocol; no experimental results are claimed.")
    return "\n".join(out) + "\n"