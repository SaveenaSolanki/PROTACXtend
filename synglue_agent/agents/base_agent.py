"""Shared ReAct-style agent base classes."""

from __future__ import annotations

import time
from typing import Protocol

from synglue_agent.backend.schemas import WorkflowState
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


class AgentProtocol(Protocol):
    name: str

    def run(self, state: WorkflowState) -> WorkflowState:
        ...


class ReActAgent:
    """Small deterministic ReAct agent wrapper around toolbox calls."""

    name = "ReActAgent"
    thought = "Use deterministic SynGlue tools."
    action = "run"

    def __init__(self, toolbox: ProtacDesignToolbox | None = None):
        self.toolbox = toolbox or ProtacDesignToolbox()

    def run(self, state: WorkflowState) -> WorkflowState:
        started = time.time()
        try:
            state = self._execute(state)
            observation = self._observation(state)
        except Exception as exc:
            state.errors.append(f"{self.name}: {exc}")
            observation = f"error={exc}"
        self.toolbox.add_trace(state, self.name, self.thought, self.action, observation, time.time() - started)
        return state

    def _execute(self, state: WorkflowState) -> WorkflowState:
        return state

    def _observation(self, state: WorkflowState) -> str:
        return "completed"
