"""LangGraph-ready agent tool wrapper — Module 3 Cooperativity predictor."""

from __future__ import annotations

from typing import Any, Dict

from protacxtend.modules.cooperativity_alpha_predictor import (
    MODEL_VERSION,
    CooperativityEvidenceError,
    predict_cooperativity,
)

TOOL_NAME = "run_cooperativity_predictor"
EXPENSIVE = True


def tool_spec() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": ("Predict PROTAC ternary cooperativity. Structural mode returns an "
                        "interpretable cooperativity-FEASIBILITY score (NOT experimental "
                        "alpha) with feature evidence; predicted alpha is only returned once "
                        "an experimental-alpha-trained model exists."),
        "expensive": EXPENSIVE,
        "model_version": MODEL_VERSION,
        "input_schema": {
            "type": "object",
            "properties": {
                "protac": {"type": "string"}, "poi": {"type": "string"}, "e3": {"type": "string"},
                "ternary_structure": {"type": "string"},
                "ternary_ensemble": {"type": "array", "items": {"type": "string"}},
                "smiles": {"type": "string"},
                "poi_chain": {"type": "string"}, "e3_chain": {"type": "string"},
                "model_path": {"type": "string"},
            },
        },
    }


def run_cooperativity_predictor(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        result = predict_cooperativity(**payload)
        return {"success": True, "result": result.model_dump(), "error": ""}
    except CooperativityEvidenceError as exc:
        return {"success": False, "result": None,
                "error": f"cooperativity: evidence required ({exc})"}
    except TypeError as exc:
        return {"success": False, "result": None,
                "error": f"cooperativity: bad argument ({exc})"}
    except Exception as exc:
        return {"success": False, "result": None,
                "error": f"cooperativity: unexpected failure ({exc})"}
