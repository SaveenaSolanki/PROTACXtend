"""Structural cooperativity surrogate (Module 3, step 7).

An interpretable, structure-based "cooperativity feasibility score" from
interface quality (buried surface area, contacts, H-bonds, salt bridges,
hydrophobic contacts, clashes) and ensemble stability. This score is a
heuristic ranked in [0,1] and is NEVER presented as experimental alpha; the
predict API returns predicted_alpha=None in surrogate mode so the boundary is
unambiguous.

IMPORTANT: the coefficients below are heuristic, UNTRAINED and NOT
experimentally calibrated. They were chosen as reasonable interface-quality
weights, not fitted to any measured cooperativity; the score is a feasibility
demonstration, not a prediction of alpha magnitude or sign.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from synglue_agent.modules.cooperativity_alpha_predictor.features import (
    interface_features,
)
from synglue_agent.modules.cooperativity_alpha_predictor.schemas import (
    InterfaceFeatures,
    SurrogateEvidence,
)

# component scales (deterministic, documented in README)
SCALES = {"bsa": 3000.0, "contacts": 60.0, "hbonds": 8.0, "salts": 4.0,
          "hydrophobic": 30.0, "clashes": 5.0}


def _n(value: float, scale: float, invert: bool = False) -> float:
    x = max(0.0, min(1.0, value / scale)) if scale else 0.0
    return 1.0 - x if invert else x


def cooperativity_feasibility_score(interface: InterfaceFeatures) -> SurrogateEvidence:
    """Deterministic interpretable score (0..1). Formula (documented):

      0.30*BSA + 0.20*contacts + 0.15*H-bonds + 0.10*salt + 0.05*hydrophobic
      + 0.10*(1 - clash_n) + 0.10*ensemble_stability
    """
    bsa_n = _n(interface.buried_surface_area_angstrom2, SCALES["bsa"])
    contact_n = _n(interface.intermolecular_contacts, SCALES["contacts"])
    hb_n = _n(interface.putative_hbonds, SCALES["hbonds"])
    salt_n = _n(interface.salt_bridges, SCALES["salts"])
    hydro_n = _n(interface.hydrophobic_contacts, SCALES["hydrophobic"])
    clash_n = _n(interface.steric_clashes, SCALES["clashes"])
    if interface.n_poses >= 2:
        ens = max(0.0, 1.0 - interface.ensemble_bsa_relstd)
    else:
        ens = 0.5  # neutral prior when only a single pose is available
    score = (0.30 * bsa_n + 0.20 * contact_n + 0.15 * hb_n + 0.10 * salt_n
             + 0.05 * hydro_n + 0.10 * (1.0 - clash_n) + 0.10 * ens)
    score = max(0.0, min(1.0, score))
    return SurrogateEvidence(
        interface=interface,
        components={"buried_surface": round(bsa_n, 4),
                    "contacts": round(contact_n, 4),
                    "hbonds": round(hb_n, 4),
                    "salt_bridges": round(salt_n, 4),
                    "hydrophobic": round(hydro_n, 4),
                    "clash_penalty": round(clash_n, 4),
                    "ensemble_stability": round(ens, 4)},
        formula_note="score = 0.30*BSA + 0.20*contacts + 0.15*Hbond + 0.10*salt "
                     "+ 0.05*hydrophobic + 0.10*(1-clash_n) + 0.10*ensemble_stability; "
                     "coefficients HEURISTIC/UNTRAINED, NOT experimentally calibrated",
        cooperativity_feasibility_score=round(score, 4),
    )


def surrogate_from_structures(
    structure_paths: list[str],
    poi_chain: str,
    e3_chain: str,
    n_sasa_dots: int = 64,
) -> tuple[SurrogateEvidence, list[dict[str, Any]]]:
    """Compute interface features + surrogate score for pose(s)."""
    interface, per_pose = interface_features(
        structure_paths, poi_chain=poi_chain, e3_chain=e3_chain, n_dots=n_sasa_dots)
    return cooperativity_feasibility_score(interface), per_pose
