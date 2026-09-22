"""Evidence-grounding experiment (Section 10).

Every scientific claim is scored for support, provenance and context match.
No semantic-similarity shortcut is used for the support relation: the caller
supplies, per claim, whether the cited source actually supports it and whether
the source context matches the task context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

CONTEXT_FIELDS = ("target", "disease", "cell_type", "mutation", "species",
                  "assay", "e3", "molecule")
EVIDENCE_TYPES = ("measured", "retrieved", "calculated", "predicted", "missing",
                  "not_verifiable")


@dataclass
class Claim:
    text: str
    citation_ids: List[str] = field(default_factory=list)
    evidence_type: str = "missing"
    supported: bool = False                      # citation actually supports claim
    primary_source: bool = False
    context_match: Dict[str, bool] = field(default_factory=dict)
    date: Optional[str] = None


def evidence_metrics(claims: Sequence[Claim],
                     citations_resolvable: Dict[str, bool] | None = None,
                     cutoff: Optional[str] = None) -> Dict[str, Any]:
    n = len(claims)
    if n == 0:
        return {"n_claims": 0, "citation_precision": None,
                "citation_coverage": None, "primary_source_rate": None,
                "unsupported_claim_rate": None, "contradiction_detection": None,
                "context_match_rate": None, "temporal_compliance": None}
    resolvable = citations_resolvable or {}
    cited = [c for c in claims if c.citation_ids]
    supported = [c for c in claims if c.supported and c.citation_ids]
    unsupported = [c for c in claims if not c.supported]
    primary = [c for c in cited if c.primary_source]

    # citation precision: fraction of cited claims whose citation resolves AND supports
    precision_den = len(cited) or 1
    precision = sum(1 for c in cited
                    if c.supported and all(resolvable.get(i, True) for i in c.citation_ids)
                    ) / precision_den
    coverage = len(supported) / n

    ctx_total = ctx_match = 0
    for c in cited:
        for f in CONTEXT_FIELDS:
            if f in c.context_match:
                ctx_total += 1
                ctx_match += 1 if c.context_match[f] else 0
    context_rate = (ctx_match / ctx_total) if ctx_total else None

    if cutoff:
        compliant = [c for c in cited if c.date is None or str(c.date) <= cutoff]
        temporal = len(compliant) / (len(cited) or 1)
    else:
        temporal = None

    return {
        "n_claims": n,
        "n_cited": len(cited),
        "citation_precision": round(precision, 4),
        "citation_coverage": round(coverage, 4),
        "primary_source_rate": round(len(primary) / precision_den, 4),
        "unsupported_claim_rate": round(len(unsupported) / n, 4),
        "unsupported_claims": [c.text for c in unsupported],
        "context_match_rate": None if context_rate is None else round(context_rate, 4),
        "temporal_compliance": None if temporal is None else round(temporal, 4),
    }


def contradiction_metrics(pairs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """pairs: [{claim_a, claim_b, truly_contradictory, system_flagged}]."""
    truly = [p for p in pairs if p.get("truly_contradictory")]
    flagged = [p for p in truly if p.get("system_flagged")]
    return {
        "n_contradictions": len(truly),
        "detected": len(flagged),
        "contradiction_detection": round(len(flagged) / len(truly), 4) if truly else None,
        "false_contradiction_flags": sum(
            1 for p in pairs if p.get("system_flagged") and not p.get("truly_contradictory")),
    }
