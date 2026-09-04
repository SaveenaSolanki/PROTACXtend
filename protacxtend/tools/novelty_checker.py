"""Novelty and similarity tools."""

from __future__ import annotations

from typing import Sequence

from protacxtend.backend.schemas import CandidateRecord
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def compute_morgan_fingerprint(smiles: str):
    return {"smiles": smiles, "rdkit_available": _TOOLBOX.rdkit_available}


def calculate_tanimoto_similarity(smiles_a: str, smiles_b: str) -> float:
    return _TOOLBOX.calculate_similarity(smiles_a, smiles_b)


def find_nearest_known_protac(smiles: str) -> tuple[str | None, float]:
    best_name = None
    best_score = 0.0
    for row in _TOOLBOX.load_known_protacs():
        score = _TOOLBOX.calculate_similarity(smiles, row.get("smiles", ""))
        if score > best_score:
            best_name = row.get("name") or row.get("protac_id")
            best_score = score
    return best_name, best_score


def calculate_novelty_score(smiles: str) -> float:
    _, score = find_nearest_known_protac(smiles)
    return max(0.0, 1.0 - score)


def flag_duplicates(smiles: str, duplicate_threshold: float = 0.98) -> bool:
    _, score = find_nearest_known_protac(smiles)
    return score >= duplicate_threshold


def search_pubchem_similarity_for_novelty(smiles: str, threshold: int = 95, top_k: int = 20) -> dict:
    from protacxtend.tools.pubchem_lookup import pubchem_similarity_search

    result = pubchem_similarity_search(smiles, threshold=threshold, top_k=top_k)
    if result["success"]:
        result["output_type"] = "real_pubchem_api"
        result["real_output_generated"] = True
    else:
        result["output_type"] = "not_connected_or_failed"
        result["real_output_generated"] = False
    return result


def check_novelty(candidates: Sequence[CandidateRecord]):
    return _TOOLBOX.check_novelty(candidates)
