"""Report generation and export helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from synglue_agent.backend.schemas import WorkflowState
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def generate_markdown_report(state: WorkflowState) -> str:
    return _TOOLBOX.generate_markdown_report(state)


def generate_candidate_table(state: WorkflowState) -> list[dict[str, Any]]:
    return _TOOLBOX.generate_candidate_table(
        state.final_ranked_candidates or state.valid_candidates,
        state.ranking_results,
        state.degradation_predictions,
        state.admet_predictions,
        state.novelty_results,
        state.ternary_feasibility_results,
    )


def export_csv(rows: Sequence[dict[str, Any]], path: str | Path) -> Path:
    return _TOOLBOX.export_csv(rows, Path(path))


def export_json(payload: Any, path: str | Path) -> Path:
    return _TOOLBOX.export_json(payload, Path(path))


def generate_provenance_table(state: WorkflowState) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": candidate.candidate_id,
            "warhead_source": candidate.warhead_source,
            "e3_ligand": candidate.e3_ligand_name,
            "linker_source": candidate.provenance.get("linker_source"),
            "assembly_strategy": candidate.assembly_strategy,
        }
        for candidate in state.valid_candidates
    ]


def generate_failure_summary(state: WorkflowState) -> dict[str, int]:
    summary: dict[str, int] = {}
    for attempt in state.construction_attempts:
        if attempt.success:
            continue
        key = attempt.failure_category or "unknown"
        summary[key] = summary.get(key, 0) + 1
    return summary
