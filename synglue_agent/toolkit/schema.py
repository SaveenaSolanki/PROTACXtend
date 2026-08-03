"""Schema helpers for the Excel-backed toolkit registry."""

from __future__ import annotations

import re
from typing import Any


SECTION_SHEETS = {
    "modalities": "Modalities",
    "tools": "Tools_Expanded",
    "databases": "Databases_Expanded",
    "packages": "Packages",
    "skills": "Skills",
    "agent_modules": "Agent_Modules",
}


NAME_COLUMNS = {
    "modalities": "modality",
    "tools": "tool",
    "databases": "database",
    "packages": "package",
    "skills": "skill",
    "agent_modules": "agent_module",
}


def normalize_column_name(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    text = re.sub(r"[^0-9A-Za-z]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_").lower()
    return text or "unnamed"


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value).strip().lower())


def clean_value(value: Any) -> Any:
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def structured_entry(section: str, source_sheet: str, source_row: int, row: dict[str, Any]) -> dict[str, Any] | None:
    cleaned = {normalize_column_name(key): clean_value(value) for key, value in row.items()}
    if not any(value not in (None, "") for value in cleaned.values()):
        return None
    name_key = NAME_COLUMNS[section]
    name = cleaned.get(name_key)
    if not name:
        return None
    return {
        "id": f"{section}:{normalize_text(name).replace(' ', '_')}",
        "name": str(name).strip(),
        "section": section,
        "source_sheet": source_sheet,
        "source_row": source_row,
        "fields": cleaned,
    }
