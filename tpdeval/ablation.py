"""Ablation study (Section 23).

Two families:
  * PROTACXtend component ablations (planner, evidence engine, structure/ternary,
    critic, provenance, tool routing, failure recovery).
  * The isolating ablation: SAME LLM, SAME tools, SAME evidence, DIFFERENT planner.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AblationSpec:
    key: str
    name: str
    removed_components: List[str] = field(default_factory=list)
    held_constant: Dict[str, str] = field(default_factory=dict)
    isolates: str = ""


COMPONENTS = [
    "tpd_specific_planner",
    "evidence_engine",
    "structure_ternary_module",
    "critic_system",
    "provenance_layer",
    "specialized_tool_routing",
    "failure_recovery_logic",
]

ABLATIONS: List[AblationSpec] = [
    AblationSpec("full", "Full PROTACXtend", [], {}, "reference"),
    *[AblationSpec(f"minus_{c}", f"PROTACXtend minus {c}", [c], {},
                   f"contribution of {c}")
      for c in COMPONENTS],
    AblationSpec(
        "same_llm_tools_different_planner",
        "SAME LLM + SAME tools + SAME evidence, DIFFERENT planner",
        [], {"llm": "matched", "tools": "matched", "evidence": "matched"},
        "isolates TPD-specific orchestration from model/tool/evidence effects"),
    AblationSpec(
        "generic_planner",
        "Generic (non-TPD) planner + matched tools",
        ["tpd_specific_planner"], {"llm": "matched", "tools": "matched",
                                   "evidence": "matched"},
        "planner-only effect"),
]


def ablation_deltas(full_score: float, ablations: Dict[str, float]) -> Dict[str, float]:
    """Contribution of each component = full - ablated (higher = more important)."""
    return {k: round(full_score - v, 4) for k, v in ablations.items()}


def planner_isolation(full: Dict[str, float], generic: Dict[str, float]) -> Dict[str, object]:
    return {
        "n_tasks": len(set(full) | set(generic)),
        "full_mean": round(sum(full.values()) / max(1, len(full)), 4),
        "generic_planner_mean": round(sum(generic.values()) / max(1, len(generic)), 4),
        "planner_delta": round(
            sum(full.values()) / max(1, len(full))
            - sum(generic.values()) / max(1, len(generic)), 4),
        "interpretation": "same LLM, same tools, same evidence; delta attributable to planner",
    }
