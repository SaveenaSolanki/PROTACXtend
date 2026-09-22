"""Specialized Scientific Modules — the nine logical divisions.

These modules sit *beneath* one orchestrator. They do not own control flow:
the orchestrator builds the task graph and the tool executor owns computation.
A module's job is to interpret one slice of the shared engine state, attach
evidence, and report a typed :class:`ModuleResult` with a stable ``module_id``.

Binding to computation is intentionally indirect (``context.tools``) so the
same module registry works with either legacy engine and with injected fakes
in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from protacxtend.canonical.evidence import CanonicalEvidenceStore
from protacxtend.canonical.schemas import (
    ModuleResult,
    ScientificModuleId,
    ScientificRequest,
    TaskStatus,
)
from protacxtend.canonical.tool_executor import ToolExecutor


@dataclass
class ModuleContext:
    tools: ToolExecutor
    evidence: CanonicalEvidenceStore
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class CanonicalState:
    request: ScientificRequest
    engine_state: Any = None
    module_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════
# Engine-state normalisation (WorkflowState object OR adaptive dict)
# ══════════════════════════════════════════════════════════════════════

def _to_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


class EngineView:
    """Read-only, uniform view over either execution engine's state."""

    def __init__(self, state: Any):
        self._state = state or {}

    def raw(self, key: str, default: Any = None) -> Any:
        if isinstance(self._state, dict):
            return self._state.get(key, default)
        return getattr(self._state, key, default)

    def list(self, key: str) -> list[Any]:
        value = self.raw(key, []) or []
        return list(value) if isinstance(value, (list, tuple)) else []

    def dict(self, key: str) -> dict[str, Any]:
        value = self.raw(key, {}) or {}
        return value if isinstance(value, dict) else {}

    def first(self, key: str) -> Any:
        items = self.list(key)
        return items[0] if items else None

    def as_dict(self, key: str) -> dict[str, Any]:
        value = _to_dict(self.raw(key))
        return value if isinstance(value, dict) else {}


# ══════════════════════════════════════════════════════════════════════
# Base module
# ══════════════════════════════════════════════════════════════════════

class ScientificModule:
    module_id: ScientificModuleId
    title: str = ""
    description: str = ""
    optional: bool = False

    def execute(self, state: CanonicalState, context: ModuleContext) -> ModuleResult:  # pragma: no cover - abstract
        raise NotImplementedError

    # ------------------------------------------------------------------
    def _result(
        self,
        *,
        status: TaskStatus,
        summary: str,
        outputs: dict[str, Any],
        context: ModuleContext,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
        tool: str = "",
    ) -> ModuleResult:
        result = ModuleResult(
            module_id=self.module_id.value,
            title=self.title,
            status=status,
            summary=summary,
            outputs=outputs,
            warnings=list(warnings or []),
            errors=list(errors or []),
            provenance={"tool_version": f"protacxtend:{self.module_id.value}:v1", "tool": tool},
        )
        result.evidence_refs = context.evidence.add_module_result(result)
        return result

    def _engine_view(self, state: CanonicalState, context: ModuleContext) -> EngineView:
        if state.engine_state is None:
            state.engine_state = context.tools.call(
                "scientific_engine", {"request": state.request.normalized_request or state.request.raw_request}
            )
        return EngineView(state.engine_state)


# ══════════════════════════════════════════════════════════════════════
# 1. Target & Disease
# ══════════════════════════════════════════════════════════════════════

class TargetDiseaseModule(ScientificModule):
    module_id = ScientificModuleId.TARGET_DISEASE
    title = "Target & Disease"

    def execute(self, state: CanonicalState, context: ModuleContext) -> ModuleResult:
        view = self._engine_view(state, context)
        target = view.as_dict("target_record")
        if not target and isinstance(state.engine_state, dict):
            target = view.as_dict("target_info")
        name = state.request.target or target.get("target_name") or target.get("name")
        outputs = {
            "target": name,
            "uniprot_id": target.get("uniprot_id"),
            "structures": target.get("structures") or [],
            "disease_context": state.request.disease_context,
            "cell_line": state.request.cell_line,
            "tractability_score": target.get("tractability_score"),
        }
        status = TaskStatus.SUCCEEDED if name else TaskStatus.DEGRADED
        warnings = [] if name else ["No target resolved from request or curated data."]
        return self._result(
            status=status,
            summary=f"Target '{name or 'unresolved'}' with {len(outputs['structures'])} structure(s).",
            outputs=outputs,
            context=context,
            warnings=warnings,
            tool="deterministic_engine.target_resolution",
        )


# ══════════════════════════════════════════════════════════════════════
# 2. TPD Tractability
# ══════════════════════════════════════════════════════════════════════

class TPDTractabilityModule(ScientificModule):
    module_id = ScientificModuleId.TPD_TRACTABILITY
    title = "TPD Tractability"

    def execute(self, state: CanonicalState, context: ModuleContext) -> ModuleResult:
        view = self._engine_view(state, context)
        binders = view.list("retrieved_binders")
        ligands = view.list("selected_e3_ligands")
        target = view.as_dict("target_record") or view.as_dict("target_info")
        has_structures = bool(target.get("structures"))
        outputs = {
            "known_binder_count": len(binders),
            "known_e3_ligand_count": len(ligands),
            "has_experimental_structure": has_structures,
            "tractability_score": target.get("tractability_score"),
            "tractable": bool(binders) and bool(ligands),
        }
        status = TaskStatus.SUCCEEDED if (binders or ligands) else TaskStatus.DEGRADED
        warnings = [] if binders else ["No known binders retrieved; warhead evidence is weak."]
        return self._result(
            status=status,
            summary=f"{len(binders)} binder(s), {len(ligands)} E3 ligand(s), structures={has_structures}.",
            outputs=outputs,
            context=context,
            warnings=warnings,
            tool="deterministic_engine.binder_retrieval",
        )


# ══════════════════════════════════════════════════════════════════════
# 3. E3 Selection
# ══════════════════════════════════════════════════════════════════════

class E3SelectionModule(ScientificModule):
    module_id = ScientificModuleId.E3_SELECTION
    title = "E3 Selection"

    def execute(self, state: CanonicalState, context: ModuleContext) -> ModuleResult:
        view = self._engine_view(state, context)
        ligands = [_to_dict(item) for item in view.list("selected_e3_ligands")]
        context_preds = [_to_dict(item) for item in view.list("e3_context_predictions")]
        names = sorted({str(item.get("e3_ligase") or item.get("name") or "") for item in ligands if item})
        outputs = {
            "e3_ligases": [name for name in names if name],
            "n_ligands": len(ligands),
            "cell_context_predictions": context_preds[:10],
            "requested_e3": state.request.e3_ligase or "unspecified",
            "assumption": not bool(state.request.e3_ligase),
        }
        status = TaskStatus.SUCCEEDED if ligands else TaskStatus.DEGRADED
        warnings = [] if state.request.e3_ligase else ["E3 ligase not user-specified; default branching flagged as assumption."]
        return self._result(
            status=status,
            summary=f"E3 ligands for {', '.join(outputs['e3_ligases']) or 'none'}.",
            outputs=outputs,
            context=context,
            warnings=warnings,
            tool="deterministic_engine.e3_selection",
        )


# ══════════════════════════════════════════════════════════════════════
# 4. Chemistry / Warhead
# ══════════════════════════════════════════════════════════════════════

class ChemistryWarheadModule(ScientificModule):
    module_id = ScientificModuleId.CHEMISTRY_WARHEAD
    title = "Chemistry / Warhead"

    def execute(self, state: CanonicalState, context: ModuleContext) -> ModuleResult:
        view = self._engine_view(state, context)
        warheads = view.list("selected_warheads")
        linkers = view.list("generated_linkers")
        candidates = view.list("valid_candidates") or view.list("assembled_candidates")
        novelty = [_to_dict(item) for item in view.list("novelty_results")]
        exits = view.list("exit_vectors")
        n_assembled = len(view.list("assembled_candidates"))
        outputs = {
            "n_warheads": len(warheads),
            "n_linkers": len(linkers),
            "n_exit_vectors": len(exits),
            "n_assembled": n_assembled,
            "n_valid": len(view.list("valid_candidates")),
            "n_novel": sum(1 for item in novelty if item.get("is_novel")),
            "top_candidate_smiles": [
                (item.get("full_protac_smiles") if isinstance(item, dict) else getattr(item, "full_protac_smiles", ""))
                for item in candidates[:3]
            ],
        }
        status = TaskStatus.SUCCEEDED if candidates else TaskStatus.DEGRADED
        warnings = [] if candidates else ["No chemically valid PROTAC candidate was assembled."]
        return self._result(
            status=status,
            summary=f"{outputs['n_valid']} valid candidate(s) from {outputs['n_warheads']} warhead(s) x {outputs['n_linkers']} linker(s).",
            outputs=outputs,
            context=context,
            warnings=warnings,
            tool="deterministic_engine.construction_validation",
        )


# ══════════════════════════════════════════════════════════════════════
# 5. Structure / Ternary
# ══════════════════════════════════════════════════════════════════════

class StructureTernaryModule(ScientificModule):
    module_id = ScientificModuleId.STRUCTURE_TERNARY
    title = "Structure / Ternary"

    def execute(self, state: CanonicalState, context: ModuleContext) -> ModuleResult:
        view = self._engine_view(state, context)
        ternary = view.list("ternary_feasibility_results")
        if not ternary:
            ternary = list(view.dict("ternary_feasibility").values())
        cooperativity = view.list("cooperativity_predictions")
        outputs = {
            "n_ternary_records": len(ternary),
            "ternary_scores": [
                (item.get("ternary_plausibility_score") if isinstance(item, dict) else getattr(item, "ternary_plausibility_score", None))
                for item in ternary[:10]
            ],
            "n_cooperativity_records": len(cooperativity),
            "structure_backed": bool(ternary),
        }
        status = TaskStatus.SUCCEEDED if ternary else TaskStatus.DEGRADED
        warnings = [] if ternary else ["No ternary/structure evidence produced; structural claims must not be made."]
        return self._result(
            status=status,
            summary=f"{len(ternary)} ternary record(s); structural claims {'allowed' if ternary else 'blocked' }.",
            outputs=outputs,
            context=context,
            warnings=warnings,
            tool="deterministic_engine.ternary",
        )


# ══════════════════════════════════════════════════════════════════════
# 6. Degradation
# ══════════════════════════════════════════════════════════════════════

class DegradationModule(ScientificModule):
    module_id = ScientificModuleId.DEGRADATION
    title = "Degradation"

    def execute(self, state: CanonicalState, context: ModuleContext) -> ModuleResult:
        view = self._engine_view(state, context)
        preds = [_to_dict(item) for item in view.list("degradation_predictions")]
        revised = [_to_dict(item) for item in view.list("revised_degradation")]
        hook = [_to_dict(item) for item in view.list("hook_effect_predictions")]
        model_versions = sorted({str(item.get("model_version") or "") for item in preds if item})
        heuristic_only = all("heuristic" in version.lower() for version in model_versions) if model_versions else False
        outputs = {
            "n_predictions": len(preds),
            "model_versions": [version for version in model_versions if version],
            "heuristic_fallback": heuristic_only,
            "top_dc50": [item.get("predicted_dc50_nm") or item.get("dc50_nm") for item in preds[:5]],
            "hook_effect_records": len(hook),
            "ternary_revised": len(revised),
        }
        status = TaskStatus.SUCCEEDED if preds else TaskStatus.DEGRADED
        warnings = []
        if heuristic_only:
            warnings.append("Degradation predictions use heuristic fallback, not a validated trained model.")
        if not preds:
            warnings.append("No degradation predictions were produced.")
        return self._result(
            status=status,
            summary=f"{len(preds)} degradation prediction(s).",
            outputs=outputs,
            context=context,
            warnings=warnings,
            tool="deterministic_engine.degradation",
        )


# ══════════════════════════════════════════════════════════════════════
# 7. ADME / Safety
# ══════════════════════════════════════════════════════════════════════

class ADMESafetyModule(ScientificModule):
    module_id = ScientificModuleId.ADME_SAFETY
    title = "ADME / Safety"

    def execute(self, state: CanonicalState, context: ModuleContext) -> ModuleResult:
        view = self._engine_view(state, context)
        admet = [_to_dict(item) for item in view.list("admet_predictions")]
        ad = [_to_dict(item) for item in view.list("applicability_domain_results")]
        penalties = [
            item.get("overall_admet_penalty") for item in admet if item.get("overall_admet_penalty") is not None
        ]
        outputs = {
            "n_admet_predictions": len(admet),
            "max_admet_penalty": max(penalties) if penalties else None,
            "applicability_domain_records": len(ad),
            "outside_domain": sum(
                1 for item in ad if item.get("domain_status") not in {"in_domain", "inside", None}
            ),
        }
        status = TaskStatus.SUCCEEDED if admet else TaskStatus.DEGRADED
        warnings = [] if admet else ["ADME/safety predictions unavailable."]
        return self._result(
            status=status,
            summary=f"{len(admet)} ADMET record(s), {len(ad)} applicability-domain record(s).",
            outputs=outputs,
            context=context,
            warnings=warnings,
            tool="deterministic_engine.admet",
        )


# ══════════════════════════════════════════════════════════════════════
# 8. Resistance / Biomarker
# ══════════════════════════════════════════════════════════════════════

class ResistanceBiomarkerModule(ScientificModule):
    module_id = ScientificModuleId.RESISTANCE_BIOMARKER
    title = "Resistance / Biomarker"

    def execute(self, state: CanonicalState, context: ModuleContext) -> ModuleResult:
        e3 = state.request.e3_ligase
        if not e3:
            ligands = EngineView(state.engine_state).list("selected_e3_ligands") if state.engine_state is not None else []
            if ligands:
                first = _to_dict(ligands[0])
                e3 = str(first.get("e3_ligase") or "")
        profile = context.tools.call(
            "resistance_profile", {"e3_ligase": e3, "target": state.request.target}
        )
        if isinstance(profile, dict) and "_tool_error" in profile:
            return self._result(
                status=TaskStatus.DEGRADED,
                summary="Resistance module unavailable.",
                outputs={"error": profile["_tool_error"]},
                context=context,
                warnings=["Resistance/biomarker evidence not produced."],
                tool="resistance_mechanisms.predict_resistance",
            )
        status = TaskStatus.SUCCEEDED if profile.get("source") else TaskStatus.DEGRADED
        warnings = []
        if profile.get("overall_resistance_risk", 0) and float(profile["overall_resistance_risk"]) >= 0.5:
            warnings.append("Elevated resistance risk for the selected E3 ligase.")
        return self._result(
            status=status,
            summary=f"Resistance risk {profile.get('overall_resistance_risk')} for E3 {e3 or 'unspecified'}.",
            outputs=profile,
            context=context,
            warnings=warnings,
            tool="resistance_mechanisms.predict_resistance",
        )


# ══════════════════════════════════════════════════════════════════════
# 9. Experimental Design
# ══════════════════════════════════════════════════════════════════════

class ExperimentalDesignModule(ScientificModule):
    module_id = ScientificModuleId.EXPERIMENTAL_DESIGN
    title = "Experimental Design"

    def execute(self, state: CanonicalState, context: ModuleContext) -> ModuleResult:
        view = self._engine_view(state, context)
        ranked = view.list("final_ranked_candidates") or view.list("valid_candidates")
        candidate_ids = [
            (item.get("candidate_id") if isinstance(item, dict) else getattr(item, "candidate_id", ""))
            for item in ranked[:6]
        ]
        outputs = {
            "candidate_ids": [cid for cid in candidate_ids if cid],
            "assay_ladder": [
                "compound identity and purity",
                "binary target engagement",
                "tertiary/ternary proximity evidence",
                "cellular degradation dose response",
                "proteasome and E3 dependence controls",
                "selectivity and viability counter-assay",
            ],
            "controls": ["vehicle", "proteasome inhibitor rescue", "E3 competition", "inactive analog"],
            "n_design_candidates": len(candidate_ids),
        }
        status = TaskStatus.SUCCEEDED if candidate_ids else TaskStatus.DEGRADED
        warnings = [] if candidate_ids else ["No candidates available to design experiments around."]
        return self._result(
            status=status,
            summary=f"Experimental ladder for {len(candidate_ids)} candidate(s).",
            outputs=outputs,
            context=context,
            warnings=warnings,
            tool="scientific_contract.experiment_design",
        )


# ══════════════════════════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════════════════════════

MODULE_CLASSES: list[type[ScientificModule]] = [
    TargetDiseaseModule,
    TPDTractabilityModule,
    E3SelectionModule,
    ChemistryWarheadModule,
    StructureTernaryModule,
    DegradationModule,
    ADMESafetyModule,
    ResistanceBiomarkerModule,
    ExperimentalDesignModule,
]


def canonical_modules() -> dict[str, ScientificModule]:
    """Return ``{module_id: module}`` for the nine canonical modules."""
    return {module_cls.module_id.value: module_cls() for module_cls in MODULE_CLASSES}


def module_dependencies() -> dict[str, list[str]]:
    """Declared DAG edges between module ids (node ids == module ids)."""
    ids = [module_cls.module_id.value for module_cls in MODULE_CLASSES]
    target, tractability, e3, chemistry, structure, degradation, adme, resistance, design = ids
    return {
        target: [],
        tractability: [target],
        e3: [target],
        chemistry: [tractability, e3],
        structure: [chemistry],
        degradation: [chemistry, structure],
        adme: [chemistry],
        resistance: [e3],
        design: [degradation, adme, resistance],
    }
