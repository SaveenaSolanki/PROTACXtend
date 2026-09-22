"""Proteome-context selectivity scoring for PROTAC hypotheses.

Combines two independently inspectable evidence components:

  1. a cell-line / proteome context table (``cell_context_atlas.csv``,
     local curated priors), and
  2. BRD/BET domain-aware ligand evidence (``brd_bet_intelligence``) for any
     query whose target is BRD2/BRD3/BRD4/BRDT.

The BRD component is only added when the target is a BET bromodomain; its
``evidence_level`` (measured / proxy / absent) is reported verbatim so a
target-level prior is never mistaken for a measurement of the query warhead.
"""

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
    backend: str = "protacxtend_proteome_context_v0.2"
    brd_bet_evidence: dict[str, Any] | None = None

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


def _brd_bet_component(target: str | None, warhead: str | None,
                       warhead_smiles: str | None) -> dict[str, Any] | None:
    if not target:
        return None
    try:
        from protacxtend.modules.brd_bet_intelligence import (
            is_bet_target, score_brd_bet,
        )
        if not is_bet_target(target):
            return None
        return score_brd_bet(target, warhead_name=warhead,
                             warhead_smiles=warhead_smiles)
    except Exception as exc:  # never break the caller on optional evidence
        return {"status": "ERROR", "evidence_level": "absent",
                "score": None, "error": str(exc)}


def score_proteome_context(
    target: str,
    e3: str,
    cell_line: str = "default",
    table_path: str | Path | None = None,
    warhead: str | None = None,
    warhead_smiles: str | None = None,
) -> ProteomeSelectivityResult:
    rows = _load_rows(table_path)
    target_u = str(target).upper()
    e3_u = str(e3).upper()
    cell_u = str(cell_line).upper()
    matches = [
        row for row in rows
        if row.get("target", "").upper() == target_u
        and row.get("e3", "").upper() == e3_u
        and row.get("cell_line", "").upper() in {cell_u, "DEFAULT"}
    ]
    warnings: list[str] = []

    # --- BRD/BET domain-aware evidence (independent component) -------------
    brd = _brd_bet_component(target, warhead, warhead_smiles)

    if not matches:
        warnings.append("No matching proteome/cell-context row; using conservative prior.")
        base = {
            "selectivity_score": 0.45, "off_target_risk": 0.55,
            "context_dependency": 0.75, "status": "INSUFFICIENT EVIDENCE",
        }
    else:
        row = matches[0]
        target_expr = _float(row, "target_expression_score")
        e3_expr = _float(row, "e3_expression_score")
        resistance = _float(row, "resistance_risk", 0.3)
        off_target = _float(row, "off_target_risk", 0.4)
        selectivity = max(0.0, min(1.0, 0.40 * target_expr + 0.30 * e3_expr
                                   + 0.20 * (1.0 - off_target)
                                   + 0.10 * (1.0 - resistance)))
        dependency = max(0.0, min(1.0, abs(target_expr - e3_expr) + resistance * 0.5))
        base = {
            "selectivity_score": round(selectivity, 3),
            "off_target_risk": round(off_target, 3),
            "context_dependency": round(dependency, 3),
            "status": ("SUPPORTED" if selectivity >= 0.62 and off_target <= 0.55
                       else "REVISE"),
        }

    # --- combine, keeping components separately inspectable ---------------
    if brd and brd.get("score") is not None:
        # BET-specific measured evidence modulates the generic context score
        # (mean of the two, so neither dominates); a proxy prior gets half
        # weight relative to a measured result.
        w = 1.0 if brd.get("evidence_level") == "measured" else 0.5
        combined = ((base["selectivity_score"] * 1.0 + brd["score"] * w)
                    / (1.0 + w))
        base["selectivity_score"] = round(combined, 3)
        warnings.append(
            f"BRD/BET component included (evidence_level={brd.get('evidence_level')}"
            f", status={brd.get('status')}).")
    elif brd and brd.get("evidence_level") == "absent":
        warnings.append("BRD/BET target but no curated ligand evidence; "
                        "domain/family selectivity UNKNOWN.")

    return ProteomeSelectivityResult(
        target=str(target),
        e3=str(e3),
        cell_line=str(cell_line),
        status=base["status"],
        selectivity_score=base["selectivity_score"],
        off_target_risk=base["off_target_risk"],
        context_dependency=base["context_dependency"],
        evidence_rows=matches[:3],
        warnings=warnings,
        brd_bet_evidence=brd,
    )
