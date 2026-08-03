"""Agent-callable wrappers for cloned PROTAC research repositories.

The files under ``data/protac_repos/env_specs`` are installation metadata, not
callable tools by themselves. This module exposes safe, workflow-ready wrapper
functions around the cloned repos while keeping heavy workflows manual-only.
It does not run training, docking, folding, notebooks, or external APIs.
"""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any

from synglue_agent.tools.chemistry_core import detect_attachment_points, validate_smiles
from synglue_agent.tools.repo_tool_adapter import PROJECT_ROOT, get_repo_tool, list_repo_tools, repo_tool_status


PROTAC_REPO_DIR = PROJECT_ROOT / "data" / "protac_repos"
REPO_DIR = PROTAC_REPO_DIR / "repos"
ENV_SPEC_DIR = PROTAC_REPO_DIR / "env_specs"

HEAVY_MANUAL_TOOLS = {
    "MEGA-PROTAC": "ternary docking/MEGADOCK-style workflow; manual-only until an explicit safe wrapper is reviewed.",
    "PROTACFold": "AlphaFold/structure-prediction-style workflow; manual-only until heavy execution gates are added.",
    "SE3-protacs": "3D/docking/geometric workflow; manual-only until resource controls are added.",
    "TERNIFY": "ternary complex scoring workflow; example data can be listed safely, but modeling is manual-only.",
    "PROTAC-Degradation-Predictor": "model inference/training repo; no validated local model wrapper is connected.",
    "Machine-Learning-for-Predicting-Targeted-Protein-Degradation": "model training/inference repo; cloned only and not connected.",
    "ProtacGPT": "generative model repo; cloned only and not connected.",
    "protacSpace": "dataset/generation repo; cloned only and not connected.",
    "Bellerophon": "pipeline script repo; assets can be inspected safely, but pipeline execution is manual-only.",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _safe_text(path: Path, max_chars: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception:
        return ""


def _status_payload(name: str) -> dict[str, Any]:
    status = repo_tool_status(name)
    status["agent_callable"] = bool(status.get("registered"))
    status["safe_execution_policy"] = "metadata_and_safe_local_wrappers_only"
    status["heavy_execution_allowed"] = False
    return status


def list_protac_repo_wrappers() -> dict[str, Any]:
    """Return all PROTAC repo tools with callable wrapper status."""

    records = [record for record in list_repo_tools() if record.get("source") == "protac_repos"]
    wrapped = []
    for record in records:
        name = record["name"]
        capability = "metadata_status"
        if name == "degradomap":
            capability = "local_degradomap_csv_loader"
        elif name == "PROTAC-Splitter":
            capability = "safe_input_validation_plus_optional_heuristic_subprocess"
        elif name == "TERNIFY":
            capability = "local_example_complex_catalog"
        elif name == "Bellerophon":
            capability = "local_asset_catalog"
        wrapped.append({**_status_payload(name), "safe_capability": capability})
    return {
        "success": True,
        "records": wrapped,
        "count": len(wrapped),
        "limitations": "Repo wrappers do not imply model/docking/folding execution.",
    }


def get_protac_repo_wrapper_status(name: str) -> dict[str, Any]:
    status = _status_payload(name)
    if not status.get("registered"):
        return status
    status["safe_capabilities"] = []
    canonical = status["name"]
    if canonical == "degradomap":
        status["safe_capabilities"].append("load local degradomap CSV tables")
    if canonical == "PROTAC-Splitter":
        status["safe_capabilities"].append("validate/split with no transformer and no XGBoost when isolated import succeeds")
    if canonical == "TERNIFY":
        status["safe_capabilities"].append("list local ternary example complexes")
    if canonical == "Bellerophon":
        status["safe_capabilities"].append("list local SDF/SVG pipeline assets")
    if canonical in HEAVY_MANUAL_TOOLS:
        status["manual_only_reason"] = HEAVY_MANUAL_TOOLS[canonical]
    return status


def load_env_spec_summary(name: str | None = None) -> dict[str, Any]:
    """Read env spec files as metadata so the agent can explain setup state."""

    specs = []
    paths = sorted(ENV_SPEC_DIR.glob("*")) if name is None else sorted(ENV_SPEC_DIR.glob(f"{name}__*"))
    for path in paths:
        specs.append(
            {
                "repo_name": path.name.split("__", 1)[0] if "__" in path.name else path.stem,
                "path": str(path.relative_to(PROJECT_ROOT)),
                "suffix": path.suffix,
                "exists": path.exists(),
                "preview": _safe_text(path, max_chars=800),
            }
        )
    return {"success": bool(specs), "records": specs, "count": len(specs), "error": None if specs else "no_env_specs_found"}


def smoke_test_protac_repo_import(name: str, import_name: str | None = None, timeout: float = 20.0) -> dict[str, Any]:
    """Run a safe import-only smoke test inside the repo's isolated Python."""

    status = repo_tool_status(name)
    if not status.get("registered"):
        return {**status, "success": False, "status": "missing", "error": "Repo tool is not registered."}
    python_executable = status.get("python_executable")
    if not python_executable:
        return {**status, "success": False, "status": "not_tested", "error": "No isolated Python executable is recorded."}
    py_path = PROJECT_ROOT / python_executable
    if not py_path.exists():
        return {**status, "success": False, "status": "failed", "error": f"Python executable not found: {python_executable}"}
    module_name = import_name or {
        "degradomap": "degradomap",
        "PROTAC-Splitter": "protac_splitter",
        "PROTAC-Degradation-Predictor": "protac_degradation_predictor",
    }.get(status["name"])
    if not module_name:
        return {**status, "success": False, "status": "skipped_manual_review", "error": "No safe import module is mapped for this repo."}
    code = (
        "import importlib, json; "
        f"module=importlib.import_module({module_name!r}); "
        "print(json.dumps({'module': module.__name__, 'file': getattr(module, '__file__', None), "
        "'version': getattr(module, '__version__', None)}))"
    )
    try:
        completed = subprocess.run([str(py_path), "-c", code], check=False, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return {**status, "success": False, "status": "failed", "error": f"Import smoke test failed to run: {exc}"}
    if completed.returncode != 0:
        return {**status, "success": False, "status": "failed", "error": completed.stderr.strip() or completed.stdout.strip()}
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {**status, "success": False, "status": "failed", "error": f"Could not parse import smoke output: {exc}"}
    return {**status, "success": True, "status": "success", "smoke_test": payload}


def load_degradomap_tables(table_name: str | None = None, max_rows: int = 100) -> dict[str, Any]:
    """Load degradomap local CSV tables without running its analysis pipeline."""

    repo = REPO_DIR / "degradomap"
    data_dir = repo / "data"
    if not data_dir.exists():
        return {"success": False, "records": [], "status": "missing", "error": f"degradomap data directory not found: {data_dir}"}
    tables = sorted(data_dir.glob("*.csv"))
    if table_name:
        needle = table_name.lower().replace(".csv", "")
        tables = [path for path in tables if path.stem.lower() == needle or needle in path.stem.lower()]
    records = []
    for path in tables:
        rows = _read_csv(path)
        records.append(
            {
                "table_name": path.name,
                "path": str(path.relative_to(PROJECT_ROOT)),
                "row_count": len(rows),
                "columns": list(rows[0]) if rows else [],
                "preview_rows": rows[: max(0, int(max_rows))],
            }
        )
    return {
        "success": bool(records),
        "status": "ok" if records else "no_tables",
        "records": records,
        "evidence_type": "local_database",
        "tool_status": repo_tool_status("degradomap").get("status"),
        "limitations": "Loaded local degradomap CSV data only; no model fitting, UniProt calls, or analysis pipeline was run.",
    }


def list_ternify_example_complexes() -> dict[str, Any]:
    """Catalog local TERNIFY example complexes without running modeling."""

    data_dir = REPO_DIR / "TERNIFY" / "data"
    if not data_dir.exists():
        return {"success": False, "records": [], "status": "missing", "error": f"TERNIFY data directory not found: {data_dir}"}
    records = []
    for directory in sorted(path for path in data_dir.iterdir() if path.is_dir()):
        expected = ["poi.pdb", "e3.pdb", "protac.sdf", "poi.sdf", "e3.sdf", "tcs.inp"]
        files = {name: (directory / name).exists() for name in expected}
        records.append(
            {
                "complex_id": directory.name,
                "path": str(directory.relative_to(PROJECT_ROOT)),
                "files": files,
                "complete": all(files.values()),
            }
        )
    return {
        "success": bool(records),
        "status": "ok" if records else "no_examples",
        "records": records,
        "evidence_type": "local_files",
        "tool_status": repo_tool_status("TERNIFY").get("status"),
        "limitations": "Catalog only; TERNIFY scoring/modeling was not run.",
    }


def list_bellerophon_assets() -> dict[str, Any]:
    """Catalog Bellerophon local assets without running its pipeline script."""

    repo = REPO_DIR / "Bellerophon"
    if not repo.exists():
        return {"success": False, "records": [], "status": "missing", "error": f"Bellerophon repo not found: {repo}"}
    records = []
    for path in sorted(repo.glob("*")):
        if path.suffix.lower() in {".sdf", ".svg", ".py", ".txt"}:
            records.append(
                {
                    "name": path.name,
                    "path": str(path.relative_to(PROJECT_ROOT)),
                    "suffix": path.suffix,
                    "size_bytes": path.stat().st_size,
                }
            )
    return {
        "success": bool(records),
        "status": "ok" if records else "no_assets",
        "records": records,
        "evidence_type": "local_files",
        "tool_status": repo_tool_status("Bellerophon").get("status"),
        "limitations": "Asset catalog only; Bellerophon pipeline execution remains manual-only.",
    }


def split_protac_with_safe_wrapper(smiles: str, timeout: float = 120.0) -> dict[str, Any]:
    """Try PROTAC-Splitter's no-model heuristic path, with honest fallback."""

    validation = validate_smiles(smiles)
    attachment = detect_attachment_points(smiles)
    base = {
        "input_smiles": smiles,
        "valid_smiles": validation.valid,
        "canonical_smiles": validation.canonical_smiles,
        "attachment_points": attachment,
        "tool_status": repo_tool_status("PROTAC-Splitter").get("status"),
    }
    if not validation.valid:
        return {**base, "success": False, "status": "failed", "error": validation.error}
    status = repo_tool_status("PROTAC-Splitter")
    py = status.get("python_executable")
    py_path = PROJECT_ROOT / py if py else None
    if not py_path or not py_path.exists():
        return {
            **base,
            "success": True,
            "status": "validated_only",
            "split": None,
            "model_name": None,
            "limitations": "PROTAC-Splitter isolated Python is unavailable; returned RDKit validation/attachment metadata only.",
        }
    code = (
        "import json; "
        "from protac_splitter.protac_splitter import split_protac; "
        f"result=split_protac({smiles!r}, use_transformer=False, use_xgboost=False); "
        "print(json.dumps(result))"
    )
    try:
        completed = subprocess.run([str(py_path), "-c", code], check=False, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return {**base, "success": False, "status": "failed", "error": f"PROTAC-Splitter wrapper failed to run: {exc}"}
    if completed.returncode != 0:
        return {
            **base,
            "success": True,
            "status": "validated_only",
            "split": None,
            "model_name": None,
            "error": completed.stderr.strip() or completed.stdout.strip(),
            "limitations": "PROTAC-Splitter heuristic path did not run; returned RDKit validation/attachment metadata only.",
        }
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {**base, "success": False, "status": "failed", "error": f"Could not parse PROTAC-Splitter output: {exc}"}
    return {
        **base,
        "success": True,
        "status": "ok",
        "split": payload.get("default_pred_n0"),
        "model_name": payload.get("model_name"),
        "raw_output": payload,
        "limitations": "No transformer, XGBoost, download, or training path was used.",
    }


def protac_degradation_predictor_status() -> dict[str, Any]:
    """Return model-wrapper readiness without running prediction/training."""

    status = get_protac_repo_wrapper_status("PROTAC-Degradation-Predictor")
    status.update(
        {
            "success": False,
            "prediction_available": False,
            "status": "manual_only",
            "error": "No validated local model checkpoint/input schema wrapper is connected.",
            "claim_allowed": "Do not claim PROTAC-Degradation-Predictor inference until a model wrapper smoke test succeeds.",
        }
    )
    return status


def manual_only_tool_response(name: str, task: str | None = None) -> dict[str, Any]:
    status = get_protac_repo_wrapper_status(name)
    reason = HEAVY_MANUAL_TOOLS.get(status.get("name", name), "Manual review required before execution.")
    return {
        **status,
        "success": False,
        "status": "unsafe_heavy_manual_only",
        "task": task,
        "error": reason,
        "claim_allowed": "May claim repo is present/configured only; no scientific result was generated.",
    }


def execute_protac_repo_tool(name: str, task: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dispatch safe repo-backed operations for agent workflows."""

    inputs = inputs or {}
    record = get_repo_tool(name)
    if record is None:
        return {"success": False, "status": "missing", "name": name, "error": "No matching PROTAC repo tool found."}
    canonical = record["name"]
    task_l = (task or "").lower()
    if canonical == "degradomap" and any(term in task_l for term in ["load", "table", "e3", "expression", "degradomap"]):
        return load_degradomap_tables(inputs.get("table_name"), max_rows=int(inputs.get("max_rows", 100)))
    if canonical == "TERNIFY" and any(term in task_l for term in ["list", "example", "catalog", "data"]):
        return list_ternify_example_complexes()
    if canonical == "Bellerophon" and any(term in task_l for term in ["asset", "list", "catalog", "sdf"]):
        return list_bellerophon_assets()
    if canonical == "PROTAC-Splitter" and any(term in task_l for term in ["split", "component", "validate"]):
        return split_protac_with_safe_wrapper(str(inputs.get("smiles", "")))
    if canonical == "PROTAC-Degradation-Predictor":
        return protac_degradation_predictor_status()
    return manual_only_tool_response(canonical, task)


__all__ = [
    "execute_protac_repo_tool",
    "get_protac_repo_wrapper_status",
    "list_protac_repo_wrappers",
    "load_env_spec_summary",
    "smoke_test_protac_repo_import",
    "load_degradomap_tables",
    "list_ternify_example_complexes",
    "list_bellerophon_assets",
    "split_protac_with_safe_wrapper",
    "protac_degradation_predictor_status",
    "manual_only_tool_response",
]
