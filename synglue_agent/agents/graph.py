"""Workflow graph for SynGlue-Agent.

The graph uses LangGraph when installed. In minimal environments, the same node
order is executed by ``LocalSynGlueWorkflowGraph``.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Tuple

from synglue_agent.agents.active_learning_agent import ActiveLearningAgent
from synglue_agent.agents.admet_agent import ADMETAgent
from synglue_agent.agents.binder_agent import TargetBinderRetrievalAgent
from synglue_agent.agents.context_agent import CellContextAgent
from synglue_agent.agents.cooperativity_agent import CooperativityPredictionAgent, HookEffectPredictionAgent
from synglue_agent.agents.construction_agent import CandidateValidationAgent, MolecularConstructionAgent
from synglue_agent.agents.design_planner_agent import DesignPlannerAgent
from synglue_agent.agents.e3_agent import E3LigandSelectionAgent
from synglue_agent.agents.evolution_agent import EvolutionRefinementAgent
from synglue_agent.agents.exit_vector_agent import ExitVectorDetectionAgent
from synglue_agent.agents.linker_agent import LinkerGenerationAgent
from synglue_agent.agents.novelty_agent import NoveltyAgent
from synglue_agent.agents.prediction_agent import ApplicabilityDomainAgent, DegradationPredictionAgent
from synglue_agent.agents.proximity_agent import ProximityDiversityAgent
from synglue_agent.agents.ranking_agent import RankingAgent
from synglue_agent.agents.reflection_agent import ReflectionReviewAgent
from synglue_agent.agents.report_agent import ReportAgent
from synglue_agent.agents.safety_agent import SafetyAgent
from synglue_agent.agents.search_control_agent import (
    CheapFilterAgent,
    ControlledSearchAgent,
    ExpensiveModelingSelectionAgent,
    StereochemistryEnumerationAgent,
)
from synglue_agent.agents.supervisor_agent import SupervisorAgent
from synglue_agent.agents.target_agent import TargetResolverAgent
from synglue_agent.agents.ternary_agent import TernaryFeasibilityAgent
from synglue_agent.backend.schemas import WorkflowState
from synglue_agent.tools.memory_manager import write_workflow_memory
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


Node = Tuple[str, Callable[[WorkflowState], WorkflowState]]


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
        self.nodes: List[Node] = [
            ("parse_user_request", SupervisorAgent().run),
            ("create_design_plan", DesignPlannerAgent().run),
            ("control_np_hard_search", ControlledSearchAgent().run),
            ("safety_precheck", SafetyAgent().run),
            ("resolve_target", TargetResolverAgent().run),
            ("retrieve_target_binders", TargetBinderRetrievalAgent().run),
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
            ("generate_report", ReportAgent().run),
            ("update_memory", MemoryUpdateAgent().run),
        ]

    def run(self, user_request: str | WorkflowState) -> WorkflowState:
        state = user_request if isinstance(user_request, WorkflowState) else WorkflowState(user_request=user_request)
        retry_counts: dict[str, int] = {}
        for node_name, node in self.nodes:
            state = node(state)
            if self._should_retry(node_name, state, retry_counts):
                retry_counts[node_name] = retry_counts.get(node_name, 0) + 1
                state.warnings.append(f"Planner retry policy repeated step: {node_name}")
                state = node(state)
            if self._should_stop(state):
                break
        return state

    def _should_stop(self, state: WorkflowState) -> bool:
        if state.design_plan.get("status") == "needs_user_input":
            return True
        terminal_errors = [
            "Planner requires a target protein/gene",
            "No warheads selected",
            "No E3 ligands selected",
            "No PROTAC candidates assembled",
            "No valid or unverified candidates",
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
    for name, node in local.nodes:
        graph.add_node(name, node)
    ordered = [name for name, _ in local.nodes]
    graph.set_entry_point(ordered[0])
    for current, nxt in zip(ordered, ordered[1:]):
        graph.add_edge(current, nxt)
    graph.add_edge(ordered[-1], END)
    return graph.compile()


def get_workflow_graph():
    return build_langgraph_workflow() or LocalSynGlueWorkflowGraph()


def run_syn_glue_workflow(user_request: str) -> WorkflowState:
    graph = get_workflow_graph()
    if hasattr(graph, "invoke"):  # LangGraph compiled graph.
        result = graph.invoke(WorkflowState(user_request=user_request))
        return result if isinstance(result, WorkflowState) else WorkflowState(**result)
    return graph.run(user_request)


from synglue_agent.agents.warhead_agent import WarheadSelectionAgent  # noqa: E402
