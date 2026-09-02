"""Warhead selection agent — selects warheads from library or user input."""

from __future__ import annotations
from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WarheadRecord, WorkflowState

class WarheadSelectionAgent(ReActAgent):
    name = "WarheadSelectionAgent"
    thought = "Select warhead molecules from curated library or provided smiles."
    action = "select_warheads"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        objective = state.parsed_objective
        warheads = []

        # 1. If user provided a warhead SMILES, use it
        if objective.warhead_smiles:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(objective.warhead_smiles)
            valid = "valid" if mol else "invalid"
            record = WarheadRecord(
                name=objective.warhead_smiles[:20],
                target=objective.target_name or "custom",
                smiles=objective.warhead_smiles,
                source="user_provided",
                potency_score=0.5,
                derivatization_score=0.5,
                exit_vector_confidence=0.3,
                source_confidence=0.8,
                chemical_validity=valid,
            )
            warheads.append(record)

        # 2. Also check curated library for known binders to this target
        curated = self.toolbox.load_curated_warheads()
        target_upper = (objective.target_name or "").upper()
        for row in curated:
            row_target = (row.get("target", "") or "").upper()
            row_name = (row.get("name", "") or "")
            if target_upper and target_upper in row_target:
                from rdkit import Chem
                smiles = row.get("smiles", "")
                mol = Chem.MolFromSmiles(smiles) if smiles else None
                record = WarheadRecord(
                    name=row_name or row.get("name", "unknown"),
                    target=row.get("target", objective.target_name or ""),
                    smiles=smiles,
                    source=row.get("source", "curated"),
                    potency_score=0.6,
                    derivatization_score=0.5,
                    exit_vector_confidence=0.4,
                    source_confidence=0.7,
                    chemical_validity="valid" if mol else "invalid",
                )
                # Avoid duplicates with user-provided
                if not any(w.smiles == record.smiles for w in warheads):
                    warheads.append(record)

        # 3. If no warheads found, add demo warheads from curated list
        if not warheads:
            for row in curated[:5]:
                smiles = row.get("smiles", "")
                from rdkit import Chem
                mol = Chem.MolFromSmiles(smiles) if smiles else None
                record = WarheadRecord(
                    name=row.get("name", f"warhead_{row.get('id', 'demo')}"),
                    target=row.get("target", objective.target_name or "unknown"),
                    smiles=smiles,
                    source=row.get("source", "curated_demo"),
                    potency_score=0.4,
                    derivatization_score=0.4,
                    exit_vector_confidence=0.3,
                    source_confidence=0.5,
                    chemical_validity="valid" if mol else "invalid",
                )
                warheads.append(record)
            state.warnings.append("No target-matched warheads found. Included demo warheads for demonstration.")

        state.selected_warheads = warheads
        return state

    def _observation(self, state: WorkflowState) -> str:
        wh = state.selected_warheads
        valid = sum(1 for w in wh if w.chemical_validity == "valid")
        return f"warheads={len(wh)}, valid={valid}"
