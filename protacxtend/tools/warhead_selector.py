"""Warhead selection functions."""

from __future__ import annotations

from typing import Optional, Sequence

from protacxtend.backend.schemas import BinderRecord, TargetRecord, WarheadRecord
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def select_warheads(
    target_record: Optional[TargetRecord],
    binders: Sequence[BinderRecord],
    user_warhead_smiles: Optional[str] = None,
    max_warheads: int = 6,
) -> list[WarheadRecord]:
    return _TOOLBOX.select_warheads(target_record, binders, user_warhead_smiles, max_warheads)


def score_warhead_potency(activity_nM: float | None) -> float:
    return _TOOLBOX.score_warhead_potency(activity_nM)


def score_derivatization_feasibility(warhead: WarheadRecord) -> float:
    return warhead.derivatization_score


def detect_warhead_exit_vectors(warheads: Sequence[WarheadRecord]):
    return _TOOLBOX.detect_exit_vectors(warheads, "warhead")


def rank_warheads(warheads: Sequence[WarheadRecord]) -> list[WarheadRecord]:
    return sorted(
        warheads,
        key=lambda item: item.potency_score + item.derivatization_score + item.exit_vector_confidence + item.source_confidence,
        reverse=True,
    )


def lookup_warhead_in_pubchem(name: str) -> dict:
    from protacxtend.tools.pubchem_lookup import search_compound_by_name

    result = search_compound_by_name(name)
    if result["success"]:
        result["output_type"] = "real_pubchem_api"
        result["real_output_generated"] = True
    else:
        result["output_type"] = "not_connected_or_failed"
        result["real_output_generated"] = False
    return result
