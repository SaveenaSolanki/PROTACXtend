"""predict_cooperativity — Module 3 public API.

Behavior is honest by construction:

* Structural inputs (ternary_structure / ternary_ensemble, with explicit
  POI/E3 chain ids) => interpretable structural SURROGATE features and a
  "cooperativity feasibility score"; predicted_alpha stays None because no
  experimental-alpha-trained model exists yet (no fabricated alpha).
* A trained-model artifact path (model_path) is accepted for the future when a
  curated dataset justifies training; if the artifact is missing, the call
  degrades to the surrogate and says so.
* Missing both structures AND a trained model => explicit failure requiring
  evidence (never a made-up number).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from protacxtend.modules.cooperativity_alpha_predictor.alpha_def import (
    alpha_to_log,
    cooperativity_class,
)
from protacxtend.modules.cooperativity_alpha_predictor.features import (
    molecular_features,
)
from protacxtend.modules.cooperativity_alpha_predictor.schemas import (
    CooperativityPrediction,
    SurrogateEvidence,
)
from protacxtend.modules.cooperativity_alpha_predictor.surrogate import (
    surrogate_from_structures,
)
from protacxtend.modules.lysine_ubiquitination_feasibility.core import (
    LysineScorerError,
)


class CooperativityEvidenceError(ValueError):
    """Raised when the evidence required for any cooperativity statement is absent."""


DEFAULT_LIMITATIONS = [
    "No experimental-alpha-trained model exists yet (curated dataset empty); "
    "the returned score is a STRUCTURAL cooperativity-FEASIBILITY surrogate, "
    "NOT an experimental alpha prediction.",
    "Surrogate coefficients are HEURISTIC and UNTRAINED — never fitted to or "
    "calibrated against experimental cooperativity; the score is a ranked "
    "feasibility heuristic only and must never be quoted as alpha.",
    "Static geometry: no conformational ensemble sampling, solvent model or "
    "binding free-energy integration is performed.",
    "alpha definition: alpha = Kd2/Kd2(ternary) in one assay system (see alpha_def).",
]


def predict_cooperativity(
    protac: str = "",
    poi: str = "",
    e3: str = "",
    ternary_structure: str | None = None,
    ternary_ensemble: list[str] | None = None,
    smiles: str | None = None,
    poi_chain: str | None = None,
    e3_chain: str | None = None,
    model_path: str | None = None,
    n_sasa_dots: int = 64,
    **_: Any,
) -> CooperativityPrediction:
    """Predict cooperativity (alpha) with calibrated honesty.

    Args:
        protac/poi/e3: human identifiers (recorded for provenance/OOD notes).
        ternary_structure: single ternary-complex PDB path.
        ternary_ensemble: multiple pose PDB paths (enables ensemble features).
        smiles: PROTAC SMILES (optional molecular descriptors).
        poi_chain / e3_chain: chain ids in the structure(s) — REQUIRED with a
            structure so interface features are well-defined.
        model_path: optional trained-model artifact (future); absent => surrogate.
    """
    paths = [p for p in ([ternary_structure] if ternary_structure else []) + (list(ternary_ensemble or []))]
    structure_available = bool(paths)
    limitations = list(DEFAULT_LIMITATIONS)
    evidence = SurrogateEvidence()

    if structure_available:
        if not poi_chain or not e3_chain:
            raise CooperativityEvidenceError(
                "poi_chain and e3_chain are required when a ternary structure is "
                "provided (interface features need unambiguous chain assignment).")
        try:
            evidence, per_pose = surrogate_from_structures(
                paths, poi_chain=poi_chain, e3_chain=e3_chain, n_sasa_dots=n_sasa_dots)
        except (LysineScorerError, OSError) as exc:
            raise CooperativityEvidenceError(f"cannot compute structural features: {exc}") from exc
    else:
        limitations.append("No ternary structure supplied — structural surrogate not computed.")

    mol = molecular_features(smiles)
    evidence.molecular = mol

    # trained-model path (future; artifact gate)
    predicted_alpha: float | None = None
    predicted_log: float | None = None
    conf: float | None = None
    uncertainty: dict[str, Any] = {}
    applicability = ""
    model_kind = "structural_surrogate"

    # INVARIANT: the feasibility score is a separate heuristic field and can
    # never populate predicted_alpha / predicted_log_alpha. Only a genuinely
    # trained (curated-data) model may set them, and none exists yet.
    if model_path:
        if not Path(model_path).exists():
            limitations.append(f"model_path {model_path} not found -> surrogate mode only")
        else:
            raise NotImplementedError(
                "trained cooperativity model artifact loading is reserved for the "
                "post-curation stage (no curated dataset exists yet)")

    if not structure_available and predicted_alpha is None:
        raise CooperativityEvidenceError(
            "No evidence available for a cooperativity statement: supply a ternary "
            "structure (ternary_structure/ternary_ensemble + poi_chain/e3_chain) "
            "or a trained model artifact (model_path). Refusing to fabricate alpha.")

    if predicted_alpha is not None:
        predicted_log = alpha_to_log(predicted_alpha)
        cls = cooperativity_class(predicted_alpha)
        uncertainty = {"kind": "model_posterior_std", "note": "trained-model uncertainty"}
    else:
        cls = "not_assessed"
        uncertainty = {"kind": "surrogate_heuristic",
                       "note": "no trained model; feasibility surrogate only, "
                               "alpha NOT predicted"}
        if evidence.cooperativity_feasibility_score >= 0.6:
            limitations.append("Structural feasibility is high, but high interface "
                               "quality does NOT guarantee positive alpha (measured "
                               "cooperativity may still be neutral/negative).")
        applicability = ("structural surrogate applicable only to the input pose(s); "
                         "OOD relative to any trained model is not assessable without data")

    status = "SUPPORTED" if structure_available else "INSUFFICIENT"
    return CooperativityPrediction(
        model_kind=model_kind,
        protac=protac, poi=poi, e3=e3,
        predicted_alpha=predicted_alpha,
        predicted_log_alpha=predicted_log,
        cooperativity_class=cls,
        confidence=conf,
        uncertainty=uncertainty,
        feature_evidence=evidence,
        structure_available=structure_available,
        model_applicability=applicability,
        limitations=limitations,
        status=status,
    )
