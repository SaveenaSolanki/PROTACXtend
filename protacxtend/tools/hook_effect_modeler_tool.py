"""LangGraph-ready agent tool wrapper for Module 1 (Hook Effect Modeler).

The wrapper exposes a JSON-in/JSON-out typed tool so PROTACXtend agent nodes can
call the validated equilibrium model without importing the module internals.
Errors are returned as structured tool failures (never exceptions to the graph).

    tool = run_hook_effect_modeler({"alpha": 10.0, "e3_conc_nM": 100.0, ...})
    tool.status -> "SUPPORTED"
"""

from __future__ import annotations

from typing import Any, Dict

from protacxtend.modules.hook_effect_modeler import (
    MODEL_VERSION,
    HookEffectResult,
    HookModelError,
    simulate_hook_effect,
)

TOOL_NAME = "run_hook_effect_modeler"
EXPENSIVE = False


def tool_spec() -> dict[str, Any]:
    """JSON schema descriptor for LLM/agent planning layers."""
    return {
        "name": TOOL_NAME,
        "description": ("Simulate the PROTAC ternary-complex dose-response (hook effect) "
                        "with a mechanistic three-body equilibrium model. Returns ternary "
                        "curve, optimal concentration, hook onset/severity, maximum occupancy."),
        "expensive": EXPENSIVE,
        "model_version": MODEL_VERSION,
        "input_schema": {
            "type": "object",
            "properties": {
                "poI_conc_nM": {"type": "number", "minimum": 0},
                "e3_conc_nM": {"type": "number", "minimum": 0},
                "kd_poi_protac_nM": {"type": "number", "exclusiveMinimum": 0},
                "kd_e3_protac_nM": {"type": "number", "exclusiveMinimum": 0},
                "alpha": {"type": "number", "minimum": 0},
                "min_dose_nM": {"type": "number", "exclusiveMinimum": 0},
                "max_dose_nM": {"type": "number", "exclusiveMinimum": 0},
                "points": {"type": "integer", "minimum": 20, "maximum": 1000},
                "uncertainty_pct": {
                    "type": "object",
                    "properties": {"kd": {"type": "number"}, "alpha": {"type": "number"}},
                },
                "seed": {"type": "integer"},
            },
        },
    }


def run_hook_effect_modeler(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute the hook-effect simulation from a JSON payload.

    Returns {"success": bool, "result": {...HookEffectResult}, "error": str}
    """
    try:
        result: HookEffectResult = simulate_hook_effect(**payload)
        return {"success": True, "result": result.model_dump(), "error": ""}
    except HookModelError as exc:
        return {"success": False, "result": None,
                "error": f"hook_effect_modeler: invalid inputs ({exc})"}
    except TypeError as exc:
        return {"success": False, "result": None,
                "error": f"hook_effect_modeler: bad argument ({exc})"}
    except Exception as exc:  # graph-safety: tool failures never crash the agent
        return {"success": False, "result": None,
                "error": f"hook_effect_modeler: unexpected failure ({exc})"}


def run_hook_effect_agent(params: dict[str, Any]) -> dict[str, Any]:
    """Alias used by LangGraph nodes (keeps node code short)."""
    return run_hook_effect_modeler(params)
