"""Configuration helpers for PROTACXtend."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_DIR = PACKAGE_ROOT / "data"
_DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs"


def _configured_dir(env_name: str, default: Path) -> Path:
    return Path(os.environ.get(env_name) or default).expanduser()


def _writable_dir(path: Path) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return path
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "protacxtend"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def get_output_dir(*, create: bool = False) -> Path:
    path = _configured_dir("PROTACXTEND_OUTPUT_DIR", _DEFAULT_OUTPUT_ROOT)
    if create:
        return _writable_dir(path)
    return path


def get_workflow_log_dir(*, create: bool = False) -> Path:
    path = _configured_dir("PROTACXTEND_WORKFLOW_LOG_DIR", get_output_dir(create=create) / "workflow_logs")
    if create:
        return _writable_dir(path)
    return path


def get_memory_dir(*, create: bool = False) -> Path:
    path = _configured_dir("PROTACXTEND_MEMORY_DIR", get_output_dir(create=create) / "memory")
    if create:
        return _writable_dir(path)
    return path


def get_learning_dir(*, create: bool = False) -> Path:
    path = _configured_dir("PROTACXTEND_LEARNING_DIR", get_memory_dir(create=create) / "learnings")
    if create:
        return _writable_dir(path)
    return path


def get_run_output_root(*, create: bool = False) -> Path:
    path = _configured_dir("PROTACXTEND_RUN_OUTPUT_DIR", get_output_dir(create=create) / "runs")
    if create:
        return _writable_dir(path)
    return path


def get_coverage_file(*, create: bool = False) -> Path:
    path = _configured_dir("PROTACXTEND_COVERAGE_FILE", get_output_dir(create=create) / "coverage" / "coverage_cells.jsonl")
    if create:
        _writable_dir(path.parent)
    return path


OUTPUT_DIR = get_output_dir(create=True)
REPORT_DIR = OUTPUT_DIR / "reports"
CANDIDATE_DIR = OUTPUT_DIR / "candidates"
FIGURE_DIR = OUTPUT_DIR / "figures"
MEMORY_DIR = get_memory_dir(create=True)
WORKFLOW_LOG_DIR = get_workflow_log_dir(create=True)
RELATIONAL_MEMORY_DIR = MEMORY_DIR / "relational_store"
VECTOR_MEMORY_DIR = MEMORY_DIR / "vector_store"


DEFAULT_RANKING_WEIGHTS = {
    "dc50": 0.24,
    "dmax": 0.19,
    "admet": 0.13,
    "ternary": 0.12,
    "cooperativity": 0.11,
    "hook": 0.08,
    "e3_context": 0.06,
    "novelty": 0.05,
    "synthetic": 0.02,
}

DEFAULT_LINKER_TYPES = ["PEG", "alkyl", "piperazine", "triazole"]
DEFAULT_E3_LIGASES = ["CRBN", "VHL"]


def ensure_directories() -> None:
    for path in [
        get_output_dir(create=True) / "reports",
        get_output_dir(create=True) / "candidates",
        get_output_dir(create=True) / "figures",
        get_workflow_log_dir(create=True),
        get_learning_dir(create=True),
        get_memory_dir(create=True) / "relational_store",
        get_memory_dir(create=True) / "vector_store",
    ]:
        path.mkdir(parents=True, exist_ok=True)
