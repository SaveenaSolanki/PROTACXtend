"""PROTACXtend toolbox facade.

This file provides a scientist-facing toolbox organized by PROTAC design task.
The workflow agents can call these methods directly, while production teams can
replace individual methods with validated services, models, or database clients.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence

from synglue_agent.backend.schemas import CandidateRecord, TargetRecord, WorkflowState
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


@dataclass(frozen=True)
class ToolCapability:
    name: str
    layer: str
    status: str
    inputs: str
    outputs: str
    agent: str


class TargetBiologyToolbox:
    def __init__(self, core: ProtacDesignToolbox):
        self.core = core

    def resolve_target_package(self, target_name: str, uniprot_id: str | None = None) -> dict[str, Any]:
        record = self.core.resolve_target(target_name, uniprot_id)
        return {
            "target_record": record,
            "synonym_count": len(record.synonyms),
            "structure_count": len(record.structures),
            "tractability_score": record.tractability_score,
            "online_tools": ["UniProt", "ChEMBL Target", "Open Targets", "PDB", "AlphaFold"],
            "status": "local_curated_with_online_stubs",
        }

    def assess_degradation_tractability(self, target_record: TargetRecord) -> dict[str, Any]:
        score = target_record.tractability_score
        return {
            "target": target_record.gene_symbol,
            "tractability_score": score,
            "drivers": ["known binder count", "structure availability", "target class prior"],
            "status": "deterministic_proxy",
        }


class ComponentToolbox:
    def __init__(self, core: ProtacDesignToolbox):
        self.core = core

    def retrieve_and_rank_warheads(self, target_record: TargetRecord, user_warhead_smiles: str | None = None):
        binders = [] if user_warhead_smiles else self.core.retrieve_known_binders(target_record)
        warheads = self.core.select_warheads(target_record, binders, user_warhead_smiles, max_warheads=12)
        return {"binders": binders, "warheads": warheads, "status": "local_curated_plus_user_input"}

    def compare_e3_ligases(self, e3_ligases: Sequence[str] = ("CRBN", "VHL")) -> dict[str, Any]:
        comparison = {}
        for ligase in e3_ligases:
            ligands = self.core.select_e3_ligands(ligase, max_ligands_per_e3=6)
            comparison[ligase] = {
                "ligand_count": len(ligands),
                "mean_exit_vector_confidence": round(sum(item.exit_vector_confidence for item in ligands) / max(1, len(ligands)), 3),
                "ligands": ligands,
            }
        return comparison

    def enumerate_component_pairs(self, warheads, e3_ligands) -> list[dict[str, Any]]:
        return [
            {
                "warhead": warhead.name,
                "e3_ligand": ligand.name,
                "e3_ligase": ligand.e3_ligase,
                "pair_score": round(0.45 * warhead.exit_vector_confidence + 0.35 * ligand.exit_vector_confidence + 0.20 * warhead.derivatization_score, 3),
            }
            for warhead in warheads
            for ligand in e3_ligands
        ]


class ExitVectorToolbox:
    def __init__(self, core: ProtacDesignToolbox):
        self.core = core

    def enumerate_exit_vector_hypotheses(self, molecules, role: str) -> list[dict[str, Any]]:
        vectors = self.core.detect_exit_vectors(molecules, role)
        hypotheses = []
        for vector in vectors:
            hypotheses.append(
                {
                    "molecule_name": vector.molecule_name,
                    "role": vector.molecule_role,
                    "attachment_smarts": vector.attachment_smarts,
                    "confidence": vector.confidence,
                    "strategy": "curated_marker" if vector.confidence >= 0.7 else "needs_curated_map_or_manual_review",
                    "warning": vector.warning,
                }
            )
        return hypotheses

    def exit_vector_risk_matrix(self, molecules, role: str) -> list[dict[str, Any]]:
        return [
            {
                "molecule": item["molecule_name"],
                "risk": "low" if item["confidence"] >= 0.7 else "high",
                "reason": item["warning"] or "Explicit attachment vector is present.",
            }
            for item in self.enumerate_exit_vector_hypotheses(molecules, role)
        ]


class LinkerDesignToolbox:
    def __init__(self, core: ProtacDesignToolbox):
        self.core = core

    def generate_state_of_the_art_linker_panel(self, linker_types: Sequence[str], max_linkers: int = 96):
        curated = self.core.generate_linkers(linker_types, max_linkers=max_linkers)
        rule_based = self.core.generate_rule_based_linkers(linker_types, max_linkers=max_linkers)
        merged = self.core.remove_duplicate_linkers(list(curated) + list(rule_based))
        return merged[:max_linkers]

    def score_linker_conformation(self, linker_smiles: str) -> dict[str, Any]:
        props = self.core.compute_basic_properties(linker_smiles)
        rotors = props.get("rotatable_bonds", 0)
        flexibility = min(1.0, float(rotors) / 14.0)
        return {
            "rotatable_bonds": rotors,
            "flexibility_score": round(flexibility, 3),
            "reachability_prior": round(max(0.0, 1.0 - abs(float(rotors) - 8.0) / 14.0), 3),
            "status": "deterministic_geometry_proxy",
        }

    def propose_property_matched_replacements(self, parent_linker_class: str) -> list[dict[str, Any]]:
        replacements = self.core.generate_linkers([parent_linker_class, "PEG", "alkyl", "triazole", "piperazine"], max_linkers=20)
        return [
            {
                "name": linker.name,
                "smiles": linker.smiles,
                "class": linker.linker_class,
                "synthetic_feasibility_proxy": linker.synthetic_feasibility_proxy,
                "property_delta_goal": "reduce TPSA/rotors or improve reachability",
            }
            for linker in replacements
        ]


class ConstructionStrategyToolbox:
    def __init__(self, core: ProtacDesignToolbox):
        self.core = core

    def enumerate_construction_strategies(self) -> list[dict[str, str]]:
        return [
            {"strategy": "curated_template", "use": "known attachment chemistry and curated handles"},
            {"strategy": "reaction_smarts", "use": "validated RDKit reaction SMARTS when installed"},
            {"strategy": "brics_recap", "use": "fragment-aware recombination and linker recovery"},
            {"strategy": "known_linker_grafting", "use": "PROTAC-DB/PROTACpedia linker transfer"},
            {"strategy": "matched_linker_replacement", "use": "MMP-inspired property-preserving linker swaps"},
            {"strategy": "generative_linker_conditioned", "use": "plug-in LinkInvent/Reinvent/DiffLinker-style model"},
            {"strategy": "retrosynthesis_aware", "use": "route-score filter or ASKCOS/Manifold/IBM RXN wrapper"},
        ]

    def construct_with_all_strategies(self, warheads, e3_ligands, linkers, target_record, candidate_count: int, use_retrosynthesis: bool):
        return self.core.construct_protac_candidates(warheads, e3_ligands, linkers, target_record, candidate_count, use_retrosynthesis)

    def diagnose_failures(self, attempts) -> dict[str, int]:
        summary: dict[str, int] = {}
        for attempt in attempts:
            if attempt.success:
                continue
            key = attempt.failure_category or "unknown"
            summary[key] = summary.get(key, 0) + 1
        return summary


class PredictionAndADMETToolbox:
    def __init__(self, core: ProtacDesignToolbox):
        self.core = core

    def run_prediction_stack(self, candidates, target_record):
        degradation = self.core.predict_degradation(candidates, target_record)
        admet = self.core.predict_admet(candidates)
        domain = self.core.compute_applicability_domain(candidates)
        return {"degradation": degradation, "admet": admet, "domain": domain, "model_status": "heuristic_demo_replace_with_syn_glue"}

    def protac_aware_prefilter(self, candidates: Sequence[CandidateRecord], max_tpsa: float | None = None) -> list[CandidateRecord]:
        retained = []
        for candidate in candidates:
            props = self.core.compute_basic_properties(candidate.full_protac_smiles)
            if max_tpsa and props.get("tpsa", 0) > max_tpsa:
                candidate.warning_flags.append("tpsa_preference_penalty")
            retained.append(candidate)
        return retained

    def estimate_permeability_solubility_balance(self, candidate: CandidateRecord) -> dict[str, Any]:
        props = self.core.compute_basic_properties(candidate.full_protac_smiles)
        permeability = max(0.0, min(1.0, 0.65 - props.get("tpsa", 0) / 350.0 + props.get("logp", 0) / 8.0))
        solubility = max(0.0, min(1.0, 0.70 - props.get("logp", 0) / 7.0 - max(0, props.get("mw", 0) - 850) / 900.0))
        return {"permeability_proxy": round(permeability, 3), "solubility_proxy": round(solubility, 3)}


class TernaryComplexToolbox:
    def __init__(self, core: ProtacDesignToolbox):
        self.core = core

    def triage_ternary_complex(self, candidates, target_record):
        return self.core.assess_ternary_feasibility(candidates, target_record)

    def docking_workflow_plan(self) -> list[dict[str, str]]:
        return [
            {"stage": "pose sourcing", "tool": "PDB/AlphaFold plus ligand-bound homologs"},
            {"stage": "binary docking", "tool": "DiffDock/GNINA/AutoDock Vina wrapper"},
            {"stage": "ternary docking", "tool": "HADDOCK/MEGADOCK/LightDock wrapper"},
            {"stage": "interface scoring", "tool": "PRODIGY-like buried surface and complementarity scoring"},
            {"stage": "MD refinement", "tool": "optional OpenMM/Gromacs ensemble relaxation"},
        ]


class ReviewAndEvolutionToolbox:
    def __init__(self, core: ProtacDesignToolbox):
        self.core = core

    def run_meta_review(self, state: WorkflowState) -> dict[str, Any]:
        reviews = self.core.critique_candidates(
            state.final_ranked_candidates or state.valid_candidates[:20],
            state.ranking_results,
            state.degradation_predictions,
            state.admet_predictions,
            state.novelty_results,
        )
        return {
            "reviews": reviews,
            "review_count": len(reviews),
            "high_risk_count": sum(1 for review in reviews if review.risk_score > 0.3),
        }

    def propose_active_learning_next_tests(self, state: WorkflowState) -> list[dict[str, str]]:
        top_ids = [ranking.candidate_id for ranking in state.ranking_results[:5]]
        return [
            {"candidate_id": candidate_id, "next_test": "cellular DC50/Dmax assay with matched target expression context"}
            for candidate_id in top_ids
        ]

    def human_checkpoint_packet(self, state: WorkflowState) -> dict[str, Any]:
        return {
            "requires_human_review": True,
            "review_roles": ["medicinal chemistry", "cheminformatics", "structural biology", "DMPK/Tox"],
            "candidate_count": len(state.final_ranked_candidates or state.valid_candidates),
            "critical_warnings": state.warnings + state.errors,
        }


class ProtacXtendToolbox:
    """Facade that exposes the state-of-the-art PROTAC toolbox to agents."""

    def __init__(self, core: ProtacDesignToolbox | None = None):
        self.core = core or ProtacDesignToolbox()
        self.target = TargetBiologyToolbox(self.core)
        self.components = ComponentToolbox(self.core)
        self.exit_vectors = ExitVectorToolbox(self.core)
        self.linkers = LinkerDesignToolbox(self.core)
        self.construction = ConstructionStrategyToolbox(self.core)
        self.prediction = PredictionAndADMETToolbox(self.core)
        self.ternary = TernaryComplexToolbox(self.core)
        self.review = ReviewAndEvolutionToolbox(self.core)

    def capability_catalog(self) -> list[ToolCapability]:
        return [
            ToolCapability("Target resolver and tractability", "perception", "local plus online stubs", "target name, UniProt, disease", "resolved target, structures, tractability", "TargetResolverAgent"),
            ToolCapability("Binder retrieval and warhead ranking", "perception/computation", "local plus API stubs", "target, activity threshold", "binders, warheads, potency and exit-vector confidence", "BinderAgent/WarheadAgent"),
            ToolCapability("E3 ligand comparison", "computation", "local curated", "CRBN/VHL/IAP/MDM2", "E3 ligands, handle confidence, diversity", "E3Agent"),
            ToolCapability("Exit-vector hypothesis engine", "computation", "deterministic rules", "warhead/E3 SMILES", "attachment hypotheses and risk matrix", "ExitVectorAgent"),
            ToolCapability("State-of-the-art linker panel", "computation/generation", "curated plus rule-based", "linker classes and constraints", "PEG, alkyl, triazole, piperazine, amide, rigid, mixed polar linkers", "LinkerAgent"),
            ToolCapability("Multi-strategy PROTAC construction", "action", "deterministic with RDKit hooks", "components and linker", "assembled candidates, failures, provenance", "ConstructionAgent"),
            ToolCapability("SynGlue DC50/Dmax stack", "computation", "heuristic stub", "candidate and components", "DC50, Dmax, confidence, model version", "PredictionAgent"),
            ToolCapability("PROTAC-aware ADME/Tox", "computation", "heuristic stub", "candidate SMILES", "MW, TPSA, logP, hERG, AMES, DILI, CYP, P-gp, solubility", "ADMETAgent"),
            ToolCapability("Novelty and duplicate checker", "memory/computation", "local known set", "candidate SMILES", "nearest known PROTAC, similarity, novelty", "NoveltyAgent"),
            ToolCapability("Ternary feasibility triage", "computation", "geometry proxy plus docking stubs", "top candidates and structures", "reachability, ternary plausibility, docking plan", "TernaryAgent"),
            ToolCapability("Tournament ranking", "computation", "weighted deterministic", "all scores and constraints", "rank, tier, penalties, uncertainty", "RankingAgent"),
            ToolCapability("Reflection and evolution", "review/action", "deterministic critique", "top candidates and warnings", "review score, refinements, active-learning tests", "Reflection/EvolutionAgent"),
            ToolCapability("Human review checkpoint", "safety", "policy rules", "final candidates", "review packet and required expert roles", "SafetyAgent"),
        ]

    def catalog_as_rows(self) -> list[dict[str, str]]:
        return [capability.__dict__ for capability in self.capability_catalog()]


ProtacAutopilotToolbox = ProtacXtendToolbox
