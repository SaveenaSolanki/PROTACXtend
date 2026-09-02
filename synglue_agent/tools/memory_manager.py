"""Short-term and long-term memory helpers."""

from __future__ import annotations

from synglue_agent.backend.schemas import WorkflowState
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def write_workflow_memory(state: WorkflowState) -> dict:
    update = _TOOLBOX.write_workflow_memory(state)
    state.memory_updates.append(update)
    return update


def retrieve_target_memory(target_name: str) -> list[dict]:
    return []


def retrieve_failed_linker_memory(target_name: str | None = None) -> list[dict]:
    return []


def retrieve_successful_patterns(target_name: str | None = None) -> list[dict]:
    return []


def update_sar_memory(state: WorkflowState) -> dict:
    return write_workflow_memory(state)
