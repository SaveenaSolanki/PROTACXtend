"""Ternary feasibility agent with full docking → P4ward pipeline.

This agent orchestrates the complete structure-aware pipeline:
  POI PDB + Warhead SMILES
    → Receptor preparation (strip non-ATOM lines)
    → Warhead 3D generation (OpenBabel)
    → Vina docking
    → Exit vector detection
    → MOL2 export for P4ward
    → P4ward ternary complex modeling
    → Lysine accessibility check
    → Failure diagnosis (if no complexes form)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import WorkflowState, CandidateRecord
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox

logger = logging.getLogger("protacpilot.ternary_agent")

# Try importing the docking pipeline
try:
    from synglue_agent.tools.docking_pipeline import (
        dock_and_prepare_for_p4ward,
        run_docking_pipeline,
        DockingPose,
        ExitVector,
        LigandMol2Set,
    )
    DOCKING_AVAILABLE = True
except ImportError as e:
    DOCKING_AVAILABLE = False
    logger.warning(f"Docking pipeline not available: {e}")

# Try importing the P4ward wrapper
try:
    from synglue_agent.tools.p4ward_wrapper import P4wardWrapper
    P4WARD_AVAILABLE = True
except ImportError as e:
    P4WARD_AVAILABLE = False
    logger.warning(f"P4ward wrapper not available: {e}")


class TernaryFeasibilityAgent(ReActAgent):
    """Assess ternary complex feasibility via docking + P4ward.

    Workflow when structure-aware ranking is enabled:
      1. Run warhead docking (Vina) → docked poses + exit vectors
      2. Export MOL2 files for P4ward
      3. Run P4ward ternary complex modeling
      4. Analyze lysine accessibility
      5. Diagnose failures if no complexes form

    Falls back to geometry-proxy scoring when docking/P4ward unavailable.
    """

    name = "TernaryFeasibilityAgent"
    thought = "Evaluate ternary complex formation via docking → P4ward pipeline."
    action = "assess_ternary_feasibility"

    def __init__(self, toolbox: Optional[ProtacDesignToolbox] = None):
        super().__init__(toolbox=toolbox)
        self._docking_result: Optional[Dict[str, Any]] = None
        self._p4ward_result: Optional[Any] = None
        self._mol2_set: Optional[LigandMol2Set] = None
        self._pipeline_mode: str = "none"

    # -----------------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------------

    def _execute(self, state: WorkflowState) -> WorkflowState:
        if not state.parsed_objective.use_structure_aware_ranking:
            logger.info("Structure-aware ranking not requested. Running finalist geometry proxy only.")
            return self._run_geometry_fallback(state)

        # Determine which tools are available
        can_dock = DOCKING_AVAILABLE and self._vina_available()
        can_p4ward = P4WARD_AVAILABLE and self._p4ward_available()

        if can_dock and can_p4ward:
            self._pipeline_mode = "full_docking_p4ward"
            logger.info("Full docking → P4ward pipeline enabled.")
            state = self._run_full_pipeline(state)
        elif can_dock and not can_p4ward:
            self._pipeline_mode = "docking_only"
            logger.info("Docking available but P4ward not. Running docking + exit vectors only.")
            state = self._run_docking_only(state)
        else:
            self._pipeline_mode = "geometry_proxy"
            logger.info("Neither docking nor P4ward available. Using geometry-proxy fallback.")
            state = self._run_geometry_fallback(state)

        return state

    # -----------------------------------------------------------------------
    # Full docking → P4ward pipeline
    # -----------------------------------------------------------------------

    def _run_full_pipeline(self, state: WorkflowState) -> WorkflowState:
        """Run complete docking → MOL2 → P4ward pipeline."""
        # 1. Extract inputs from workflow state
        receptor_pdb = self._get_target_pdb(state)
        warhead_smiles = state.parsed_objective.warhead_smiles
        e3_name = (state.parsed_objective.e3_ligase or "CRBN").upper()
        protac_smiles_list = self._collect_protac_smiles(state)

        if not receptor_pdb:
            logger.warning("No target PDB available. Cannot run docking.")
            state.warnings.append("No target PDB structure available for docking.")
            return self._run_geometry_fallback(state)

        if not warhead_smiles:
            logger.warning("No warhead SMILES available. Cannot run docking.")
            state.warnings.append("No warhead SMILES available for docking.")
            return self._run_geometry_fallback(state)

        # 2. Run docking → get MOL2 files
        output_dir = Path(
            os.environ.get("PROTACPILOT_WORK_DIR", str(Path.cwd()))
        ) / "docking_p4ward" / "run"

        logger.info("Step 1/3: Docking warhead to POI...")
        docking = dock_and_prepare_for_p4ward(
            receptor_pdb=receptor_pdb,
            warhead_smiles=warhead_smiles,
            e3_name=e3_name,
            protac_smiles_list=protac_smiles_list,
            output_dir=str(output_dir),
            fast=True,
        )
        self._docking_result = docking.get("docking_result")

        if self._docking_result.get("status") != "completed":
            logger.warning(
                f"Docking failed: {self._docking_result.get('error', 'unknown')}. "
                "Falling back to geometry proxy."
            )
            state.warnings.append(
                f"Warhead docking failed: {self._docking_result.get('error', 'unknown')}. "
                "Using geometry-based ternary feasibility scoring."
            )
            return self._run_geometry_fallback(state)

        best_pose = self._docking_result.get("best_pose")
        ev = self._docking_result.get("exit_vector")
        mol2_set = self._docking_result.get("mol2_set")
        self._mol2_set = mol2_set

        if best_pose:
            logger.info(
                f"Docking found {len(self._docking_result.get('poses', []))} poses. "
                f"Best: {best_pose.affinity_kcal_mol:.2f} kcal/mol"
            )
        if ev:
            logger.info(
                f"Exit vector: atom {ev.atom_index} ({ev.atom_symbol}), "
                f"solvent accessibility={ev.solvent_accessibility:.2f}"
            )

        # 3. Run P4ward with the MOL2 files
        logger.info("Step 2/3: Running P4ward ternary complex modeling...")

        if not mol2_set or not mol2_set.receptor_ligand_mol2 or not mol2_set.ligase_ligand_mol2:
            logger.warning("MOL2 files not available from docking. Cannot run P4ward.")
            state.warnings.append("MOL2 files not generated from docking. Skipping P4ward.")
            return self._run_geometry_fallback(state)

        # Group PROTAC SMILES by linker type for P4ward screening
        protac_by_linker = self._group_protacs_by_linker(state, protac_smiles_list)

        p4ward = self._get_p4ward_wrapper()
        try:
            results = p4ward.multi_linker_screen(
                receptor_pdb=mol2_set.receptor_pdb,
                ligase_pdb=mol2_set.ligase_pdb,
                receptor_ligand_mol2=mol2_set.receptor_ligand_mol2,
                ligase_ligand_mol2=mol2_set.ligase_ligand_mol2,
                protac_smiles_by_linker=protac_by_linker,
                e3=e3_name,
                output_dir=str(output_dir / "p4ward"),
                config_mode="fast",
            )
            self._p4ward_result = results
        except Exception as e:
            logger.error(f"P4ward run failed: {e}")
            state.warnings.append(f"P4ward failed: {e}. Using docking-only results.")
            results = {}

        # 4. Translate results into workflow state
        logger.info("Step 3/3: Analyzing results...")
        state.ternary_feasibility_results = self._build_ternary_results(
            results, best_pose, ev, mol2_set
        )

        # 5. Add failure diagnosis if needed
        if not state.ternary_feasibility_results:
            diagnosis = self._diagnose_failure(docking)
            state.warnings.append(diagnosis)
            logger.warning(diagnosis)

        # 6. Store docking metadata for downstream agents
        self._store_docking_metadata(state, best_pose, ev)

        return state

    # -----------------------------------------------------------------------
    # Docking-only mode (no P4ward)
    # -----------------------------------------------------------------------

    def _run_docking_only(self, state: WorkflowState) -> WorkflowState:
        """Run just the docking and exit vector analysis without P4ward."""
        receptor_pdb = self._get_target_pdb(state)
        warhead_smiles = state.parsed_objective.warhead_smiles
        e3_name = (state.parsed_objective.e3_ligase or "CRBN").upper()

        if not receptor_pdb or not warhead_smiles:
            return self._run_geometry_fallback(state)

        output_dir = Path(
            os.environ.get("PROTACPILOT_WORK_DIR", str(Path.cwd()))
        ) / "docking_only"

        docking = run_docking_pipeline(
            receptor_pdb=receptor_pdb,
            warhead_smiles=warhead_smiles,
            e3_name=e3_name,
            output_dir=str(output_dir),
            fast=True,
        )

        self._docking_result = docking

        if docking.get("status") == "completed":
            best_pose = docking.get("best_pose")
            ev = docking.get("exit_vector")
            state.ternary_feasibility_results = [{
                "candidate_id": "docking_only",
                "method": "docking",
                "pose_affinity_kcal_mol": best_pose.affinity_kcal_mol if best_pose else None,
                "num_poses": len(docking.get("poses", [])),
                "exit_vector_atom": ev.atom_index if ev else None,
                "exit_vector_solvent_accessibility": ev.solvent_accessibility if ev else None,
                "docking_status": "completed",
            }]
            self._store_docking_metadata(state, best_pose, ev)
            logger.info(
                f"Docking completed: {len(docking.get('poses', []))} poses, "
                f"best={best_pose.affinity_kcal_mol if best_pose else 'N/A'} kcal/mol"
            )
        else:
            state.warnings.append(
                f"Docking failed: {docking.get('error', 'unknown')}. "
                "Using geometry-proxy fallback."
            )
            return self._run_geometry_fallback(state)

        return state

    # -----------------------------------------------------------------------
    # Geometry-proxy fallback
    # -----------------------------------------------------------------------

    def _run_geometry_fallback(self, state: WorkflowState) -> WorkflowState:
        """Fallback: fast geometry and linker reachability scoring."""
        budget = getattr(state.search_policy, "expensive_modeling_budget", 12)
        ranking_ids = list(state.expensive_modeling_candidate_ids) or [
            r.candidate_id for r in state.ranking_results[: min(budget, len(state.ranking_results))]
        ]
        top_candidates = [
            c for c in state.valid_candidates if c.candidate_id in ranking_ids
        ]
        state.ternary_feasibility_results = self.toolbox.assess_ternary_feasibility(
            top_candidates, state.target_record, top_n=budget
        )

        # Mark as geometry proxy
        for r in state.ternary_feasibility_results:
            if isinstance(r, dict):
                r["method"] = "geometry_proxy"
            elif hasattr(r, "_asdict"):
                d = r._asdict()
                d["method"] = "geometry_proxy"

        if not state.ternary_feasibility_results:
            state.warnings.append(
                "Ternary feasibility fallback: no results. "
                "Geometry proxy could not assess candidates."
            )

        return state

    # -----------------------------------------------------------------------
    # Input helpers
    # -----------------------------------------------------------------------

    def _get_target_pdb(self, state: WorkflowState) -> str:
        """Get the target protein PDB path from workflow state or env."""
        # Check environment override
        env_pdb = os.environ.get("PROTACPILOT_TARGET_PDB", "")
        if env_pdb and os.path.exists(env_pdb):
            return env_pdb

        # Check from workflow state
        if state.target_record:
            for f in getattr(state.target_record, "structures", []):
                if f.endswith(".pdb") and os.path.exists(f):
                    return f
            for f in getattr(state.target_record, "structure_files", []):
                if f.endswith(".pdb") and os.path.exists(f):
                    return f

        # Check standard locations
        uniprot = state.parsed_objective.target_uniprot_id
        if uniprot:
            candidates = [
                f"/tmp/{uniprot.lower()}.pdb",
                f"/storage/proteins/{uniprot}.pdb",
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        return ""

    def _get_e3_pdb(self, state: WorkflowState) -> str:
        """Get the E3 ligase PDB path."""
        e3_name = (state.parsed_objective.e3_ligase or "CRBN").upper()
        pdb_map = {"CRBN": "4CI3", "VHL": "4W9H"}
        pdb_id = pdb_map.get(e3_name, "4CI3")

        # Check env override
        env_dir = os.environ.get("PROTACPILOT_PDB_DIR", "")
        if env_dir:
            pdb_path = Path(env_dir) / f"{pdb_id}.pdb"
            if pdb_path.exists():
                return str(pdb_path)

        # Check common locations
        for loc in ["/tmp", "/storage/pdb"]:
            pdb_path = Path(loc) / f"{pdb_id}.pdb"
            if pdb_path.exists():
                return str(pdb_path)

        # Return identifier for P4ward to handle
        return f"{pdb_id}.pdb"

    def _collect_protac_smiles(self, state: WorkflowState) -> List[str]:
        """Collect all PROTAC SMILES from candidates."""
        smiles_set = set()
        finalist_ids = set(state.expensive_modeling_candidate_ids or [])
        for c in state.valid_candidates:
            if finalist_ids and c.candidate_id not in finalist_ids:
                continue
            smi = getattr(c, "full_protac_smiles", "") or self._build_protac_smiles(c)
            if smi and smi not in smiles_set:
                smiles_set.add(smi)
        return list(smiles_set)

    def _group_protacs_by_linker(
        self, state: WorkflowState, protac_smiles: List[str]
    ) -> Dict[str, List[str]]:
        """Group PROTAC SMILES by linker type for P4ward screening."""
        linker_map: Dict[str, List[str]] = {}

        # Map candidate SMILES back to their linker types
        finalist_ids = set(state.expensive_modeling_candidate_ids or [])
        for c in state.valid_candidates:
            if finalist_ids and c.candidate_id not in finalist_ids:
                continue
            smi = getattr(c, "full_protac_smiles", "") or self._build_protac_smiles(c)
            if smi and smi in protac_smiles:
                linker_key = "custom"
                if c.linker_smiles:
                    # Extract linker length as key
                    length = len(c.linker_smiles.replace("[*:1]", "").replace("[*:2]", "").strip())
                    linker_key = f"linker_{length}atoms"
                if linker_key not in linker_map:
                    linker_map[linker_key] = []
                if smi not in linker_map[linker_key]:
                    linker_map[linker_key].append(smi)

        # If no linker info, put all in one group
        if not linker_map:
            linker_map["all_candidates"] = protac_smiles

        return linker_map

    def _build_protac_smiles(self, candidate: CandidateRecord) -> Optional[str]:
        """Build a full PROTAC SMILES from component parts."""
        if getattr(candidate, "full_protac_smiles", ""):
            return candidate.full_protac_smiles

        parts = []
        if candidate.warhead_smiles:
            parts.append(candidate.warhead_smiles)
        if candidate.linker_smiles:
            parts.append(candidate.linker_smiles.replace("[*:1]", "").replace("[*:2]", ""))
        if candidate.e3_ligand_smiles:
            parts.append(candidate.e3_ligand_smiles)

        return "".join(parts) if len(parts) >= 3 else None

    # -----------------------------------------------------------------------
    # Result builders
    # -----------------------------------------------------------------------

    def _build_ternary_results(
        self,
        p4ward_results: Dict[str, Any],
        best_pose: Optional[Any],
        exit_vector: Optional[Any],
        mol2_set: Optional[LigandMol2Set],
    ) -> List[Dict[str, Any]]:
        """Build workflow state results from P4ward output."""
        results = []

        # Add P4ward results
        if p4ward_results:
            for linker_label, run_result in p4ward_results.items():
                for tc in getattr(run_result, "top_complexes", []):
                    results.append({
                        "candidate_id": f"p4ward_{linker_label}_rank{tc.rank}",
                        "linker_label": linker_label,
                        "score": tc.score,
                        "accessible_lysines": tc.accessible_lysines,
                        "is_feasible": tc.is_feasible,
                        "interface_score": tc.interface_score,
                        "linker_strain": tc.linker_strain,
                        "method": "p4ward",
                        "p4ward_status": run_result.status,
                    })

                # Add diagnosis from P4ward
                if run_result.warnings:
                    for w in run_result.warnings:
                        results.append({
                            "candidate_id": f"diagnosis_{linker_label}",
                            "linker_label": linker_label,
                            "method": "p4ward_diagnosis",
                            "warning": w,
                        })

        # Add docking info as a result entry
        if best_pose:
            results.insert(0, {
                "candidate_id": "docking_summary",
                "method": "docking",
                "best_affinity_kcal_mol": best_pose.affinity_kcal_mol,
                "num_docking_poses": len(self._docking_result.get("poses", [])) if self._docking_result else 0,
                "docking_status": self._docking_result.get("status") if self._docking_result else "unknown",
            })

        if exit_vector:
            results.insert(0, {
                "candidate_id": "exit_vector",
                "method": "exit_vector_analysis",
                "exit_vector_atom": exit_vector.atom_index,
                "exit_vector_element": exit_vector.atom_symbol,
                "exit_vector_solvent_accessibility": exit_vector.solvent_accessibility,
                "exit_vector_direction": list(exit_vector.vector_direction),
                "exit_vector_distance_to_surface": exit_vector.distance_to_protein_surface,
            })

        return results

    def _diagnose_failure(self, docking: Dict[str, Any]) -> str:
        """Generate a diagnosis when no ternary complexes are found."""
        reasons = []
        recommendations = []

        docking_status = docking.get("docking_result", {}).get("status", "unknown")
        if docking_status != "completed":
            reasons.append(f"Docking failed: {docking.get('docking_result', {}).get('error', 'unknown')}")
            recommendations.append("Check warhead SMILES validity and POI PDB structure quality.")

        mol2_set = docking.get("docking_result", {}).get("mol2_set")
        if not mol2_set:
            reasons.append("MOL2 files were not generated from docking.")
            recommendations.append("Ensure warhead and E3 ligand structures are available.")

        if not reasons:
            reasons = [
                "P4ward did not produce valid ternary complexes.",
                "Possible causes: linker too short, wrong exit vector, "
                "or incompatible POI-E3 protein-protein interface.",
            ]
            recommendations = [
                "Try longer linkers (C10–C14 PEG or alkyl-PEG mixed).",
                "Try switching E3 ligase (CRBN ↔ VHL).",
                "Check if the warhead exit vector is pointing toward solvent.",
                "Consider using unbound (apo) protein structures.",
            ]

        diagnosis = " | ".join(reasons)
        diagnosis += " Recommended: " + " ".join(recommendations)

        return diagnosis

    # -----------------------------------------------------------------------
    # Metadata storage
    # -----------------------------------------------------------------------

    def _store_docking_metadata(
        self,
        state: WorkflowState,
        best_pose: Optional[Any],
        exit_vector: Optional[Any],
    ):
        """Store docking metadata for downstream agents (e.g., report, reflection)."""
        # This method stores docking info in a location accessible to
        # downstream agents. We store it in the design_plan dict for now.
        if "docking_metadata" not in state.design_plan:
            state.design_plan["docking_metadata"] = {}

        if best_pose:
            state.design_plan["docking_metadata"]["best_affinity_kcal_mol"] = \
                best_pose.affinity_kcal_mol
            state.design_plan["docking_metadata"]["num_poses"] = \
                len(self._docking_result.get("poses", [])) if self._docking_result else 0

        if exit_vector:
            state.design_plan["docking_metadata"]["exit_vector_atom"] = exit_vector.atom_index
            state.design_plan["docking_metadata"]["exit_vector_solvent_accessibility"] = \
                exit_vector.solvent_accessibility

        if self._mol2_set:
            state.design_plan["docking_metadata"]["mol2_receptor_ligand"] = \
                self._mol2_set.receptor_ligand_mol2
            state.design_plan["docking_metadata"]["mol2_ligase_ligand"] = \
                self._mol2_set.ligase_ligand_mol2

    # -----------------------------------------------------------------------
    # Tool availability checks
    # -----------------------------------------------------------------------

    def _vina_available(self) -> bool:
        """Check if Vina is installed."""
        import shutil
        return shutil.which("vina") is not None

    def _p4ward_available(self) -> bool:
        """Check if P4ward is available."""
        try:
            p4ward = self._get_p4ward_wrapper()
            return p4ward is not None
        except Exception:
            return False

    def _get_p4ward_wrapper(self) -> Optional[P4wardWrapper]:
        """Get or create a P4wardWrapper instance."""
        if hasattr(self, "_p4ward_wrapper") and self._p4ward_wrapper:
            return self._p4ward_wrapper

        try:
            mode = os.environ.get("PROTACPILOT_P4WARD_MODE", "docker")
            image = os.environ.get("PROTACPILOT_P4WARD_IMAGE", "paulajlr/p4ward:latest")
            p4ward_path = os.environ.get("PROTACPILOT_P4WARD_PATH", None)
            num_cpus = int(os.environ.get("PROTACPILOT_P4WARD_CPU", "8"))

            self._p4ward_wrapper = P4wardWrapper(
                mode=mode,
                docker_image=image,
                p4ward_path=Path(p4ward_path) if p4ward_path else None,
                num_processors=num_cpus,
            )
            return self._p4ward_wrapper
        except Exception as e:
            logger.debug(f"P4ward not available: {e}")
            return None

    # -----------------------------------------------------------------------
    # Reporting
    # -----------------------------------------------------------------------

    def _observation(self, state: WorkflowState) -> str:
        mode = self._pipeline_mode
        n_results = len(state.ternary_feasibility_results)

        if self._docking_result:
            best_pose = self._docking_result.get("best_pose")
            affinity = f"{best_pose.affinity_kcal_mol:.1f}" if best_pose else "N/A"
        else:
            affinity = "N/A"

        feasible = sum(
            1 for r in state.ternary_feasibility_results
            if isinstance(r, dict) and r.get("is_feasible")
        )

        return (
            f"mode={mode}, n_results={n_results}, "
            f"affinity={affinity}, feasible={feasible}"
        )
