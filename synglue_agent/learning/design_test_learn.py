"""Design-test-learn optimizer for locked PROTAC experiment feedback."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from synglue_agent.tools.assay_feedback import record_assay_feedback
from synglue_agent.tools.repo_tool_adapter import PROJECT_ROOT


REGISTRY_DIR = PROJECT_ROOT / "outputs" / "design_test_learn"


@dataclass
class LockedPrediction:
    candidate_id: str
    prediction: dict[str, Any]
    locked_at: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NextBatchDecision:
    status: str
    next_batch: list[str] = field(default_factory=list)
    expected_information_gain: dict[str, float] = field(default_factory=dict)
    decision_change_probability: dict[str, float] = field(default_factory=dict)
    model_update_record: dict[str, Any] = field(default_factory=dict)
    rollback_pointer: str = ""
    warnings: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def lock_predictions(predictions: list[dict[str, Any]], run_id: str = "") -> dict[str, Any]:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    run = run_id or stamp.replace(":", "").replace("+", "Z")
    locked = [LockedPrediction(candidate_id=str(p.get("candidate_id", f"candidate_{i}")), prediction=p, locked_at=stamp).model_dump() for i, p in enumerate(predictions)]
    path = REGISTRY_DIR / f"{run}_locked_predictions.json"
    path.write_text(json.dumps({"run_id": run, "locked_predictions": locked}, indent=2), encoding="utf-8")
    return {"success": True, "run_id": run, "path": str(path), "locked_count": len(locked)}


def recommend_next_batch(
    candidates: list[dict[str, Any]],
    feedback: list[dict[str, Any]] | str | Path | None = None,
    batch_size: int = 6,
) -> NextBatchDecision:
    feedback_update: dict[str, Any] = {}
    warnings: list[str] = []
    if feedback:
        feedback_update = record_assay_feedback(feedback)
    scored = []
    for candidate in candidates:
        cid = str(candidate.get("candidate_id", ""))
        score = float(candidate.get("final_priority_score", candidate.get("score", 0.5)) or 0.5)
        uncertainty = float(candidate.get("uncertainty", candidate.get("model_uncertainty", 0.5)) or 0.5)
        diversity = float(candidate.get("diversity_score", candidate.get("novelty_score", 0.5)) or 0.5)
        info_gain = max(0.0, min(1.0, 0.45 * uncertainty + 0.35 * diversity + 0.20 * score))
        decision_change = max(0.0, min(1.0, 0.55 * uncertainty + 0.25 * (1.0 - abs(score - 0.5) * 2.0) + 0.20 * diversity))
        scored.append((cid, info_gain, decision_change, score))
    scored.sort(key=lambda item: (item[1], item[2], item[3]), reverse=True)
    next_batch = [item[0] for item in scored[: max(1, int(batch_size))] if item[0]]
    if not next_batch:
        warnings.append("No candidate IDs supplied; cannot recommend a concrete batch.")
    rollback = ""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    if feedback_update:
        rollback = str(REGISTRY_DIR / "last_validated_model_pointer.json")
        Path(rollback).write_text(json.dumps({"status": "no_model_promoted", "reason": "validation gate required"}, indent=2), encoding="utf-8")
    return NextBatchDecision(
        status="SUPPORTED" if next_batch else "INSUFFICIENT EVIDENCE",
        next_batch=next_batch,
        expected_information_gain={cid: round(info, 3) for cid, info, _, _ in scored},
        decision_change_probability={cid: round(prob, 3) for cid, _, prob, _ in scored},
        model_update_record=feedback_update,
        rollback_pointer=rollback,
        warnings=warnings,
    )

