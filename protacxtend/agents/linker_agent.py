"""Linker generation agent."""

from __future__ import annotations

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WorkflowState
from protacxtend.tools.protac_autopilot_toolbox import ProtacXtendToolbox


def _run_with_deadline(fn, timeout_s: float):
    """Run fn in a daemon thread bounded by timeout_s; returns (result, error)."""
    import threading

    box: dict = {}

    def wrapper() -> None:
        try:
            box["out"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["err"] = exc

    t = threading.Thread(target=wrapper, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        return None, "deadline_exceeded"
    if "err" in box:
        raise box["err"]
    return box.get("out"), None


class LinkerGenerationAgent(ReActAgent):
    name = "LinkerGenerationAgent"
    thought = "Generate curated and rule-based linker candidates matching requested classes and PROTAC-aware constraints."
    action = "generate_linkers"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        # Deadline-safe generation: respect the propagated run deadline (typed
        # abstention instead of hanging past the budget).
        from protacxtend.agents.binder_agent import deadline_remaining

        remaining = deadline_remaining()
        if remaining is not None and remaining <= 3.0:
            state.errors.append(
                "LinkerGenerationAgent: run deadline too short for linker generation "
                f"({remaining:.2f}s remaining); typed abstention — no linkers claimed."
            )
            return state

        budget = min(remaining if remaining is not None else 20.0, 20.0)
        xtend = ProtacXtendToolbox(self.toolbox)
        out, failure = _run_with_deadline(
            lambda: xtend.linkers.generate_state_of_the_art_linker_panel(
                state.parsed_objective.preferred_linker_types,
                max_linkers=state.search_policy.linker_budget,
            ),
            budget,
        )
        if failure == "deadline_exceeded":
            state.errors.append(
                "LinkerGenerationAgent: linker generation exceeded the run deadline; "
                "no generation is claimed (deadline abstention)."
            )
            state.generated_linkers = []
            return state
        state.generated_linkers = out or []
        if not state.generated_linkers:
            state.generated_linkers = self.toolbox.generate_rule_based_linkers(["PEG", "alkyl", "piperazine", "triazole"])
            state.warnings.append("Requested linker generation failed; relaxed to default rule-based linker library.")
        return state

    def _observation(self, state: WorkflowState) -> str:
        classes = sorted({linker.linker_class for linker in state.generated_linkers})
        return f"linkers={len(state.generated_linkers)}, classes={classes}"
