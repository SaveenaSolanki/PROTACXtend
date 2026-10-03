"""Standardized mechanistic evidence types and non-equivalence guard.

Evidence-type taxonomy (M-closure spec §21):

    EXPERIMENTAL | CURATED_DATABASE | STRUCTURAL | CALCULATED |
    MECHANISTIC_SIMULATION | MODEL_PREDICTED | STRUCTURAL_PROXY |
    INFERRED | UNAVAILABLE

Downstream code must never treat these as equivalent: a guard walks a
candidate evidence block and refuses aggregation paths that would merge a
proxy/prediction with experimental evidence into a single opaque score.
"""

from __future__ import annotations

import enum
from typing import Any, Iterable

EVIDENCE_TYPES = (
    "EXPERIMENTAL",
    "CURATED_DATABASE",
    "STRUCTURAL",
    "CALCULATED",
    "MECHANISTIC_SIMULATION",
    "MODEL_PREDICTED",
    "STRUCTURAL_PROXY",
    "INFERRED",
    "UNAVAILABLE",
)


class EvidenceType(str, enum.Enum):
    EXPERIMENTAL = "EXPERIMENTAL"
    CURATED_DATABASE = "CURATED_DATABASE"
    STRUCTURAL = "STRUCTURAL"
    CALCULATED = "CALCULATED"
    MECHANISTIC_SIMULATION = "MECHANISTIC_SIMULATION"
    MODEL_PREDICTED = "MODEL_PREDICTED"
    STRUCTURAL_PROXY = "STRUCTURAL_PROXY"
    INFERRED = "INFERRED"
    UNAVAILABLE = "UNAVAILABLE"


#: Evidence types that are never interchangeable for scientific claims.
NON_EQUIVALENT_GROUPS = (
    # measured-only tier
    frozenset({EvidenceType.EXPERIMENTAL, EvidenceType.CURATED_DATABASE}),
    # structural/geometry tier (from coordinates; not binding measurements)
    frozenset({EvidenceType.STRUCTURAL, EvidenceType.CALCULATED}),
    # simulated/modeled tier (never promoted to measured)
    frozenset({EvidenceType.MECHANISTIC_SIMULATION, EvidenceType.MODEL_PREDICTED, EvidenceType.STRUCTURAL_PROXY}),
)

#: Which evidence types may support a "measured" scientific claim downstream.
MEASURED_CLAIM_TYPES = frozenset({EvidenceType.EXPERIMENTAL, EvidenceType.CURATED_DATABASE})

#: Which evidence types may support a "geometric/structural" claim.
STRUCTURAL_CLAIM_TYPES = frozenset({EvidenceType.STRUCTURAL, EvidenceType.CALCULATED})


_TYPE_ALIASES = {
    "STRUCTURAL_COOPERATIVITY_PROXY": "STRUCTURAL_PROXY",
}


def _split_types(evidence_types: Iterable[str]) -> set[EvidenceType]:
    """Expand compound tags (e.g. STRUCTURAL/CALCULATED) into enum members."""
    out: set[EvidenceType] = set()
    for t in evidence_types:
        if not t:
            continue
        for part in str(t).upper().split("/"):
            part = part.strip()
            part = _TYPE_ALIASES.get(part, part)
            if part:
                out.add(EvidenceType(part))
    return out


def assert_no_equivalence(evidence_types: Iterable[str]) -> list[str]:
    """Return violations where two evidence types would be merged as equal.

    Used by ranking/nomination paths to prove that M1-M4 outputs never blend
    measured, structural, and predicted evidence into one opaque score.
    """
    types = _split_types(evidence_types)
    violations: list[str] = []
    for group in NON_EQUIVALENT_GROUPS:
        present = types & group
        if len(present) > 1:
            violations.append(
                "evidence types are not interchangeable: "
                + " vs ".join(sorted(t.value for t in present))
            )
    return violations


def classify_claim(evidence_types: Iterable[str]) -> str:
    """Highest defensible claim tier for a set of evidence types.

    Returns 'measured' | 'structural' | 'simulated' | 'unavailable'.
    """
    types = _split_types(evidence_types)
    if types & MEASURED_CLAIM_TYPES:
        return "measured"
    if types & STRUCTURAL_CLAIM_TYPES:
        return "structural"
    if types & {EvidenceType.MECHANISTIC_SIMULATION, EvidenceType.MODEL_PREDICTED, EvidenceType.STRUCTURAL_PROXY}:
        return "simulated"
    if types & {EvidenceType.INFERRED}:
        return "inferred"
    return "unavailable"


def evidence_type_matrix_rows() -> list[dict[str, str]]:
    """Rows for the evidence-type matrix artifact (spec §21 / §27)."""
    rows = []
    for t in EVIDENCE_TYPES:
        rows.append({
            "evidence_type": t,
            "examples": {
                "EXPERIMENTAL": "literature/assay measured Kd, DC50, alpha",
                "CURATED_DATABASE": "curated DOI-backed records (e.g. cooperative alpha table)",
                "STRUCTURAL": "PDB coordinates, lysine SASA from structure",
                "CALCULATED": "interface contacts, distances, Shrake-Rupley SASA",
                "MECHANISTIC_SIMULATION": "M1 equilibrium hook model output",
                "MODEL_PREDICTED": "M4 degradation model output",
                "STRUCTURAL_PROXY": "M3 proxy score (never labelled alpha)",
                "INFERRED": "interpretation across records",
                "UNAVAILABLE": "missing input/source; abstention",
            }[t],
            "usable_for_claim": {
                "EXPERIMENTAL": "measured", "CURATED_DATABASE": "measured",
                "STRUCTURAL": "structural", "CALCULATED": "structural",
                "MECHANISTIC_SIMULATION": "simulated", "MODEL_PREDICTED": "simulated",
                "STRUCTURAL_PROXY": "simulated", "INFERRED": "inferred",
                "UNAVAILABLE": "none",
            }[t],
            "can_be_promoted_to_experimental": "no",
        })
    return rows