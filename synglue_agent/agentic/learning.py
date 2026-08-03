"""Learning and adaptation layer backed by structured JSONL memory."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from synglue_agent.backend.config import MEMORY_DIR, ensure_directories
from synglue_agent.backend.schemas import WorkflowState, model_to_dict
from synglue_agent.schemas.memory_schema import DesignMemoryRecord


class LearningAgent:
    """Store and retrieve useful verified workflow experience."""

    name = "LearningAgent"

    def __init__(self, memory_path: str | Path | None = None):
        ensure_directories()
        self.memory_path = Path(memory_path) if memory_path else MEMORY_DIR / "agentic_design_memory.jsonl"

    def store_from_workflow(
        self,
        run_id: str,
        user_request: str,
        state: WorkflowState,
        user_feedback: str | None = None,
    ) -> DesignMemoryRecord:
        top = [
            {"candidate_id": ranking.candidate_id, "rank": ranking.rank, "score": ranking.final_priority_score}
            for ranking in state.ranking_results[:10]
        ]
        record = DesignMemoryRecord(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_request=user_request,
            target=state.parsed_objective.target_name,
            e3_ligase=state.parsed_objective.e3_ligase or "CRBN/VHL",
            warheads_used=sorted({candidate.warhead_name for candidate in state.valid_candidates if candidate.warhead_name}),
            linkers_used=sorted({candidate.linker_class for candidate in state.valid_candidates if candidate.linker_class}),
            exit_vectors_used=sorted({str(candidate.provenance.get("exit_vector_source", "unknown")) for candidate in state.valid_candidates}),
            candidates_generated=len(state.assembled_candidates),
            candidates_valid=len(state.valid_candidates),
            candidates_failed=max(0, len(state.construction_attempts) - len(state.valid_candidates)),
            top_candidates=top,
            failure_modes=sorted({attempt.failure_category or "unknown" for attempt in state.construction_attempts if not attempt.success}),
            warnings=list(state.warnings),
            model_versions={"degradation": state.degradation_predictions[0].model_version if state.degradation_predictions else "not_run"},
            tool_versions={"ranking": "weighted-deterministic-v0.1"},
            user_feedback=user_feedback,
            reusable_lessons=self._lessons(state),
        )
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        with self.memory_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(model_to_dict(record), sort_keys=True) + "\n")
        return record

    def retrieve_similar_runs(self, target: str, e3_ligase: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        if not self.memory_path.exists() or not target:
            return []
        hits: list[dict[str, Any]] = []
        target_upper = target.upper()
        e3_upper = (e3_ligase or "").upper()
        with self.memory_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(item.get("target", "")).upper() != target_upper:
                    continue
                if e3_upper and e3_upper not in str(item.get("e3_ligase", "")).upper():
                    continue
                hits.append(item)
        return hits[-limit:]

    def _lessons(self, state: WorkflowState) -> list[str]:
        lessons = []
        if state.valid_candidates:
            lessons.append("Target/E3/linker combination produced valid or unverified candidates.")
        if any("heuristic" in (prediction.warning or "").lower() for prediction in state.degradation_predictions):
            lessons.append("Use heuristic degradation values only as non-validated prioritization signals.")
        if state.warnings:
            lessons.append("Carry warning flags into future planning for this target/E3 context.")
        return lessons
