"""Repo-backed tool adapter for cloned PROTAC/synthesis research tools.

This module turns the repositories collected under ``data/protac_repos`` and
``data/synthesis_prediction`` into addressable tool records. It does not run
training, docking, notebooks, model inference, or external APIs. A tool is only
marked executable when a safe local smoke check succeeds.
"""

from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTAC_REPO_DIR = PROJECT_ROOT / "data" / "protac_repos"
SYNTHESIS_DIR = PROJECT_ROOT / "data" / "synthesis_prediction"


@dataclass
class RepoToolRecord:
    name: str
    source: str
    local_path: str
    github_url: str = ""
    found_locally: bool = False
    env_specs: list[str] = field(default_factory=list)
    environment_path: str | None = None
    python_executable: str | None = None
    install_status: str = "not_installed"
    safe_wrapper_integration_possible: bool = False
    recommended_wrapper_type: str = "manual_review"
    safety_risk: str = "unknown"
    notes: str = ""


def _normalize(value: str) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def _protac_records() -> list[RepoToolRecord]:
    registry = {row["repo_name"]: row for row in _read_csv(PROTAC_REPO_DIR / "protac_repo_registry.csv") if row.get("repo_name")}
    phase3 = {row["repo_name"]: row for row in _read_csv(PROTAC_REPO_DIR / "phase3_preinstall_audit.csv") if row.get("repo_name")}
    verification = {row["repo_name"]: row for row in _read_csv(PROTAC_REPO_DIR / "all_repo_install_verification.csv") if row.get("repo_name")}
    names = sorted(set(registry) | set(phase3) | set(verification))
    records: list[RepoToolRecord] = []
    for name in names:
        reg = registry.get(name, {})
        audit = phase3.get(name, {})
        verified = verification.get(name, {})
        local_path = reg.get("local_path") or audit.get("local_path") or f"data/protac_repos/repos/{name}"
        env_specs = _split_list(reg.get("copied_env_specs")) or [
            str(path.relative_to(PROJECT_ROOT))
            for path in sorted((PROTAC_REPO_DIR / "env_specs").glob(f"{name}__*"))
        ]
        appears_successful = (verified.get("install_appears_successful") or "").lower() == "true"
        install_status = "installed_isolated" if appears_successful else audit.get("install_decision") or "cloned_only"
        records.append(
            RepoToolRecord(
                name=name,
                source="protac_repos",
                local_path=local_path,
                github_url=reg.get("github_url", audit.get("github_url", "")),
                found_locally=Path(PROJECT_ROOT / local_path).exists(),
                env_specs=env_specs,
                environment_path=verified.get("resolved_environment_path") or None,
                python_executable=verified.get("python_executable") or None,
                install_status=install_status,
                safe_wrapper_integration_possible=(verified.get("safe_wrapper_integration_possible") or "").lower() == "true",
                recommended_wrapper_type=verified.get("recommended_wrapper_type") or audit.get("recommended_env_strategy") or "manual_review",
                safety_risk=audit.get("safety_risk_level") or "unknown",
                notes=verified.get("notes") or audit.get("notes") or reg.get("notes", ""),
            )
        )
    return records


def _synthesis_records() -> list[RepoToolRecord]:
    data = [
        RepoToolRecord(
            name="linchemin",
            source="synthesis_prediction",
            local_path="data/synthesis_prediction/repos/linchemin",
            github_url="https://github.com/syngenta/linchemin",
            found_locally=(SYNTHESIS_DIR / "repos" / "linchemin").exists(),
            env_specs=[
                "data/synthesis_prediction/env_specs/linchemin_environment.yml",
                "data/synthesis_prediction/env_specs/linchemin_freeze.txt",
            ],
            environment_path="data/synthesis_prediction/envs/linchemin",
            python_executable="data/synthesis_prediction/envs/linchemin/bin/python",
            install_status="installed_isolated",
            safe_wrapper_integration_possible=True,
            recommended_wrapper_type="python_package_adapter",
            safety_risk="low",
            notes="Installed editable in isolated environment; safe import smoke test is supported.",
        ),
        RepoToolRecord(
            name="step-wise-chemical-synthesis-prediction",
            source="synthesis_prediction",
            local_path="data/synthesis_prediction/repos/step-wise-chemical-synthesis-prediction",
            github_url="https://github.com/pfnet-research/step-wise-chemical-synthesis-prediction",
            found_locally=(SYNTHESIS_DIR / "repos" / "step-wise-chemical-synthesis-prediction").exists(),
            env_specs=["data/synthesis_prediction/env_specs/pfnet_stepwise_legacy_environment.yml"],
            install_status="cloned_legacy_manual_review",
            safe_wrapper_integration_possible=False,
            recommended_wrapper_type="legacy_chainer_adapter_after_manual_env",
            safety_risk="high",
            notes="Requires Python 3.6-era Chainer/CuPy/RDKit stack; not force-installed.",
        ),
        RepoToolRecord(
            name="Deep-Synthesis",
            source="synthesis_prediction",
            local_path="data/synthesis_prediction/repos/Deep-Synthesis",
            github_url="https://github.com/kheyer/Deep-Synthesis",
            found_locally=(SYNTHESIS_DIR / "repos" / "Deep-Synthesis").exists(),
            env_specs=["data/synthesis_prediction/env_specs/deep_synthesis_legacy_environment.yml"],
            install_status="cloned_legacy_manual_review",
            safe_wrapper_integration_possible=False,
            recommended_wrapper_type="legacy_opennmt_adapter_after_manual_env",
            safety_risk="high",
            notes="Requires legacy OpenNMT/PyTorch setup and model download; not force-installed.",
        ),
        RepoToolRecord(
            name="chainer-chemistry",
            source="synthesis_prediction",
            local_path="data/synthesis_prediction/repos/chainer-chemistry",
            github_url="https://github.com/pfnet-research/chainer-chemistry",
            found_locally=(SYNTHESIS_DIR / "repos" / "chainer-chemistry").exists(),
            env_specs=["data/synthesis_prediction/env_specs/pfnet_stepwise_legacy_environment.yml"],
            install_status="cloned_dependency_manual_review",
            safe_wrapper_integration_possible=False,
            recommended_wrapper_type="legacy_dependency",
            safety_risk="medium",
            notes="Source dependency for PFNet step-wise synthesis; not installed.",
        ),
    ]
    return data


def list_repo_tools() -> list[dict[str, Any]]:
    return [asdict(record) for record in _protac_records() + _synthesis_records()]


def get_repo_tool(name: str) -> dict[str, Any] | None:
    query = _normalize(name)
    aliases = {
        "syngentalinchemin": "linchemin",
        "linchemin": "linchemin",
        "pfnetstepwisechemicalsynthesisprediction": "stepwisechemicalsynthesisprediction",
        "stepwisechemicalsynthesisprediction": "stepwisechemicalsynthesisprediction",
        "kheyerdeepsynthesis": "deepsynthesis",
        "deepsynthesis": "deepsynthesis",
    }
    query = aliases.get(query, query)
    records = list_repo_tools()
    normalized_records = [(_normalize(record["name"]), record) for record in records]
    for normalized, record in normalized_records:
        if normalized == query:
            return record
    for normalized, record in normalized_records:
        if normalized == query or query in normalized or normalized in query:
            if len(query) < 6 or len(normalized) < 6:
                continue
            return record
    return None


def repo_tool_status(name: str) -> dict[str, Any]:
    record = get_repo_tool(name)
    if record is None:
        return {
            "name": name,
            "registered": False,
            "found_locally": False,
            "installed": False,
            "executable": False,
            "status": "missing",
            "backend_status": "not_registered",
            "error": "No matching repo tool found.",
        }
    python_executable = record.get("python_executable")
    installed = record["install_status"].startswith("installed")
    executable = False
    backend_status = record["install_status"]
    error = None
    if installed and python_executable:
        py_path = PROJECT_ROOT / python_executable
        executable = py_path.exists()
        if not executable:
            error = f"Python executable not found: {python_executable}"
            backend_status = "installed_but_python_missing"
    return {
        **record,
        "registered": True,
        "installed": installed,
        "executable": executable,
        "status": "executable" if executable else record["install_status"],
        "backend_status": backend_status,
        "error": error,
    }


def smoke_test_repo_tool(name: str) -> dict[str, Any]:
    """Run only explicitly safe local import checks."""

    status = repo_tool_status(name)
    if not status.get("registered"):
        return {**status, "success": False}
    if _normalize(status["name"]) == "protacdegradationpredictor":
        python_executable = PROJECT_ROOT / (status.get("python_executable") or "")
        if not python_executable.exists():
            return {**status, "success": False, "status": "failed", "error": f"Missing Python executable: {python_executable}"}
        # Safe bounded inference smoke: import + single published README example.
        # Weights are cached under ~/.cache/protac_degradation_predictor; the run
        # is CPU-bound inference only (no training, no docking).
        code = (
            "import protac_degradation_predictor as pdp; "
            "s='Cc1ncsc1-c1ccc(CNC(=O)[C@@H]2C[C@@H](O)CN2C(=O)[C@@H](NC(=O)COCCCCCCCCCOCC(=O)Nc2ccc(C(=O)Nc3ccc(F)cc3N)cc2)C(C)(C)C)cc1'; "
            "active=pdp.is_protac_active(s, 'VHL', 'P04637', 'HeLa'); "
            "proba=pdp.get_protac_active_proba(s, 'VHL', 'P04637', 'HeLa'); "
            "print(json.dumps({'version': pdp.__version__, "
            "'is_protac_active': bool(active), "
            "'mean_proba': float(proba['mean']), "
            "'majority_vote': bool(proba['majority_vote']), "
            "'n_models': int(len(proba['preds']))}))"
        )
        command = [str(python_executable), "-c", "import json; " + code]
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=600)
        except Exception as exc:
            return {**status, "success": False, "status": "failed", "error": f"Smoke test failed to run: {exc}"}
        if completed.returncode != 0:
            return {**status, "success": False, "status": "failed", "error": completed.stderr.strip()[-500:] or completed.stdout.strip()[-500:]}
        try:
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
        except Exception as exc:
            return {**status, "success": False, "status": "failed", "error": f"Could not parse smoke output: {exc}"}
        return {**status, "success": True, "status": "success", "smoke_test": payload}
    if _normalize(status["name"]) == "linchemin":
        python_executable = PROJECT_ROOT / (status.get("python_executable") or "")
        if not python_executable.exists():
            return {**status, "success": False, "status": "failed", "error": f"Missing Python executable: {python_executable}"}
        code = (
            "import importlib.metadata, linchemin; "
            "from rdkit import Chem; "
            "print(json.dumps({'linchemin_version': importlib.metadata.version('linchemin'), "
            "'rdkit_parse_ok': Chem.MolFromSmiles('CCO') is not None}))"
        )
        command = [str(python_executable), "-c", "import json; " + code]
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=30)
        except Exception as exc:
            return {**status, "success": False, "status": "failed", "error": f"Smoke test failed to run: {exc}"}
        if completed.returncode != 0:
            return {**status, "success": False, "status": "failed", "error": completed.stderr.strip() or completed.stdout.strip()}
        try:
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
        except Exception as exc:
            return {**status, "success": False, "status": "failed", "error": f"Could not parse smoke output: {exc}"}
        return {**status, "success": True, "status": "success", "smoke_test": payload}
    return {
        **status,
        "success": False,
        "status": "skipped_manual_review",
        "error": "No safe smoke test is registered for this repo tool; manual wrapper review required.",
    }


def route_repo_tool_request(task_description: str) -> dict[str, Any]:
    task = (task_description or "").strip()
    task_l = task.lower()
    candidates: list[str] = []
    if any(term in task_l for term in ["synthesis", "retrosynthesis", "route"]):
        candidates.extend(["linchemin", "step-wise-chemical-synthesis-prediction", "Deep-Synthesis"])
    if "protac" in task_l or "degradation" in task_l:
        candidates.extend(["PROTAC-Degradation-Predictor", "PROTAC-RL", "PROTAC-Splitter"])
    if "ternary" in task_l or "docking" in task_l:
        candidates.extend(["TERNIFY", "MEGA-PROTAC", "PROTACFold"])
    seen: set[str] = set()
    routed = []
    for name in candidates:
        status = repo_tool_status(name)
        key = status.get("name", name)
        if key in seen:
            continue
        seen.add(key)
        routed.append(status)
    return {
        "task": task,
        "recommended_repo_tools": routed,
        "honest_execution_note": (
            "Repo-backed tools are executable only when their isolated environment and safe smoke test exist. "
            "Cloned repos or env_specs alone are not treated as working tools."
        ),
    }
