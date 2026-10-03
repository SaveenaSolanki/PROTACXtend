"""Formal DESIGN gates.

A DESIGN result is only ``valid_candidate`` when the product passes every gate:
chemical validity, component fidelity, attachment validity, conformer
feasibility, evidence status, applicability domain and uncertainty. Otherwise it
is a ``design_brief`` (hypothetical) or a ``justified_no_go``.
"""

from __future__ import annotations

from typing import Any

from protacxtend.backend.schemas import WorkflowState
from protacxtend.identity_gate import candidate_passes_identity_gate, evaluate_candidate_identity, gate_payload

GATE_NAMES = [
    "chemical_validity",
    "component_fidelity",
    "attachment_validity",
    "conformer_feasibility",
    "evidence_status",
    "applicability_domain",
    "uncertainty",
]


def _capped_mol(smiles: str):
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        rw = Chem.RWMol(mol)
        for atom in rw.GetAtoms():
            if atom.GetAtomicNum() == 0:
                atom.SetAtomicNum(1)
                atom.SetIsotope(0)
                atom.SetAtomMapNum(0)
        capped = rw.GetMol()
        Chem.SanitizeMol(capped)
        return capped
    except Exception:  # noqa: BLE001
        return None


def chemical_validity_gate(candidate) -> dict[str, Any]:
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(candidate.full_protac_smiles)
        if mol is None:
            return {"gate": "chemical_validity", "passed": False, "detail": "RDKit parse failed"}
        from rdkit.Chem import Descriptors

        return {"gate": "chemical_validity", "passed": True,
                "detail": f"sanitized; MW={Descriptors.MolWt(mol):.1f}"}
    except Exception as exc:  # noqa: BLE001
        return {"gate": "chemical_validity", "passed": False, "detail": f"RDKit error: {exc}"}


def component_fidelity_gate(candidate) -> dict[str, Any]:
    provenance = candidate.provenance or {}
    gate = provenance.get("identity_assembly_gate")
    if not gate:
        evaluated = evaluate_candidate_identity(candidate)
        gate = gate_payload(evaluated)
        candidate.provenance = dict(candidate.provenance or {})
        candidate.provenance["identity_assembly_gate"] = gate
    passed = bool(gate.get("all_required_passed"))
    return {"gate": "component_fidelity", "passed": passed,
            "detail": "identity/assembly gate passed" if passed else "; ".join(gate.get("reasons") or ["identity/assembly gate failed"])}


def attachment_validity_gate(candidate) -> dict[str, Any]:
    provenance = candidate.provenance or {}
    if provenance.get("verified_components"):
        maps = provenance.get("attachment_maps") or {}
        return {"gate": "attachment_validity", "passed": bool(maps),
                "detail": f"verified atom maps: {maps}"}
    warhead_has = "[*" in (candidate.warhead_smiles or "")
    e3_has = "[*" in (candidate.e3_ligand_smiles or "")
    return {"gate": "attachment_validity", "passed": bool(warhead_has and e3_has),
            "detail": ("hypothetical marker present" if warhead_has and e3_has
                       else "missing attachment marker")}


def conformer_feasibility_gate(candidate, *, n_confs: int = 1) -> dict[str, Any]:
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem

        mol = Chem.MolFromSmiles(candidate.full_protac_smiles)
        if mol is None:
            return {"gate": "conformer_feasibility", "passed": False, "detail": "parse failed"}
        mol = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()
        params.randomSeed = 0
        conf_ids = AllChem.EmbedMultipleConfs(mol, numConfs=n_confs, params=params)
        if not conf_ids:
            return {"gate": "conformer_feasibility", "passed": False, "detail": "ETKDG embedding failed"}
        return {"gate": "conformer_feasibility", "passed": True,
                "detail": f"embedded {len(conf_ids)} conformer(s)",
                "n_rotatable_bonds": candidate.rotatable_bonds}
    except Exception as exc:  # noqa: BLE001
        return {"gate": "conformer_feasibility", "passed": False, "detail": f"error: {exc}"}


def evidence_status_gate(candidate) -> dict[str, Any]:
    passed = candidate_passes_identity_gate(candidate)
    return {"gate": "evidence_status", "passed": passed,
            "detail": "source-backed component identities" if passed else "binding/identity evidence unverified"}


def applicability_domain_gate(state: WorkflowState, candidate) -> dict[str, Any]:
    for ad in state.applicability_domain_results:
        if ad.candidate_id == candidate.candidate_id:
            status = getattr(ad, "domain_status", "unknown")
            return {"gate": "applicability_domain", "passed": status != "outside",
                    "detail": f"domain_status={status}"}
    return {"gate": "applicability_domain", "passed": False, "detail": "not computed"}


def uncertainty_gate(state: WorkflowState, candidate) -> dict[str, Any]:
    warnings = list(candidate.warning_flags or [])
    low_conf = [
        p.model_confidence for p in state.degradation_predictions
        if p.candidate_id == candidate.candidate_id and p.model_confidence < 0.45
    ]
    passed = not warnings and not low_conf
    return {"gate": "uncertainty", "passed": passed,
            "detail": f"warnings={warnings}, low_confidence_predictions={len(low_conf)}"}


def evaluate_candidate(state: WorkflowState, candidate) -> dict[str, Any]:
    gates = [
        chemical_validity_gate(candidate),
        component_fidelity_gate(candidate),
        attachment_validity_gate(candidate),
        conformer_feasibility_gate(candidate),
        evidence_status_gate(candidate),
        applicability_domain_gate(state, candidate),
        uncertainty_gate(state, candidate),
    ]
    return {
        "candidate_id": candidate.candidate_id,
        "gates": gates,
        "n_passed": sum(1 for g in gates if g["passed"]),
        "all_passed": all(g["passed"] for g in gates),
    }


HARD_GATES = [
    "chemical_validity",
    "component_fidelity",
    "attachment_validity",
    "evidence_status",
]
SOFT_GATES = [
    "conformer_feasibility",
    "applicability_domain",
    "uncertainty",
]


def evaluate_design_gates(state: WorkflowState) -> dict[str, Any]:
    """Evaluate all candidates and derive the final DESIGN state.

    ``valid_candidate`` requires the four hard gates (chemical validity,
    component fidelity, attachment validity, source-backed evidence status).
    Conformer feasibility, applicability domain and uncertainty are advisory:
    a failure is recorded as a caveat, not used to discard a source-backed
    reference.
    """
    candidates = list(state.valid_candidates or [])
    evaluations = [evaluate_candidate(state, c) for c in candidates]

    def hard_ok(ev: dict[str, Any]) -> bool:
        return all(g["passed"] for g in ev["gates"] if g["gate"] in HARD_GATES)

    def evidence_ok(ev: dict[str, Any]) -> bool:
        return all(g["passed"] for g in ev["gates"] if g["gate"] == "evidence_status")

    def soft_caveats(ev: dict[str, Any]) -> list[str]:
        return [g["gate"] for g in ev["gates"] if g["gate"] in SOFT_GATES and not g["passed"]]

    valid = [e for e in evaluations if hard_ok(e)]
    verified_valid = [e for e in valid if evidence_ok(e)]
    if verified_valid:
        final_state = "valid_candidate"
    elif candidates or state.design_plan.get("design_brief"):
        final_state = "design_brief"
    else:
        final_state = "justified_no_go"
    by_candidate = {e["candidate_id"]: e for e in evaluations}
    caveats = {e["candidate_id"]: soft_caveats(e) for e in valid if soft_caveats(e)}
    return {
        "schema": "design.gates.v1",
        "hard_gates": HARD_GATES,
        "soft_gates": SOFT_GATES,
        "gate_names": GATE_NAMES,
        "evaluations": evaluations,
        "by_candidate": by_candidate,
        "n_candidates": len(candidates),
        "n_hard_gates_passed": len(valid),
        "n_verified_valid": len(verified_valid),
        "soft_gate_caveats": caveats,
        "final_state": final_state,
        "note": "valid_candidate requires all hard gates including source-backed evidence; soft-gate failures are caveats.",
    }


__all__ = ["GATE_NAMES", "evaluate_candidate", "evaluate_design_gates"]
