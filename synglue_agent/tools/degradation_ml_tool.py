"""LangGraph-ready agent tool — Module 4 predict_degradation."""

from __future__ import annotations

from typing import Any, Dict

from synglue_agent.modules.degradation_ml import (
    MODEL_VERSION,
    DegradationModelError,
    predict_degradation,
)

TOOL_NAME = "run_degradation_predictor"
EXPENSIVE = False


def tool_spec() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": ("Predict PROTAC degradation potency (pDC50, DC50 nM, empirical "
                        "interval, OOD score) from a trained model on the curated "
                        "PROTAC-DB benchmark set. degradation probability and Dmax are "
                        "None until measured labels exist (never fabricated)."),
        "expensive": EXPENSIVE,
        "model_version": MODEL_VERSION,
        "input_schema": {"type": "object",
                         "properties": {"smiles": {"type": "string"},
                                        "target": {"type": "string"},
                                        "e3": {"type": "string"},
                                        "model_path": {"type": "string"}},
                         "required": ["smiles"]},
    }


def run_degradation_predictor(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        result = predict_degradation(**payload)
        return {"success": True, "result": result.model_dump(), "error": ""}
    except (DegradationModelError, ValueError) as exc:
        return {"success": False, "result": None,
                "error": f"degradation: {exc}"}
    except Exception as exc:  # graph safety
        return {"success": False, "result": None,
                "error": f"degradation: unexpected failure ({exc})"}
