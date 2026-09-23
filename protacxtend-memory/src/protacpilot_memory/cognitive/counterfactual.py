"""Counterfactual learning for important failures (Master Prompt §28).

Stored as separate reasoning artifacts. Observations and evidence are never
rewritten by a counterfactual.
"""

from __future__ import annotations

from typing import Any

from ..config import MemoryConfig
from ..store.store import MemoryStore
from ..util import new_id, now_iso


class CounterfactualAnalyzer:
    def __init__(self, store: MemoryStore, config: MemoryConfig | None = None) -> None:
        self.store = store
        self.config = config or store.config

    def analyze(
        self,
        prediction_id: str,
        *,
        outcome_id: str | None = None,
        episode_id: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        alternative_assumption: str | None = None,
    ) -> dict[str, Any]:
        prediction = self.store.require_prediction(prediction_id)
        outcomes = self.store.outcomes_for(prediction_id)
        outcome = None
        if outcome_id:
            outcome = self.store.get_outcome(outcome_id)
        if outcome is None and outcomes:
            outcome = outcomes[-1]

        context = prediction.get("context_json") or {}
        assumptions = context.get("assumptions") or []
        analysis = {
            "what_was_predicted": {
                "metric": prediction.get("metric"),
                "predicted_value": prediction.get("predicted_value"),
                "predicted_class": prediction.get("predicted_class"),
                "confidence": prediction.get("confidence"),
            },
            "what_occurred": {
                "observed_value": (outcome or {}).get("observed_value"),
                "observed_class": (outcome or {}).get("observed_class"),
                "prediction_error": (outcome or {}).get("prediction_error"),
                "error_method": (outcome or {}).get("error_method"),
            },
            "assumptions": assumptions,
            "questionable_assumption": alternative_assumption or self._questionable(assumptions, outcome),
            "alternative_explanations": self._alternatives(prediction, outcome, episode_id),
            "would_updated_hypothesis_predict": self._would_predict(outcome),
            "note": "counterfactual reasoning artifact; observations and evidence unchanged",
        }
        analysis_id = new_id("CF")
        import json

        self.store.db.execute(
            """
            INSERT INTO counterfactual_analyses
                (id, created_at, project_id, session_id, prediction_id, outcome_id,
                 episode_id, question, analysis_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id, now_iso(), project_id or prediction.get("project_id"),
                session_id, prediction_id, (outcome or {}).get("id"), episode_id,
                "What assumption, if revised, would explain the prediction error?",
                json.dumps(analysis),
            ),
        )
        return {"id": analysis_id, "prediction_id": prediction_id, **analysis}

    def for_prediction(self, prediction_id: str) -> list[dict[str, Any]]:
        import json

        rows = self.store.db.query(
            "SELECT * FROM counterfactual_analyses WHERE prediction_id = ? ORDER BY created_at DESC",
            (prediction_id,),
        )
        return [dict(r) | {"analysis_json": json.loads(r["analysis_json"])} for r in rows]

    # ── heuristics (deterministic, labelled as such) ─────────────────────────
    @staticmethod
    def _questionable(assumptions: list[Any], outcome: dict[str, Any] | None) -> str | None:
        if assumptions:
            return str(assumptions[0])
        if outcome and (outcome.get("prediction_error") or 0) >= 0.5:
            return "the model's core mechanistic assumption for this context"
        return None

    def _alternatives(self, prediction: dict[str, Any], outcome: dict[str, Any] | None, episode_id: str | None) -> list[dict[str, Any]]:
        alternatives = []
        if episode_id:
            for rel in self.store.relations_for(episode_id):
                other = rel["source_memory_id"] if rel["target_memory_id"] == episode_id else rel["target_memory_id"]
                if rel["relation_type"] in {"contradicts", "exception_to", "related_context"}:
                    trace = self.store.get_trace(other)
                    if trace:
                        alternatives.append({
                            "memory_id": other,
                            "relation": rel["relation_type"],
                            "title": trace.get("title"),
                        })
        return alternatives[:5]

    @staticmethod
    def _would_predict(outcome: dict[str, Any] | None) -> str:
        if not outcome:
            return "unknown"
        if (outcome.get("prediction_error") or 0) >= 0.5:
            return "an updated hypothesis incorporating the revised assumption would predict the observed outcome"
        return "the original hypothesis already predicted the outcome"
