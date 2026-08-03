"""Perception layer: collect request, tools, data, model, and memory context."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from synglue_agent.backend.config import DATA_DIR
from synglue_agent.models.degradation_model import discover_degradation_models
from synglue_agent.schemas.agentic_schema import PerceptionState
from synglue_agent.tools.docking_status import detect_docking_backends
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox, RDKIT_AVAILABLE


class PerceptionAgent:
    """Collect context without inventing missing data."""

    name = "PerceptionAgent"

    def __init__(self, toolbox: ProtacDesignToolbox | None = None):
        self.toolbox = toolbox or ProtacDesignToolbox()

    def run(self, request: str, config: dict[str, Any] | None = None) -> PerceptionState:
        config = config or {}
        objective = self.toolbox.parse_user_request(request)
        detected = {
            "target_name": objective.target_name,
            "e3_ligase": objective.e3_ligase,
            "candidate_count": objective.candidate_count,
            "linker_constraints": objective.preferred_linker_types,
            "admet_constraints": objective.admet_constraints,
            "disease_context": objective.disease_context,
            "cell_line": objective.cell_line,
            "assay_context": objective.assay_context,
        }
        missing = [key for key in ["target_name"] if not detected.get(key)]
        if not objective.e3_ligase:
            missing.append("e3_ligase")
        if not objective.warhead_smiles:
            missing.append("warhead_smiles_or_known_binder_source")

        available_tools = self._detect_tools()
        available_models = {"degradation": discover_degradation_models(config.get("model_dir", "models/"))}
        local_data = self._local_data_status()
        memory = self._retrieve_memory(objective.target_name, objective.e3_ligase)
        risk_flags = []
        if available_models["degradation"].get("status") != "model_loaded":
            risk_flags.append("trained_degradation_model_missing_use_heuristic_fallback")
        if not available_tools.get("rdkit", {}).get("available"):
            risk_flags.append("rdkit_unavailable_chemical_validation_limited")
        if objective.use_structure_aware_ranking and not (
            available_tools.get("vina", {}).get("available") or available_tools.get("gnina", {}).get("available")
        ):
            risk_flags.append("docking_requested_but_backend_unavailable")

        confidence = 1.0 - min(0.6, 0.15 * len(missing) + 0.1 * len(risk_flags))
        return PerceptionState(
            raw_request=request,
            normalized_request=" ".join(request.strip().split()),
            detected_entities=detected,
            available_tools=available_tools,
            available_models=available_models,
            available_local_data=local_data,
            retrieved_memory=memory,
            missing_information=missing,
            scientific_risk_flags=risk_flags,
            perception_confidence=round(confidence, 3),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _detect_tools(self) -> dict[str, Any]:
        docking = detect_docking_backends().get("backends", {})
        try:
            import langgraph  # noqa: F401

            langgraph_available = True
        except Exception:
            langgraph_available = False
        return {
            "rdkit": {"available": bool(RDKIT_AVAILABLE), "role": "chemical validation/descriptors"},
            "langgraph": {"available": langgraph_available, "role": "optional graph orchestration"},
            "vina": docking.get("vina", {"available": False}),
            "gnina": docking.get("gnina", {"available": False}),
            "openbabel": docking.get("openbabel", {"available": False}),
        }

    def _local_data_status(self) -> dict[str, Any]:
        expected = [
            "curated_targets.csv",
            "curated_warheads.csv",
            "curated_e3_ligands.csv",
            "curated_linkers.csv",
            "known_protac_smiles.csv",
            "protacdb_local.csv",
            "protacpedia_local.csv",
        ]
        return {
            name: {
                "available": (DATA_DIR / name).exists(),
                "path": str(DATA_DIR / name),
                "rows": len(self.toolbox.load_table(name)) if (DATA_DIR / name).exists() else 0,
            }
            for name in expected
        }

    def _retrieve_memory(self, target: str, e3_ligase: str | None) -> list[dict[str, Any]]:
        try:
            from synglue_agent.agentic.learning import LearningAgent

            return LearningAgent().retrieve_similar_runs(target=target, e3_ligase=e3_ligase, limit=5)
        except Exception:
            return []

