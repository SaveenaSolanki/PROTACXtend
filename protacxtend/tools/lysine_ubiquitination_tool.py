"""LangGraph-ready agent tool wrapper for Module 2 (Lysine Ubiquitination).

JSON-in/JSON-out, graph-safe (never raises to the agent).

    out = run_lysine_ubiquitination_tool({"structure_paths": [...],
                                          "poi_chain": "A",
                                          "e2_catalytic": {"chain": "B",
                                                           "residue_number": 85}})
"""

from __future__ import annotations

from typing import Any, Dict

from protacxtend.modules.lysine_ubiquitination_feasibility import (
    MODEL_VERSION,
    LysineScorerError,
    score_lysine_ubiquitination,
)

TOOL_NAME = "run_lysine_ubiquitination"
EXPENSIVE = True  # structural geometry scoring over pose ensembles


def tool_spec() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": ("Score POI lysines in PROTAC ternary-complex structures for E2-mediated "
                        "ubiquitination feasibility: Nzeta..catalytic-Sy distance, Shrake-Rupley "
                        "SASA, approach angle, steric clashes and ensemble consistency. "
                        "Requires PDB pose(s) containing the E2 catalytic cysteine."),
        "expensive": EXPENSIVE,
        "model_version": MODEL_VERSION,
        "input_schema": {
            "type": "object",
            "properties": {
                "structure_paths": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "poi_chain": {"type": "string"},
                "e2_catalytic": {"type": "object",
                                 "properties": {"chain": {"type": "string"},
                                                "residue_number": {"type": "integer"},
                                                "residue_name": {"type": "string"}},
                                 "required": ["chain", "residue_number"]},
                "lysine_resnums": {"type": "array", "items": {"type": "integer"}},
                "distance_cutoff_angstrom": {"type": "number"},
                "orientation_cutoff_deg": {"type": "number"},
                "sasa_cutoff_angstrom2": {"type": "number"},
                "clash_cutoff_angstrom": {"type": "number"},
                "n_sasa_dots": {"type": "integer"},
            },
            "required": ["structure_paths", "poi_chain", "e2_catalytic"],
        },
    }


def run_lysine_ubiquitination(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        result = score_lysine_ubiquitination(**payload)
        return {"success": True, "result": result.model_dump(), "error": ""}
    except LysineScorerError as exc:
        return {"success": False, "result": None, "error": f"lysine_ubiquitination: {exc}"}
    except TypeError as exc:
        return {"success": False, "result": None, "error": f"lysine_ubiquitination: bad argument ({exc})"}
    except Exception as exc:  # graph safety
        return {"success": False, "result": None,
                "error": f"lysine_ubiquitination: unexpected failure ({exc})"}
