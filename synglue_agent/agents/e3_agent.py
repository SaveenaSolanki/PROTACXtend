"""E3 ligase selection agent — selects E3 ligase and ligand from library."""

from __future__ import annotations
from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import E3LigandRecord, WorkflowState

E3_SUBCELLULAR = {
    "CRBN": {"nuclear": True, "cytoplasmic": True, "importin": "KPNB1"},
    "VHL": {"nuclear": False, "cytoplasmic": True, "importin": None},
    "DCAF1": {"nuclear": True, "cytoplasmic": False, "importin": None},
    "RNF114": {"nuclear": False, "cytoplasmic": True, "importin": None},
    "FEM1B": {"nuclear": False, "cytoplasmic": True, "importin": None},
    "MDM2": {"nuclear": True, "cytoplasmic": True, "importin": None},
    "IAP": {"nuclear": False, "cytoplasmic": True, "importin": None},
}

class E3LigandSelectionAgent(ReActAgent):
    name = "E3LigandSelectionAgent"
    thought = "Select E3 ligase and ligand based on target biology and subcellular colocalization."
    action = "select_e3_ligands"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        objective = state.parsed_objective
        ligands = []

        # 1. If user provided an E3 ligand SMILES, use it
        if objective.e3_ligand_smiles:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(objective.e3_ligand_smiles)
            ligase = objective.e3_ligase or "CRBN"
            record = E3LigandRecord(
                name=f"user_{ligase}",
                e3_ligase=ligase,
                smiles=objective.e3_ligand_smiles,
                ligand_class="user_provided",
                source="user",
                exit_vector_confidence=0.5,
                stereochemistry_valid=mol is not None,
                source_confidence=0.8,
                diversity_score=0.5,
            )
            ligands.append(record)
            state.selected_e3_ligands = ligands
            return state

        # 2. Load from curated library
        curated = self.toolbox.load_curated_e3_ligands()

        # 3. If user specified an E3 ligase, filter by it
        user_e3 = (objective.e3_ligase or "").upper()
        if user_e3:
            filtered = [row for row in curated if row.get("e3_ligase", "").upper() == user_e3]
            if not filtered:
                state.warnings.append(f"E3 ligase '{user_e3}' not found in library. Using all available.")
                filtered = curated
        else:
            filtered = curated
            # Auto-select based on target subcellular location
            state.warnings.append("No E3 ligase specified. Including all curated E3 ligands for comparison.")

        for row in filtered:
            from rdkit import Chem
            smiles = row.get("smiles", "")
            mol = Chem.MolFromSmiles(smiles) if smiles else None
            ligase = row.get("e3_ligase", "CRBN")
            subcell = E3_SUBCELLULAR.get(ligase, {"nuclear": False, "cytoplasmic": True})
            
            record = E3LigandRecord(
                name=row.get("name", f"e3_{ligase}"),
                e3_ligase=ligase,
                smiles=smiles,
                ligand_class=row.get("ligand_class", "unknown"),
                source=row.get("source", "curated"),
                exit_vector_confidence=float(row.get("exit_vector_confidence", 0.5)),
                stereochemistry_valid=mol is not None,
                source_confidence=float(row.get("source_confidence", 0.5)),
                diversity_score=float(row.get("diversity_score", 0.5)),
            )
            ligands.append(record)

        budget = max(1, getattr(state, "search_policy", None).e3_ligand_budget if getattr(state, "search_policy", None) else len(ligands))
        ligands.sort(key=lambda item: item.exit_vector_confidence + item.source_confidence + item.diversity_score, reverse=True)
        state.selected_e3_ligands = ligands[:budget]
        
        if not state.selected_e3_ligands:
            state.errors.append("E3LigandSelectionAgent: No E3 ligands selected.")
        
        return state

    def _observation(self, state: WorkflowState) -> str:
        e3s = state.selected_e3_ligands
        families = list(set(l.e3_ligase for l in e3s))
        return f"ligands={len(e3s)}, families={families}"
