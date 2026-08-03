"""Goal-setting layer for agentic PROTAC design."""

from __future__ import annotations

from typing import Any

from synglue_agent.schemas.agentic_schema import DesignGoal, PerceptionState, ReasoningState


class GoalSettingAgent:
    """Convert request and reasoning into explicit design goals."""

    name = "GoalSettingAgent"

    def run(self, perception: PerceptionState, reasoning: ReasoningState, config: dict[str, Any] | None = None) -> DesignGoal:
        config = config or {}
        entities = perception.detected_entities
        target = entities.get("target_name") or ""
        e3 = entities.get("e3_ligase") or "CRBN/VHL"
        objectives = [
            "maximize degradation confidence",
            "minimize predicted DC50",
            "maximize Dmax",
            "preserve novelty",
            "maintain synthetic plausibility",
        ]
        constraints = entities.get("admet_constraints") or {}
        if constraints.get("avoid_hERG"):
            objectives.append("reduce hERG risk")
        return DesignGoal(
            target=target,
            e3_ligase=e3,
            candidate_count=int(entities.get("candidate_count") or 50),
            design_mode="agentic_protac_design",
            required_outputs=["markdown_report", "candidate_csv", "candidate_json", "provenance_log", "memory_record"],
            optimization_objectives=objectives,
            hard_constraints={"target_required": True, **constraints},
            soft_constraints={"preferred_linkers": entities.get("linker_constraints") or []},
            validation_depth=str(config.get("validation_depth", "medium")),
            stop_criteria=[
                "minimum valid candidates reached",
                "maximum construction attempts reached",
                "no valid exit vector found",
                "no linker-compatible candidate found",
                "required model backend unavailable",
            ],
            fallback_policy={
                "allow_heuristic_fallback": bool(config.get("allow_heuristic_fallback", True)),
                "model_missing": "use heuristic fallback and warn",
                "docking_missing": "use geometry-only ternary feasibility",
                "e3_missing": "branch over CRBN/VHL and mark assumption",
            },
            success_criteria=["valid candidates generated", "ranking produced", "all scientific claims provenance-labeled"],
        )

