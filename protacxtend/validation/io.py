"""Provenance-rich benchmark row I/O.

Every harness writes through :class:`RowWriter` so that the benchmark tables
share one schema and no row can silently omit provenance or failure fields.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from protacxtend.audit.provenance import benchmark_provenance, file_sha256


class RowWriter:
    """Accumulate benchmark rows and persist them (CSV + JSON + parquet)."""

    def __init__(self, name: str, out_dir: str | Path) -> None:
        self.name = name
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.rows: list[dict[str, Any]] = []

    # ── row construction ───────────────────────────────────────────────
    def provenance(self, **kwargs: Any) -> dict[str, Any]:
        return benchmark_provenance(**kwargs)

    def add(self, row: dict[str, Any]) -> dict[str, Any]:
        self.rows.append(row)
        self._flush()
        return row

    def _flush(self) -> None:
        if not self.rows:
            return
        keys: list[str] = []
        for row in self.rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        csv_path = self.out_dir / f"{self.name}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.rows)
        (self.out_dir / f"{self.name}.json").write_text(
            json.dumps({"benchmark": self.name, "n": len(self.rows), "rows": self.rows},
                       indent=2, default=str),
            encoding="utf-8")

    def finalize(self, summary: dict[str, Any] | None = None) -> None:
        self._flush()
        try:
            import pandas as pd

            pd.DataFrame(self.rows).to_parquet(self.out_dir / f"{self.name}.parquet", index=False)
        except Exception:
            pass
        if summary is not None:
            (self.out_dir / f"{self.name}_summary.json").write_text(
                json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # ── failure accounting ─────────────────────────────────────────────
    def failure(self, *, structure_id: str = "", ligand_id: str = "", engine: str = "",
                stage: str, outcome: str, reason: str, **extra: Any) -> dict[str, Any]:
        """Build a failure record.

        Failure records are persisted separately (``failures.csv``) and must not
        be mixed into the main row list, otherwise the denominator is double
        counted.  The caller keeps them in a dedicated ``failures`` list.
        """
        row = {
            "structure_id": structure_id, "ligand_id": ligand_id, "engine": engine,
            "stage": stage, "outcome": outcome, "status": outcome,
            "success": False, "failure_reason": reason[:400],
        }
        row.update(extra)
        return row


def write_summary_json(path: str | Path, payload: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


__all__ = ["RowWriter", "write_summary_json", "file_sha256"]
