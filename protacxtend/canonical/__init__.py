"""Canonical PROTACXtend execution stack.

One control plane:

    Scientific Request Parser
      -> Orchestrator
      -> Task Graph
      -> Specialized Scientific Modules (9)
      -> Tool Executor
      -> Evidence Store
      -> Critic / Verifier
      -> Decision Engine
      -> TherapeuticStrategy

The historical stacks (``protacxtend.agents.graph`` and
``protacxtend.agents.agentic_core``) are execution engines reached through the
Tool Executor, not parallel entry points. The legacy seven-layer
``protacxtend.agentic`` package is deprecated.
"""

from protacxtend.canonical.critic import CriticVerifier
from protacxtend.canonical.critics import (
    BaseCritic,
    EvidenceCritic,
    MechanismCritic,
    ReproducibilityCritic,
    default_critics,
)
from protacxtend.canonical.decision import DecisionEngine
from protacxtend.canonical.evidence import CanonicalEvidenceStore
from protacxtend.canonical.failures import (
    CriticResult,
    Failure,
    FailureClass,
    classify_failure,
    failure_taxonomy,
    make_failure,
)
from protacxtend.canonical.modules import (
    MODULE_CLASSES,
    CanonicalState,
    ModuleContext,
    ScientificModule,
    canonical_modules,
    module_dependencies,
)
from protacxtend.canonical.orchestrator import CanonicalOrchestrator, run_canonical
from protacxtend.canonical.policy import (
    ExecutionPolicy,
    PolicyAction,
    PolicyDecision,
    RetryPolicy,
    policy_from_config,
)
from protacxtend.canonical.request_parser import ScientificRequestParser
from protacxtend.canonical.schemas import (
    SCIENTIFIC_MODULE_ORDER,
    STRATEGY_SCHEMA_VERSION,
    ADMERisk,
    BinaryStructureAssessment,
    Biomarker,
    CanonicalRunResult,
    CombinationStrategy,
    Contradiction,
    CriticVerdict,
    DegradationPredictionSummary,
    E3Recommendation,
    EvidenceBundle,
    ExperimentalPlan,
    ExperimentalPlanStep,
    GoNoGoCriterion,
    ModuleResult,
    ResistanceMechanism,
    RunManifest,
    SafetyRisk,
    ScientificModuleId,
    ScientificRequest,
    TargetValidation,
    TaskGraphSpec,
    TaskNodeSpec,
    TaskStatus,
    TernaryComplexAssessment,
    TherapeuticStrategy,
    TPDTractabilityAssessment,
    UncertaintyDecomposition,
)
from protacxtend.canonical.task_graph import TaskGraph, TaskGraphExecutor
from protacxtend.canonical.tool_executor import ToolExecutionError, ToolExecutor

__all__ = [
    "ADMERisk",
    "BaseCritic",
    "BinaryStructureAssessment",
    "Biomarker",
    "CanonicalEvidenceStore",
    "CanonicalOrchestrator",
    "CanonicalRunResult",
    "CanonicalState",
    "CombinationStrategy",
    "Contradiction",
    "CriticResult",
    "CriticVerdict",
    "CriticVerifier",
    "DecisionEngine",
    "DegradationPredictionSummary",
    "E3Recommendation",
    "EvidenceBundle",
    "EvidenceCritic",
    "ExecutionPolicy",
    "ExperimentalPlan",
    "ExperimentalPlanStep",
    "Failure",
    "FailureClass",
    "GoNoGoCriterion",
    "MechanismCritic",
    "MODULE_CLASSES",
    "ModuleContext",
    "ModuleResult",
    "PolicyAction",
    "PolicyDecision",
    "ReproducibilityCritic",
    "ResistanceMechanism",
    "RetryPolicy",
    "RunManifest",
    "SCIENTIFIC_MODULE_ORDER",
    "STRATEGY_SCHEMA_VERSION",
    "SafetyRisk",
    "ScientificModule",
    "ScientificModuleId",
    "ScientificRequest",
    "ScientificRequestParser",
    "TPDTractabilityAssessment",
    "TargetValidation",
    "TaskGraph",
    "TaskGraphExecutor",
    "TaskGraphSpec",
    "TaskNodeSpec",
    "TaskStatus",
    "TernaryComplexAssessment",
    "TherapeuticStrategy",
    "ToolExecutionError",
    "ToolExecutor",
    "UncertaintyDecomposition",
    "canonical_modules",
    "classify_failure",
    "default_critics",
    "failure_taxonomy",
    "make_failure",
    "module_dependencies",
    "policy_from_config",
    "run_canonical",
]
