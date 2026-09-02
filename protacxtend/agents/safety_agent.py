"""Safety and scientific guardrail agent — validates input safety before workflow starts."""

from __future__ import annotations
from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WorkflowState

KNOWN_HAZARD_PATTERNS = [
    "c1ccc2c(c1)ccc3c2cccc3",  # benzopyrene-like
    "c1cc2c(cc1)c3cc4ccc5ccc6ccc7ccc8ccc9ccc%10ccc%11ccc%12c%10c%9c8c7c6c5c4c3c2",  # large PAH
]

class SafetyAgent(ReActAgent):
    name = "SafetyAgent"
    thought = "Check user request for haz ard patterns, unreasonable targets, or missing critical information."
    action = "safety_precheck"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        request = state.user_request.upper()
        issues = []

        # 1. Check for hazardous substructures in any provided SMILES
        if state.parsed_objective.warhead_smiles:
            canonical = state.parsed_objective.warhead_smiles.replace("[*:1]", "").replace("[*:2]", "")
            for pattern in KNOWN_HAZARD_PATTERNS:
                if pattern in canonical:
                    issues.append(f"Warhead contains suspect substructure: {pattern[:30]}...")

        # 2. Check for impossible targets
        impossible_targets = ["GREEN FLUORESCENT PROTEIN", "LUCIFERASE", "T7 RNA POLYMERASE", "HSA", "BSA"]
        if state.parsed_objective.target_name and state.parsed_objective.target_name.upper() in impossible_targets:
            issues.append(f"Target {state.parsed_objective.target_name} is a reporter/assay protein, not a therapeutic target.")

        # 3. Chemical validity of provided SMILES
        if state.parsed_objective.warhead_smiles:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(state.parsed_objective.warhead_smiles)
            if mol is None:
                issues.append(f"Warhead SMILES is invalid: {state.parsed_objective.warhead_smiles[:50]}")

        if state.parsed_objective.e3_ligand_smiles:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(state.parsed_objective.e3_ligand_smiles)
            if mol is None:
                issues.append(f"E3 ligand SMILES is invalid: {state.parsed_objective.e3_ligand_smiles[:50]}")

        # 4. Warn about excessive candidate counts
        if state.parsed_objective.candidate_count > 500:
            issues.append(f"Candidate count ({state.parsed_objective.candidate_count}) is high; may cause long runtime.")

        if issues:
            state.warnings.extend(issues)
        return state

    def _observation(self, state: WorkflowState) -> str:
        return f"warnings={len(state.warnings)}"
