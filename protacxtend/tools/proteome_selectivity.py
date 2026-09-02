"""Proteome-context selectivity scoring for PROTAC hypotheses."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from protacxtend.tools.repo_tool_adapter import PROJECT_ROOT


DEFAULT_CONTEXT_TABLE = PROJECT_ROOT / "protacxtend" / "data" / "cell_context_atlas.csv"


@dataclass
class ProteomeSelectivityResult:
    target: str
    e3: str
    cell_line: str
    status: str
    selectivity_score: float
    off_target_risk: float
    context_dependency: float
    evidence_rows: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backend: str = "protacxtend_proteome_context_v0.1"

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _load_rows(path: str | Path | None = None) -> list[dict[str, str]]:
    table = Path(path) if path else DEFAULT_CONTEXT_TABLE
    if not table.exists():
        return []
    with table.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _float(row: dict[str, Any], key: str, default: float = 0.5) -> float:
    try:
        return float(row.get(key, default))
    except Exception:
        return default


def score_proteome_context(
    target: str,
    e3: str,
    cell_line: str = "default",
    table_path: str | Path | None = None,
) -> ProteomeSelectivityResult:
    rows = _load_rows(table_path)
    target_u = target.upper()
    e3_u = e3.upper()
    cell_u = cell_line.upper()
    matches = [
        row for row in rows
        if row.get("target", "").upper() == target_u
        and row.get("e3", "").upper() == e3_u
        and row.get("cell_line", "").upper() in {cell_u, "DEFAULT"}
    ]
    warnings: list[str] = []
    if not matches:
        warnings.append("No matching proteome/cell-context row; using conservative prior.")
        return ProteomeSelectivityResult(
            target=target,
            e3=e3,
            cell_line=cell_line,
            status="INSUFFICIENT EVIDENCE",
            selectivity_score=0.45,
            off_target_risk=0.55,
            context_dependency=0.75,
            warnings=warnings,
        )
    row = matches[0]
    target_expr = _float(row, "target_expression_score")
    e3_expr = _float(row, "e3_expression_score")
    resistance = _float(row, "resistance_risk", 0.3)
    off_target = _float(row, "off_target_risk", 0.4)
    selectivity = max(0.0, min(1.0, 0.40 * target_expr + 0.30 * e3_expr + 0.20 * (1.0 - off_target) + 0.10 * (1.0 - resistance)))
    dependency = max(0.0, min(1.0, abs(target_expr - e3_expr) + resistance * 0.5))
    status = "SUPPORTED" if selectivity >= 0.62 and off_target <= 0.55 else "REVISE"
    return ProteomeSelectivityResult(
        target=target,
        e3=e3,
        cell_line=cell_line,
        status=status,
        selectivity_score=round(selectivity, 3),
        off_target_risk=round(off_target, 3),
        context_dependency=round(dependency, 3),
        evidence_rows=matches[:3],
        warnings=warnings,
    )

