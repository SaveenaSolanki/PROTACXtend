#!/usr/bin/env python3
"""Verify isolated PROTAC repository environment status without running repo code."""

from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


BASE_DIR = Path("data/protac_repos")
CSV_PATH = BASE_DIR / "all_repo_install_verification.csv"
MD_PATH = BASE_DIR / "all_repo_install_verification.md"
INSTALL_LOG_DIR = BASE_DIR / "install_logs"


@dataclass
class EnvSpec:
    repo_name: str
    env_kind: str
    env_name_or_path: str
    repo_path: str
    install_log_path: str
    recommended_wrapper_type: str


ENV_SPECS = [
    EnvSpec("TERNIFY", "venv", ".venvs/protac-ternify", "data/protac_repos/repos/TERNIFY", "data/protac_repos/install_logs/ternify_install.log", "python_function_adapter"),
    EnvSpec("PROTAC-Splitter", "venv", ".venvs/protac-splitter", "data/protac_repos/repos/PROTAC-Splitter", "data/protac_repos/install_logs/protac_splitter_editable.log", "python_package_adapter_after_import_smoke_test"),
    EnvSpec("Bellerophon", "venv", ".venvs/protac-bellerophon", "data/protac_repos/repos/Bellerophon", "data/protac_repos/install_logs/bellerophon_install.log", "python_script_adapter_after_manual_review"),
    EnvSpec("degradomap", "venv", ".venvs/protac-degradomap", "data/protac_repos/repos/degradomap", "data/protac_repos/install_logs/degradomap_editable.log", "metadata_or_pipeline_adapter_after_manual_review"),
    EnvSpec("PROTACFold", "venv", ".venvs/protac-protacfold", "data/protac_repos/repos/PROTACFold", "data/protac_repos/install_logs/protacfold_install.log", "manual_wrapper_only_due_alphafold_review"),
    EnvSpec("PROTAC-RL", "conda", "protac-rl", "data/protac_repos/repos/PROTAC-RL", "data/protac_repos/install_logs/protac_rl_conda.log", "model_utility_adapter_after_import_smoke_test"),
    EnvSpec("PROTAC-Degradation-Predictor", "conda", "protac-degradation-predictor", "data/protac_repos/repos/PROTAC-Degradation-Predictor", "data/protac_repos/install_logs/protac_degradation_predictor_conda.log", "python_package_adapter_after_import_smoke_test"),
    EnvSpec("MEGA-PROTAC", "conda", "protac-mega-protac", "data/protac_repos/repos/MEGA-PROTAC", "data/protac_repos/install_logs/mega_protac_conda.log", "manual_wrapper_only_due_megadock_review"),
    EnvSpec("SE3-protacs", "conda", "protac-se3-protacs", "data/protac_repos/repos/SE3-protacs", "data/protac_repos/install_logs/se3_protacs_conda.log", "manual_wrapper_only_due_docking_review"),
]

EXTERNAL_BINARIES = [
    "obabel",
    "babel",
    "vina",
    "gnina",
    "megadock",
    "megadock-gpu",
    "alphafold",
    "rosetta_scripts",
    "rosetta_scripts.linuxgccrelease",
    "relax",
    "docking_protocol",
]


def run(args: list[str], env: dict[str, str] | None = None, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env=env,
        timeout=timeout,
    )


def conda_env_prefixes() -> dict[str, str]:
    result = run(["conda", "env", "list"], timeout=30)
    prefixes: dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace("*", " ").split()
        if not parts:
            continue
        path = parts[-1]
        if "/" not in path:
            continue
        name = Path(path).name
        prefixes[name] = path
        if len(parts) >= 2 and "/" not in parts[0]:
            prefixes[parts[0]] = path
    return prefixes


def python_path_for(spec: EnvSpec, conda_prefixes: dict[str, str]) -> tuple[str, bool, str]:
    if spec.env_kind == "venv":
        env_path = Path(spec.env_name_or_path)
        python = env_path / "bin" / "python"
        return str(python), python.exists(), str(env_path)

    prefix = conda_prefixes.get(spec.env_name_or_path)
    if not prefix:
        candidates = [path for name, path in conda_prefixes.items() if name == spec.env_name_or_path]
        prefix = candidates[0] if candidates else ""
    python = Path(prefix) / "bin" / "python" if prefix else Path()
    return str(python), bool(prefix and python.exists()), prefix or spec.env_name_or_path


def env_for_python(python_path: str) -> dict[str, str]:
    env = os.environ.copy()
    bin_dir = str(Path(python_path).parent)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    return env


def one_line_output(result: subprocess.CompletedProcess[str], limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", result.stdout.strip())
    return text[:limit] if text else ""


def python_version(python_path: str, env: dict[str, str]) -> tuple[str, bool]:
    result = run([python_path, "--version"], env=env)
    return one_line_output(result), result.returncode == 0


def pip_check(python_path: str, env: dict[str, str]) -> tuple[bool, str]:
    result = run([python_path, "-m", "pip", "check"], env=env, timeout=90)
    output = one_line_output(result, limit=1200)
    return result.returncode == 0, output or "no output"


def import_check(python_path: str, env: dict[str, str], module: str, version_expr: str = "") -> str:
    default_expr = f'getattr({module}, "__version__", "import_ok")'
    expr = version_expr or default_expr
    code = f"import {module}\nprint({expr})\n"
    result = run([python_path, "-c", code], env=env, timeout=45)
    if result.returncode == 0:
        return "ok: " + one_line_output(result, limit=200)
    return "missing/error: " + one_line_output(result, limit=300)


def openbabel_import_check(python_path: str, env: dict[str, str]) -> str:
    code = (
        "try:\n"
        "    from openbabel import openbabel\n"
        "    print('ok: openbabel package')\n"
        "except Exception as exc:\n"
        "    try:\n"
        "        import openbabel\n"
        "        print('ok: openbabel module')\n"
        "    except Exception as exc2:\n"
        "        print(f'missing/error: {type(exc2).__name__}: {exc2}')\n"
        "        raise SystemExit(1)\n"
    )
    result = run([python_path, "-c", code], env=env, timeout=45)
    return one_line_output(result, limit=300)


def binary_availability(env: dict[str, str]) -> str:
    found = []
    missing = []
    for binary in EXTERNAL_BINARIES:
        path = shutil.which(binary, path=env.get("PATH"))
        if path:
            found.append(f"{binary}={path}")
        else:
            missing.append(binary)
    return "found: " + ", ".join(found) if found else "none found; missing: " + ", ".join(missing)


def log_status(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "install log not found"
    text = path.read_text(encoding="utf-8", errors="replace")
    tail = "\n".join(text.splitlines()[-25:]).lower()
    if any(token in tail for token in ["error", "failed", "not found", "could not", "no matching distribution"]):
        return True, "log exists; warning/error wording found near tail"
    if any(token in tail for token in ["success", "successfully", "done", "installed", "complete"]):
        return True, "log exists; success-like wording found near tail"
    return True, "log exists; no clear success/failure marker in tail"


def safe_wrapper_possible(spec: EnvSpec, install_success: bool, external_availability: str) -> tuple[bool, str]:
    heavy_manual = spec.repo_name in {"PROTACFold", "MEGA-PROTAC", "SE3-protacs"}
    if not install_success:
        return False, "no; resolve environment or missing dependency issues first"
    if heavy_manual:
        return False, "not yet; requires manual review of heavy docking/AlphaFold/MEGADOCK style dependencies"
    return True, "yes; only after later repo-specific smoke import/API review"


def verify_one(spec: EnvSpec, conda_prefixes: dict[str, str]) -> dict[str, object]:
    python_path, env_found, resolved_env = python_path_for(spec, conda_prefixes)
    env = env_for_python(python_path) if env_found else os.environ.copy()
    log_exists, log_note = log_status(Path(spec.install_log_path))

    if env_found:
        py_version, python_ok = python_version(python_path, env)
        pip_ok, pip_output = pip_check(python_path, env)
        rdkit_status = import_check(python_path, env, "rdkit")
        torch_status = import_check(python_path, env, "torch")
        openbabel_status = openbabel_import_check(python_path, env)
        binaries = binary_availability(env)
    else:
        py_version = "environment python not found"
        python_ok = False
        pip_ok = False
        pip_output = "not checked because environment python was not found"
        rdkit_status = "not checked"
        torch_status = "not checked"
        openbabel_status = "not checked"
        binaries = "not checked"

    missing_dependencies = "none reported by pip check" if pip_ok else pip_output
    install_appears_successful = bool(env_found and python_ok and pip_ok)
    wrapper_possible, wrapper_note = safe_wrapper_possible(spec, install_appears_successful, binaries)
    notes = "; ".join(
        [
            log_note,
            "repository code not imported or executed",
            wrapper_note,
        ]
    )

    return {
        "repo_name": spec.repo_name,
        "environment_name_or_path": spec.env_name_or_path,
        "environment_kind": spec.env_kind,
        "resolved_environment_path": resolved_env,
        "python_executable": python_path,
        "python_version": py_version,
        "install_log_path": spec.install_log_path,
        "install_log_found": log_exists,
        "install_appears_successful": install_appears_successful,
        "missing_dependencies": missing_dependencies,
        "rdkit_import_status": rdkit_status,
        "pytorch_import_status": torch_status,
        "openbabel_import_status": openbabel_status,
        "openbabel_obabel_availability": "available" if "obabel=" in binaries or "babel=" in binaries else "not found",
        "external_binary_availability": binaries,
        "safe_wrapper_integration_possible": wrapper_possible,
        "recommended_wrapper_type": spec.recommended_wrapper_type,
        "notes": notes,
    }


def write_markdown(df: pd.DataFrame) -> None:
    lines = [
        "# All PROTAC Repo Install Verification",
        "",
        "This verification inspected isolated environments only. It did not run repository workflows, notebooks, training, docking, AlphaFold, MEGADOCK, Rosetta, CLIs, or imports from cloned repository packages.",
        "",
        "Checks performed: environment Python version, `python -m pip check`, RDKit import, PyTorch import, OpenBabel Python import, and external binary path lookup.",
        "",
    ]
    for row in df.to_dict("records"):
        lines.extend(
            [
                f"## {row['repo_name']}",
                "",
                f"- Environment: `{row['environment_name_or_path']}` ({row['environment_kind']})",
                f"- Resolved path: `{row['resolved_environment_path']}`",
                f"- Python version: `{row['python_version']}`",
                f"- Install log: `{row['install_log_path']}`",
                f"- Install appears successful: `{row['install_appears_successful']}`",
                f"- Missing dependencies: {row['missing_dependencies']}",
                f"- RDKit import status: {row['rdkit_import_status']}",
                f"- PyTorch import status: {row['pytorch_import_status']}",
                f"- OpenBabel import status: {row['openbabel_import_status']}",
                f"- OpenBabel/obabel availability: {row['openbabel_obabel_availability']}",
                f"- External binary availability: {row['external_binary_availability']}",
                f"- Safe wrapper integration possible: `{row['safe_wrapper_integration_possible']}`",
                f"- Recommended wrapper type: `{row['recommended_wrapper_type']}`",
                f"- Notes: {row['notes']}",
                "",
            ]
        )
    MD_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    conda_prefixes = conda_env_prefixes()
    rows = [verify_one(spec, conda_prefixes) for spec in ENV_SPECS]
    df = pd.DataFrame(rows)
    df.to_csv(CSV_PATH, index=False, quoting=csv.QUOTE_MINIMAL)
    write_markdown(df)

    print(f"verified environments: {len(df)}")
    print(f"appears successful: {int(df['install_appears_successful'].sum())}")
    print(f"safe wrapper possible now: {int(df['safe_wrapper_integration_possible'].sum())}")
    print(f"csv path: {CSV_PATH}")
    print(f"markdown path: {MD_PATH}")


if __name__ == "__main__":
    main()
