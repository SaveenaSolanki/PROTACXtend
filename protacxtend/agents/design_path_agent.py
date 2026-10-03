"""Design-path node: one defensible DESIGN route.

Two outcomes are separated explicitly:

* **verified reference candidate** — assembled from source-backed, atom-mapped
  components (MZ1 warhead + VHL ligand + PEG3 linker; PDB 5T35). This is a real,
  reviewable molecule.
* **design brief** — the case supplied components but no atom-mapped exit
  vector. Generation may still sketch hypotheses, but the result is labelled a
  design brief, never a final PROTAC.

The node records component provenance, attachment maps and applicability limits
onto the state and on every candidate it creates.
"""

from __future__ import annotations

from typing import Any

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import CandidateRecord, WorkflowState
from protacxtend.tools import verified_components as vc
from protacxtend.identity_gate import source_record_from_verified_component


class DesignPathAgent(ReActAgent):
    name = "DesignPathAgent"
    thought = "Assemble one source-backed reference candidate or declare a design brief."
    action = "design_path"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        target = (state.target_record.gene_symbol if state.target_record else "") or \
            state.parsed_objective.target_name or ""
        # Choose a requested E3 that has a full verified reference set.
        requested = [e.upper() for e in vc_registry_e3s(state)]
        reference = None
        e3_choice = ""
        for candidate_e3 in requested:
            reference = vc.reference_components(target, candidate_e3)
            if reference:
                e3_choice = candidate_e3
                break
        if reference:
            warhead = reference["warhead"]
            e3_ligand = reference["e3_ligand"]
            linker = reference["linker"]
        else:
            e3_choice = requested[0] if requested else "VHL"
            warhead = vc.warhead_for(target)
            e3_ligand = vc.e3_ligand_for(e3_choice)
            linker = vc.linker_for_protac(e3_ligand["source_protac"]) if e3_ligand else None

        supplied_warhead = bool(state.parsed_objective.warhead_smiles)
        supplied_e3_ligand = bool(state.parsed_objective.e3_ligand_smiles)
        design_brief = supplied_warhead or supplied_e3_ligand  # supplied = no verified map

        path: dict[str, Any] = {
            "target": target,
            "e3_choice": e3_choice,
            "verified_reference_available": bool(warhead and e3_ligand and linker),
            "design_brief_required": bool(design_brief),
            "reason": "",
            "components": {},
        }

        if warhead and e3_ligand and linker and not supplied_warhead and not supplied_e3_ligand:
            candidate = self._assemble_reference(state, warhead, linker, e3_ligand)
            if candidate is not None:
                state.assembled_candidates = [candidate] + [
                    c for c in state.assembled_candidates
                    if c.full_protac_smiles != candidate.full_protac_smiles
                ]
                state.selected_warheads = [self._warhead_record(warhead)]
                state.selected_e3_ligands = [self._e3_record(e3_ligand)]
                path["reason"] = (
                    f"Real atom-mapped components from {reference['reference'].get('name', 'a source PROTAC')} "
                    f"({reference['reference'].get('doi', 'source')}) were used; "
                    "product is a reviewable reference candidate."
                )
            else:
                path["verified_reference_available"] = False
                path["reason"] = "verified component assembly failed RDKit sanitization"
                design_brief = True
        else:
            if supplied_warhead or supplied_e3_ligand:
                path["reason"] = (
                    "Case supplies components without atom-mapped attachment atoms; "
                    "any assembled product is a design brief, not a final PROTAC."
                )
            else:
                path["reason"] = (
                    f"No verified source-backed component pair for target={target!r} "
                    f"and E3={e3_choice!r}."
                )
            design_brief = True

        path["design_brief_required"] = bool(design_brief)
        path["components"] = {
            "warhead": _component_summary(warhead),
            "e3_ligand": _component_summary(e3_ligand),
            "linker": _component_summary(linker),
        }
        state.design_plan["design_path"] = path
        state.design_plan["design_brief"] = bool(design_brief)
        return state

    # ── helpers ──────────────────────────────────────────────────────
    def _assemble_reference(self, state: WorkflowState, warhead: dict, linker: dict,
                            e3_ligand: dict) -> CandidateRecord | None:
        full, message = self.toolbox.assemble_components(
            warhead["smiles"], linker["smiles"], e3_ligand["smiles"]
        )
        if not full:
            state.warnings.append(f"DesignPathAgent: reference assembly failed: {message}")
            return None
        props = self.toolbox.compute_basic_properties(full)
        target = warhead.get("target") or ""
        return CandidateRecord(
            candidate_id="SGA-VERIFIED-MZ1",
            target=target,
            e3_ligase=e3_ligand.get("e3_ligase", ""),
            warhead_name=warhead.get("name", ""),
            warhead_smiles=warhead["smiles"],
            warhead_source=warhead.get("source", ""),
            e3_ligand_name=e3_ligand.get("name", ""),
            e3_ligand_smiles=e3_ligand["smiles"],
            linker_name=linker.get("name", ""),
            linker_smiles=linker["smiles"],
            linker_class="PEG",
            full_protac_smiles=full,
            assembly_strategy="verified_component_join",
            reaction_class="amide_coupling",
            validity_status=self.toolbox.validate_smiles(full),
            synthetic_feasibility_score=0.8,
            provenance={
                "verified_components": True,
                "attachment_maps": {
                    "warhead": warhead.get("attachment_atom_map"),
                    "e3_ligand": e3_ligand.get("attachment_atom_map"),
                },
                "sources": {
                    "warhead": warhead.get("source"),
                    "e3_ligand": e3_ligand.get("source"),
                    "linker": linker.get("source"),
                },
                "source_components": {
                    "target_binder": source_record_from_verified_component(warhead).model_dump(),
                    "e3_ligand": source_record_from_verified_component(e3_ligand).model_dump(),
                    "linker": source_record_from_verified_component(linker).model_dump(),
                },
                "applicability": {
                    "warhead": warhead.get("applicability"),
                    "e3_ligand": e3_ligand.get("applicability"),
                    "linker": linker.get("applicability"),
                },
                "assembly_message": message,
            },
            mw=props.get("mw"), tpsa=props.get("tpsa"), logp=props.get("logp"),
            hbd=int(props.get("hbd", 0)), hba=int(props.get("hba", 0)),
            rotatable_bonds=int(props.get("rotatable_bonds", 0)),
        )

    def _warhead_record(self, comp: dict):
        from protacxtend.backend.schemas import WarheadRecord

        return WarheadRecord(
            name=comp.get("name", ""), target=comp.get("target", ""), smiles=comp["smiles"],
            source=comp.get("source", "verified_components"), potency_score=0.7,
            derivatization_score=0.9, exit_vector_confidence=0.95, source_confidence=0.9,
            chemical_validity=self.toolbox.validate_smiles(comp["smiles"]),
            provenance={"verified": True, "source": comp.get("source"),
                        "applicability": comp.get("applicability"),
                        "attachment_atom_map": comp.get("attachment_atom_map")},
        )

    def _e3_record(self, comp: dict):
        from protacxtend.backend.schemas import E3LigandRecord

        return E3LigandRecord(
            name=comp.get("name", ""), e3_ligase=comp.get("e3_ligase", ""), smiles=comp["smiles"],
            ligand_class="verified", source=comp.get("source", "verified_components"),
            exit_vector_confidence=0.95, stereochemistry_valid=True, source_confidence=0.9,
            provenance={"verified": True, "source": comp.get("source"),
                        "applicability": comp.get("applicability"),
                        "attachment_atom_map": comp.get("attachment_atom_map")},
        )

    def _observation(self, state: WorkflowState) -> str:
        path = state.design_plan.get("design_path", {})
        return (f"verified_reference={path.get('verified_reference_available')}, "
                f"design_brief={path.get('design_brief_required')}")


def vc_registry_e3s(state: WorkflowState) -> list[str]:
    requested: list[str] = []
    if state.parsed_objective.e3_ligase:
        requested.append(state.parsed_objective.e3_ligase)
    for path in vc.verified_paths():
        requested.append(path["e3_ligase"])
    requested.append("VHL")
    # preserve order, drop duplicates
    seen: set[str] = set()
    out: list[str] = []
    for item in requested:
        if item and item.upper() not in seen:
            seen.add(item.upper())
            out.append(item)
    return out


def _component_summary(comp: dict | None) -> dict[str, Any]:
    if not comp:
        return {}
    return {
        "component_id": comp.get("component_id"),
        "name": comp.get("name"),
        "source": comp.get("source"),
        "attachment_atom_map": comp.get("attachment_atom_map"),
        "applicability": comp.get("applicability"),
        "verified": comp.get("verified", False),
    }


__all__ = ["DesignPathAgent"]
