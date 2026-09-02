#!/usr/bin/env python3
"""Collect PROTAC-related research repositories without installing them.

This script clones or safely updates a fixed list of public GitHub repositories,
inspects their dependency markers, and writes a reproducible registry for later
manual integration work. It intentionally does not import, execute, train, dock,
or install any cloned project.
"""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import pandas as pd


REPO_URLS = [
    "https://github.com/biomed-AI/PROTAC-RL",
    "https://github.com/Fenglei104/DeepPROTACs",
    "https://github.com/gaoqiweng/PROTAC-Model",
    "https://github.com/NilsDunlop/PROTACFold",
    "https://github.com/giaguaro/PROTACable",
    "https://github.com/jidushanbojue/Protac-invent",
    "https://github.com/ribesstefano/PROTAC-Splitter",
    "https://github.com/karanicolaslab/PROTAC_ternary",
    "https://github.com/doheejin/ProTACT",
    "https://github.com/PROTACs/PROTAC-STAN",
    "https://github.com/GilbertoPPereira/PROTACability",
    "https://github.com/ribesstefano/PROTAC-Degradation-Predictor",
    "https://github.com/WIMNZhao/TERNIFY",
    "https://github.com/AnHorn/AIMLinker",
    "https://github.com/AstraZeneca/Machine-Learning-for-Predicting-Targeted-Protein-Degradation",
    "https://github.com/yauz3/MEGA-PROTAC",
    "https://github.com/the-ahuja-lab/SynGlue",
    "https://github.com/gaoqiweng/PROTAC-Model_benchmark",
    "https://github.com/drugparadigm/SE3-protacs",
    "https://github.com/ccdc-opensource/science-paper-protac-conformer-generator-2025",
    "https://github.com/giulia-apprato/Bellerophon",
    "https://github.com/zhao-fuqiang/PROTAC-shotgun",
    "https://github.com/cancer-nanomedicine-lab/PROTAC_descriptors",
    "https://github.com/leezx/computational-PROTAC-development",
    "https://github.com/yugyeong0609/PROTAC",
    "https://github.com/wxfsd/ProtacDatabase",
    "https://github.com/Fraunhofer-ITMP/protacSpace",
    "https://github.com/crisprking/degradomap",
    "https://github.com/sylershao/ProtacGPT",
]

BASE_DIR = Path("data/protac_repos")
REPOS_DIR = BASE_DIR / "repos"
LOGS_DIR = BASE_DIR / "logs"
ENV_SPECS_DIR = BASE_DIR / "env_specs"
REGISTRY_CSV = BASE_DIR / "protac_repo_registry.csv"
REGISTRY_XLSX = BASE_DIR / "protac_repo_registry.xlsx"
README_PATH = BASE_DIR / "README.md"
INSTALL_PLAN_PATH = BASE_DIR / "install_plan.md"

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
README_FILES = ["README.md", "README.rst", "README.txt", "readme.md"]
LICENSE_FILES = ["LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "COPYING.txt"]


@dataclass
class GitResult:
    status: str
    note: str


def sanitize_repo_name(url: str) -> str:
    name = Path(urlparse(url).path).name
    if name.endswith(".git"):
        name = name[:-4]
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "repo"


def run_command(args: list[str], cwd: Path | None, log_file: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"$ {' '.join(args)}\n")
        handle.write(result.stdout or "")
        handle.write(f"\n[exit_code={result.returncode}]\n\n")
    return result


def clone_or_update(url: str, local_path: Path, log_file: Path) -> GitResult:
    log_file.write_text(f"Repository: {url}\nLocal path: {local_path}\n\n", encoding="utf-8")

    if local_path.exists() and not (local_path / ".git").is_dir():
        return GitResult(
            "skipped_existing_non_git",
            "Local folder exists but is not a git repository; skipped to avoid overwrite.",
        )

    if local_path.exists():
        fetch = run_command(["git", "fetch", "--all", "--prune"], local_path, log_file)
        if fetch.returncode != 0:
            return GitResult("update_failed", "git fetch failed; see repo log.")
        pull = run_command(["git", "pull", "--ff-only"], local_path, log_file)
        if pull.returncode != 0:
            return GitResult("update_failed", "git pull --ff-only failed; see repo log.")
        return GitResult("updated_existing", "Existing git repository updated with fast-forward pull.")

    clone = run_command(["git", "clone", url, str(local_path)], None, log_file)
    if clone.returncode != 0:
        return GitResult("clone_failed", "git clone failed; see repo log.")
    return GitResult("cloned", "Repository cloned successfully.")


def first_existing(root: Path, names: Iterable[str]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def existing_files(root: Path, names: Iterable[str]) -> list[str]:
    return [name for name in names if (root / name).exists()]


def copy_env_specs(repo_name: str, repo_path: Path, dependency_files: list[str]) -> list[str]:
    copied = []
    for relative_name in dependency_files:
        source = repo_path / relative_name
        if not source.is_file():
            continue
        safe_relative = relative_name.replace("/", "__")
        destination = ENV_SPECS_DIR / f"{repo_name}__{safe_relative}"
        shutil.copy2(source, destination)
        copied.append(str(destination))
    return copied


def read_readme_snippet(readme_path: Path | None) -> str:
    if not readme_path or not readme_path.is_file():
        return ""
    text = readme_path.read_text(encoding="utf-8", errors="replace")
    install_lines = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(token in lowered for token in ["install", "conda", "pip ", "docker", "requirements"]):
            install_lines.append(line.strip())
        if len(install_lines) >= 8:
            break
    return " | ".join(line for line in install_lines if line)[:500]


def recommend_install(dependency_files: list[str]) -> str:
    files = set(dependency_files)
    if "Dockerfile" in files:
        return "Isolated Docker build later after manual review"
    if {"environment.yml", "environment.yaml", "conda.yml"} & files:
        return "Create separate conda/mamba environment"
    if "requirements.txt" in files:
        return "Create separate Python venv and install requirements there"
    if {"pyproject.toml", "setup.py", "setup.cfg"} & files:
        return "Editable install in an isolated environment after review"
    return "Manual inspection required"


def infer_language(repo_path: Path, dependency_files: list[str]) -> str:
    suffix_counts: dict[str, int] = {}
    if not repo_path.exists():
        return "unknown"
    for path in repo_path.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in {".py", ".ipynb", ".r", ".jl", ".m", ".cpp", ".c", ".h", ".java", ".js", ".ts"}:
            suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
    if any(name in dependency_files for name in ["requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"]):
        suffix_counts[".py"] = suffix_counts.get(".py", 0) + 3
    if not suffix_counts:
        return "unknown/manual"
    top = max(suffix_counts, key=suffix_counts.get)
    return {
        ".py": "Python",
        ".ipynb": "Jupyter/Python",
        ".r": "R",
        ".jl": "Julia",
        ".m": "MATLAB",
        ".cpp": "C++",
        ".c": "C/C++",
        ".h": "C/C++",
        ".java": "Java",
        ".js": "JavaScript",
        ".ts": "TypeScript",
    }.get(top, "unknown/manual")


def classify_repo(repo_name: str, dependency_files: list[str], readme_snippet: str) -> str:
    text = f"{repo_name} {' '.join(dependency_files)} {readme_snippet}".lower()
    labels = []
    if any(token in text for token in ["dataset", "database", "benchmark", "descriptors", "data"]):
        labels.append("dataset/benchmark")
    if any(token in text for token in ["model", "predict", "learning", "gpt", "invent", "stan", "rl"]):
        labels.append("model")
    if any(token in text for token in ["splitter", "linker", "conformer", "space", "descriptor"]):
        labels.append("molecular processing utility")
    if any(token in text for token in ["ternary", "dock", "complex", "fold", "se3"]):
        labels.append("ternary-complex/docking")
    return "; ".join(labels) if labels else "manual review"


def inspect_repo(url: str) -> dict[str, str | bool]:
    repo_name = sanitize_repo_name(url)
    local_path = REPOS_DIR / repo_name
    log_file = LOGS_DIR / f"{repo_name}.log"
    git_result = clone_or_update(url, local_path, log_file)

    dependency_files: list[str] = []
    readme_path: Path | None = None
    license_path: Path | None = None
    copied_specs: list[str] = []
    readme_snippet = ""
    likely_language = "unknown"

    if local_path.exists() and (local_path / ".git").is_dir():
        dependency_files = existing_files(local_path, DEPENDENCY_FILES)
        readme_path = first_existing(local_path, README_FILES)
        license_path = first_existing(local_path, LICENSE_FILES)
        readme_snippet = read_readme_snippet(readme_path)
        copied_specs = copy_env_specs(repo_name, local_path, dependency_files)
        likely_language = infer_language(local_path, dependency_files)

    install_method = recommend_install(dependency_files)
    classification = classify_repo(repo_name, dependency_files, readme_snippet)
    notes = "; ".join(
        item
        for item in [
            git_result.note,
            f"Detected files: {', '.join(dependency_files)}" if dependency_files else "No standard dependency files detected",
            f"README install hints: {readme_snippet}" if readme_snippet else "",
            f"Copied env specs: {len(copied_specs)}" if copied_specs else "",
            f"Category: {classification}",
        ]
        if item
    )

    return {
        "repo_name": repo_name,
        "github_url": url,
        "local_path": str(local_path),
        "clone_status": git_result.status,
        "install_method_detected": install_method,
        "has_license": bool(license_path),
        "has_readme": bool(readme_path),
        "likely_language": likely_language,
        "notes": notes,
        "recommended_next_step": install_method,
        "detected_dependency_files": ", ".join(dependency_files),
        "copied_env_specs": ", ".join(copied_specs),
        "repo_category": classification,
        "log_file": str(log_file),
    }


def write_readme(total_repos: int) -> None:
    README_PATH.write_text(
        f"""# PROTAC Repository Collection

This folder collects public PROTAC, targeted protein degradation, linker, and ternary-complex repositories for academic research and benchmarking.

Cloning a repository does not mean the tool is installed, importable, executable, validated, or safe to run. This collection only records repository state and dependency hints for future isolated testing.

Each repository must be license-checked before redistribution, publication packaging, production use, or inclusion in a derived tool. The registry marks whether a license-like file was detected, but it does not interpret license terms.

The registry distinguishes cloned status, install-file detection, and future install recommendations. It does not claim executable status for any repository because no imports, CLIs, notebooks, training jobs, docking workflows, or untrusted scripts were executed.

Future PROTAC agentic-AI integration should wrap each repository as a tool module only after successful manual review, isolated environment creation, dependency resolution, smoke testing, and license approval.

Requested repositories: {total_repos}

Key files:

- `repos/`: cloned or updated repositories
- `logs/`: one Git operation log per repository
- `env_specs/`: copied dependency files with repository-prefixed names
- `protac_repo_registry.csv`: machine-readable registry
- `protac_repo_registry.xlsx`: spreadsheet registry
- `install_plan.md`: recommended isolation and integration plan
""",
        encoding="utf-8",
    )


def write_install_plan(df: pd.DataFrame) -> None:
    def bullets(rows: pd.DataFrame, column: str = "recommended_next_step") -> str:
        if rows.empty:
            return "- None detected from current metadata.\n"
        lines = []
        for _, row in rows.iterrows():
            lines.append(f"- **{row['repo_name']}**: {row[column]}. Status: {row['clone_status']}.")
        return "\n".join(lines) + "\n"

    models = df[df["repo_category"].str.contains("model", case=False, na=False)]
    datasets = df[df["repo_category"].str.contains("dataset", case=False, na=False)]
    utilities = df[df["repo_category"].str.contains("molecular processing", case=False, na=False)]
    ternary = df[df["repo_category"].str.contains("ternary", case=False, na=False)]

    plan_rows = "\n".join(
        f"- **{row.repo_name}**: {row.recommended_next_step}. Detected: {row.detected_dependency_files or 'none'}."
        for row in df.itertuples(index=False)
    )

    INSTALL_PLAN_PATH.write_text(
        f"""# PROTAC Repository Install Plan

## Overview

This plan prepares the collected repositories for future PROTAC agentic-AI integration. The collection step cloned or updated repositories and inspected visible install metadata only. No repository code was executed and no packages were installed into the base environment.

## Why isolated environments are required

These repositories span different research eras, dependency stacks, chemistry toolkits, ML frameworks, docking/conformer workflows, and possible GPU assumptions. Installing them together in the base environment would risk dependency conflicts and accidental execution of unreviewed code. Each repository should be tested in a separate Docker image, conda/mamba environment, or Python virtual environment.

## Repo-by-repo install recommendation

{plan_rows}

## Which repos look like models

{bullets(models)}
## Which repos look like datasets

{bullets(datasets)}
## Which repos look like molecular processing utilities

{bullets(utilities)}
## Which repos look like ternary-complex/docking tools

{bullets(ternary)}
## Which repos should not be auto-executed before manual review

All repositories in this collection should avoid automatic execution before manual review. In particular, do not run training scripts, docking workflows, notebooks, shell installers, downloaded checkpoints, or project-specific CLIs until their source, data paths, licenses, and resource requirements have been inspected.

## Next integration step for PROTAC agentic AI

Create one isolated environment per repository, install only that repository's declared dependencies, run minimal import or CLI smoke tests, record executable status separately from clone status, and then wrap successful tools behind small adapter modules in the PROTAC agentic-AI toolkit.
""",
        encoding="utf-8",
    )


def main() -> None:
    for directory in [REPOS_DIR, LOGS_DIR, ENV_SPECS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    rows = []
    for url in REPO_URLS:
        try:
            rows.append(inspect_repo(url))
        except Exception as exc:  # Keep the collection moving if one repo surprises us.
            repo_name = sanitize_repo_name(url)
            log_file = LOGS_DIR / f"{repo_name}.log"
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write(f"\n[collector_exception] {exc!r}\n")
            rows.append(
                {
                    "repo_name": repo_name,
                    "github_url": url,
                    "local_path": str(REPOS_DIR / repo_name),
                    "clone_status": "collector_failed",
                    "install_method_detected": "Manual inspection required",
                    "has_license": False,
                    "has_readme": False,
                    "likely_language": "unknown",
                    "notes": f"Collector exception: {exc!r}",
                    "recommended_next_step": "Manual inspection required",
                    "detected_dependency_files": "",
                    "copied_env_specs": "",
                    "repo_category": "manual review",
                    "log_file": str(log_file),
                }
            )

    df = pd.DataFrame(rows)
    df.to_csv(REGISTRY_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
    df.to_excel(REGISTRY_XLSX, index=False, engine="openpyxl")
    write_readme(len(REPO_URLS))
    write_install_plan(df)

    total = len(REPO_URLS)
    successful = int(df["clone_status"].isin(["cloned", "updated_existing"]).sum())
    failed = int(df["clone_status"].isin(["clone_failed", "update_failed", "collector_failed"]).sum())
    existing = int(df["clone_status"].isin(["updated_existing", "skipped_existing_non_git"]).sum())

    print(f"total repos requested: {total}")
    print(f"successfully cloned or updated: {successful}")
    print(f"failed clone/update count: {failed}")
    print(f"already existing count: {existing}")
    print(f"registry file path: {REGISTRY_CSV}")
    print(f"install plan path: {INSTALL_PLAN_PATH}")


if __name__ == "__main__":
    main()
