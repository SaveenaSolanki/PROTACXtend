"""Structured exceptions for the agentic control layer."""


class AgenticWorkflowError(Exception):
    """Base exception for agentic orchestration failures."""


class ToolExecutionError(AgenticWorkflowError):
    """Raised when a deterministic tool cannot be executed."""


class ScientificValidationError(AgenticWorkflowError):
    """Raised when scientific validation requires stopping the workflow."""

