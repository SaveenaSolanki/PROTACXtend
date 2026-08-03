#!/usr/bin/env python3
"""Generate safe Phase 2 isolated-environment preparation outputs.

This script reads the Phase 1 PROTAC repository registry, inspects only static
metadata files in each cloned repository, and writes commented install-command
templates. It does not execute repository code, import cloned packages, install
dependencies, run notebooks, train models, run docking workflows, or modify any
cloned repository.
"""

from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path

import pandas as pd


BASE_DIR = Path("data/protac_repos")
REGISTRY_PATH = BASE_DIR / "protac_repo_registry.csv"
MATRIX_PATH = BASE_DIR / "phase2_env_matrix.csv"
COMMANDS_SH_PATH = BASE_DIR / "phase2_env_commands.sh"
COMMANDS_MD_PATH = BASE_DIR / "phase2_env_commands.md"
MANUAL_REVIEW_PATH = BASE_DIR / "phase2_manual_review.md"

DETECT_FILES = [
    "environment.yml",
    "environment.yaml",
    "conda.yml",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Dockerfile",
    "docker-compose.yml",
    "README.md",
    "LICENSE",
    "LICENSE.txt",
]

CONDA_FILES = ["environment.yml", "environment.yaml", "conda.yml"]
REQUIREMENTS_FILES = ["requirements.txt"]
EDITABLE_FILES = ["pyproject.toml", "setup.py"]
README_HINT_TERMS = ["install", "installation", "conda", "mamba", "pip", "requirements", "docker", "environment"]
HEAVY_TERMS = [
    "dock",
    "docking",
    "gpu",
    "cuda",
    "train",
    "training",
    "alphafold",
    "rosetta",
    "conformer",
    "ternary",
    "molecular dynamics",
    "md simulation",
]
DATASET_TERMS = ["dataset", "database", "benchmark", "descriptors", "data only", "notebook"]
UTILITY_TERMS = ["splitter", "linker", "utility", "package", "predictor", "descriptor", "model", "tool"]


def safe_env_name(repo_name: str) -> str:
    name = repo_name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return f"protac-{name}" if not name.startswith("protac-") else name


def repo_path_from_row(row: pd.Series) -> Path:
    raw_path = row.get("local_path", "")
    return Path(str(raw_path))


def detect_files(repo_path: Path) -> list[str]:
    found = []
    for filename in DETECT_FILES:
        if (repo_path / filename).exists():
            found.append(filename)
    return found


def read_text_if_small(path: Path, max_bytes: int = 250_000) -> str:
    if not path.is_file():
        return ""
    try:
        if path.stat().st_size > max_bytes:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def readme_install_hints(repo_path: Path) -> str:
    readme = repo_path / "README.md"
    text = read_text_if_small(readme)
    hints = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(term in lowered for term in README_HINT_TERMS):
            compact = re.sub(r"\s+", " ", line.strip())
            if compact:
                hints.append(compact)
        if len(hints) >= 6:
            break
    return " | ".join(hints)


def repo_text_for_classification(row: pd.Series, repo_path: Path) -> str:
    pieces = [
        str(row.get("repo_name", "")),
        str(row.get("notes", "")),
        str(row.get("repo_category", "")),
        readme_install_hints(repo_path),
    ]
    return " ".join(pieces).lower()


def has_notebooks(repo_path: Path) -> bool:
    if not repo_path.exists():
        return False
    try:
        return any(path.suffix == ".ipynb" for path in repo_path.rglob("*.ipynb") if ".git" not in path.parts)
    except OSError:
        return False


def choose_priority(
    dependency_files: list[str],
    readme_hints: str,
    classification_text: str,
    repo_path: Path,
) -> tuple[str, bool, str]:
    has_conda = any(name in dependency_files for name in CONDA_FILES)
    has_requirements = "requirements.txt" in dependency_files
    has_editable = any(name in dependency_files for name in EDITABLE_FILES)
    has_readme = "README.md" in dependency_files
    heavy_likely = any(term in classification_text for term in HEAVY_TERMS)
    dataset_likely = any(term in classification_text for term in DATASET_TERMS)
    utility_likely = any(term in classification_text for term in UTILITY_TERMS)
    notebooks = has_notebooks(repo_path)
    has_docker = "Dockerfile" in dependency_files

    reasons = []
    manual_review_required = False

    if has_docker:
        manual_review_required = True
        reasons.append("Dockerfile detected; review Docker context before building")
    if heavy_likely:
        manual_review_required = True
        reasons.append("heavy docking/GPU/training/ternary-complex keywords detected")
    if not has_readme:
        manual_review_required = True
        reasons.append("README.md not detected")
    if not any(name in dependency_files for name in CONDA_FILES + ["requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.py", "setup.cfg", "Dockerfile", "docker-compose.yml"]):
        manual_review_required = True
        reasons.append("no standard dependency files detected")

    if manual_review_required and (heavy_likely or not has_readme or not dependency_files):
        priority = "Manual"
    elif has_conda or (has_requirements and utility_likely):
        priority = "High"
    elif has_editable or readme_hints:
        priority = "Medium"
    elif dataset_likely or notebooks:
        priority = "Low"
    else:
        priority = "Manual"

    if dataset_likely or notebooks:
        reasons.append("dataset/notebook or benchmark-style repository likely")
        if priority == "High" and not utility_likely:
            priority = "Low"

    if not reasons:
        reasons.append("clear static dependency markers detected")
    return priority, manual_review_required, "; ".join(reasons)


def command_section_id(repo_name: str) -> str:
    anchor = safe_env_name(repo_name).replace("protac-", "", 1)
    return f"phase2-{anchor}"


def generate_commands(repo_name: str, repo_path: Path, dependency_files: list[str]) -> tuple[list[str], list[str], str]:
    env_name = safe_env_name(repo_name)
    shell_lines = [f"# ===== {repo_name} ====="]
    md_lines = [f"### {repo_name}", "", f"- Safe environment name: `{env_name}`", f"- Repository path: `{repo_path}`"]
    strategies = []

    conda_file = next((name for name in CONDA_FILES if name in dependency_files), None)
    if conda_file:
        strategies.append("conda/mamba")
        env_file = repo_path / conda_file
        shell_lines.extend(
            [
                f"# mamba env create -n {env_name} -f {env_file}",
                f"# conda env create -n {env_name} -f {env_file}",
            ]
        )
        md_lines.extend(
            [
                "",
                "Recommended isolated conda/mamba command:",
                "",
                "```bash",
                f"mamba env create -n {env_name} -f {env_file}",
                f"conda env create -n {env_name} -f {env_file}",
                "```",
            ]
        )

    if "requirements.txt" in dependency_files:
        strategies.append("venv/pip")
        req_file = repo_path / "requirements.txt"
        shell_lines.extend(
            [
                f"# python -m venv .venvs/{env_name}",
                f"# source .venvs/{env_name}/bin/activate",
                "# python -m pip install --upgrade pip",
                f"# pip install -r {req_file}",
            ]
        )
        md_lines.extend(
            [
                "",
                "Alternative isolated venv/pip command:",
                "",
                "```bash",
                f"python -m venv .venvs/{env_name}",
                f"source .venvs/{env_name}/bin/activate",
                "python -m pip install --upgrade pip",
                f"pip install -r {req_file}",
                "```",
            ]
        )

    if any(name in dependency_files for name in EDITABLE_FILES):
        strategies.append("editable-venv")
        shell_lines.extend(
            [
                f"# python -m venv .venvs/{env_name}",
                f"# source .venvs/{env_name}/bin/activate",
                "# python -m pip install --upgrade pip",
                f"# pip install -e {repo_path}",
            ]
        )
        md_lines.extend(
            [
                "",
                "Editable install command for isolated manual testing:",
                "",
                "```bash",
                f"python -m venv .venvs/{env_name}",
                f"source .venvs/{env_name}/bin/activate",
                "python -m pip install --upgrade pip",
                f"pip install -e {repo_path}",
                "```",
            ]
        )

    if "Dockerfile" in dependency_files:
        strategies.append("docker-manual-review")
        shell_lines.append(f"# docker build -t protac-toolkit/{env_name}:latest {repo_path}")
        md_lines.extend(
            [
                "",
                "Docker build template, manual review required before use:",
                "",
                "```bash",
                f"docker build -t protac-toolkit/{env_name}:latest {repo_path}",
                "```",
            ]
        )

    if not strategies:
        strategies.append("manual inspection required")
        shell_lines.append("# manual inspection required")
        md_lines.extend(["", "Manual inspection required before any environment creation."])

    if "manual inspection required" not in strategies:
        md_lines.extend(
            [
                "",
                "Generic smoke-test plan after manual environment creation:",
                "",
                "```bash",
                "python --version",
                "python -m pip list | head",
                f"ls {repo_path}",
                "```",
                "",
                "Do not import repository modules until a later smoke-import phase explicitly approves it.",
            ]
        )
        shell_lines.extend(
            [
                "# Generic smoke-test plan after manual environment creation:",
                "# python --version",
                "# python -m pip list | head",
                f"# ls {repo_path}",
            ]
        )

    shell_lines.append("")
    md_lines.append("")
    return shell_lines, md_lines, "; ".join(dict.fromkeys(strategies))


def build_outputs() -> pd.DataFrame:
    registry = pd.read_csv(REGISTRY_PATH).fillna("")
    rows = []
    shell_sections = [
        "#!/usr/bin/env bash",
        "# Phase 2 isolated environment command templates.",
        "# Safety: every install/build/smoke-test command is commented out intentionally.",
        "# Uncomment and run one repository section at a time only after manual review.",
        "",
    ]
    md_sections = [
        "# Phase 2 Isolated Environment Commands",
        "",
        "These are manual command templates only. They were generated from static dependency-file inspection.",
        "",
        "No commands in `phase2_env_commands.sh` are active by default. Do not run bulk installs.",
        "",
    ]
    manual_sections = [
        "# Phase 2 Manual Review List",
        "",
        "The repositories below should not be installed yet without human review of licenses, dependency files, README instructions, resource needs, and any scripts that could launch training, docking, notebooks, or GPU workloads.",
        "",
    ]

    for _, row in registry.iterrows():
        repo_name = str(row["repo_name"])
        github_url = str(row.get("github_url", ""))
        repo_path = repo_path_from_row(row)
        dependency_files = detect_files(repo_path) if repo_path.exists() else []
        readme_hints = readme_install_hints(repo_path)
        classification_text = repo_text_for_classification(row, repo_path)
        shell_lines, md_lines, env_strategy = generate_commands(repo_name, repo_path, dependency_files)
        priority, manual_required, reason_notes = choose_priority(
            dependency_files,
            readme_hints,
            classification_text,
            repo_path,
        )

        section = command_section_id(repo_name)
        shell_sections.extend(shell_lines)
        md_sections.extend([f"<a id=\"{section}\"></a>", *md_lines])

        notes = []
        if readme_hints:
            notes.append(f"README install hints: {readme_hints}")
        notes.append(reason_notes)
        if "requirements-dev.txt" in dependency_files:
            notes.append("requirements-dev.txt detected but not used for initial install template")
        if "docker-compose.yml" in dependency_files:
            notes.append("docker-compose.yml detected; review compose services before use")

        if manual_required or priority == "Manual":
            manual_sections.extend(
                [
                    f"## {repo_name}",
                    "",
                    f"- GitHub: {github_url}",
                    f"- Local path: `{repo_path}`",
                    f"- Detected files: {', '.join(dependency_files) if dependency_files else 'none'}",
                    f"- Priority: {priority}",
                    f"- Reason: {'; '.join(notes)}",
                    "",
                ]
            )

        rows.append(
            {
                "repo_name": repo_name,
                "github_url": github_url,
                "local_path": str(repo_path),
                "clone_status": str(row.get("clone_status", "")),
                "dependency_files_detected": ", ".join(dependency_files),
                "env_strategy": env_strategy,
                "safe_env_name": safe_env_name(repo_name),
                "command_file_section": section,
                "manual_review_required": bool(manual_required),
                "install_priority": priority,
                "notes": "; ".join(notes),
            }
        )

    matrix = pd.DataFrame(rows)
    matrix.to_csv(MATRIX_PATH, index=False)
    COMMANDS_SH_PATH.write_text("\n".join(shell_sections).rstrip() + "\n", encoding="utf-8")
    COMMANDS_MD_PATH.write_text("\n".join(md_sections).rstrip() + "\n", encoding="utf-8")
    MANUAL_REVIEW_PATH.write_text("\n".join(manual_sections).rstrip() + "\n", encoding="utf-8")
    os.chmod(COMMANDS_SH_PATH, 0o755)
    return matrix


def main() -> None:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Missing Phase 1 registry: {REGISTRY_PATH}")

    matrix = build_outputs()
    conda_count = int(matrix["env_strategy"].str.contains("conda/mamba", regex=False).sum())
    venv_count = int(matrix["env_strategy"].str.contains("venv/pip", regex=False).sum())
    docker_count = int(matrix["env_strategy"].str.contains("docker", regex=False).sum())
    manual_count = int(matrix["manual_review_required"].sum())

    print(
        textwrap.dedent(
            f"""
            total repositories processed: {len(matrix)}
            conda/mamba env strategy: {conda_count}
            venv/pip strategy: {venv_count}
            docker strategy: {docker_count}
            requiring manual review: {manual_count}
            matrix path: {MATRIX_PATH}
            shell commands path: {COMMANDS_SH_PATH}
            markdown commands path: {COMMANDS_MD_PATH}
            manual review path: {MANUAL_REVIEW_PATH}
            """
        ).strip()
    )


if __name__ == "__main__":
    main()
