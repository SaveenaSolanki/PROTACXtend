"""PROTACXtend scientific data contracts and the controlled run.

Public entry points::

    from protacxtend.contracts import run_controlled, write_artifacts
    from protacxtend.contracts.entities import parse_request
"""

from __future__ import annotations

from .entities import parse_request
from .records import (
    Artifact,
    Binder,
    CanonicalRunRecord,
    CandidateFunnel,
    Decision,
    E3Ligand,
    E3Ligase,
    Evidence,
    Linker,
    Prediction,
    ProtacCandidate,
    RequestParse,
    Target,
    Warhead,
)
from .run import INJECTIONS, has_scientific_result, run_controlled, write_artifacts

__all__ = [
    "parse_request", "run_controlled", "write_artifacts", "has_scientific_result",
    "INJECTIONS", "RequestParse", "Target", "E3Ligase", "Binder", "Warhead",
    "E3Ligand", "Linker", "ProtacCandidate", "Prediction", "Evidence", "Decision",
    "Artifact", "CandidateFunnel", "CanonicalRunRecord",
]
