"""Prediction and outcome store (Master Prompt §10, §52).

Predictions are persisted *before* outcomes exist. Prediction error is computed
deterministically at outcome time.
"""

from __future__ import annotations

from typing import Any

from ..cognitive.prediction_error import compute_prediction_error
from ..errors import NotFoundError
from ..util import dumps, loads, new_id, now_iso
from .base import BaseStore


class PredictionStore(BaseStore):
    def create_prediction(
        self,
        *,
        prediction_type: str,
        project_id: str | None = None,
        session_id: str | None = None,
        candidate_id: str | None = None,
        metric: str | None = None,
        predicted_value: float | None = None,
        predicted_class: str | None = None,
        predicted_probability: float | None = None,
        confidence: float = 0.5,
        scale: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        prediction_id = new_id("PRED")
        self.db.execute(
            """
            INSERT INTO prediction_events
                (id, project_id, session_id, candidate_id, prediction_type, metric,
                 predicted_value, predicted_class, predicted_probability, confidence,
                 scale, context_json, created_at, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                prediction_id, project_id, session_id, candidate_id, prediction_type,
                metric, predicted_value, predicted_class, predicted_probability,
                float(confidence), scale, dumps(context or {}), now_iso(),
            ),
        )
        return prediction_id

    def get_prediction(self, prediction_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM prediction_events WHERE id = ?", (prediction_id,))
        if row is None:
            return None
        return dict(row) | {"context_json": loads(row["context_json"], {})}

    def require_prediction(self, prediction_id: str) -> dict[str, Any]:
        prediction = self.get_prediction(prediction_id)
        if prediction is None:
            raise NotFoundError("prediction", prediction_id)
        return prediction

    def unresolved_predictions(self, project_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        sql = "SELECT * FROM prediction_events WHERE resolved = 0"
        params: list[Any] = []
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY created_at ASC LIMIT ?"
        params.append(limit)
        return [dict(r) | {"context_json": loads(r["context_json"], {})}
                for r in self.db.query(sql, params)]

    def record_outcome(
        self,
        prediction_id: str,
        *,
        observed_value: float | None = None,
        observed_class: str | None = None,
        observed_probability: float | None = None,
        outcome_type: str | None = None,
        evidence_id: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        prediction = self.require_prediction(prediction_id)
        outcome_data = {
            "observed_value": observed_value,
            "observed_class": observed_class,
            "observed_probability": observed_probability,
        }
        error, method, breakdown = compute_prediction_error(prediction, outcome_data)
        outcome_id = new_id("OUT")
        self.db.execute(
            """
            INSERT INTO outcome_events
                (id, prediction_id, observed_value, observed_class, observed_probability,
                 outcome_type, evidence_id, prediction_error, error_method, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                outcome_id, prediction_id, observed_value, observed_class,
                observed_probability, outcome_type, evidence_id, error, method,
                notes, now_iso(),
            ),
        )
        self.db.execute(
            "UPDATE prediction_events SET resolved = 1 WHERE id = ?", (prediction_id,)
        )
        return {
            "id": outcome_id,
            "prediction_id": prediction_id,
            "observed_value": observed_value,
            "observed_class": observed_class,
            "observed_probability": observed_probability,
            "outcome_type": outcome_type,
            "evidence_id": evidence_id,
            "prediction_error": error,
            "error_method": method,
            "breakdown": breakdown,
            "notes": notes,
            "created_at": now_iso(),
        }

    def get_outcome(self, outcome_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM outcome_events WHERE id = ?", (outcome_id,))
        return dict(row) if row else None

    def outcomes_for(self, prediction_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.query(
            "SELECT * FROM outcome_events WHERE prediction_id = ? ORDER BY created_at", (prediction_id,)
        )]

    def prediction_accuracy(self, project_id: str | None = None, project_prediction_ids: list[str] | None = None) -> float:
        """Mean 1 - error over resolved predictions (calibration proxy)."""
        if project_prediction_ids is not None:
            if not project_prediction_ids:
                return 0.0
            placeholders = ", ".join("?" for _ in project_prediction_ids)
            row = self.db.query_one(
                f"SELECT AVG(prediction_error) AS e FROM outcome_events WHERE prediction_id IN ({placeholders})",
                project_prediction_ids,
            )
        else:
            row = self.db.query_one(
                """
                SELECT AVG(o.prediction_error) AS e FROM outcome_events o
                JOIN prediction_events p ON p.id = o.prediction_id
                WHERE (? IS NULL OR p.project_id = ?)
                """,
                (project_id, project_id),
            )
        if row is None or row["e"] is None:
            return 0.0
        return max(0.0, min(1.0, 1.0 - float(row["e"])))
