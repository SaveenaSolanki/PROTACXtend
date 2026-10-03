"""Shared structured request model for all PROTACxtend research commands.

Design rules (per the request-understanding rebuild):
- raw text is always preserved alongside parsed fields;
- target mentions are parsed separately from intent, and E3 requests
  distinguish ``explicit`` (\"use CRBN\") from ``delegated``
  (\"find a suitable E3\") from ``unspecified``;
- resolution status is tool-set (verified/tentative/ambiguous/unknown)
  and never inferred by the model; fuzzy matches are suggestions only;
- corrections are state transitions logged before/after.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

RESEARCH_ACTIONS = (
    "plan", "investigate", "reason", "compare", "design", "optimize", "structure",
    "selectivity", "degradation", "admet", "synthesis", "experiment", "evidence", "run",
)

#: Named E3 recruiters that count as an explicit preference (never the bare word "E3").
NAMED_E3 = {
    "CRBN", "VHL", "MDM2", "KEAP1", "XIAP", "CIAP1", "CIAP2", "DCAF1", "DCAF11",
    "DCAF15", "DCAF16", "KLHDC2", "FEM1B", "RNF4", "RNF114", "RNF126", "FBXO22",
    "GID4", "SKP1", "UBR7", "TRIM21", "TRIM24", "AHRLIGAN", "CUL4A", "SPOP", "DDB1",
}
#: Delegation signals: \"suitable E3\", \"find an E3\", etc. -> research task, never a question.
E3_DELEGATION_WORDS = ("suitable", "appropriate", "find", "choose", "evaluate", "select",
                       "optimal", "best", "candidate", "which", "screen", "discover")
#: Workflow-action mapping for the TUI research commands.
COMMAND_ACTIONS = {
    "plan": "plan", "investigate": "investigate", "reason": "reason", "compare": "compare",
    "design": "design", "optimize": "optimize", "structure": "structure",
    "selectivity": "selectivity", "degradation": "degradation", "admet": "admet",
    "synthesis": "synthesis", "experiment": "experiment", "evidence": "evidence", "run": "run",
}
#: Genuinely ambiguous short names the resolver must never silently convert offline.
AMBIGUOUS_MAP: dict[str, list[str]] = {
    "BRD": ["BRD2", "BRD3", "BRD4"],
    "MAPK": ["MAPK1", "MAPK3"],
    "JAK": ["JAK1", "JAK2", "JAK3"],
    "EGFR1": ["EGFR", "ERBB3"],
}

MUTATION_RE = __import__("re").compile(r"\b([A-Z]{1,2}\d{2,4}[A-Z]?(?:del|ins|dup)?)\b")


@dataclass
class TargetResolution:
    """Tool-set identity for one target mention. Never model-inferred."""

    symbol: str = ""                 # canonical gene symbol
    uniprot_id: str = ""
    organism: str = ""               # scientific name
    organism_taxid: int = 0
    matched_name: str = ""           # name/label matched by the resolver
    match_type: str = ""             # accession | exact_symbol | alias | protein_name | fuzzy | none
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    source_url: str = ""
    resolver_source: str = "none"    # curated_table | uniprot_live | uniprot_cache | none
    status: str = "unresolved"       # verified | tentative | ambiguous | unknown | unresolved
    confidence: float = 0.0
    suggestion: str = ""              # single fuzzy suggestion (never auto-applied)

    def canonical_id(self) -> str:
        return self.uniprot_id or self.symbol


@dataclass
class TargetMention:
    raw: str = ""
    entity_kind: str = "symbol"      # accession | symbol | alias | protein_name | unknown
    organism: str = "Homo sapiens"
    mutation: str = ""               # e.g. G12C (parsed, not part of identity)
    isoform: str = ""                # e.g. isoform 2 (if explicitly stated)
    resolution: Optional[TargetResolution] = None


@dataclass
class E3Request:
    mode: str = "unspecified"        # explicit | delegated | unspecified
    named_e3: str = ""               # set when explicit


@dataclass
class Clarification:
    pending: bool = False
    question: str = ""
    candidates: list[str] = field(default_factory=list)
    for_field: str = ""              # target | e3 | organism | other


@dataclass
class RequestUnderstanding:
    """Full structured parse of the current utterance + relevant state."""

    raw_text: str = ""
    action: str = "plan"             # one of RESEARCH_ACTIONS
    intent: str = "plan_protac_strategy"
    target_mentions: list[TargetMention] = field(default_factory=list)
    primary_target: Optional[TargetResolution] = None
    organism: str = "Homo sapiens"
    disease_context: str = ""
    cell_line: str = ""
    mutation: str = ""
    isoform: str = ""
    e3: E3Request = field(default_factory=E3Request)
    supplied_ligands: dict[str, str] = field(default_factory=dict)  # warhead_smiles/e3_ligand_smiles/linker_smiles
    constraints: dict[str, Any] = field(default_factory=dict)
    delegated_choices: list[str] = field(default_factory=list)      # e.g. ["e3_selection"]
    clarification: Clarification = field(default_factory=Clarification)
    assumptions: list[str] = field(default_factory=list)
    state_before: Optional[dict[str, Any]] = None   # correction log
    state_after: Optional[dict[str, Any]] = None
    warnings: list[str] = field(default_factory=list)

    def to_snapshot(self) -> dict[str, Any]:
        """Serializable state snapshot (used for before/after logs and tests)."""
        target = None
        if self.primary_target:
            target = {
                "symbol": self.primary_target.symbol,
                "uniprot_id": self.primary_target.uniprot_id,
                "organism": self.primary_target.organism,
                "match_type": self.primary_target.match_type,
                "resolver_source": self.primary_target.resolver_source,
                "status": self.primary_target.status,
                "alternatives": self.primary_target.alternatives,
            }
        return {
            "action": self.action,
            "intent": self.intent,
            "raw_text": self.raw_text,
            "target": target,
            "mentions": [m.raw for m in self.target_mentions],
            "organism": self.organism,
            "disease_context": self.disease_context,
            "mutation": self.mutation,
            "isoform": self.isoform,
            "e3": {"mode": self.e3.mode, "named_e3": self.e3.named_e3},
            "supplied_ligands": self.supplied_ligands,
            "delegated_choices": self.delegated_choices,
            "clarification_pending": self.clarification.pending,
            "assumptions": self.assumptions,
        }


@dataclass
class EvidenceStage:
    step: str = ""
    label: str = "computational"     # observed | computational | missing
    summary: str = ""
    evidence: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class PlanDocument:
    """Traceable plan: interpretation + evidence stages + decisions."""

    understanding: Optional[RequestUnderstanding] = None
    interpretation_line: str = ""
    stages: list[EvidenceStage] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    status: str = "plan_ready"       # plan_ready | plan_with_limitation | clarification_needed
    abstain_e3_recommendation: bool = False
    provenance: list[str] = field(default_factory=list)

    def stages_by_step(self) -> dict[str, EvidenceStage]:
        return {s.step: s for s in self.stages}