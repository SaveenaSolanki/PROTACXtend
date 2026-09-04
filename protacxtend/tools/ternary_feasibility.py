"""Ternary feasibility and optional docking infrastructure (Phase 11)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence

from protacxtend.backend.schemas import CandidateRecord, TargetRecord
from protacxtend.tools.alphafold_client import retrieve_alphafold_id
from protacxtend.tools.docking_status import detect_docking_backends
from protacxtend.tools.pdb_client import retrieve_pdb_structures
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
from protacxtend.tools.rcsb_pdb_lookup import search_pdb_by_uniprot


_TOOLBOX = ProtacDesignToolbox()


def retrieve_target_structure(target_name: str) -> list[str]:
    return retrieve_pdb_structures(target_name)


def retrieve_e3_structure(e3_ligase: str) -> str | None:
    return {"CRBN": "4CI3", "VHL": "4W9H", "IAP": "local_stub", "MDM2": "local_stub"}.get(e3_ligase.upper())


def fast_linker_geometry_filter(candidate: CandidateRecord) -> float:
    return _TOOLBOX.assess_ternary_feasibility([candidate], None)[0].fast_geometry_feasibility_score


def estimate_reachability(candidate: CandidateRecord) -> float:
    return _TOOLBOX.assess_ternary_feasibility([candidate], None)[0].linker_reachability_score


def run_optional_docking_stub(candidate: CandidateRecord) -> dict:
    return {"candidate_id": candidate.candidate_id, "status": "not_run_stub_available"}


def compute_ternary_feasibility_score(candidate: CandidateRecord, target_record: TargetRecord | None = None) -> float:
    return _TOOLBOX.assess_ternary_feasibility([candidate], target_record)[0].ternary_plausibility_score


def assess_ternary_feasibility(candidates: Sequence[CandidateRecord], target_record: TargetRecord | None = None, top_n: int = 12):
    return _TOOLBOX.assess_ternary_feasibility(candidates, target_record, top_n)


def generate_ligand_conformers(smiles: str) -> dict[str, Any]:
    if not smiles:
        return {"success": False, "error": "SMILES is required.", "ligand_files": {}, "backend": "rdkit"}
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except Exception as exc:
        return {
            "success": False,
            "error": f"RDKit unavailable: {exc}",
            "ligand_files": {},
            "backend": "rdkit",
            "limitations": "Conformer generation requires RDKit.",
        }
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"success": False, "error": "Invalid SMILES.", "ligand_files": {}, "backend": "rdkit"}
    mol = Chem.AddHs(mol)
    embed = AllChem.EmbedMolecule(mol, randomSeed=42)
    if embed != 0:
        return {"success": False, "error": "RDKit embedding failed.", "ligand_files": {}, "backend": "rdkit"}
    AllChem.UFFOptimizeMolecule(mol, maxIters=200)
    handle = tempfile.NamedTemporaryFile(suffix=".sdf", delete=False)
    handle.close()
    writer = Chem.SDWriter(handle.name)
    writer.write(mol)
    writer.close()
    return {
        "success": True,
        "error": None,
        "backend": "rdkit",
        "ligand_files": {"ligand_sdf": handle.name},
        "limitations": "Conformer generated with RDKit UFF.",
    }


def prepare_ligand_for_docking(smiles: str) -> dict[str, Any]:
    backends = detect_docking_backends()["backends"]
    conformer = generate_ligand_conformers(smiles)
    if not conformer["success"]:
        return {
            "backend": "rdkit",
            "success": False,
            "error": conformer["error"],
            "ligand_files": {},
            "limitations": conformer.get("limitations", "Ligand preparation failed."),
        }
    ligand_sdf = conformer["ligand_files"]["ligand_sdf"]
    if not backends["openbabel"]["available"]:
        return {
            "backend": "rdkit",
            "success": True,
            "error": None,
            "ligand_files": {"ligand_sdf": ligand_sdf, "ligand_pdbqt": None},
            "limitations": "OpenBabel missing; PDBQT conversion was not performed.",
        }
    ligand_pdbqt = tempfile.NamedTemporaryFile(suffix=".pdbqt", delete=False)
    ligand_pdbqt.close()
    command = [
        backends["openbabel"]["path"] or "obabel",
        "-isdf",
        ligand_sdf,
        "-opdbqt",
        "-O",
        ligand_pdbqt.name,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
    except Exception as exc:
        return {
            "backend": "openbabel",
            "success": False,
            "error": f"PDBQT conversion failed: {exc}",
            "ligand_files": {"ligand_sdf": ligand_sdf, "ligand_pdbqt": None},
            "limitations": "OpenBabel conversion failed.",
        }
    return {
        "backend": "openbabel",
        "success": True,
        "error": None,
        "ligand_files": {"ligand_sdf": ligand_sdf, "ligand_pdbqt": ligand_pdbqt.name},
        "limitations": "Ligand SDF and PDBQT generated.",
    }


def check_binary_structure_availability(target: dict[str, Any] | None, e3: dict[str, Any] | None) -> dict[str, Any]:
    target = target or {}
    e3 = e3 or {}
    target_uniprot = target.get("uniprot_id")
    e3_uniprot = e3.get("uniprot_id")

    def _rcsb_lookup(uniprot_id: str | None) -> dict[str, Any]:
        if not uniprot_id:
            return {"checked": False, "success": False, "records": [], "error": "no_uniprot_id"}
        result = search_pdb_by_uniprot(uniprot_id, top_k=5, timeout=6.0)
        return {"checked": True, "success": bool(result.get("success")), "records": result.get("records", []), "error": result.get("error")}

    target_rcsb = _rcsb_lookup(target_uniprot)
    e3_rcsb = _rcsb_lookup(e3_uniprot)
    target_alphafold = retrieve_alphafold_id(target.get("name", "") if target else "") if target else None
    e3_alphafold = retrieve_alphafold_id(e3.get("name", "") if e3 else "") if e3 else None
    return {
        "success": True,
        "error": None,
        "target": {
            "uniprot_id": target_uniprot,
            "rcsb_available": target_rcsb["success"],
            "rcsb_records": target_rcsb["records"],
            "alphafold_id": target_alphafold,
        },
        "e3": {
            "uniprot_id": e3_uniprot,
            "rcsb_available": e3_rcsb["success"],
            "rcsb_records": e3_rcsb["records"],
            "alphafold_id": e3_alphafold,
        },
        "limitations": "RCSB/AlphaFold availability check only; no structural preparation performed.",
    }


def _collect_docking_inputs(candidate: Any) -> dict[str, Any]:
    provenance = getattr(candidate, "provenance", {}) if candidate is not None else {}
    if not isinstance(provenance, dict):
        provenance = {}
    return {
        "receptor_pdbqt": provenance.get("receptor_pdbqt"),
        "ligand_pdbqt": provenance.get("ligand_pdbqt"),
        "box_center": provenance.get("box_center"),
        "box_size": provenance.get("box_size"),
        "output_pdbqt": provenance.get("vina_output_pdbqt") or os.path.join(tempfile.gettempdir(), "vina_out.pdbqt"),
    }


def run_vina_if_available(candidate: Any) -> dict[str, Any]:
    backends = detect_docking_backends()["backends"]
    vina = backends["vina"]
    inputs = _collect_docking_inputs(candidate)
    result = {
        "backend": "vina",
        "input_structures": {"receptor_pdbqt": inputs["receptor_pdbqt"]},
        "ligand_files": {"ligand_pdbqt": inputs["ligand_pdbqt"]},
        "command_run": None,
        "docking_score": None,
        "success": False,
        "error": None,
        "limitations": None,
    }
    if not vina["available"]:
        result["error"] = "registered_but_not_executable"
        result["limitations"] = "AutoDock Vina binary not found."
        return result
    missing = []
    if not inputs["receptor_pdbqt"]:
        missing.append("receptor_pdbqt")
    if not inputs["ligand_pdbqt"]:
        missing.append("ligand_pdbqt")
    box_center = inputs["box_center"]
    box_size = inputs["box_size"]
    if not isinstance(box_center, (list, tuple)) or len(box_center) != 3:
        missing.append("box_center[x,y,z]")
    if not isinstance(box_size, (list, tuple)) or len(box_size) != 3:
        missing.append("box_size[x,y,z]")
    if missing:
        result["error"] = f"missing_docking_inputs: {', '.join(missing)}"
        result["limitations"] = "Vina available but docking inputs are incomplete."
        return result
    command = [
        vina["path"] or "vina",
        "--receptor",
        str(inputs["receptor_pdbqt"]),
        "--ligand",
        str(inputs["ligand_pdbqt"]),
        "--center_x",
        str(box_center[0]),
        "--center_y",
        str(box_center[1]),
        "--center_z",
        str(box_center[2]),
        "--size_x",
        str(box_size[0]),
        "--size_y",
        str(box_size[1]),
        "--size_z",
        str(box_size[2]),
        "--out",
        str(inputs["output_pdbqt"]),
        "--num_modes",
        "9",
    ]
    result["command_run"] = " ".join(command)
    try:
        proc = subprocess.run(command, check=True, capture_output=True, text=True, timeout=240)
    except Exception as exc:
        result["error"] = f"vina_run_failed: {exc}"
        result["limitations"] = "Vina execution failed."
        return result
    score = None
    for line in proc.stdout.splitlines():
        cols = line.strip().split()
        if len(cols) >= 2 and cols[0].isdigit():
            try:
                score = float(cols[1])
                break
            except ValueError:
                continue
    result["docking_score"] = score
    result["success"] = score is not None
    result["error"] = None if result["success"] else "vina_completed_without_parseable_score"
    result["limitations"] = "Docking score from Vina output." if result["success"] else "Vina ran but score parsing failed."
    return result


def run_gnina_if_available(candidate: Any) -> dict[str, Any]:
    backends = detect_docking_backends()["backends"]
    gnina = backends["gnina"]
    result = {
        "backend": "gnina",
        "input_structures": {},
        "ligand_files": {},
        "command_run": None,
        "docking_score": None,
        "success": False,
        "error": "registered_but_not_executable" if not gnina["available"] else "not_implemented_phase11",
        "limitations": "GNINA is optional in Phase 11 and is not required.",
    }
    return result


def assess_ternary_feasibility(candidate: Any, backend: str = "auto", top_n: int = 12) -> Any:
    # Backward-compatible path for prior workflow calls that pass a sequence.
    if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes, bytearray)):
        return _TOOLBOX.assess_ternary_feasibility(candidate, None, top_n)

    target = {
        "name": getattr(candidate, "target", None) if candidate is not None else None,
        "uniprot_id": getattr(candidate, "provenance", {}).get("target_uniprot_id") if candidate is not None and isinstance(getattr(candidate, "provenance", {}), dict) else None,
    }
    e3 = {
        "name": getattr(candidate, "e3_ligase", None) if candidate is not None else None,
        "uniprot_id": getattr(candidate, "provenance", {}).get("e3_uniprot_id") if candidate is not None and isinstance(getattr(candidate, "provenance", {}), dict) else None,
    }
    structure_info = check_binary_structure_availability(target, e3)

    selected = (backend or "auto").lower()
    if selected == "vina":
        out = run_vina_if_available(candidate)
        out["input_structures"]["availability_checks"] = structure_info
        return out
    if selected == "gnina":
        out = run_gnina_if_available(candidate)
        out["input_structures"]["availability_checks"] = structure_info
        return out

    if selected == "auto":
        out = run_vina_if_available(candidate)
        out["input_structures"]["availability_checks"] = structure_info
        if out["success"] or out["error"] not in {"registered_but_not_executable"}:
            return out
        gnina_out = run_gnina_if_available(candidate)
        gnina_out["input_structures"]["availability_checks"] = structure_info
        if gnina_out["success"]:
            return gnina_out
        return {
            "backend": "geometry_proxy_stub",
            "input_structures": {"availability_checks": structure_info},
            "ligand_files": {},
            "command_run": None,
            "docking_score": None,
            "success": True,
            "error": None,
            "limitations": "geometry_proxy_stub; no docking was performed.",
        }

    return {
        "backend": selected,
        "input_structures": {"availability_checks": structure_info},
        "ligand_files": {},
        "command_run": None,
        "docking_score": None,
        "success": False,
        "error": f"unsupported_backend:{backend}",
        "limitations": "Use backend in {auto, vina, gnina}.",
    }
