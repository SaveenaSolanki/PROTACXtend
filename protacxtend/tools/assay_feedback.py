"""Assay feedback ingestion for active-learning retraining."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

from protacxtend.backend.schemas import AssayFeedbackRecord
from protacxtend.tools.learning_memory import LearningMemory, LearningSource, Outcome, ProblemType
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "active", "success"}:
        return True
    if text in {"false", "0", "no", "n", "inactive", "failure"}:
        return False
    return None


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def load_assay_feedback_csv(path: str | Path) -> list[AssayFeedbackRecord]:
    """Load dose/degradation assay feedback from CSV."""
    records: list[AssayFeedbackRecord] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            records.append(
                AssayFeedbackRecord(
                    candidate_id=row.get("candidate_id", ""),
                    target=row.get("target", ""),
                    e3_ligase=row.get("e3_ligase", ""),
                    cell_line=row.get("cell_line", "default") or "default",
                    smiles=row.get("smiles", ""),
                    measured_dc50_nM=_float_or_none(row.get("measured_dc50_nM")),
                    measured_dmax_percent=_float_or_none(row.get("measured_dmax_percent")),
                    measured_hook_concentration_nM=_float_or_none(row.get("measured_hook_concentration_nM")),
                    degradation_observed=_bool_or_none(row.get("degradation_observed")),
                    source=row.get("source", "user_feedback") or "user_feedback",
                    notes=row.get("notes", ""),
                )
            )
    return records


def record_assay_feedback(feedback: Iterable[AssayFeedbackRecord | dict[str, Any]] | str | Path) -> dict[str, Any]:
    """Append assay feedback to retraining data and structured learning memory."""
    if isinstance(feedback, (str, Path)):
        records = load_assay_feedback_csv(feedback)
    else:
        records = [item if isinstance(item, AssayFeedbackRecord) else AssayFeedbackRecord(**item) for item in feedback]
    update = ProtacDesignToolbox().update_active_learning_from_feedback(records)
    memory = LearningMemory()
    learning_ids: list[str] = []
    for record in records:
        outcome = (
            Outcome.SUCCESS.value
            if record.degradation_observed is True
            else Outcome.FAILURE.value
            if record.degradation_observed is False
            else Outcome.PARTIAL.value
        )
        entry = memory.record(
            problem_type=ProblemType.DEGRADATION_PREDICTION.value,
            approach="assay_feedback_closed_loop",
            outcome=outcome,
            failure_reason="other" if record.degradation_observed is not False else "low_confidence",
            details=(
                f"candidate={record.candidate_id}; target={record.target}; e3={record.e3_ligase}; "
                f"cell={record.cell_line}; dc50={record.measured_dc50_nM}; "
                f"dmax={record.measured_dmax_percent}; hook={record.measured_hook_concentration_nM}; "
                f"notes={record.notes}"
            ),
            confidence=0.9,
            source=LearningSource.HUMAN_FEEDBACK.value,
            target=record.target,
            e3_ligase=record.e3_ligase,
            auto_validate_human=True,
        )
        learning_ids.append(entry.learning_id)
    return {
        "active_learning": update.model_dump(),
        "learning_ids": learning_ids,
        "feedback_count": len(records),
    }
