"""LangGraph-ready agent tool — Module 6 rank_e3_ligases."""

from __future__ import annotations

from typing import Any, Dict

from protacxtend.modules.e3_opportunity import (
    MODEL_VERSION,
    rank_e3_ligases,
)

TOOL_NAME = "run_e3_opportunity"
EXPENSIVE = True


def tool_spec() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": ("Rank E3 ligases for PROTAC development for a POI "
                        "across evidence axes (cell-context expression, "
                        "localization, recruiter availability, precedent, "
                        "structure, lysine, selectivity, OOD). Verdicts: "
                        "SUPPORTED / PROMISING / EXPLORATORY / "
                        "INSUFFICIENT EVIDENCE. Never claims suitability from "
                        "expression alone; structural feasibility is UNKNOWN "
                        "without ternary data."),
        "expensive": EXPENSIVE,
        "model_version": MODEL_VERSION,
        "input_schema": {"type": "object",
                         "properties": {"poi": {"type": "string"},
                                        "cell_line": {"type": "string"},
                                        "tissue": {"type": "string"},
                                        "disease": {"type": "string"},
                                        "warhead": {"type": "string"},
                                        "poi_structure": {"type": "string"},
                                        "top_k": {"type": "integer"}},
                         "required": ["poi"]},
    }


def run_e3_opportunity(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        result = rank_e3_ligases(**payload)
        return {"success": True, "result": result, "error": ""}
    except (ValueError, KeyError) as exc:
        return {"success": False, "result": None,
                "error": f"e3_opportunity: {exc}"}
    except Exception as exc:  # graph safety
        return {"success": False, "result": None,
                "error": f"e3_opportunity: unexpected failure ({exc})"}
