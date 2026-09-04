"""BindingDB-style tools backed by a real local TSV when present."""

from __future__ import annotations

from typing import Sequence

from protacxtend.backend.schemas import BinderRecord, TargetRecord
from protacxtend.tools.chembl_client import normalize_activity_to_nM
from protacxtend.tools.bindingdb_lookup import search_bindingdb_local
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def retrieve_bindingdb_binders(target_record: TargetRecord, potency_threshold_nM: float = 1000.0) -> list[BinderRecord]:
    query = target_record.uniprot_id or target_record.gene_symbol or target_record.target_name
    result = search_bindingdb_local(query)
    if not result["success"]:
        return []
    binders = []
    for item in result["records"]:
        if item["activity_value"] is None or item["activity_value"] > potency_threshold_nM:
            continue
        binders.append(
            BinderRecord(
                name=item.get("molecule_name") or "BindingDB ligand",
                target=target_record.gene_symbol or target_record.target_name,
                smiles=item.get("smiles") or "",
                activity_type=item.get("activity_type") or "unknown",
                activity_nM=item.get("activity_value"),
                assay_confidence=item.get("confidence_score") or 0.0,
                source="BindingDB local TSV",
                metadata={"real_output_generated": True, "source_url": item.get("source_url")},
            )
        )
    return binders


def normalize_binding_affinity(value: float, unit: str = "nM") -> float:
    return normalize_activity_to_nM(value, unit)


def filter_by_activity_type(binders: Sequence[BinderRecord], activity_types: Sequence[str]) -> list[BinderRecord]:
    allowed = set(activity_types)
    return [binder for binder in binders if binder.activity_type in allowed]
