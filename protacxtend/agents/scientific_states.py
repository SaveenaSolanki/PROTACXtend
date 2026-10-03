"""Typed scientific outcome states.

Completion is not a scientific state. Every final result carries one of these
explicit labels so a reviewer can tell a supported answer from a design brief or
a justified no-go.
"""

from __future__ import annotations

from enum import Enum


class ScientificState(str, Enum):
    SUPPORTED_ANSWER = "supported_answer"          # evidence-backed, reviewable answer
    CONDITIONAL_HYPOTHESIS = "conditional_hypothesis"  # mechanism/feasibility, not measured
    DESIGN_BRIEF = "design_brief"                  # components mapped only hypothetically
    VALID_CANDIDATE = "valid_candidate"            # sanitized product with real attachments
    JUSTIFIED_NO_GO = "justified_no_go"            # required input absent; refuse
    UNRESOLVED = "unresolved"                      # engine failed before a scientific step


#: States that may be presented to a user as a final result.
FINAL_STATES = {
    ScientificState.SUPPORTED_ANSWER,
    ScientificState.CONDITIONAL_HYPOTHESIS,
    ScientificState.DESIGN_BRIEF,
    ScientificState.VALID_CANDIDATE,
    ScientificState.JUSTIFIED_NO_GO,
}
