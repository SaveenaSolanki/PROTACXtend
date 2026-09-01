"""Exit-vector detection agent — identifies linker attachment points on warheads and E3 ligands."""

from __future__ import annotations
from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import ExitVectorRecord, WorkflowState
from synglue_agent.tools.rdkit_chemistry import detect_exit_vector_atoms

class ExitVectorDetectionAgent(ReActAgent):
    name = "ExitVectorDetectionAgent"
    thought = "Detect suitable linker attachment points on warhead and E3 ligand molecules."
    action = "detect_exit_vectors"

    @staticmethod
    def _atom_index(atom_record) -> int | None:
        if isinstance(atom_record, dict):
            value = atom_record.get("atom_index")
        else:
            value = atom_record
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _execute(self, state: WorkflowState) -> WorkflowState:
        vectors = []

        # 1. Detect exit vectors on warheads
        for warhead in state.selected_warheads:
            result = detect_exit_vector_atoms(warhead.smiles)
            if result.get("success"):
                for atom_record in result.get("exit_vector_atoms", [])[:3]:
                    atom_idx = self._atom_index(atom_record)
                    if atom_idx is None:
                        continue
                    vectors.append(ExitVectorRecord(
                        molecule_name=warhead.name,
                        molecule_role="warhead",
                        smiles=warhead.smiles,
                        attachment_atom_index=atom_idx,
                        attachment_smarts=f"[*:1]",
                        confidence=result.get("confidence", 0.5),
                        rationale=f"Detected exit vector at atom {atom_idx}",
                    ))
            else:
                vectors.append(ExitVectorRecord(
                    molecule_name=warhead.name,
                    molecule_role="warhead",
                    smiles=warhead.smiles,
                    confidence=0.0,
                    rationale="Fallback: no exit vector detected algorithmically",
                    warning=result.get("error", "detection failed"),
                ))

        # 2. Detect exit vectors on E3 ligands
        for ligand in state.selected_e3_ligands:
            result = detect_exit_vector_atoms(ligand.smiles)
            if result.get("success"):
                for atom_record in result.get("exit_vector_atoms", [])[:3]:
                    atom_idx = self._atom_index(atom_record)
                    if atom_idx is None:
                        continue
                    vectors.append(ExitVectorRecord(
                        molecule_name=ligand.name,
                        molecule_role="e3_ligand",
                        smiles=ligand.smiles,
                        attachment_atom_index=atom_idx,
                        attachment_smarts=f"[*:2]",
                        confidence=result.get("confidence", 0.5),
                        rationale=f"Detected exit vector at atom {atom_idx}",
                    ))
            else:
                vectors.append(ExitVectorRecord(
                    molecule_name=ligand.name,
                    molecule_role="e3_ligand",
                    smiles=ligand.smiles,
                    confidence=0.0,
                    rationale="Fallback: no exit vector detected",
                    warning=result.get("error", "detection failed"),
                ))

        state.exit_vectors = vectors
        
        if not vectors:
            state.warnings.append("ExitVectorDetectionAgent: No exit vectors detected for any molecule.")
        
        return state

    def _observation(self, state: WorkflowState) -> str:
        warhead_vecs = sum(1 for v in state.exit_vectors if v.molecule_role == "warhead")
        e3_vecs = sum(1 for v in state.exit_vectors if v.molecule_role == "e3_ligand")
        return f"warhead_vectors={warhead_vecs}, e3_vectors={e3_vecs}"
