"""Toolkit status detection for registered Excel entries.

Phase 2 annotates registry rows with local availability and implementation
status. It does not run expensive tools, docking engines, scientific models, or
external API workflows.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import re
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any

from protacxtend.toolkit.registry import load_toolkit_registry
from protacxtend.toolkit.schema import normalize_text


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "protacxtend" / "data"


PACKAGE_IMPORTS = {
    "rdkit": "rdkit",
    "openbabel": "openbabel",
    "biopython": "Bio",
    "scikit-learn": "sklearn",
    "qdrant-client": "qdrant_client",
    "faiss-cpu": "faiss",
    "mdanalysis": "MDAnalysis",
    "fair-esm": "esm",
}


CLI_COMMANDS = {
    "pymol": "pymol",
    "ucsf chimerax": "chimerax",
    "ucsf chimera": "chimera",
    "vmd": "vmd",
    "autodock vina": "vina",
    "smina": "smina",
    "gnina": "gnina",
    "rdock": "rbdock",
    "dock6": "dock6",
    "gromacs": "gmx",
    "namd": "namd2",
    "openbabel": "obabel",
    "crest": "crest",
    "xtb": "xtb",
    "orca": "orca",
    "nextflow": "nextflow",
}


LOCAL_FILES = {
    "protac-db 3.0": DATA_DIR / "protacdb_local.csv",
    "protacpedia": DATA_DIR / "protacpedia_local.csv",
    "drugbank": DATA_DIR / "drugbank_local.csv",
    "bindingdb": DATA_DIR / "bindingdb.tsv",
    "lean magnetdb trie": DATA_DIR / "Lean_MagnetDB_Trie.pkl",
    "clean metadata hash": DATA_DIR / "Clean_Metadata_Hash.pkl",
}


REAL_IMPLEMENTATIONS = {
    "rdkit": [
        ("protacxtend.tools.rdkit_chemistry", "validate_smiles"),
        ("protacxtend.tools.rdkit_chemistry", "calculate_descriptors"),
        ("protacxtend.tools.rdkit_chemistry", "calculate_morgan_fingerprint"),
    ],
    "pubchem": [
        ("protacxtend.tools.pubchem_lookup", "search_compound_by_name"),
        ("protacxtend.tools.pubchem_lookup", "get_compound_by_cid"),
    ],
    "uniprot": [
        ("protacxtend.tools.uniprot_lookup", "search_uniprot"),
        ("protacxtend.tools.uniprot_lookup", "get_uniprot_record"),
    ],
    "rcsb pdb": [
        ("protacxtend.tools.rcsb_pdb_lookup", "search_pdb_by_uniprot"),
        ("protacxtend.tools.rcsb_pdb_lookup", "get_pdb_entry"),
    ],
    "chembl": [
        ("protacxtend.tools.chembl_lookup", "search_targets"),
        ("protacxtend.tools.chembl_lookup", "get_target_activities"),
    ],
    "bindingdb": [
        ("protacxtend.tools.bindingdb_lookup", "search_bindingdb_local"),
        ("protacxtend.tools.bindingdb_lookup", "load_bindingdb_local_tsv"),
    ],
    "adme/tox skill": [("protacxtend.tools.admet_predictors", "predict_admet")],
    "drugbank": [("protacxtend.tools.drugbank_client", "search_drugbank_compounds")],
    "lean magnetdb inference": [("protacxtend.tools.magnetdb_lookup", "run_lean_magnetdb_inference")],
}


STUB_IMPLEMENTATIONS = {
    "target assessment": [("protacxtend.tools.target_resolver", "resolve_target")],
    "warhead mining": [("protacxtend.tools.chembl_client", "retrieve_known_binders")],
    "e3 ligase selection": [("protacxtend.tools.e3_selector", "select_e3_ligands")],
    "linker design": [("protacxtend.tools.linker_generator", "generate_linkers_for_pair")],
    "assembly agent": [("protacxtend.agents.construction_agent", "MolecularConstructionAgent")],
    "dc50/dmax prediction": [("protacxtend.tools.degradation_predictor", "predict_dc50_dmax")],
    "adme/tox skill": [("protacxtend.tools.admet_predictor", "predict_admet")],
    "synthesis planning": [("protacxtend.tools.retrosynthesis_filter", "retrosynthesis_feasibility_filter")],
    "novelty/ip check": [("protacxtend.tools.novelty_checker", "check_novelty")],
    "ternary complex modeling": [("protacxtend.tools.ternary_feasibility", "assess_ternary_feasibility")],
    "ranking skill": [("protacxtend.tools.ranker", "pairwise_tournament_ranking")],
    "report generation": [("protacxtend.tools.report_generator", "generate_candidate_table")],
    "supervisor": [("protacxtend.agents.supervisor_agent", "SupervisorAgent")],
    "target agent": [("protacxtend.agents.target_agent", "TargetResolverAgent")],
    "warhead agent": [("protacxtend.agents.warhead_agent", "WarheadSelectionAgent")],
    "e3 agent": [("protacxtend.agents.e3_agent", "E3LigandSelectionAgent")],
    "linker agent": [("protacxtend.agents.linker_agent", "LinkerGenerationAgent")],
    "docking/ternary agent": [("protacxtend.agents.ternary_agent", "TernaryFeasibilityAgent")],
    "adme/tox agent": [("protacxtend.agents.admet_agent", "ADMETAgent")],
    "novelty/ip agent": [("protacxtend.agents.novelty_agent", "NoveltyAgent")],
    "ranking agent": [("protacxtend.agents.ranking_agent", "RankingAgent")],
    "report agent": [("protacxtend.agents.report_agent", "ReportAgent")],
}


ALIASES = {
    "pdb": "rcsb pdb",
    "protein data bank": "rcsb pdb",
    "protac-aware adme/tox": "adme/tox skill",
    "deepchem": "deepchem",
    "chemprop": "chemprop",
    "magnetdb": "lean magnetdb inference",
    "lean magnetdb": "lean magnetdb inference",
}


def _canonical_name(name: Any) -> str:
    normalized = normalize_text(name)
    return ALIASES.get(normalized, normalized)


def _source_link(entry: dict[str, Any]) -> Any:
    fields = entry.get("fields", {})
    for key in ("source_link", "link", "key_links"):
        if fields.get(key):
            return fields[key]
    return None


def detect_package_availability(package_name: str) -> dict[str, Any]:
    normalized = _canonical_name(package_name)
    import_name = PACKAGE_IMPORTS.get(normalized, str(package_name).replace("-", "_").replace(" ", "_"))
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$", import_name):
        return {"available": False, "evidence": f"{import_name!r} is not a valid import name"}
    try:
        available = importlib.util.find_spec(import_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError) as exc:
        return {"available": False, "evidence": f"import check failed for {import_name}: {exc}"}
    return {
        "available": available,
        "evidence": f"importlib.util.find_spec({import_name!r}) {'succeeded' if available else 'returned None'}",
    }


def detect_cli_availability(command_name: str) -> dict[str, Any]:
    normalized = _canonical_name(command_name)
    command = CLI_COMMANDS.get(normalized, command_name)
    path = shutil.which(command)
    return {
        "available": path is not None,
        "evidence": f"shutil.which({command!r}) -> {path}" if path else f"shutil.which({command!r}) returned None",
    }


def _detect_local_file(name: str) -> dict[str, Any] | None:
    path = LOCAL_FILES.get(_canonical_name(name))
    if path is None:
        return None
    return {
        "available": path.exists(),
        "evidence": f"local file check: {path}",
        "execution_mode": "local_file",
    }


@lru_cache(maxsize=None)
def _has_callable(module_name: str, attr_name: str) -> bool:
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return False
    return callable(getattr(module, attr_name, None))


def _callable_evidence(checks: list[tuple[str, str]]) -> tuple[bool, str]:
    if not checks:
        return False, "no callable mapped in this codebase"
    found = []
    missing = []
    for module_name, attr_name in checks:
        if _has_callable(module_name, attr_name):
            found.append(f"{module_name}.{attr_name}")
        else:
            missing.append(f"{module_name}.{attr_name}")
    if found:
        return True, "callable detected: " + ", ".join(found)
    return False, "mapped callables missing or not importable: " + ", ".join(missing)


@lru_cache(maxsize=None)
def _rdkit_smoke_test() -> dict[str, Any]:
    try:
        from protacxtend.tools.rdkit_chemistry import calculate_descriptors, validate_smiles
    except Exception as exc:
        return {"success": False, "evidence": f"RDKit chemistry wrapper import failed: {exc}"}
    validation = validate_smiles("CC(=O)OC1=CC=CC=C1C(=O)O")
    descriptors = calculate_descriptors("CC(=O)OC1=CC=CC=C1C(=O)O")
    if validation.get("success") and descriptors.get("success") and descriptors.get("descriptors", {}).get("MW", 0) > 0:
        return {"success": True, "evidence": "RDKit aspirin validation and descriptor smoke test succeeded"}
    return {
        "success": False,
        "evidence": (
            "RDKit smoke test failed: "
            f"validation={validation.get('error')}; descriptors={descriptors.get('error')}"
        ),
    }


@lru_cache(maxsize=None)
def _admet_smoke_test() -> dict[str, Any]:
    try:
        from protacxtend.tools.admet_predictors import predict_admet
    except Exception as exc:
        return {"success": False, "evidence": f"ADMET predictor import failed: {exc}"}
    result = predict_admet("CCO", backend="auto")
    if result.get("success") and result.get("backend_used") != "heuristic_stub":
        return {"success": True, "evidence": f"ADMET smoke test succeeded with backend={result.get('backend_used')}"}
    return {
        "success": False,
        "evidence": f"ADMET smoke test did not produce executable backend: backend={result.get('backend_used')} status={result.get('status')}",
    }


def classify_existing_implementation(tool_name: str) -> dict[str, Any]:
    normalized = _canonical_name(tool_name)
    real_found, real_evidence = _callable_evidence(REAL_IMPLEMENTATIONS.get(normalized, []))
    if real_found:
        if normalized == "drugbank":
            has_key = bool(os.getenv("DRUGBANK_API_KEY") or os.getenv("DRUGBANK_TOKEN"))
            if not has_key:
                return {
                    "classification": "not_connected",
                    "executable": False,
                    "execution_mode": "api",
                    "evidence": f"{real_evidence}; DrugBank API credentials not configured",
                    "failure_reason": "DrugBank API wrapper exists but DRUGBANK_API_KEY/DRUGBANK_TOKEN is missing",
                }
            real_evidence = f"{real_evidence}; DrugBank API credentials configured"
        if normalized == "lean magnetdb inference":
            trie_path = DATA_DIR / "Lean_MagnetDB_Trie.pkl"
            meta_path = DATA_DIR / "Clean_Metadata_Hash.pkl"
            if not trie_path.exists() or not meta_path.exists():
                return {
                    "classification": "not_connected",
                    "executable": False,
                    "execution_mode": "local_file",
                    "evidence": f"{real_evidence}; missing files: {trie_path} or {meta_path}",
                    "failure_reason": "Lean MagnetDB wrapper exists but local pickle files are missing",
                }
            real_evidence = f"{real_evidence}; local files present: {trie_path}, {meta_path}"
        if normalized == "bindingdb":
            try:
                from protacxtend.tools.bindingdb_lookup import find_bindingdb_local_tsv

                bindingdb_path = find_bindingdb_local_tsv()
            except Exception as exc:
                bindingdb_path = None
                real_evidence = f"{real_evidence}; BindingDB local TSV detection failed: {exc}"
            if bindingdb_path is None:
                return {
                    "classification": "not_connected",
                    "executable": False,
                    "execution_mode": "local_file",
                    "evidence": f"{real_evidence}; BindingDB local TSV not present",
                    "failure_reason": "BindingDB wrapper exists but no local TSV/API source is configured",
                }
            real_evidence = f"{real_evidence}; BindingDB local TSV present: {bindingdb_path}"
        if normalized == "rdkit":
            smoke = _rdkit_smoke_test()
            if not smoke["success"]:
                return {
                    "classification": "not_connected",
                    "executable": False,
                    "execution_mode": "python_package",
                    "evidence": f"{real_evidence}; {smoke['evidence']}",
                    "failure_reason": "RDKit callable exists but import/smoke test did not pass",
                }
            real_evidence = f"{real_evidence}; {smoke['evidence']}"
        if normalized == "adme/tox skill":
            smoke = _admet_smoke_test()
            if not smoke["success"]:
                return {
                    "classification": "stub",
                    "executable": False,
                    "execution_mode": "stub",
                    "evidence": f"{real_evidence}; {smoke['evidence']}",
                    "failure_reason": "ADMET layer currently falls back to heuristic_stub",
                }
            real_evidence = f"{real_evidence}; {smoke['evidence']}"
        return {
            "classification": "real",
            "executable": True,
            "execution_mode": "python_package",
            "evidence": real_evidence,
            "failure_reason": None,
        }
    stub_found, stub_evidence = _callable_evidence(STUB_IMPLEMENTATIONS.get(normalized, []))
    if stub_found:
        return {
            "classification": "stub",
            "executable": False,
            "execution_mode": "stub",
            "evidence": stub_evidence,
            "failure_reason": "existing implementation is heuristic/demo/local scaffold output",
        }
    return {
        "classification": "not_connected",
        "executable": False,
        "execution_mode": "not_connected",
        "evidence": "no callable implementation mapped in this codebase",
        "failure_reason": "registered in Excel but not connected",
    }


def _availability_for_entry(entry: dict[str, Any]) -> dict[str, Any]:
    name = entry["name"]
    section = entry["section"]
    local = _detect_local_file(name)
    if local is not None:
        return local
    if section == "packages":
        result = detect_package_availability(name)
        return {**result, "execution_mode": "python_package"}
    if section == "tools":
        package = detect_package_availability(name)
        if package["available"]:
            return {**package, "execution_mode": "python_package"}
        cli = detect_cli_availability(name)
        if cli["available"]:
            return {**cli, "execution_mode": "cli"}
        return {
            "available": False,
            "execution_mode": "not_connected",
            "evidence": f"{package['evidence']}; {cli['evidence']}",
        }
    if section == "databases":
        implementation = classify_existing_implementation(name)
        if implementation["classification"] == "real":
            mode = "api"
            normalized = _canonical_name(name)
            if normalized in {"bindingdb", "lean magnetdb inference"}:
                mode = "local_file"
            return {
                "available": True,
                "execution_mode": mode,
                "evidence": "API wrapper callable exists; no external query run in Phase 2",
            }
        return {"available": False, "execution_mode": "not_connected", "evidence": "no API config or safe check configured"}
    return {"available": False, "execution_mode": "not_connected", "evidence": "availability not applicable for registry-only section"}


def _status_for_entry(entry: dict[str, Any]) -> dict[str, Any]:
    availability = _availability_for_entry(entry)
    implementation = classify_existing_implementation(entry["name"])
    execution_mode = implementation["execution_mode"]
    if implementation["classification"] == "not_connected":
        execution_mode = availability.get("execution_mode", "not_connected")
    failure_reason = implementation["failure_reason"]
    if availability["available"] is False and failure_reason is None:
        failure_reason = "registered but not available on this server"
    return {
        "name": entry["name"],
        "section": entry["section"],
        "registered": True,
        "available": bool(availability["available"]),
        "executable": bool(implementation["executable"]),
        "classification": implementation["classification"],
        "execution_mode": execution_mode,
        "evidence": {
            "availability": availability["evidence"],
            "implementation": implementation["evidence"],
        },
        "failure_reason": failure_reason,
        "source_sheet": entry["source_sheet"],
        "source_row": entry["source_row"],
        "source_link": _source_link(entry),
    }


def get_all_tool_statuses() -> list[dict[str, Any]]:
    registry = load_toolkit_registry()
    statuses: list[dict[str, Any]] = []
    for section in registry["sections"]:
        for entry in registry[section]:
            statuses.append(_status_for_entry(entry))
    return statuses


def get_tool_status(tool_name: str) -> dict[str, Any]:
    query = _canonical_name(tool_name)
    for status in get_all_tool_statuses():
        if _canonical_name(status["name"]) == query:
            return status
    legacy_implementation = classify_existing_implementation(tool_name)
    if legacy_implementation["classification"] != "not_connected" or query in {"lean magnetdb inference", "drugbank"}:
        availability = {"available": False, "evidence": "legacy/internal tool availability inferred from implementation"}
        if legacy_implementation["classification"] == "real":
            availability["available"] = True
        return {
            "name": tool_name,
            "section": "legacy_internal",
            "registered": False,
            "available": bool(availability["available"]),
            "executable": bool(legacy_implementation["executable"]),
            "classification": legacy_implementation["classification"],
            "execution_mode": legacy_implementation["execution_mode"],
            "evidence": {"availability": availability["evidence"], "implementation": legacy_implementation["evidence"]},
            "failure_reason": legacy_implementation["failure_reason"] or "legacy/internal tool not in Agent_Toolkit.xlsx",
            "source_sheet": None,
            "source_row": None,
            "source_link": None,
        }
    return {
        "name": tool_name,
        "section": None,
        "registered": False,
        "available": False,
        "executable": False,
        "classification": "not_connected",
        "execution_mode": "not_connected",
        "evidence": {"availability": "not present in registry", "implementation": "not present in registry"},
        "failure_reason": "not present in Agent_Toolkit.xlsx",
        "source_sheet": None,
        "source_row": None,
        "source_link": None,
    }


def summarize_toolkit_status() -> dict[str, Any]:
    statuses = get_all_tool_statuses()
    summary = {
        "registered": len(statuses),
        "available": sum(1 for status in statuses if status["available"]),
        "executable": sum(1 for status in statuses if status["executable"]),
        "stub": sum(1 for status in statuses if status["classification"] == "stub"),
        "not_connected": sum(1 for status in statuses if status["classification"] == "not_connected"),
        "by_section": {},
    }
    for status in statuses:
        section = status["section"]
        bucket = summary["by_section"].setdefault(
            section,
            {"registered": 0, "available": 0, "executable": 0, "stub": 0, "not_connected": 0},
        )
        bucket["registered"] += 1
        bucket["available"] += int(status["available"])
        bucket["executable"] += int(status["executable"])
        bucket["stub"] += int(status["classification"] == "stub")
        bucket["not_connected"] += int(status["classification"] == "not_connected")
    return summary
