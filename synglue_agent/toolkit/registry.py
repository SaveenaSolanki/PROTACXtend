"""Excel-backed toolkit registry for PROTACXtend.

Phase 1 is intentionally registry-only: it loads the source workbook, preserves
all rows from the key sheets, and exposes structured search helpers. It does not
connect APIs, execute tools, or alter scientific scoring.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from synglue_agent.toolkit.schema import SECTION_SHEETS, normalize_text, structured_entry


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXCEL_PATH = PROJECT_ROOT / "data" / "toolkit" / "Agent_Toolkit.xlsx"
HEADER_ROW_INDEX = 3


def _resolve_excel_path(excel_path: str | Path) -> Path:
    path = Path(excel_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Toolkit Excel registry not found: {path}")
    return path


def _load_section(path: Path, section: str, sheet_name: str) -> list[dict[str, Any]]:
    raw = pd.read_excel(path, sheet_name=sheet_name, header=HEADER_ROW_INDEX)
    raw = raw.dropna(how="all")
    entries: list[dict[str, Any]] = []
    for frame_index, row in raw.iterrows():
        source_row = int(frame_index) + 2
        entry = structured_entry(section, sheet_name, source_row, row.to_dict())
        if entry is not None:
            entries.append(entry)
    return entries


@lru_cache(maxsize=4)
def _load_toolkit_registry_cached(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    registry: dict[str, Any] = {
        "source_path": str(path),
        "sections": list(SECTION_SHEETS.keys()),
    }
    for section, sheet_name in SECTION_SHEETS.items():
        registry[section] = _load_section(path, section, sheet_name)
    return registry


def load_toolkit_registry(excel_path: str | Path = "data/toolkit/Agent_Toolkit.xlsx") -> dict[str, Any]:
    """Load all key registry sections from ``Agent_Toolkit.xlsx``."""

    path = _resolve_excel_path(excel_path)
    return _load_toolkit_registry_cached(str(path.resolve()))


def _section(section: str, excel_path: str | Path = "data/toolkit/Agent_Toolkit.xlsx") -> list[dict[str, Any]]:
    if section not in SECTION_SHEETS:
        raise ValueError(f"Unknown registry section: {section}")
    return load_toolkit_registry(excel_path)[section]


def get_modalities() -> list[dict[str, Any]]:
    return _section("modalities")


def get_tools() -> list[dict[str, Any]]:
    return _section("tools")


def get_databases() -> list[dict[str, Any]]:
    return _section("databases")


def get_packages() -> list[dict[str, Any]]:
    return _section("packages")


def get_skills() -> list[dict[str, Any]]:
    return _section("skills")


def get_agent_modules() -> list[dict[str, Any]]:
    return _section("agent_modules")


def _entries_for_search(registry: dict[str, Any], section: str | None = None) -> Iterable[dict[str, Any]]:
    if section:
        if section not in SECTION_SHEETS:
            raise ValueError(f"Unknown registry section: {section}")
        yield from registry[section]
        return
    for key in SECTION_SHEETS:
        yield from registry[key]


def _score_entry(entry: dict[str, Any], terms: list[str]) -> int:
    name = normalize_text(entry.get("name"))
    haystack = normalize_text(" ".join(str(value) for value in entry.get("fields", {}).values() if value is not None))
    score = 0
    for term in terms:
        if term in name:
            score += 5
        if term in haystack:
            score += 1
    return score


def search_registry(query: str, section: str | None = None, top_k: int = 10) -> list[dict[str, Any]]:
    registry = load_toolkit_registry()
    terms = [term for term in normalize_text(query).split(" ") if term]
    entries = list(_entries_for_search(registry, section))
    if not terms:
        return entries[:top_k]
    scored = [(score, entry) for entry in entries if (score := _score_entry(entry, terms))]
    scored.sort(key=lambda item: (item[0], item[1]["section"], item[1]["name"]), reverse=True)
    return [entry for _, entry in scored[:top_k]]


def search_tools(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    return search_registry(query, section="tools", top_k=top_k)


def search_databases(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    return search_registry(query, section="databases", top_k=top_k)


def search_skills(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    return search_registry(query, section="skills", top_k=top_k)


def get_agent_module(module_name: str) -> dict[str, Any] | None:
    query = normalize_text(module_name)
    for module in get_agent_modules():
        if normalize_text(module.get("name")) == query:
            return module
    return None


def summarize_registry() -> dict[str, Any]:
    registry = load_toolkit_registry()
    sections = {
        section: {
            "source_sheet": SECTION_SHEETS[section],
            "count": len(registry[section]),
        }
        for section in SECTION_SHEETS
    }
    return {
        "source_path": registry["source_path"],
        "sections": sections,
        "total_rows": sum(item["count"] for item in sections.values()),
    }


# Backward-compatible names for older scaffold callers. These are registry-only
# summaries in Phase 1, not tool availability/execution status.
def get_tool_status(tool_name: str) -> dict[str, Any]:
    query = normalize_text(tool_name)
    registry = load_toolkit_registry()
    for section in SECTION_SHEETS:
        for entry in registry[section]:
            if normalize_text(entry["name"]) == query:
                return {
                    "name": entry["name"],
                    "type": entry["section"],
                    "registered": True,
                    "available": False,
                    "executable": False,
                    "source_sheet": entry["source_sheet"],
                    "source_row": entry["source_row"],
                }
    result = search_registry(tool_name, top_k=1)
    if result:
        entry = result[0]
        return {
            "name": entry["name"],
            "type": entry["section"],
            "registered": True,
            "available": False,
            "executable": False,
            "source_sheet": entry["source_sheet"],
            "source_row": entry["source_row"],
        }
    return {
        "name": tool_name,
        "type": None,
        "registered": False,
        "available": False,
        "executable": False,
        "source_sheet": None,
        "source_row": None,
    }


def summarize_toolkit_status() -> dict[str, Any]:
    summary = summarize_registry()
    return {
        "source_path": summary["source_path"],
        "collections": {
            section: {"registered": data["count"], "available": 0, "executable": 0}
            for section, data in summary["sections"].items()
        },
        "totals": {"registered": summary["total_rows"], "available": 0, "executable": 0},
    }
