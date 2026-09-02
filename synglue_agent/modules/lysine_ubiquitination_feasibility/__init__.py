"""Lysine Ubiquitination Feasibility Scorer (Module 2).

Public API: ``score_lysine_ubiquitination(structure_paths, poi_chain,
e2_catalytic={...}, ...)``

    from synglue_agent.modules.lysine_ubiquitination_feasibility import \\
        score_lysine_ubiquitination

    result = score_lysine_ubiquitination(
        structure_paths=["pose1.pdb", "pose2.pdb"],
        poi_chain="A",
        e2_catalytic={"chain": "B", "residue_number": 85},
    )
    result.ranked_lysines[0].productive_pose_fraction
"""

from synglue_agent.modules.lysine_ubiquitination_feasibility.core import (
    LysineScorerError,
    read_pdb,
    score_lysine_ubiquitination,
)
from synglue_agent.modules.lysine_ubiquitination_feasibility.schemas import (
    MODEL_VERSION,
    LysineUbiquitinationInput,
    LysineUbiquitinationResult,
)

__all__ = [
    "score_lysine_ubiquitination",
    "read_pdb",
    "LysineScorerError",
    "LysineUbiquitinationInput",
    "LysineUbiquitinationResult",
    "MODEL_VERSION",
]
