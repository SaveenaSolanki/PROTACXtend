"""ChEMBL-style binder retrieval tools."""

from __future__ import annotations

import math
from typing import Sequence

from synglue_agent.backend.schemas import BinderRecord, TargetRecord
from synglue_agent.tools.chembl_lookup import (
    get_target_activities,
    normalize_activity_value,
    rank_warhead_candidates,
    search_targets,
)
from synglue_agent.tools.online_ligand_miner import resolve_target_from_chembl, retrieve_chembl_bioactive_ligands, search_chembl_targets
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def search_target(target_name: str) -> TargetRecord:
    return _TOOLBOX.resolve_target(target_name)


def search_chembl_target_online(target_name: str):
    result = search_targets(target_name)
    if result["success"]:
        return result["records"], []
    return [], [result["error"]]


def resolve_chembl_target_online(target_name: str):
    return resolve_target_from_chembl(target_name)


def retrieve_known_binders(
    target_record: TargetRecord,
    potency_threshold_nM: float = 1000.0,
    activity_types: Sequence[str] = ("IC50", "Ki", "Kd", "EC50"),
) -> list[BinderRecord]:
    return _TOOLBOX.retrieve_known_binders(target_record, potency_threshold_nM, activity_types)


def retrieve_target_activities(target_record: TargetRecord) -> list[BinderRecord]:
    return retrieve_known_binders(target_record)


def retrieve_online_target_activities(target_record: TargetRecord) -> tuple[list[BinderRecord], list[str]]:
    target_chembl_id = target_record.external_ids.get("chembl_target_id") if target_record.external_ids else None
    if not target_chembl_id:
        return [], ["No ChEMBL target ID available for executable ligand mining."]
    result = get_target_activities(target_chembl_id)
    if not result["success"]:
        return [], [f"ChEMBL executable activity lookup returned {result['error']}."]
    binders = []
    for item in rank_warhead_candidates(result["records"]):
        binders.append(
            BinderRecord(
                name=item.get("molecule_name") or item.get("molecule_id") or "ChEMBL ligand",
                target=target_record.gene_symbol or target_record.target_name,
                smiles=item.get("smiles") or "",
                activity_type=item.get("activity_type") or "unknown",
                activity_nM=item.get("activity_value"),
                p_activity=item.get("pchembl_value"),
                assay_confidence=item.get("confidence_score") or 0.0,
                source="ChEMBL REST API",
                metadata={
                    "target_chembl_id": target_chembl_id,
                    "molecule_chembl_id": item.get("molecule_id"),
                    "assay_description": item.get("assay_description"),
                    "needs_exit_vector_hypothesis": True,
                    "real_output_generated": True,
                    "source_url": item.get("source_url"),
                },
            )
        )
    return binders, []


def normalize_activity_to_nM(value: float, unit: str = "nM") -> float:
    normalized = normalize_activity_value(value, unit)
    return value if normalized is None else normalized


def compute_p_activity(activity_nM: float) -> float:
    if activity_nM <= 0:
        return 0.0
    return -math.log10(activity_nM * 1e-9)


def filter_assay_confidence(binders: Sequence[BinderRecord], min_confidence: float = 0.6) -> list[BinderRecord]:
    return [binder for binder in binders if binder.assay_confidence >= min_confidence]
