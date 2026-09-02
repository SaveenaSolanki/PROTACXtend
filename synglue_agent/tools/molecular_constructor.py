"""Multi-strategy PROTAC construction functions."""

from __future__ import annotations

from typing import Sequence

from synglue_agent.backend.schemas import E3LigandRecord, LinkerRecord, TargetRecord, WarheadRecord
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def construct_with_template(warhead_smiles: str, linker_smiles: str, e3_smiles: str):
    return _TOOLBOX.assemble_components(warhead_smiles, linker_smiles, e3_smiles)


def construct_with_reaction_smarts(warhead_smiles: str, linker_smiles: str, e3_smiles: str):
    return _TOOLBOX.assemble_components(warhead_smiles, linker_smiles, e3_smiles)


def construct_with_brics_recap(warhead_smiles: str, linker_smiles: str, e3_smiles: str):
    return _TOOLBOX.assemble_components(warhead_smiles, linker_smiles, e3_smiles)


def graft_known_linker(warhead_smiles: str, linker_smiles: str, e3_smiles: str):
    return _TOOLBOX.assemble_components(warhead_smiles, linker_smiles, e3_smiles)


def matched_linker_replacement(warhead_smiles: str, linker_smiles: str, e3_smiles: str):
    return _TOOLBOX.assemble_components(warhead_smiles, linker_smiles, e3_smiles)


def generative_linker_conditioned_assembly(warhead_smiles: str, linker_smiles: str, e3_smiles: str):
    return _TOOLBOX.assemble_components(warhead_smiles, linker_smiles, e3_smiles)


def retrosynthesis_feasibility_filter(synthetic_feasibility_score: float, threshold: float = 0.45) -> bool:
    return synthetic_feasibility_score >= threshold


def diagnose_construction_failure(message: str) -> str:
    if "missing_attachment" in message:
        return "Missing explicit warhead/linker/E3 attachment markers."
    if "duplicate" in message:
        return "Duplicate canonical candidate."
    return message or "Unknown construction failure."


def construct_protac_candidates(
    warheads: Sequence[WarheadRecord],
    e3_ligands: Sequence[E3LigandRecord],
    linkers: Sequence[LinkerRecord],
    target_record: TargetRecord | None,
    candidate_count: int = 50,
    use_retrosynthesis_filtering: bool = False,
):
    return _TOOLBOX.construct_protac_candidates(
        warheads,
        e3_ligands,
        linkers,
        target_record,
        candidate_count,
        use_retrosynthesis_filtering,
    )
