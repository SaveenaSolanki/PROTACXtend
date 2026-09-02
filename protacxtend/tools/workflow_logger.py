"""Workflow logging utilities."""

from __future__ import annotations

import time

from protacxtend.backend.schemas import WorkflowState
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def log_step(state: WorkflowState, agent: str, thought: str, action: str, observation: str, elapsed: float = 0.0) -> None:
    _TOOLBOX.add_trace(state, agent, thought, action, observation, elapsed)


def timed_log(state: WorkflowState, agent: str, thought: str, action: str, started_at: float, observation: str) -> None:
    log_step(state, agent, thought, action, observation, time.time() - started_at)
