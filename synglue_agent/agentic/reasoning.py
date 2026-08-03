"""Reasoning layer for PROTAC design context."""

from __future__ import annotations

from synglue_agent.schemas.agentic_schema import PerceptionState, ReasoningState


class ReasoningAgent:
    """Interpret perceived context using explicit, reportable rules."""

    name = "ReasoningAgent"

    def run(self, perception: PerceptionState) -> ReasoningState:
        entities = perception.detected_entities
        target = entities.get("target_name") or ""
        e3 = entities.get("e3_ligase") or ""
        model_loaded = perception.available_models.get("degradation", {}).get("status") == "model_loaded"
        rdkit_available = perception.available_tools.get("rdkit", {}).get("available", False)
        docking_available = perception.available_tools.get("vina", {}).get("available") or perception.available_tools.get("gnina", {}).get("available")
        under_specified = "target_name" in perception.missing_information

        trace = [
            {"topic": "target", "evidence": target or "missing", "warning": "target required" if not target else ""},
            {"topic": "model", "evidence": "trained degradation model loaded" if model_loaded else "heuristic fallback only", "warning": "" if model_loaded else "do not claim validated DC50/Dmax"},
            {"topic": "chemistry", "evidence": "RDKit available" if rdkit_available else "RDKit unavailable", "warning": "" if rdkit_available else "validation limited"},
        ]
        return ReasoningState(
            target_assessment={
                "target": target,
                "suitable_for_protac_design": bool(target),
                "basis": "target parsed from request" if target else "missing target",
            },
            binder_assessment={
                "known_binders_required": "warhead_smiles_or_known_binder_source" in perception.missing_information,
                "strategy": "retrieve known binders before warhead selection",
            },
            e3_assessment={
                "e3_ligase": e3 or "CRBN/VHL default branch",
                "assumption": not bool(e3),
                "basis": "user provided" if e3 else "default branch with warning",
            },
            exit_vector_assessment={
                "requires_detection": True,
                "stricter_detection_if_uncertain": True,
                "warning": "ambiguous/hypothetical exit vectors require chemist review",
            },
            linker_strategy={
                "mode": "constrained" if entities.get("linker_constraints") else "broad",
                "linkers": entities.get("linker_constraints") or [],
            },
            scoring_strategy={
                "degradation_backend": "trained_model" if model_loaded else "heuristic_fallback",
                "claim_validated_prediction": model_loaded,
            },
            ternary_strategy={
                "requested": any("docking" in flag for flag in perception.scientific_risk_flags),
                "backend_available": bool(docking_available),
                "fallback": "geometry_only" if not docking_available else "docking_enabled",
            },
            admet_strategy={
                "constraints": entities.get("admet_constraints") or {},
                "risk_level": "higher" if entities.get("admet_constraints") else "standard",
            },
            uncertainty_assessment={
                "under_specified": under_specified,
                "missing_information": perception.missing_information,
                "risk_flags": perception.scientific_risk_flags,
            },
            recommended_next_actions=[
                "ask_user_for_target" if under_specified else "create_design_goal",
                "label_heuristic_outputs" if not model_loaded else "use_model_provenance",
            ],
            reasoning_trace=trace,
        )

