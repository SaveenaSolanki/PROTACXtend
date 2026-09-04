"""ADME/Tox prediction wrappers."""

from __future__ import annotations

from typing import Sequence

from protacxtend.backend.schemas import CandidateRecord
from protacxtend.tools.admet_predictors import calculate_protac_admet_descriptors
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def compute_rdkit_descriptors(smiles: str) -> dict:
    result = calculate_protac_admet_descriptors(smiles)
    return result.get("descriptors", {}) if result.get("success") else {}


def predict_hERG(candidate: CandidateRecord) -> str:
    return _TOOLBOX.predict_admet([candidate])[0].hERG_risk


def predict_AMES(candidate: CandidateRecord) -> str:
    return _TOOLBOX.predict_admet([candidate])[0].AMES_risk


def predict_DILI(candidate: CandidateRecord) -> str:
    return _TOOLBOX.predict_admet([candidate])[0].DILI_risk


def predict_CYP(candidate: CandidateRecord) -> str:
    return _TOOLBOX.predict_admet([candidate])[0].CYP_risk


def predict_Pgp(candidate: CandidateRecord) -> str:
    return _TOOLBOX.predict_admet([candidate])[0].Pgp_risk


def predict_solubility(candidate: CandidateRecord) -> str:
    return _TOOLBOX.predict_admet([candidate])[0].solubility_risk


def compute_admet_penalty(candidate: CandidateRecord) -> float:
    return _TOOLBOX.predict_admet([candidate])[0].overall_admet_penalty


def predict_admet(candidates: Sequence[CandidateRecord]):
    return _TOOLBOX.predict_admet(candidates)
