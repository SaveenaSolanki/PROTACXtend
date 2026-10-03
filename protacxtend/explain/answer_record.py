"""Typed researcher-facing explanation answer.

One answer record per run. It is generated from the *completed route and
persisted records* (run.json, evidence.jsonl, provenance.json, strategy) by
``builder.py`` — never from display-layer text. The display layer only renders
this record.

The causal chain marks each step as one of:
    measured | computed | hypothesized | unavailable
with a ``measurement_context`` ("in_this_run" | "literature" | None) so that
published assay evidence (e.g., MZ1 DC50/Dmax from PROTAC-DB) is visibly
distinguished from measurements made inside this run. Downstream activity is
never inferred from chemical validity or a ranking score: biology steps stay
``hypothesized``/``unavailable`` unless the run record carries direct evidence.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "ExplanationAnswer.v1"

StepState = Literal["measured", "computed", "hypothesized", "unavailable"]
Mode = Literal["KNOW", "REASON", "DESIGN", "DISCOVER"]
RenderStatus = Literal["ok", "comparison_only", "invalid_error", "error"]
ScientificOutcome = Literal[
    "reference_reconstruction", "distinct_candidate", "design_brief", "abstention",
    "conflicting_evidence", "missing_evidence", "comparison_only", "invalid", "unassessed",
]


class EstablishedFact(BaseModel):
    claim: str
    evidence_kind: Literal["measured", "computed", "calculated", "retrieved", "heuristic", "missing"] = "retrieved"
    validation_state: str = "valid"
    source: str = ""                       # human-readable source w/ DOI/PDB/DB
    evidence_refs: list[str] = Field(default_factory=list)   # accessions/DOIs/PDB ids
    artifact_paths: list[str] = Field(default_factory=list)  # exact persisted files
    source_run_id: str = ""


class CausalStep(BaseModel):
    step: Literal["binding", "ternary_formation", "ubiquitination", "degradation"]
    title: str
    state: StepState
    measurement_context: Optional[Literal["in_this_run", "literature"]] = None
    detail: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    #: Exact-evidence audit against the tested molecule, protein domain or
    #: isoform, assay, cell context, time, metric, unit, and source record.
    #: Empty strings = "not in run record"; measured_in_this_run separates
    #: values taken from the run itself vs values taken from cited literature.
    exact_evidence: dict[str, Any] = Field(default_factory=dict)
    measured_in_this_run: bool = False


class FactBox(BaseModel):
    direct_answer: str = ""
    established_facts: list[EstablishedFact] = Field(default_factory=list)
    mechanistic_interpretation: dict[str, Any] = Field(
        default_factory=lambda: {"causal_chain": [], "assumptions": []})
    missing_links: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    next_discriminating_experiment: dict[str, Any] = Field(default_factory=dict)


class DesignBlock(BaseModel):
    target: str = ""
    target_identity: str = ""
    e3: str = ""
    e3_identity: str = ""
    full_product: Optional[str] = None          # SMILES when a product exists
    product_identity: Optional[str] = None      # InChIKey when computable
    missing_input_brief: Optional[str] = None   # exact missing-input design brief
    component_provenance: list[dict[str, Any]] = Field(default_factory=list)
    attachment_provenance: list[dict[str, Any]] = Field(default_factory=list)
    funnel: dict[str, int] = Field(default_factory=dict)
    outcome_class: Literal["reference_reconstruction", "distinct_candidate",
                           "design_brief", "abstention", "unassessed"] = "unassessed"


class ExplanationAnswer(BaseModel):
    """Renderer status and scientific outcome are deliberately separate:
    ``render_status`` says whether this explanation could be rendered from the
    persisted record; ``scientific_outcome`` says what the run scientifically
    produced (or did not). A successfully rendered design brief therefore has
    render_status="ok" with scientific_outcome="design_brief" — never a
    completed design."""
    schema_version: str = SCHEMA_VERSION
    run_id: str
    mode: Mode
    render_status: RenderStatus = "ok"
    scientific_outcome: ScientificOutcome = "unassessed"
    question: str = ""
    facts: FactBox = Field(default_factory=FactBox)
    design: Optional[DesignBlock] = None
    provenance: dict[str, Any] = Field(default_factory=dict)  # mode, artifact IDs, files
    citation_claim: str = ""

    @property
    def status(self) -> str:
        """Backward-compatible alias of render_status."""
        return self.render_status