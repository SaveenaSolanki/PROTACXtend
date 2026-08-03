"""Candidate and tool provenance helpers."""

from __future__ import annotations

from typing import Any

from synglue_agent.backend.schemas import WorkflowState
from synglue_agent.schemas.candidate_schema import CandidateProvenance


class ProvenanceBuilder:
    """Build provenance records from deterministic workflow state."""

    def build_candidate_provenance(self, state: WorkflowState) -> list[CandidateProvenance]:
        degradation_by_id = {item.candidate_id: item for item in state.degradation_predictions}
        admet_by_id = {item.candidate_id: item for item in state.admet_predictions}
        novelty_version = "local-known-protac-csv-v0.1"
        records: list[CandidateProvenance] = []
        for candidate in state.final_ranked_candidates or state.valid_candidates:
            deg = degradation_by_id.get(candidate.candidate_id)
            admet = admet_by_id.get(candidate.candidate_id)
            warning_text = "; ".join(filter(None, [getattr(deg, "warning", None), getattr(admet, "warning", None)]))
            records.append(
                CandidateProvenance(
                    candidate_id=candidate.candidate_id,
                    source_warhead=candidate.warhead_source or candidate.warhead_name,
                    source_e3_ligand=candidate.e3_ligand_name,
                    source_linker=candidate.provenance.get("linker_source", candidate.linker_name),
                    exit_vector_source=str(candidate.provenance.get("exit_vector_source", "curated_or_detected")),
                    construction_method=candidate.assembly_strategy,
                    rdkit_validation_status=candidate.validity_status,
                    degradation_model_name="SynGlue-demo-heuristic" if deg else None,
                    degradation_model_version=getattr(deg, "model_version", None),
                    admet_backend_name=self._extract_backend(getattr(admet, "warning", "")),
                    admet_backend_version="configured-or-descriptor-rule-v0.1" if admet else None,
                    novelty_database_version=novelty_version,
                    ternary_backend_name="geometry_or_docking_if_configured",
                    ternary_backend_version="v0.1",
                    evidence={"warning": warning_text},
                    warnings=list(candidate.warning_flags),
                )
            )
        return records

    def provenance_log(self, state: WorkflowState) -> list[dict[str, Any]]:
        return [
            {
                "agent": trace.agent,
                "action": trace.action,
                "observation": trace.observation,
                "runtime_seconds": trace.processing_time_s,
            }
            for trace in state.workflow_log
        ]

    def _extract_backend(self, warning: str | None) -> str | None:
        if not warning:
            return None
        if "backend=" not in warning:
            return "unknown"
        return warning.split("backend=", 1)[1].split(";", 1)[0].strip()

