#!/usr/bin/env python3
"""Phase 3 safe pre-install audit for selected PROTAC repositories.

The audit only reads static files and writes reports. It does not install
packages, execute cloned repository code, run notebooks, import repo modules,
launch CLIs, run docking, run training, or modify cloned repositories.
"""

from __future__ import annotations

import csv
import os
import re
from pathlib import Path

import pandas as pd


BASE_DIR = Path("data/protac_repos")
REGISTRY_PATH = BASE_DIR / "protac_repo_registry.csv"
PHASE2_MATRIX_PATH = BASE_DIR / "phase2_env_matrix.csv"
AUDIT_CSV_PATH = BASE_DIR / "phase3_preinstall_audit.csv"
AUDIT_XLSX_PATH = BASE_DIR / "phase3_preinstall_audit.xlsx"
AUDIT_MD_PATH = BASE_DIR / "phase3_preinstall_audit.md"
INSTALL_ORDER_MD_PATH = BASE_DIR / "phase3_recommended_install_order.md"
SAFE_COMMANDS_PATH = BASE_DIR / "phase3_safe_commands.sh"

SELECTED_REPOS = [
    "PROTAC-RL",
    "PROTACFold",
    "MEGA-PROTAC",
    "SE3-protacs",
    "PROTAC-Degradation-Predictor",
    "TERNIFY",
    "PROTAC-Splitter",
    "Bellerophon",
    "degradomap",
]

STATIC_FILES = [
    "README.md",
    "README.rst",
    "LICENSE",
    "LICENSE.txt",
    "COPYING",
    "requirements.txt",
    "requirements-dev.txt",
    "environment.yml",
    "environment.yaml",
    "conda.yml",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Dockerfile",
    "docker-compose.yml",
]
DEPENDENCY_FILES = [
    "requirements.txt",
    "requirements-dev.txt",
    "environment.yml",
    "environment.yaml",
    "conda.yml",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Dockerfile",
    "docker-compose.yml",
]
CONDA_FILES = ["environment.yml", "environment.yaml", "conda.yml"]
LICENSE_FILES = ["LICENSE", "LICENSE.txt", "COPYING"]
README_FILES = ["README.md", "README.rst"]
SCRIPT_SUFFIXES = {".py", ".sh", ".R"}
DATA_FOLDER_TERMS = {"data", "dataset", "datasets", "benchmark", "benchmarks"}
MODEL_FOLDER_TERMS = {"model", "models", "checkpoint", "checkpoints", "weight", "weights", "ckpt", "pretrained"}

KEYWORDS = {
    "torch_requirement": [r"\bpytorch\b", r"\btorch\b"],
    "tensorflow_requirement": [r"\btensorflow\b", r"\btf\b"],
    "cuda_or_gpu_required": [r"\bcuda\b", r"\bgpu\b", r"\bnvidia\b"],
    "rdkit_required": [r"\brdkit\b"],
    "openbabel_required": [r"\bopenbabel\b", r"\bopen babel\b", r"\bobabel\b"],
    "vina_or_gnina_required": [r"\bvina\b", r"\bautodock\b", r"\bgnina\b"],
    "megadock_required": [r"\bmegadock\b", r"\bmega dock\b"],
    "alphafold_required": [r"\balphafold\b", r"\balpha fold\b"],
    "rosetta_required": [r"\brosetta\b"],
    "ccdc_or_csd_required": [r"\bccdc\b", r"\bcsd python api\b", r"\bcsd\b"],
    "large_datasets": [r"\blarge dataset\b", r"\bfull dataset\b", r"\bdownload dataset\b", r"\bzenodo\b"],
    "pretrained_checkpoints": [r"\bpretrained\b", r"\bcheckpoint\b", r"\bweights?\b", r"\bckpt\b"],
    "training_keywords_detected": [r"\btrain\b", r"\btraining\b", r"\btrainer\b", r"\bepoch\b"],
    "docking_keywords_detected": [r"\bdocking\b", r"\bdock\b", r"\bpose\b", r"\bternary complex\b"],
}
EXTERNAL_BINARY_PATTERNS = [
    r"\bmegadock\b",
    r"\brosetta\b",
    r"\balphafold\b",
    r"\bvina\b",
    r"\bautodock\b",
    r"\bgnina\b",
    r"\bopenbabel\b",
    r"\bobabel\b",
    r"\bccdc\b",
    r"\bcsd python api\b",
    r"\bcsd\b",
    r"\bapt[- ]get\b",
    r"\bapt install\b",
    r"\bsystem package\b",
]


def safe_env_name(repo_name: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", repo_name.lower())
    name = re.sub(r"-+", "-", name).strip("-")
    return name if name.startswith("protac-") else f"protac-{name}"


def read_small_text(path: Path, max_bytes: int = 300_000) -> str:
    if not path.is_file():
        return ""
    try:
        if path.stat().st_size > max_bytes:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect_root_files(repo_path: Path) -> list[str]:
    return [name for name in STATIC_FILES if (repo_path / name).exists()]


def collect_static_text(repo_path: Path, detected_files: list[str]) -> str:
    parts = []
    for name in detected_files:
        if name in STATIC_FILES:
            parts.append(read_small_text(repo_path / name))
    return "\n".join(part for part in parts if part).lower()


def detect_python_requirement(text: str) -> str:
    patterns = [
        r"python\s*(?:version|>=|==|=|:)?\s*([23](?:\.\d+){1,2})",
        r"python_requires\s*=\s*[\"']?([^\"'\n,]+)",
        r"python\s*[>=<~!, ]+([23]\.\d+)",
    ]
    matches = []
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            cleaned = re.sub(r"\s+", " ", str(match)).strip()
            if cleaned and cleaned not in matches:
                matches.append(cleaned)
    return "; ".join(matches[:5]) if matches else "not detected"


def match_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def find_notebooks(repo_path: Path) -> list[str]:
    try:
        return sorted(str(path.relative_to(repo_path)) for path in repo_path.rglob("*.ipynb") if ".git" not in path.parts)
    except OSError:
        return []


def find_scripts(repo_path: Path) -> list[str]:
    scripts = []
    try:
        for path in repo_path.rglob("*"):
            if ".git" in path.parts or not path.is_file():
                continue
            if path.suffix in SCRIPT_SUFFIXES:
                scripts.append(str(path.relative_to(repo_path)))
    except OSError:
        return []
    return sorted(scripts)


def find_named_folders(repo_path: Path, terms: set[str]) -> list[str]:
    folders = []
    try:
        for path in repo_path.rglob("*"):
            if ".git" in path.parts or not path.is_dir():
                continue
            lowered = path.name.lower()
            if lowered in terms or any(term in lowered for term in terms):
                folders.append(str(path.relative_to(repo_path)))
    except OSError:
        return []
    return sorted(folders)


def likely_repo_role(repo_name: str, text: str, notebooks: list[str], data_folders: list[str], model_folders: list[str]) -> str:
    combined = f"{repo_name.lower()} {text}"
    roles = []
    if any(term in combined for term in ["docking", "ternary", "alphafold", "megadock", "rosetta", "conformer"]):
        roles.append("ternary-complex/docking workflow")
    if any(term in combined for term in ["predict", "model", "learning", "rl", "gpt", "degradation"]):
        roles.append("model or prediction utility")
    if any(term in combined for term in ["splitter", "descriptor", "rdkit", "molecule", "linker"]):
        roles.append("molecular processing utility")
    if data_folders or any(term in combined for term in ["dataset", "benchmark", "database"]):
        roles.append("dataset/benchmark/reference")
    if notebooks:
        roles.append("notebook-oriented workflow")
    if model_folders:
        roles.append("checkpoint/model-assets repository")
    return "; ".join(dict.fromkeys(roles)) if roles else "unclear/manual review"


def recommended_env_strategy(dependency_files: list[str], docker_recommended: bool) -> str:
    strategies = []
    if any(name in dependency_files for name in CONDA_FILES):
        strategies.append("conda/mamba")
    if "requirements.txt" in dependency_files:
        strategies.append("venv/pip")
    if any(name in dependency_files for name in ["pyproject.toml", "setup.py"]):
        strategies.append("editable-venv")
    if "Dockerfile" in dependency_files or docker_recommended:
        strategies.append("docker-manual-review")
    return "; ".join(dict.fromkeys(strategies)) if strategies else "manual inspection required"


def safe_command(repo_name: str, repo_path: Path, dependency_files: list[str], docker_recommended: bool) -> str:
    env_name = safe_env_name(repo_name)
    conda_file = next((name for name in CONDA_FILES if name in dependency_files), None)
    if conda_file:
        return f"mamba env create -n {env_name} -f {repo_path / conda_file}"
    if "requirements.txt" in dependency_files:
        return (
            f"python -m venv .venvs/{env_name} && "
            f"source .venvs/{env_name}/bin/activate && "
            f"python -m pip install --upgrade pip && "
            f"pip install -r {repo_path / 'requirements.txt'}"
        )
    if any(name in dependency_files for name in ["pyproject.toml", "setup.py"]):
        return (
            f"python -m venv .venvs/{env_name} && "
            f"source .venvs/{env_name}/bin/activate && "
            f"python -m pip install --upgrade pip && "
            f"pip install -e {repo_path}"
        )
    if "Dockerfile" in dependency_files or docker_recommended:
        return f"docker build -t protac-toolkit/{env_name}:latest {repo_path}"
    return "manual inspection required"


def score_install_now_candidate(row: dict[str, object]) -> int:
    score = 0
    dependency_files = str(row["dependency_files_detected"])
    if "environment.yml" in dependency_files or "requirements.txt" in dependency_files:
        score += 4
    if "setup.py" in dependency_files or "pyproject.toml" in dependency_files:
        score += 2
    if "molecular processing utility" in str(row["likely_repo_role"]):
        score += 3
    if "model or prediction utility" in str(row["likely_repo_role"]):
        score += 2
    if str(row["external_binaries_detected"]) == "none":
        score += 3
    if not bool(row["cuda_or_gpu_required"]):
        score += 2
    if not bool(row["docking_keywords_detected"]):
        score += 2
    if bool(row["notebooks_detected"]):
        score -= 1
    return score


def initial_decision(row: dict[str, object]) -> str:
    dependency_files = str(row["dependency_files_detected"])
    has_clean_dependency = "environment.yml" in dependency_files or "environment.yaml" in dependency_files or "conda.yml" in dependency_files or "requirements.txt" in dependency_files
    has_dependency = has_clean_dependency or any(name in dependency_files for name in ["pyproject.toml", "setup.py", "setup.cfg"])
    complex_platform = any(
        bool(row[key])
        for key in [
            "megadock_required",
            "alphafold_required",
            "rosetta_required",
            "ccdc_or_csd_required",
        ]
    )
    external_binary = str(row["external_binaries_detected"]) != "none"
    docker_strategy = "docker-manual-review" in str(row["recommended_env_strategy"])
    special_setup = any(
        bool(row[key])
        for key in [
            "cuda_or_gpu_required",
            "openbabel_required",
            "training_keywords_detected",
            "docking_keywords_detected",
        ]
    )
    useful_tool = any(
        role in str(row["likely_repo_role"])
        for role in ["model or prediction utility", "molecular processing utility"]
    )
    metadata_like = any(
        role in str(row["likely_repo_role"])
        for role in ["dataset/benchmark/reference", "notebook-oriented workflow"]
    )

    if docker_strategy:
        return "docker_only_manual_review"
    if not bool(row["readme_detected"]) and not has_dependency:
        return "skip_for_now"
    if complex_platform:
        return "docker_only_manual_review" if "alphafold" in str(row["notes"]).lower() else "install_later_manual_review"
    if has_clean_dependency and not external_binary and not bool(row["cuda_or_gpu_required"]) and useful_tool:
        return "install_now_isolated"
    if has_dependency and (special_setup or external_binary):
        return "install_later_manual_review"
    if metadata_like and not useful_tool:
        return "metadata_only_for_agent_registry"
    if has_dependency:
        return "install_later_manual_review"
    return "metadata_only_for_agent_registry" if bool(row["readme_detected"]) else "skip_for_now"


def risk_level(row: dict[str, object]) -> str:
    critical = any(
        bool(row[key])
        for key in ["megadock_required", "alphafold_required", "rosetta_required", "ccdc_or_csd_required"]
    )
    high = critical or str(row["external_binaries_detected"]) != "none"
    medium = any(
        bool(row[key])
        for key in [
            "cuda_or_gpu_required",
            "openbabel_required",
            "vina_or_gnina_required",
            "training_keywords_detected",
            "docking_keywords_detected",
        ]
    )
    if high:
        return "high"
    if medium:
        return "medium"
    return "low"


def audit_repo(repo_name: str, registry: pd.DataFrame, phase2: pd.DataFrame) -> dict[str, object]:
    reg_match = registry[registry["repo_name"] == repo_name]
    phase2_match = phase2[phase2["repo_name"] == repo_name]
    reg_row = reg_match.iloc[0] if not reg_match.empty else pd.Series(dtype=object)
    phase2_row = phase2_match.iloc[0] if not phase2_match.empty else pd.Series(dtype=object)
    repo_path = Path(str(reg_row.get("local_path", BASE_DIR / "repos" / repo_name)))
    found_locally = repo_path.exists()
    detected_static = detect_root_files(repo_path) if found_locally else []
    dependency_files = [name for name in detected_static if name in DEPENDENCY_FILES]
    text = collect_static_text(repo_path, detected_static) if found_locally else ""
    notebooks = find_notebooks(repo_path) if found_locally else []
    scripts = find_scripts(repo_path) if found_locally else []
    data_folders = find_named_folders(repo_path, DATA_FOLDER_TERMS) if found_locally else []
    model_folders = find_named_folders(repo_path, MODEL_FOLDER_TERMS) if found_locally else []
    external_hits = sorted(
        {
            re.sub(r"\\b", "", pattern).replace("\\", "")
            for pattern in EXTERNAL_BINARY_PATTERNS
            if re.search(pattern, text, flags=re.IGNORECASE)
        }
    )
    docker_recommended = "docker" in text
    role = likely_repo_role(repo_name, text, notebooks, data_folders, model_folders)

    row: dict[str, object] = {
        "repo_name": repo_name,
        "github_url": str(reg_row.get("github_url", "")),
        "local_path": str(repo_path),
        "found_locally": found_locally,
        "dependency_files_detected": ", ".join(dependency_files),
        "readme_detected": any(name in detected_static for name in README_FILES),
        "license_detected": any(name in detected_static for name in LICENSE_FILES),
        "python_requirement": detect_python_requirement(text),
        "torch_requirement": match_any(text, KEYWORDS["torch_requirement"]),
        "tensorflow_requirement": match_any(text, KEYWORDS["tensorflow_requirement"]),
        "cuda_or_gpu_required": match_any(text, KEYWORDS["cuda_or_gpu_required"]),
        "rdkit_required": match_any(text, KEYWORDS["rdkit_required"]),
        "openbabel_required": match_any(text, KEYWORDS["openbabel_required"]),
        "vina_or_gnina_required": match_any(text, KEYWORDS["vina_or_gnina_required"]),
        "megadock_required": match_any(text, KEYWORDS["megadock_required"]),
        "alphafold_required": match_any(text, KEYWORDS["alphafold_required"]),
        "rosetta_required": match_any(text, KEYWORDS["rosetta_required"]),
        "ccdc_or_csd_required": match_any(text, KEYWORDS["ccdc_or_csd_required"]),
        "external_binaries_detected": ", ".join(external_hits) if external_hits else "none",
        "notebooks_detected": bool(notebooks),
        "training_keywords_detected": match_any(text, KEYWORDS["training_keywords_detected"]) or any("train" in s.lower() for s in scripts),
        "docking_keywords_detected": match_any(text, KEYWORDS["docking_keywords_detected"]) or any("dock" in s.lower() for s in scripts),
        "data_or_checkpoint_folders_detected": ", ".join(data_folders + model_folders) if data_folders or model_folders else "none",
        "likely_repo_role": role,
        "recommended_env_strategy": recommended_env_strategy(dependency_files, docker_recommended),
        "recommended_safe_command": safe_command(repo_name, repo_path, dependency_files, docker_recommended),
        "notes": "",
    }
    notes = []
    if not found_locally:
        notes.append("repository folder not found locally")
    if notebooks:
        notes.append(f"notebooks found: {len(notebooks)}")
    if scripts:
        notes.append(f"scripts found: {len(scripts)}")
    if bool(row["readme_detected"]):
        notes.append("README detected")
    if not bool(row["license_detected"]):
        notes.append("license file not detected at repository root")
    if str(phase2_row.get("manual_review_required", "")).lower() == "true":
        notes.append("Phase 2 marked manual review required")
    if docker_recommended and "Dockerfile" not in dependency_files:
        notes.append("README or metadata mentions Docker")
    if match_any(text, KEYWORDS["large_datasets"]):
        notes.append("large dataset wording detected")
    if match_any(text, KEYWORDS["pretrained_checkpoints"]):
        notes.append("pretrained checkpoint/model weight wording detected")

    row["safety_risk_level"] = risk_level(row)
    row["install_decision"] = initial_decision(row)
    row["notes"] = "; ".join(notes) if notes else "static metadata only; no obvious extra notes"
    return row


def enforce_install_now_limit(rows: list[dict[str, object]], limit: int = 3) -> None:
    candidates = [row for row in rows if row["install_decision"] == "install_now_isolated"]
    candidates.sort(key=score_install_now_candidate, reverse=True)
    allowed = {row["repo_name"] for row in candidates[:limit]}
    for row in rows:
        if row["install_decision"] == "install_now_isolated" and row["repo_name"] not in allowed:
            row["install_decision"] = "install_later_manual_review"
            row["notes"] = f"{row['notes']}; deferred because Phase 3 limits install_now_isolated to {limit} safest repositories"


def decision_rank(row: dict[str, object]) -> tuple[int, int, str]:
    decision_order = {
        "install_now_isolated": 0,
        "install_later_manual_review": 1,
        "docker_only_manual_review": 2,
        "metadata_only_for_agent_registry": 3,
        "skip_for_now": 4,
    }
    return (decision_order.get(str(row["install_decision"]), 9), -score_install_now_candidate(row), str(row["repo_name"]))


def write_safe_commands(rows: list[dict[str, object]]) -> None:
    lines = [
        "#!/usr/bin/env bash",
        "# Phase 3 safe command templates.",
        "# Every install/build/smoke-test command is commented out intentionally.",
        "# Review one repository at a time before uncommenting anything.",
        "",
    ]
    for row in rows:
        repo_name = str(row["repo_name"])
        command = str(row["recommended_safe_command"])
        lines.extend([f"# ===== {repo_name} =====", f"# decision: {row['install_decision']}"])
        if command == "manual inspection required":
            lines.append("# manual inspection required")
        elif " && " in command:
            for part in command.split(" && "):
                lines.append(f"# {part}")
        else:
            lines.append(f"# {command}")
            if command.startswith("mamba env create"):
                lines.append(f"# {command.replace('mamba env create', 'conda env create', 1)}")
        lines.extend(
            [
                "# Generic smoke-test plan after manual environment creation:",
                "# python --version",
                "# python -m pip list | head",
                f"# ls {row['local_path']}",
                "",
            ]
        )
    SAFE_COMMANDS_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.chmod(SAFE_COMMANDS_PATH, 0o755)


def write_audit_md(rows: list[dict[str, object]]) -> None:
    lines = [
        "# Phase 3 Pre-install Audit",
        "",
        "This report is based on static file inspection only. No repository code was executed, imported, installed, trained, docked, or run as a notebook.",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {row['repo_name']}",
                "",
                f"- Decision: `{row['install_decision']}`",
                f"- Risk level: `{row['safety_risk_level']}`",
                f"- Role: {row['likely_repo_role']}",
                f"- Dependency files: {row['dependency_files_detected'] or 'none'}",
                f"- Recommended strategy: {row['recommended_env_strategy']}",
                f"- Recommended command template: `{row['recommended_safe_command']}`",
                f"- External binaries: {row['external_binaries_detected']}",
                f"- Notes: {row['notes']}",
                "",
            ]
        )
    AUDIT_MD_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_install_order_md(rows: list[dict[str, object]]) -> None:
    ranked = sorted(rows, key=decision_rank)
    first = next((row for row in ranked if row["install_decision"] == "install_now_isolated"), None)
    lines = [
        "# Phase 3 Recommended Install Order",
        "",
        "This is a manual, isolated-environment order. Do not run bulk installs. Every command template is also available, commented out, in `phase3_safe_commands.sh`.",
        "",
        "## Final ranked install order",
        "",
    ]
    for index, row in enumerate(ranked, start=1):
        lines.append(
            f"{index}. **{row['repo_name']}** - `{row['install_decision']}`; risk `{row['safety_risk_level']}`; {row['likely_repo_role']}."
        )
    lines.extend(["", "## Which repo should be installed first", ""])
    if first:
        lines.extend(
            [
                f"Install **{first['repo_name']}** first, manually and in isolation, because it has the safest Phase 3 score among `install_now_isolated` candidates.",
                "",
                "Command template:",
                "",
                "```bash",
                str(first["recommended_safe_command"]),
                "```",
                "",
            ]
        )
    else:
        lines.append("No repository qualified for `install_now_isolated` in this audit.\n")

    def section(title: str, decision: str) -> None:
        lines.extend([f"## {title}", ""])
        selected = [row for row in ranked if row["install_decision"] == decision]
        if not selected:
            lines.append("None.\n")
            return
        for row in selected:
            lines.append(f"- **{row['repo_name']}**: {row['notes']}")
        lines.append("")

    section("Which repos are not installable yet", "install_later_manual_review")
    section("Which repos should remain metadata-only for now", "metadata_only_for_agent_registry")
    section("Which repos require Docker/manual review", "docker_only_manual_review")
    section("Which repos should be skipped for now", "skip_for_now")
    lines.extend(
        [
            "## What to check before Phase 4",
            "",
            "- Verify licenses and redistribution constraints.",
            "- Create only one isolated environment at a time.",
            "- Review dependency files before solving environments.",
            "- Check README warnings for GPU, docking, AlphaFold, MEGADOCK, Rosetta, CCDC/CSD, OpenBabel, and large datasets.",
            "- After installation, run only generic smoke tests first: `python --version`, `python -m pip list | head`, and `ls <repo_path>`.",
            "- Do not import repository modules until a dedicated smoke-import phase approves a target module and expected behavior.",
            "",
        ]
    )
    INSTALL_ORDER_MD_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    registry = pd.read_csv(REGISTRY_PATH).fillna("")
    phase2 = pd.read_csv(PHASE2_MATRIX_PATH).fillna("")
    rows = [audit_repo(repo_name, registry, phase2) for repo_name in SELECTED_REPOS]
    enforce_install_now_limit(rows, limit=3)

    columns = [
        "repo_name",
        "github_url",
        "local_path",
        "found_locally",
        "dependency_files_detected",
        "readme_detected",
        "license_detected",
        "python_requirement",
        "torch_requirement",
        "tensorflow_requirement",
        "cuda_or_gpu_required",
        "rdkit_required",
        "openbabel_required",
        "vina_or_gnina_required",
        "megadock_required",
        "alphafold_required",
        "rosetta_required",
        "ccdc_or_csd_required",
        "external_binaries_detected",
        "notebooks_detected",
        "training_keywords_detected",
        "docking_keywords_detected",
        "data_or_checkpoint_folders_detected",
        "likely_repo_role",
        "safety_risk_level",
        "install_decision",
        "recommended_env_strategy",
        "recommended_safe_command",
        "notes",
    ]
    df = pd.DataFrame(rows, columns=columns)
    df.to_csv(AUDIT_CSV_PATH, index=False, quoting=csv.QUOTE_MINIMAL)
    df.to_excel(AUDIT_XLSX_PATH, index=False, engine="openpyxl")
    write_safe_commands(rows)
    write_audit_md(rows)
    write_install_order_md(rows)

    print(f"total repositories audited: {len(df)}")
    for decision in [
        "install_now_isolated",
        "install_later_manual_review",
        "docker_only_manual_review",
        "metadata_only_for_agent_registry",
        "skip_for_now",
    ]:
        names = df.loc[df["install_decision"] == decision, "repo_name"].tolist()
        print(f"{decision}: {len(names)}" + (f" ({', '.join(names)})" if names else ""))
    first_rows = df[df["install_decision"] == "install_now_isolated"].copy()
    if first_rows.empty:
        print("recommended first repo to install: none")
        print("exact first install command: none")
    else:
        ranked_first = sorted(first_rows.to_dict("records"), key=decision_rank)[0]
        print(f"recommended first repo to install: {ranked_first['repo_name']}")
        print(f"exact first install command: {ranked_first['recommended_safe_command']}")
    print(f"audit csv path: {AUDIT_CSV_PATH}")
    print(f"audit xlsx path: {AUDIT_XLSX_PATH}")
    print(f"audit md path: {AUDIT_MD_PATH}")
    print(f"install order path: {INSTALL_ORDER_MD_PATH}")
    print(f"safe commands path: {SAFE_COMMANDS_PATH}")


if __name__ == "__main__":
    main()
