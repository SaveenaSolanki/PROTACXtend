"""Target resolution tools."""

from __future__ import annotations

from typing import Optional

from synglue_agent.backend.schemas import TargetRecord
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def resolve_target(target_name: str, uniprot_id: Optional[str] = None) -> TargetRecord:
    return _TOOLBOX.resolve_target(target_name, uniprot_id)


def retrieve_uniprot_record(target_name: str, uniprot_id: Optional[str] = None) -> TargetRecord:
    return _TOOLBOX.resolve_target(target_name, uniprot_id)


def retrieve_target_synonyms(target_name: str, uniprot_id: Optional[str] = None) -> list[str]:
    return _TOOLBOX.resolve_target(target_name, uniprot_id).synonyms


def retrieve_structure_availability(target_name: str, uniprot_id: Optional[str] = None) -> list[str]:
    return _TOOLBOX.resolve_target(target_name, uniprot_id).structures


def compute_target_tractability_score(target_name: str, uniprot_id: Optional[str] = None) -> float:
    return _TOOLBOX.resolve_target(target_name, uniprot_id).tractability_score
