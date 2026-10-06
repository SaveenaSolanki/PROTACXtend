"""PROTACXTEND_AGENTIC_ARCHITECTURE_V1.

Canonical state, evidence ontology, independent critic and adaptive coordinator.
Extends the existing ``protacxtend.canonical`` stack rather than replacing it.
"""
from protacxtend.architecture.state import (
    ARCHITECTURE_VERSION, STATE_SCHEMA_VERSION, EVIDENCE_SCHEMA_VERSION,
    TRACE_SCHEMA_VERSION, TerminalStatus, TherapeuticHypothesisState,
)
from protacxtend.architecture.ontology import (
    EvidenceKind, EvidenceStatus, EvidenceRecordV1, Claim, Contradiction,
    Disagreement, UncertaintyAxis, ScientificAxisProfile,
)
from protacxtend.architecture.critic import ScientificCritic, CriticVerdictV1
from protacxtend.architecture.coordinator import (
    AdaptiveCoordinator, CoordinatorDecision, DecisionType,
)

__all__ = [
    "ARCHITECTURE_VERSION", "STATE_SCHEMA_VERSION", "EVIDENCE_SCHEMA_VERSION",
    "TRACE_SCHEMA_VERSION", "TerminalStatus", "TherapeuticHypothesisState",
    "EvidenceKind", "EvidenceStatus", "EvidenceRecordV1", "Claim", "Contradiction",
    "Disagreement", "UncertaintyAxis", "ScientificAxisProfile",
    "ScientificCritic", "CriticVerdictV1", "AdaptiveCoordinator",
    "CoordinatorDecision", "DecisionType",
]
