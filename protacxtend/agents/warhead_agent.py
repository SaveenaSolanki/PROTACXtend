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

        # A source-backed verified warhead seeded by the design-path node must
        # not be replaced by the curated/demo selection path.
        if state.selected_warheads and any(w.provenance.get("verified") for w in state.selected_warheads):
            state.warnings.append(
                "WarheadSelectionAgent: using source-backed verified warhead; skipping library selection."
            )
            return state

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

        # 2b. Convert live retrieved binders into warheads. The toolbox marks
        #     binders without a known attachment chemistry with a hypothetical
        #     exit-vector marker and lowers their deriv/exit-vector confidence
        #     ("chemist review required") — this is not a filter relaxation: the
        #     conventional curated-table path simply never consumed
        #     ``state.retrieved_binders``, which is why SCIENTIFIC mode could
        #     retrieve 90 ChEMBL binders and then abort with zero warheads.
        if state.retrieved_binders:
            from protacxtend.runtime.modes import filter_scientific_rows, is_scientific

            max_warheads = int(getattr(objective, "max_warheads", None) or 6)
            binder_warheads = self.toolbox.select_warheads(
                state.target_record,
                state.retrieved_binders,
                user_warhead_smiles=objective.warhead_smiles,
                max_warheads=max_warheads,
            )
            seen = {w.smiles for w in warheads}
            for w in binder_warheads:
                if w.smiles not in seen:
                    warheads.append(w)
                    seen.add(w.smiles)
            if is_scientific():
                warheads, dropped = filter_scientific_rows(
                    [dict(w.model_dump()) if hasattr(w, "model_dump") else dict(w.__dict__) for w in warheads],
                    source_key="source",
                )
                warheads = [
                    WarheadRecord(**w) for w in warheads
                ] if warheads else []
                if dropped and state.target_record:
                    state.warnings.append(
                        f"WarheadSelectionAgent: dropped {len(dropped)} non-scientific warhead row(s) "
                        f"in SCIENTIFIC mode ({sorted({d.get('source') for d in dropped})})."
                    )

        # 3. If no warheads found, add demo warheads from curated list.
        #    SCIENTIFIC mode forbids this silent substitution and abstains with
        #    stage-specific reasons (retrieved-binder census included).
        if not warheads:
            from protacxtend.runtime.modes import SyntheticInputNotAllowed, is_scientific

            if is_scientific():
                dropped = self.toolbox.demo_rows_dropped.get("curated_warheads.csv", 0)
                n_binders = len(state.retrieved_binders)
                sources = sorted({b.source for b in state.retrieved_binders[:20]})
                detail = (
                    f" ({dropped} demo warhead row(s) were dropped because their "
                    "source is a local_demo fixture)" if dropped else ""
                )
                raise SyntheticInputNotAllowed(
                    "No warheads selected: target-matched warheads are unavailable "
                    f"and demo/placeholder warheads are forbidden in SCIENTIFIC mode{detail}. "
                    f"Stage census: {n_binders} binder(s) retrieved "
                    f"(sources={sources}); none satisfied warhead criteria. "
                    "ABSTAIN: supply a real warhead SMILES, a validated binder set, "
                    "or 'real' curated warhead rows before rerunning."
                )
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
