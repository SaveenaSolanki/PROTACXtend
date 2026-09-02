"""Proximity/diversity agent."""

from __future__ import annotations

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WorkflowState


class ProximityDiversityAgent(ReActAgent):
    name = "ProximityDiversityAgent"
    thought = "Cluster chemically similar candidates and identify diverse representatives."
    action = "diversity_clustering"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        state.diversity_clusters = self.toolbox.cluster_candidates(state.valid_candidates)
        return state

    def _observation(self, state: WorkflowState) -> str:
        return f"clusters={len(state.diversity_clusters)}"


def cluster_candidates(*args, **kwargs):
    return ProximityDiversityAgent().toolbox.cluster_candidates(*args, **kwargs)


def choose_diverse_representatives(*args, **kwargs):
    return ProximityDiversityAgent().toolbox.choose_diverse_representatives(*args, **kwargs)


def compute_redundancy_score(cluster_size: int, total: int) -> float:
    return 0.0 if total <= 0 else max(0.0, (cluster_size - 1) / total)
