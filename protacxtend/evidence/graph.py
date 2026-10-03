"""Shared evidence graph across all research commands.

Every claim a command emits points to a record with:
- kind: observed | computed | inferred | proposed
- dimension: one of the nine mechanistic axes (target engagement, E3
  recruitment, ternary formation, ubiquitination, degradation, cellular
  context, selectivity, exposure, synthesis)
- provenance: tool (name+version), query/params, source identifiers and
  artifact path — a claim without provenance cannot be added
- assay context: assay, cell line, concentration, time, species, condition
- uncertainty and conflicts (claim-level or cross-claim)

The graph enforces honesty: kind="observed" requires a measured source
identifier; degradation values are never relabeled measured by accident
(models must set kind computed/inferred and the caller must not upgrade it).
"""

from __future__ import annotations

import csv, hashlib, json, os, re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

DIMENSIONS = (
    "target_engagement", "e3_recruitment", "ternary_formation", "ubiquitination",
    "degradation", "cellular_context", "selectivity", "exposure", "synthesis",
)
KINDS = ("observed", "computed", "inferred", "proposed")

_OBSERVED_REQUIRES = ("source_ids", "assay")  # observed claims need a measured source + assay


@dataclass
class Claim:
    claim_id: str = ""
    command: str = ""                 # which command emitted it
    dimension: str = ""               # one of DIMENSIONS
    kind: str = "computed"            # observed|computed|inferred|proposed
    statement: str = ""
    value: Optional[float] = None
    unit: str = ""
    assay_context: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)   # tool, version, query, params, source_ids, artifact
    uncertainty: dict[str, Any] = field(default_factory=dict)  # ci_low/ci_high or std or note
    status: str = "standalone"        # standalone | conflicting | contradicted | confirmed
    conflict_of: list[str] = field(default_factory=list)       # claim ids
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.dimension not in DIMENSIONS:
            errs.append(f"unknown dimension {self.dimension!r}")
        if self.kind not in KINDS:
            errs.append(f"unknown kind {self.kind!r}")
        if not self.provenance.get("tool"):
            errs.append("claim lacks provenance.tool (fabricated evidence guard)")
        if self.kind == "observed":
            for req in _OBSERVED_REQUIRES:
                if not (self.provenance.get(req) or self.assay_context.get(req)):
                    errs.append(f"observed claim lacks {req} (measured source required)")
            if self.dimension == "degradation":
                tool = str(self.provenance.get("tool", "")).lower()
                statement = str(self.statement).lower()
                assay = str(self.assay_context.get("assay", "")).lower()
                source_ids = [str(x) for x in self.provenance.get("source_ids", [])]
                measured_source = bool(self.provenance.get("measured_source")) or any(
                    re.search(r"10\.\d{4,9}/", sid.lower())
                    or sid.lower().startswith(("pmid:", "pubmed:", "protacdb:", "chembl:"))
                    for sid in source_ids
                )
                model_like = any(tok in tool or tok in statement or tok in assay
                                 for tok in ("predict", "prediction", "model", "ml", "chemprop",
                                             "synglue", "tack", "heuristic", "proxy"))
                if model_like:
                    errs.append("ML predictions cannot be observed; use computed/inferred and keep predicted labeling")
                if not measured_source:
                    errs.append("observed degradation claim lacks DOI/PMID/PROTACDB/CHEMBL measured source id")
        return errs


@dataclass
class EvidenceGraph:
    claims: list[Claim] = field(default_factory=list)

    # ------------------------------------------------------------------
    def add(self, claim: Claim, *, allow_violations: bool = False) -> Claim:
        claim.claim_id = claim.claim_id or self._next_id(claim)
        errs = claim.validate()
        if errs and not allow_violations:
            raise ValueError("; ".join(errs))
        self.claims.append(claim)
        return claim

    def _next_id(self, claim: Claim) -> str:
        seed = f"{claim.command}|{claim.dimension}|{claim.statement}"
        return "ev-" + hashlib.sha1(seed.encode()).hexdigest()[:10]

    # ------------------------------------------------------------------
    def query(self, dimension: str | None = None, command: str | None = None,
              kind: str | None = None) -> list[Claim]:
        out = []
        for c in self.claims:
            if dimension and c.dimension != dimension:
                continue
            if command and c.command != command:
                continue
            if kind and c.kind != kind:
                continue
            out.append(c)
        return out

    def conflicts(self) -> list[Claim]:
        return [c for c in self.claims if c.status in ("conflicting", "contradicted") or c.conflict_of]

    def register_conflict(self, a: str, b: str) -> None:
        for c in self.claims:
            if c.claim_id == a:
                c.status = "conflicting"
                c.conflict_of.append(b)
            if c.claim_id == b:
                c.status = "conflicting"
                c.conflict_of.append(a)

    def fingerprint(self) -> str:
        payload = json.dumps([self._claim_dict(c) for c in self.claims], sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    def _claim_dict(self, c: Claim) -> dict:
        return {"command": c.command, "dimension": c.dimension, "kind": c.kind,
                "statement": c.statement, "value": c.value, "unit": c.unit,
                "assay_context": c.assay_context, "provenance": c.provenance,
                "uncertainty": c.uncertainty, "status": c.status,
                "conflict_of": c.conflict_of}

    def to_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump({"claims": [self._claim_dict(c) for c in self.claims],
                       "fingerprint": self.fingerprint()}, f, indent=1)

    def to_csv(self, path: str) -> None:
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["claim_id", "command", "dimension", "kind", "statement", "value",
                        "unit", "tool", "source_ids", "artifact", "status", "conflict_of"])
            for c in self.claims:
                w.writerow([c.claim_id, c.command, c.dimension, c.kind, c.statement,
                            c.value or "", c.unit,
                            c.provenance.get("tool", ""),
                            "; ".join(c.provenance.get("source_ids", [])),
                            c.provenance.get("artifact", ""),
                            c.status, "; ".join(c.conflict_of)])


def make_claim(*, command: str, dimension: str, kind: str = "computed", statement: str,
               value: float | None = None, unit: str = "",
               tool: str = "", version: str = "", query: str = "", params: dict | None = None,
               source_ids: list[str] | None = None, artifact: str = "",
               assay: str = "", cell_line: str = "", concentration_nM: float | None = None,
               time_h: float | None = None, species: str = "",
               measured_source: bool = False,
               ci: tuple[float, float] | None = None, std: float | None = None) -> Claim:
    return Claim(
        command=command, dimension=dimension, kind=kind, statement=statement,
        value=value, unit=unit,
        assay_context={k: v for k, v in {"assay": assay, "cell_line": cell_line,
                                         "concentration_nM": concentration_nM,
                                         "time_h": time_h, "species": species}.items() if v},
        provenance={"tool": tool, "version": version, "query": query,
                    "params": params or {}, "source_ids": source_ids or [],
                    "artifact": artifact, "measured_source": measured_source},
        uncertainty={"ci_low": ci[0] if ci else None, "ci_high": ci[1] if ci else None,
                     "std": std, "note": ""},
    )