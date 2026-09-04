"""LangGraph-ready agent tool — Module 5 predict_cell_context."""

from __future__ import annotations

from typing import Any, Dict

from protacxtend.modules.cell_context_selector import (
    MODEL_VERSION,
    CellContextModelError,
    predict_cell_context,
)

TOOL_NAME = "run_cell_context_predictor"
EXPENSIVE = True   # loads expression context + production model


def tool_spec() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": ("Predict cell-context degradation (pDC50, DC50 nM, "
                        "Dmax, derived-activity view) for a PROTAC in a "
                        "specific cell line using PROTAC+POI+E3+cell context. "
                        "Returns uncertainty, per-axis OOD flags, "
                        "applicability and gated claims. degradation "
                        "probability is threshold-derived (pDC50>=6 AND "
                        "Dmax>=60), never an experimental probability."),
        "expensive": EXPENSIVE,
        "model_version": MODEL_VERSION,
        "input_schema": {"type": "object",
                         "properties": {"protac": {"type": "string"},
                                        "poi": {"type": "string"},
                                        "e3": {"type": "string"},
                                        "cell_line": {"type": "string"},
                                        "model_path": {"type": "string"}},
                         "required": ["protac", "cell_line"]},
    }


def run_cell_context_predictor(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        result = predict_cell_context(**payload)
        return {"success": True, "result": result, "error": ""}
    except (CellContextModelError, ValueError) as exc:
        return {"success": False, "result": None,
                "error": f"cell_context: {exc}"}
    except Exception as exc:  # graph safety
        return {"success": False, "result": None,
                "error": f"cell_context: unexpected failure ({exc})"}
