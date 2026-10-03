"""Workflow graph for PROTACXtend.

The graph uses LangGraph when installed. In minimal environments, the same node
order is executed by ``LocalSynGlueWorkflowGraph``.
"""

from __future__ import annotations

import time
from typing import Callable, Iterable, List, Optional, Tuple

# ── Live progress hook ───────────────────────────────────────────────
# The TUI bridge registers a callback so each graph node reports start/done
# as it runs; without it a multi-minute run shows nothing until it finishes.
ProgressCallback = Callable[[str, str, float, int, int], None]
_progress_callback: Optional[ProgressCallback] = None


def set_progress_callback(callback: Optional[ProgressCallback]) -> None:
    """Register (or clear) the live per-node progress callback."""
    global _progress_callback
    _progress_callback = callback


def _notify_progress(stage: str, status: str, elapsed_s: float,
                     index: int, total: int) -> None:
    cb = _progress_callback
    if cb is None:
        return
    try:
        cb(stage, status, elapsed_s, index, total)
    except Exception:  # progress must never break a run
        pass

from protacxtend.agents.active_learning_agent import ActiveLearningAgent
from protacxtend.agents.admet_agent import ADMETAgent
from protacxtend.agents.binder_agent import TargetBinderRetrievalAgent
from protacxtend.agents.construction_agent import (
    CandidateValidationAgent,
    MolecularConstructionAgent,
)
from protacxtend.agents.context_agent import CellContextAgent
from protacxtend.agents.cooperativity_agent import (
    CooperativityPredictionAgent,
    HookEffectPredictionAgent,
)
from protacxtend.agents.base_agent import ReActAgent
from protacxtend.agents.answer_agent import KnowledgeAnswerAgent, ReasoningAnswerAgent
from protacxtend.agents.design_path_agent import DesignPathAgent
from protacxtend.agents.design_planner_agent import DesignPlannerAgent
from protacxtend.agents.e3_agent import E3LigandSelectionAgent
from protacxtend.agents.evolution_agent import EvolutionRefinementAgent
from protacxtend.agents.exit_vector_agent import ExitVectorDetectionAgent
from protacxtend.agents.linker_agent import LinkerGenerationAgent
from protacxtend.agents.novelty_agent import NoveltyAgent
from protacxtend.agents.prediction_agent import (
    ApplicabilityDomainAgent,
    DegradationPredictionAgent,
)
from protacxtend.agents.proximity_agent import ProximityDiversityAgent
from protacxtend.agents.ranking_agent import RankingAgent
from protacxtend.agents.reflection_agent import ReflectionReviewAgent
from protacxtend.agents.report_agent import ReportAgent
from protacxtend.agents.safety_agent import SafetyAgent
from protacxtend.agents.search_control_agent import (
    CheapFilterAgent,
    ControlledSearchAgent,
    ExpensiveModelingSelectionAgent,
    StereochemistryEnumerationAgent,
)
from protacxtend.agents.supervisor_agent import SupervisorAgent
from protacxtend.agents.target_agent import TargetResolverAgent
from protacxtend.agents.ternary_agent import TernaryFeasibilityAgent
from protacxtend.backend.schemas import WorkflowState
from protacxtend.tools.memory_manager import write_workflow_memory
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox

Node = tuple[str, Callable[[WorkflowState], WorkflowState]]

#: Capability-aware routing. A KNOW question must not run the 31-node design
#: pipeline; it runs the retrieval/report subset. ``evolution_refinement`` (the
#: dominant wall-clock cost) is excluded from every routine route and only runs
#: when explicitly requested via the full node list.
CAPABILITY_NODES: dict[str, list[str]] = {
    "KNOW": [
        "parse_user_request", "create_design_plan", "control_np_hard_search",
        "safety_precheck", "resolve_target", "retrieve_target_binders",
        "select_warheads", "select_e3_ligands", "capability_answer",
        "generate_report", "update_memory",
    ],
    "REASON": [
        "parse_user_request", "create_design_plan", "control_np_hard_search",
        "safety_precheck", "resolve_target", "retrieve_target_binders",
        "select_warheads", "select_e3_ligands", "detect_exit_vectors",
        "optional_ternary_feasibility", "predict_cooperativity", "predict_hook_effect",
        "reasoning_answer", "generate_report", "update_memory",
    ],
    "DESIGN": [
        "parse_user_request", "create_design_plan", "control_np_hard_search",
        "safety_precheck", "resolve_target", "retrieve_target_binders",
        "design_path",
        "select_warheads", "select_e3_ligands", "detect_exit_vectors",
        "generate_linkers", "construct_protacs", "expand_stereoisomers",
        "validate_protacs", "score_cell_context", "predict_admet", "check_novelty",
        "assess_applicability_domain", "cheap_filter_candidates", "predict_degradation",
        "initial_ranking", "diversity_clustering", "reflection_review",
        "optional_ternary_feasibility", "predict_cooperativity", "predict_hook_effect",
        "final_ranking", "generate_report", "update_memory",
    ],
    "DISCOVER": [
        "parse_user_request", "create_design_plan", "safety_precheck", "resolve_target",
        "select_e3_ligands", "assess_applicability_domain", "predict_degradation",
        "initial_ranking", "diversity_clustering", "reflection_review",
        "optional_ternary_feasibility", "predict_cooperativity", "predict_hook_effect",
        "final_ranking", "generate_report", "update_memory",
    ],
}


class MemoryUpdateAgent:
    name = "MemoryUpdateAgent"

    def run(self, state: WorkflowState) -> WorkflowState:
        update = write_workflow_memory(state)
        ProtacDesignToolbox().add_trace(
            state,
            self.name,
            "Persist reproducible workflow summary to local memory.",
            "update_memory",
            f"memory_path={update.get('path')}",
            0.0,
        )
        return state


class LocalSynGlueWorkflowGraph:
    """Deterministic state-machine fallback."""

    def __init__(self):
        self.nodes: list[Node] = [
            ("parse_user_request", SupervisorAgent().run),
            ("create_design_plan", DesignPlannerAgent().run),
            ("control_np_hard_search", ControlledSearchAgent().run),
            ("safety_precheck", SafetyAgent().run),
            ("resolve_target", TargetResolverAgent().run),
            ("retrieve_target_binders", TargetBinderRetrievalAgent().run),
            ("design_path", DesignPathAgent().run),
            ("select_warheads", WarheadSelectionAgent().run),
            ("select_e3_ligands", E3LigandSelectionAgent().run),
            ("detect_exit_vectors", ExitVectorDetectionAgent().run),
            ("generate_linkers", LinkerGenerationAgent().run),
            ("construct_protacs", MolecularConstructionAgent().run),
            ("expand_stereoisomers", StereochemistryEnumerationAgent().run),
            ("validate_protacs", CandidateValidationAgent().run),
            ("score_cell_context", CellContextAgent().run),
            ("predict_admet", ADMETAgent().run),
            ("check_novelty", NoveltyAgent().run),
            ("assess_applicability_domain", ApplicabilityDomainAgent().run),
            ("cheap_filter_candidates", CheapFilterAgent().run),
            ("predict_degradation", DegradationPredictionAgent().run),
            ("initial_ranking", RankingAgent(final=False).run),
            ("diversity_clustering", ProximityDiversityAgent().run),
            ("reflection_review", ReflectionReviewAgent().run),
            ("evolution_refinement", EvolutionRefinementAgent().run),
            ("select_expensive_modeling_finalists", ExpensiveModelingSelectionAgent().run),
            ("optional_ternary_feasibility", TernaryFeasibilityAgent().run),
            ("predict_cooperativity", CooperativityPredictionAgent().run),
            ("predict_hook_effect", HookEffectPredictionAgent().run),
            ("final_ranking", RankingAgent(final=True).run),
            ("active_learning_update", ActiveLearningAgent().run),
            ("capability_answer", KnowledgeAnswerAgent().run),
            ("reasoning_answer", ReasoningAnswerAgent().run),
            ("generate_report", ReportAgent().run),
            ("update_memory", MemoryUpdateAgent().run),
        ]

    def run(self, user_request: str | WorkflowState, *, capability: str = "",
            trace: list | None = None,
            route: list[str] | None = None) -> WorkflowState:
        state = user_request if isinstance(user_request, WorkflowState) else WorkflowState(user_request=user_request)
        nodes = self.nodes
        if route is not None:
            wanted = list(route)
            nodes = [(n, f) for n, f in self.nodes if n in wanted]
        elif capability:
            wanted = set(CAPABILITY_NODES.get(capability.upper(), []))
            nodes = [(n, f) for n, f in self.nodes if n in wanted]
        cap = capability.upper() if capability else ""
        # Route capability must reach the stop policy even before the planner
        # runs: KNOW/REASON/DISCOVER questions can be answerable without a
        # resolvable design target (their answer agents decide abstention).
        if cap in ("KNOW", "REASON", "DISCOVER"):
            sp = state.design_plan.setdefault("structured_seed", {})
            if isinstance(sp, dict):
                sp["capability"] = cap
        retry_counts: dict[str, int] = {}
        total_nodes = len(nodes)
        for node_index, (node_name, node) in enumerate(nodes):
            _notify_progress(node_name, "start", 0.0, node_index, total_nodes)
            started = time.time()
            state = node(state)
            elapsed = round(time.time() - started, 4)
            _notify_progress(node_name, "done", elapsed, node_index, total_nodes)
            if trace is not None:
                trace.append({"node": node_name, "s": elapsed,
                              "error": (state.errors[-1] if state.errors else "")})
            if self._should_retry(node_name, state, retry_counts):
                retry_counts[node_name] = retry_counts.get(node_name, 0) + 1
                state.warnings.append(f"Planner retry policy repeated step: {node_name}")
                _notify_progress(node_name, "retry", 0.0, node_index, total_nodes)
                retry_started = time.time()
                state = node(state)
                _notify_progress(node_name, "done", round(time.time() - retry_started, 4),
                                 node_index, total_nodes)
                if trace is not None:
                    trace.append({"node": node_name, "s": round(time.time() - retry_started, 4),
                                  "error": (state.errors[-1] if state.errors else ""),
                                  "retry": True})
            if self._should_stop(state):
                break
        if trace is not None:
            state.pipeline_status.append({"retry_counts": dict(retry_counts)})
        return state

    def _should_stop(self, state: WorkflowState) -> bool:
        if state.design_plan.get("status") == "needs_user_input":
            return True
        capability = str((state.design_plan.get("structured_seed") or {}).get("capability", "")).upper()
        terminal_errors = [
            "Planner requires a target protein/gene",
            # A target that cannot be verified must abort the run: continuing
            # with no (or a mis-resolved) target previously produced candidates
            # labelled with an unrelated protein while using wrong warheads.
            "TargetResolverAgent: Could not resolve",
            "TargetResolverAgent: No target name provided",
            "No warheads selected",
            "No E3 ligands selected",
            "No PROTAC candidates assembled",
            "No valid or unverified candidates",
        ]
        if capability in {"KNOW", "REASON", "DISCOVER"}:
            # A KNOW/REASON/DISCOVER question can be answerable without a
            # resolvable design target (e.g. a SMILES characterization, a
            # supplied-list diff, or a supplied ranking table); the answer
            # agent decides whether to abstain. Design-terminal markers
            # (no target gene / warheads / E3 / candidates) do not block the
            # retrieval/evidence nodes from producing grounded content.
            terminal_errors = [
                e for e in terminal_errors
                if e not in {
                    "TargetResolverAgent: Could not resolve",
                    "TargetResolverAgent: No target name provided",
                    "Planner requires a target protein/gene",
                    "No warheads selected",
                    "No E3 ligands selected",
                    "No PROTAC candidates assembled",
                    "No valid or unverified candidates",
                }
            ]
        elif capability == "DESIGN":
            seed = state.design_plan.get("structured_seed") or {}
            if seed.get("warhead_supplied") or seed.get("e3_ligand_supplied"):
                # Supplied components with no target still produce a design
                # brief; do not abort before the design-path node runs.
                terminal_errors = [
                    e for e in terminal_errors
                    if e not in {"TargetResolverAgent: Could not resolve",
                                 "TargetResolverAgent: No target name provided"}
                ]
        return any(any(marker in error for marker in terminal_errors) for error in state.errors)

    def _should_retry(self, node_name: str, state: WorkflowState, retry_counts: dict[str, int]) -> bool:
        plan = state.design_plan or {}
        retry_policy = plan.get("repeat_policy", {})
        retryable_steps = set(retry_policy.get("retryable_steps", []))
        max_retries = int(retry_policy.get("max_retries_per_step", 0) or 0)
        if node_name not in retryable_steps or retry_counts.get(node_name, 0) >= max_retries:
            return False
        return self._step_output_missing(node_name, state)

    def _step_output_missing(self, node_name: str, state: WorkflowState) -> bool:
        if node_name == "resolve_target":
            return state.target_record is None
        if node_name == "retrieve_target_binders":
            return not state.parsed_objective.warhead_smiles and not state.retrieved_binders
        if node_name == "predict_degradation":
            return bool(state.valid_candidates) and not state.degradation_predictions
        if node_name == "predict_admet":
            return bool(state.valid_candidates) and not state.admet_predictions
        if node_name == "optional_ternary_feasibility":
            return bool(state.parsed_objective.use_structure_aware_ranking and state.ranking_results and not state.ternary_feasibility_results)
        return False


def build_langgraph_workflow():
    """Build a LangGraph StateGraph if LangGraph is installed."""

    try:  # pragma: no cover - optional dependency.
        from langgraph.graph import END, StateGraph
    except Exception:  # pragma: no cover - default in local tests.
        return None

    local = LocalSynGlueWorkflowGraph()
    graph = StateGraph(WorkflowState)
    ordered = [name for name, _ in local.nodes]
    total = len(ordered)
    # Wrap every node so the LangGraph path emits the same live progress as the
    # local graph; otherwise a deterministic run is silent for minutes.
    for index, (name, node) in enumerate(local.nodes):
        def _wrapped(state, _name=name, _node=node, _i=index, _total=total):
            _notify_progress(_name, "start", 0.0, _i, _total)
            started = time.time()
            result = _node(state)
            _notify_progress(_name, "done", round(time.time() - started, 4), _i, _total)
            return result
        graph.add_node(name, _wrapped)
    graph.set_entry_point(ordered[0])
    for current, nxt in zip(ordered, ordered[1:]):
        graph.add_edge(current, nxt)
    graph.add_edge(ordered[-1], END)
    return graph.compile()


def get_workflow_graph():
    return build_langgraph_workflow() or LocalSynGlueWorkflowGraph()


def run_syn_glue_workflow(user_request: str | WorkflowState = "", *, state: WorkflowState | None = None,
                         capability: str = "", trace: list | None = None,
                         route: list[str] | None = None) -> WorkflowState:
    seeded = state if state is not None else user_request
    # Capability routing, explicit routes and per-node tracing require the
    # deterministic local graph: the compiled LangGraph runs the full node list
    # and cannot filter.
    if not capability and not route and trace is None:
        graph = get_workflow_graph()
        if hasattr(graph, "invoke"):  # LangGraph compiled graph.
            initial = seeded if isinstance(seeded, WorkflowState) else WorkflowState(user_request=str(seeded))
            result = graph.invoke(initial)
            return result if isinstance(result, WorkflowState) else WorkflowState(**result)
    return LocalSynGlueWorkflowGraph().run(seeded, capability=capability, trace=trace, route=route)


from protacxtend.agents.warhead_agent import WarheadSelectionAgent  # noqa: E402
