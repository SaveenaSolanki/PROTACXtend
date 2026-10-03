"""PROTACXtend scientific data contracts.

Typed, provenance-carrying records for the controlled design flow. These are
the single source of truth for the candidate funnel, the canonical run record,
the persisted artifacts and the run page.

Design rules enforced here:

* The user's original request and the parsed fields are separate objects.
* An empty or non-canonicalisable structure can never become a usable binder,
  warhead, E3 ligand or PROTAC.
* Target and E3 identities are stored once and asserted consistent everywhere.
* A prediction is a ``Prediction`` with an explicit ``kind``; a heuristic is
  never relabelled as a measurement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


ValidationState = Literal["unvalidated", "valid", "invalid", "rejected", "hypothetical"]
PredictionKind = Literal["measured", "model", "heuristic", "unavailable"]


class ScientificRecord(BaseModel):
    """Common provenance fields for every record."""

    record_id: str = Field(default_factory=lambda: _id("rec"))
    record_type: str = ""
    source_uri: str = ""
    source_record_id: str = ""
    retrieval_date: str = Field(default_factory=_now)
    version: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)
    validation_state: ValidationState = "unvalidated"


# ── Identity ─────────────────────────────────────────────────────────

class Target(ScientificRecord):
    record_type: str = "target"
    gene_symbol: str = ""
    uniprot_id: str = ""
    protein_name: str = ""
    organism: str = "human"
    synonyms: list[str] = Field(default_factory=list)
    resolution_method: str = ""
    resolution_confidence: float = 0.0


class E3Ligase(ScientificRecord):
    record_type: str = "e3_ligase"
    gene_symbol: str = ""
    uniprot_id: str = ""
    protein_name: str = ""
    organism: str = "human"


# ── Molecules ────────────────────────────────────────────────────────

class Binder(ScientificRecord):
    record_type: str = "binder"
    name: str = ""
    target_gene: str = ""
    smiles: str = ""
    canonical_smiles: str = ""
    activity_type: str = ""
    activity_nM: Optional[float] = None
    structure_valid: bool = False
    evidence_status: str = ""
    rejection_reason: str = ""


class Warhead(ScientificRecord):
    record_type: str = "warhead"
    name: str = ""
    target_gene: str = ""
    smiles: str = ""
    canonical_smiles: str = ""
    attachment_atom_map: Optional[int] = None
    attachment_smarts: str = ""
    evidence_status: str = ""


class E3Ligand(ScientificRecord):
    record_type: str = "e3_ligand"
    name: str = ""
    e3_gene: str = ""
    smiles: str = ""
    canonical_smiles: str = ""
    attachment_atom_map: Optional[int] = None
    attachment_smarts: str = ""
    evidence_status: str = ""


class Linker(ScientificRecord):
    record_type: str = "linker"
    name: str = ""
    smiles: str = ""
    canonical_smiles: str = ""
    attachment_a_map: int = 1
    attachment_b_map: int = 2


class ProtacCandidate(ScientificRecord):
    record_type: str = "protac_candidate"
    candidate_id: str = Field(default_factory=lambda: _id("SGA"))
    target_gene: str = ""
    e3_gene: str = ""
    warhead_id: str = ""
    e3_ligand_id: str = ""
    linker_id: str = ""
    assembled_smiles: str = ""
    canonical_smiles: str = ""
    inchikey: str = ""
    formula: str = ""
    mw: Optional[float] = None
    valid: bool = False
    status: Literal["valid", "rejected", "hypothetical", "unverified"] = "unverified"
    rejection_reason: str = ""
    attachment_verified: bool = False
    structure_valid: bool = False
    evidence_sufficient: bool = False
    prediction_available: bool = False
    predictions: list["Prediction"] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    score_definitions: dict[str, str] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)


# ── Claims ───────────────────────────────────────────────────────────

class Prediction(ScientificRecord):
    record_type: str = "prediction"
    candidate_id: str = ""
    endpoint: str = ""
    value: Optional[float] = None
    unit: str = ""
    kind: PredictionKind = "unavailable"
    model_name: str = ""
    model_version: str = ""
    available: bool = False
    uncertainty: str = ""
    reason: str = ""


class Evidence(ScientificRecord):
    record_type: str = "evidence"
    evidence_kind: str = ""          # measured | retrieved | calculated | predicted | missing
    claim: str = ""
    source: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    canonical_smiles: str = ""


class Decision(ScientificRecord):
    record_type: str = "decision"
    stage: str = ""
    decision_type: str = ""          # continue | stop | abstain | reject | accept | retry
    reason: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    next_stage: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class Artifact(ScientificRecord):
    record_type: str = "artifact"
    path: str = ""
    kind: str = ""
    created_at: str = Field(default_factory=_now)
    final: bool = True
    sha256: str = ""
    bytes: int = 0


# ── Request (raw vs parsed) ──────────────────────────────────────────

class RequestParse(BaseModel):
    """Original text and parsed fields, kept strictly separate."""

    raw_request: str = ""
    normalized_request: str = ""
    target: str = ""
    e3_ligase: str = ""
    target_role_token: str = ""
    malformed_tokens: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    requires_clarification: bool = False
    clarification_question: str = ""
    parsed_fields: dict[str, Any] = Field(default_factory=dict)


# ── Funnel ───────────────────────────────────────────────────────────

class CandidateFunnel(BaseModel):
    """Denominator-aware counts for the whole flow."""

    components_retrieved: int = 0
    binders_retrieved_total: int = 0
    binders_rejected_missing_structure: int = 0
    binders_rejected_missing_identity: int = 0
    binders_target_mismatch: int = 0
    binders_usable_total: int = 0
    warheads_selected: int = 0
    e3_ligands_selected: int = 0
    linkers_selected: int = 0
    construction_attempts: int = 0
    enumerated_structures: int = 0
    sanitized_molecules: int = 0
    unique_products: int = 0
    filtered_products: int = 0
    ranked_candidates: int = 0

    def reconcile(self) -> list[str]:
        """Return human-readable reconciliation notes (empty when consistent)."""
        notes: list[str] = []
        retrieved = self.binders_retrieved_total
        partition = (self.binders_rejected_missing_structure
                     + self.binders_rejected_missing_identity
                     + self.binders_target_mismatch
                     + self.binders_usable_total)
        if retrieved != partition:
            notes.append(
                f"binder partition mismatch: retrieved={retrieved} but "
                f"rejected_structure+rejected_identity+mismatch+usable={partition}")
        if self.sanitized_molecules > self.enumerated_structures:
            notes.append("sanitized_molecules exceeds enumerated_structures")
        if self.unique_products > self.sanitized_molecules:
            notes.append("unique_products exceeds sanitized_molecules")
        if self.ranked_candidates > self.filtered_products:
            notes.append("ranked_candidates exceeds filtered_products")
        return notes


class CanonicalRunRecord(BaseModel):
    """One canonical record every artifact and the UI read from."""

    run_id: str = Field(default_factory=lambda: _id("run"))
    created_at: str = Field(default_factory=_now)
    schema_version: str = "protacxtend.contracts.v1"
    request: RequestParse = Field(default_factory=RequestParse)
    target: Optional[Target] = None
    e3_ligase: Optional[E3Ligase] = None
    binders: list[Binder] = Field(default_factory=list)
    warheads: list[Warhead] = Field(default_factory=list)
    e3_ligands: list[E3Ligand] = Field(default_factory=list)
    linkers: list[Linker] = Field(default_factory=list)
    candidates: list[ProtacCandidate] = Field(default_factory=list)
    predictions: list[Prediction] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    funnel: CandidateFunnel = Field(default_factory=CandidateFunnel)
    status: Literal["VALID DESIGN", "DESIGN BRIEF ONLY", "INVALID RUN", "ABSTAINED"] = "INVALID RUN"
    #: What kind of result this is — never conflate a known-compound
    #: reconstruction with a genuine new candidate.
    classification: Literal[
        "KNOWN_COMPOUND_RECONSTRUCTION", "NEW_CANDIDATE", "DESIGN_BRIEF",
        "ABSTENTION", "INVALID_RUN",
    ] = "INVALID_RUN"
    #: Three independent gates, always reported separately.
    structure_valid: bool = False
    evidence_sufficient: bool = False
    prediction_available: bool = False
    status_reason: str = ""
    stages: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    consistency_notes: list[str] = Field(default_factory=list)
    next_experiment: str = ""

    def identity_summary(self) -> dict[str, str]:
        return {
            "target": self.target.gene_symbol if self.target else "",
            "target_uniprot": self.target.uniprot_id if self.target else "",
            "e3": self.e3_ligase.gene_symbol if self.e3_ligase else "",
            "e3_uniprot": self.e3_ligase.uniprot_id if self.e3_ligase else "",
        }


ProtacCandidate.model_rebuild()
