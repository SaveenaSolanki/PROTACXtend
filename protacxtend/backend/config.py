"""Configuration helpers for SynGlue-Agent."""

from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_DIR = PACKAGE_ROOT / "data"
OUTPUT_DIR = PACKAGE_ROOT / "outputs"
REPORT_DIR = OUTPUT_DIR / "reports"
CANDIDATE_DIR = OUTPUT_DIR / "candidates"
FIGURE_DIR = OUTPUT_DIR / "figures"
MEMORY_DIR = PACKAGE_ROOT / "memory"
WORKFLOW_LOG_DIR = MEMORY_DIR / "workflow_logs"
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
        DATA_DIR,
        REPORT_DIR,
        CANDIDATE_DIR,
        FIGURE_DIR,
        WORKFLOW_LOG_DIR,
        RELATIONAL_MEMORY_DIR,
        VECTOR_MEMORY_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
