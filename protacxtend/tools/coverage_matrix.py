"""coverage_cell tables — the search-instrumentation coverage matrix.

For every candidate a run actually evaluates, record the design cell
(warhead x E3 x linker keyed on InChIKeys). The matrix shows what the pipeline
searched vs the curated space it could have searched — the finding the ranked
candidate table conceals (AGENT_ARCHITECTURE_UPDATE §5.10).

Discipline (spec §5.10): best_pass_rate is NULL until a P4ward measurement
exists for the cell; best_proxy_score may be filled but never masquerades as
a pass rate. `measured=True` only when n_poses > 0.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from protacxtend.backend.schemas import CoverageCell
from protacxtend.tools.protac_toolbox import chem_identity

logger = logging.getLogger("protacpilot.coverage")

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_FILE = ROOT / "outputs" / "coverage" / "coverage_cells.jsonl"


def _load() -> Dict[str, CoverageCell]:
    cells: Dict[str, CoverageCell] = {}
    if COVERAGE_FILE.exists():
        for line in COVERAGE_FILE.read_text().splitlines():
            try:
                c = CoverageCell(**json.loads(line))
                cells[c.warhead_inchikey + c.e3 + c.linker_inchikey] = c
            except Exception:  # noqa: BLE001
                continue
    return cells


def record_coverage(candidates: List[Dict[str, Any]], run_id: str) -> Dict[str, Any]:
    """Append a coverage cell per evaluated candidate (append-only log)."""
    cells = _load()
    new_rows = []
    for c in candidates:
        wh_key = chem_identity(c.get("warhead_smiles") or (c.get("full_protac_smiles") or "")) or "?"
        lk = (c.get("linker_name") or c.get("linker_smiles") or "").strip()
        lk_key = chem_identity(lk) or "?"
        e3 = (c.get("e3_ligase") or "?").upper()
        key = wh_key + e3 + lk_key
        cell = cells.get(key) or CoverageCell(
            warhead_inchikey=wh_key, e3=e3, linker_inchikey=lk_key)
        cell.n_evaluated += 1
        cell.last_run_id = run_id
        # proxy may update; pass rate NEVER backfilled (measured stays False)
        cells[key] = cell
        new_rows.append(cell)
    COVERAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with COVERAGE_FILE.open("w") as fh:
        for cell in cells.values():
            fh.write(cell.model_dump_json() + "\n")
    return {"cells": len(cells), "new_evaluations": len(new_rows)}


def summarize_coverage() -> Dict[str, Any]:
    """Overlap fraction: evaluations pooled into distinct cells."""
    cells = _load()
    evaluated = [c for c in cells.values() if c.n_evaluated > 0]
    measured = [c for c in cells.values() if c.measured]
    total_combos = max(1, len(cells))
    return {
        "distinct_cells_evaluated": len(evaluated),
        "total_curated_combinations_seen": len(cells),
        "fraction_touched": round(len(evaluated) / total_combos, 4),
        "measured_cells": len(measured),
        "unmeasured": len(evaluated) - len(measured),
        "coverage_file": str(COVERAGE_FILE),
    }


# Public entry used by the runtime: record + return the summary.
def coverage_snapshot(candidates: List[Dict[str, Any]], run_id: str) -> Dict[str, Any]:
    try:
        record_coverage(candidates, run_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("coverage record failed: %s", exc)
    return summarize_coverage()


if __name__ == "__main__":
    snap = coverage_snapshot(
        [{"full_protac_smiles": "CC(=O)Oc1ccccc1C(=O)O", "e3_ligase": "CRBN",
          "linker_name": "PEG3"}], "demo_run")
    print(json.dumps(snap, indent=2))
