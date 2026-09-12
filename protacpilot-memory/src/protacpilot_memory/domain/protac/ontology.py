"""Controlled vocabularies and source-quality weights (the PROTAC ontology).

Everything here is deterministic application policy. An LLM may *propose* a
value, but these vocabularies and weights are what the system trusts.
"""

from __future__ import annotations

# ── Memory classes ───────────────────────────────────────────────────────────
MEMORY_EPISODIC = "episodic"
MEMORY_SEMANTIC = "semantic"
MEMORY_PROCEDURAL = "procedural"
MEMORY_PROSPECTIVE = "prospective"
MEMORY_NEGATIVE = "negative"
MEMORY_WORKING = "working"

MEMORY_TYPES = {
    MEMORY_EPISODIC,
    MEMORY_SEMANTIC,
    MEMORY_PROCEDURAL,
    MEMORY_PROSPECTIVE,
    MEMORY_NEGATIVE,
    MEMORY_WORKING,
}

# ── Lifecycle statuses (Master Prompt §6 / §30) ──────────────────────────────
STATUS_CANDIDATE = "candidate"
STATUS_ACTIVE = "active"
STATUS_CONSOLIDATING = "consolidating"
STATUS_CONSOLIDATED = "consolidated"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_SUPERSEDED = "superseded"
STATUS_CONTRADICTED = "contradicted"
STATUS_RETRACTED = "retracted"
STATUS_ARCHIVED = "archived"

MEMORY_STATUSES = {
    STATUS_CANDIDATE,
    STATUS_ACTIVE,
    STATUS_CONSOLIDATING,
    STATUS_CONSOLIDATED,
    STATUS_NEEDS_REVIEW,
    STATUS_SUPERSEDED,
    STATUS_CONTRADICTED,
    STATUS_RETRACTED,
    STATUS_ARCHIVED,
}

# Statuses that are legitimately retrievable.
RETRIEVABLE_STATUSES = {
    STATUS_CANDIDATE,
    STATUS_ACTIVE,
    STATUS_CONSOLIDATING,
    STATUS_CONSOLIDATED,
    STATUS_NEEDS_REVIEW,
    STATUS_CONTRADICTED,
}

# Statuses excluded from lexical indexing by retrieval queries.
SILENCED_STATUSES = {
    STATUS_SUPERSEDED,
    STATUS_RETRACTED,
    STATUS_ARCHIVED,
}

# ── Reconsolidation outcomes (Master Prompt §20) ─────────────────────────────
OUTCOME_STRENGTHEN = "STRENGTHEN"
OUTCOME_WEAKEN = "WEAKEN"
OUTCOME_REFINE_SCOPE = "REFINE_SCOPE"
OUTCOME_BRANCH = "BRANCH"
OUTCOME_SUPERSEDE = "SUPERSEDE"
OUTCOME_RETRACT = "RETRACT"
OUTCOME_NO_CHANGE = "NO_CHANGE"

RECONSOLIDATION_OUTCOMES = {
    OUTCOME_STRENGTHEN,
    OUTCOME_WEAKEN,
    OUTCOME_REFINE_SCOPE,
    OUTCOME_BRANCH,
    OUTCOME_SUPERSEDE,
    OUTCOME_RETRACT,
    OUTCOME_NO_CHANGE,
}

# ── Conflict verdicts (Master Prompt §21) ────────────────────────────────────
CONFLICT_TRUE_CONTRADICTION = "true_contradiction"
CONFLICT_CONTEXTUAL_DIFFERENCE = "contextual_difference"
CONFLICT_SCOPE_DIFFERENCE = "scope_difference"
CONFLICT_MEASUREMENT_DIFFERENCE = "measurement_difference"
CONFLICT_ASSAY_DIFFERENCE = "assay_difference"
CONFLICT_MODEL_DISAGREEMENT = "model_disagreement"
CONFLICT_COMPATIBLE = "compatible_evidence"

CONFLICT_VERDICTS = {
    CONFLICT_TRUE_CONTRADICTION,
    CONFLICT_CONTEXTUAL_DIFFERENCE,
    CONFLICT_SCOPE_DIFFERENCE,
    CONFLICT_MEASUREMENT_DIFFERENCE,
    CONFLICT_ASSAY_DIFFERENCE,
    CONFLICT_MODEL_DISAGREEMENT,
    CONFLICT_COMPATIBLE,
}

# ── Evidence hierarchy & quality weights (Master Prompt §23) ─────────────────
EVIDENCE_TYPES = {
    "internal_experiment": 1.00,
    "external_experiment": 0.95,
    "peer_reviewed_publication": 0.85,
    "curated_database": 0.75,
    "structural_observation": 0.70,
    "md_simulation": 0.50,
    "docking": 0.45,
    "simulation": 0.45,
    "ml_prediction": 0.35,
    "llm_inference": 0.15,
    "user_assertion": 0.30,
}

# Which evidence classes count as independent "kinds" for consolidation.
EXPERIMENTAL_EVIDENCE = {"internal_experiment", "external_experiment"}
COMPUTATIONAL_EVIDENCE = {
    "md_simulation", "docking", "simulation", "ml_prediction",
    "structural_observation",
}
LITERATURE_EVIDENCE = {"peer_reviewed_publication", "curated_database"}

EVIDENCE_STANCES = {"supports", "contradicts", "context"}

# ── Relation vocabulary (Master Prompt §16) ──────────────────────────────────
RELATION_TYPES = {
    "supports",
    "contradicts",
    "refines",
    "supersedes",
    "derived_from",
    "generalizes",
    "exception_to",
    "replicates",
    "failed_to_replicate",
    "caused_decision",
    "predicted",
    "observed",
    "same_context",
    "related_context",
}

# ── Entity types (Master Prompt §3E / §7) ────────────────────────────────────
ENTITY_TYPES = {
    "Target",
    "TargetDomain",
    "Protein",
    "E3Ligase",
    "Warhead",
    "E3Ligand",
    "Linker",
    "PROTAC",
    "Compound",
    "CellLine",
    "Assay",
    "Structure",
    "PDB",
    "Publication",
    "Experiment",
    "Prediction",
    "Outcome",
    "Memory",
    "Organism",
    "Tissue",
    "Model",
}

# ── Episodic event types ─────────────────────────────────────────────────────
EPISODE_EVENT_TYPES = {
    "prediction",
    "docking_experiment",
    "md_result",
    "degradation_assay",
    "permeability_assay",
    "synthesis_decision",
    "paper_observation",
    "design_choice",
    "failure",
    "user_correction",
    "outcome",
    "hypothesis",
    "experiment",
    "procedure_run",
}

# ── Replay triggers (Master Prompt §19) ──────────────────────────────────────
REPLAY_TRIGGERS = {
    "end_of_session",
    "major_experiment_imported",
    "batch_papers_imported",
    "prediction_outcome_arrived",
    "memory_conflict_detected",
    "manual",
    "scheduled",
}

# ── Event-sourcing event types (Master Prompt §39) ───────────────────────────
EVENT_ENCODED = "ENCODED"
EVENT_ENCODING_REJECTED = "ENCODING_REJECTED"
EVENT_RETRIEVED = "RETRIEVED"
EVENT_STRENGTHENED = "STRENGTHENED"
EVENT_WEAKENED = "WEAKENED"
EVENT_CONSOLIDATED = "CONSOLIDATED"
EVENT_CONFLICT_DETECTED = "CONFLICT_DETECTED"
EVENT_RECONSOLIDATED = "RECONSOLIDATED"
EVENT_SUPERSEDED = "SUPERSEDED"
EVENT_ARCHIVED = "ARCHIVED"
EVENT_DECAYED = "DECAYED"
EVENT_REVIEW_MARKED = "REVIEW_MARKED"
EVENT_STATE_CHANGED = "STATE_CHANGED"
EVENT_REPLAYED = "REPLAYED"

EVENT_TYPES = {
    EVENT_ENCODED, EVENT_ENCODING_REJECTED, EVENT_RETRIEVED, EVENT_STRENGTHENED,
    EVENT_WEAKENED, EVENT_CONSOLIDATED, EVENT_CONFLICT_DETECTED,
    EVENT_RECONSOLIDATED, EVENT_SUPERSEDED, EVENT_ARCHIVED, EVENT_DECAYED,
    EVENT_REVIEW_MARKED, EVENT_STATE_CHANGED, EVENT_REPLAYED,
}


def evidence_quality(evidence_type: str) -> float:
    return EVIDENCE_TYPES.get(evidence_type, 0.4)


def is_independent_kind(a: str, b: str) -> bool:
    """Two evidence types are independent if they belong to different kinds."""
    return _kind(a) != _kind(b)


def _kind(evidence_type: str) -> str:
    if evidence_type in EXPERIMENTAL_EVIDENCE:
        return "experimental"
    if evidence_type in COMPUTATIONAL_EVIDENCE:
        return "computational"
    if evidence_type in LITERATURE_EVIDENCE:
        return "literature"
    if evidence_type == "llm_inference":
        return "llm"
    if evidence_type == "user_assertion":
        return "user"
    return "other"
