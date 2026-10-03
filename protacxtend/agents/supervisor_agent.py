"""Supervisor and optional Agno/LangChain adapters."""

from __future__ import annotations

from typing import Any, Callable

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WorkflowState


class SupervisorAgent(ReActAgent):
    name = "SupervisorAgent"
    thought = "Parse the user's degradation objective into a structured PROTAC workflow state."
    action = "parse_user_request"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        parsed = self.toolbox.parse_user_request(state.user_request)
        seed = state.design_plan.get("structured_seed") if state.design_plan else None
        if seed:
            # A structured seed was supplied by a benchmark/API caller. The
            # seeded objective is authoritative: free-text parsing must not
            # inject a verb/noun as a target or warhead (the audited
            # "warhead='to'" / "AR inside warhead" defect).
            seeded = state.parsed_objective
            for field in ("target_name", "e3_ligase", "warhead_smiles",
                          "e3_ligand_smiles", "target_uniprot_id", "disease_context",
                          "cell_line"):
                setattr(parsed, field, getattr(seeded, field, None))
            if not seed.get("target_supplied"):
                parsed.target_name = ""
            if not seed.get("warhead_supplied"):
                parsed.warhead_smiles = None
            if not seed.get("e3_ligand_supplied"):
                parsed.e3_ligand_smiles = None
        state.parsed_objective = parsed
        if not state.parsed_objective.target_name:
            state.warnings.append("Target name was not confidently parsed. User input or target resolver should be checked.")
        return state

    def _observation(self, state: WorkflowState) -> str:
        objective = state.parsed_objective
        return (
            f"target={objective.target_name}, e3={objective.e3_ligase or 'CRBN/VHL branch'}, "
            f"candidate_count={objective.candidate_count}, linkers={objective.preferred_linker_types}"
        )


class AgnoSupervisorAdapter:
    """Adapter hook for Agno teams.

    The class is intentionally lightweight so the project imports without Agno.
    Pass an Agno agent/team callable to delegate execution in production.
    """

    def __init__(self, agno_runner: Callable[[WorkflowState], WorkflowState] | None = None):
        self.agno_runner = agno_runner
        self.local_agent = SupervisorAgent()

    def run(self, state: WorkflowState) -> WorkflowState:
        if self.agno_runner is not None:
            return self.agno_runner(state)
        return self.local_agent.run(state)


class LangChainToolAdapter:
    """Minimal LangChain-compatible callable wrapper for a deterministic tool."""

    def __init__(self, name: str, description: str, func: Callable[..., Any]):
        self.name = name
        self.description = description
        self.func = func

    def invoke(self, payload: dict[str, Any]) -> Any:
        return self.func(**payload)

    def __call__(self, **payload: Any) -> Any:
        return self.func(**payload)
