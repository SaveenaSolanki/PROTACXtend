"""Row-level evidence audit for plan gates.

Counts alone never pass an evidence gate: this module enumerates the actual
rows (record ids, DOIs, assay context, dedup rule, usable-for-objective) or
marks a figure as count-only (e.g. the curated binder count that has no
row-level source in this package).
"""

from __future__ import annotations

import csv, os
from dataclasses import dataclass, field
from typing import Any, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTEXT_CSV = os.path.join(ROOT, "protacxtend", "modules", "cell_context_selector", "data", "context_joined.csv")
CURATED_TARGETS = os.path.join(ROOT, "protacxtend", "data", "curated_targets.csv")
BINDER_TABLE = os.path.join(ROOT, "data", "protac_repos", "repos", "protacSpace", "data", "raw", "warhead.csv")


@dataclass
class DegradationRow:
    row_id: str
    protac: str
    e3: str
    cell_line: str
    dc50_nM: str
    dmax_pct: str
    doi: str
    source_db: str
    assay_text: str
    treatment_time_h: str
    derived_active: str
    dedup_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class RowAudit:
    target: str
    rows: list[DegradationRow] = field(default_factory=list)
    dedup_rule: str = ""
    n_unique: int = 0
    usable_for_objective: list[DegradationRow] = field(default_factory=list)
    binder_count: Optional[int] = None
    binder_rows_in_package: int = 0
    binder_count_only: bool = False

    @property
    def n_rows_raw(self) -> int:
        return len(self.rows)

    @property
    def n_unique_after_dedup(self) -> int:
        return self.n_unique

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "n_rows_raw": len(self.rows),
            "dedup_rule": self.dedup_rule,
            "n_unique_after_dedup": self.n_unique,
            "rows": [r.to_dict() for r in self.rows],
            "usable_for_objective": [r.to_dict() for r in self.usable_for_objective],
            "binder_count": self.binder_count,
            "binder_rows_in_package": self.binder_rows_in_package,
            "binder_count_only": self.binder_count_only,
        }


def audit_degradation_rows(target: str, *, e3_filter: str = "", require_dc50: bool = False) -> RowAudit:
    audit = RowAudit(target=target)
    if not os.path.exists(CONTEXT_CSV):
        return audit
    unique: dict[str, DegradationRow] = {}
    with open(CONTEXT_CSV, newline="") as f:
        for ridx, row in enumerate(csv.DictReader(f)):
            if (row.get("target") or "").strip().upper() != target.upper():
                continue
            e3 = (row.get("e3_gene") or row.get("e3") or "").strip()
            r = DegradationRow(
                row_id=f"ctx-{ridx:04d}",
                protac=(row.get("protac_name") or "").strip(),
                e3=e3,
                cell_line=(row.get("cell_line_raw") or row.get("cell_line") or "").strip(),
                dc50_nM=(row.get("dc50_nM") or "").strip(),
                dmax_pct=(row.get("dmax_pct") or "").strip(),
                doi=(row.get("doi") or "").strip(),
                source_db=(row.get("source_db") or "").strip(),
                assay_text=(row.get("assay_text") or "").strip(),
                treatment_time_h=(row.get("treatment_time_h") or "").strip(),
                derived_active=(row.get("derived_active") or "").strip(),
            )
            # dedup rule: same protac canonical SMILES + E3 + cell + DOI -> one row (keep first)
            key = "|".join([(row.get("protac_smiles_canonical") or "").strip(),
                           r.e3, r.cell_line, r.doi])
            r.dedup_key = key
            if key not in unique:
                unique[key] = r
    audit.rows = list(unique.values())
    audit.dedup_rule = ("unique(protac_canonical_smiles, e3, cell_line, doi) — "
                        "protocol-matching rows are already deduplicated on canonical identity")
    audit.n_unique = len(audit.rows)
    # usable for objective: has measured DC50 or Dmax, and (optionally) matching E3
    usable = []
    for r in audit.rows:
        has_measure = (r.dc50_nM not in ("", "nan")) or (r.dmax_pct not in ("", "nan"))
        e3_ok = (not e3_filter) or (r.e3.upper() == e3_filter.upper())
        usable_measure = True if not require_dc50 else (r.dc50_nM not in ("", "nan"))
        if has_measure and e3_ok and usable_measure:
            usable.append(r)
    audit.usable_for_objective = usable
    return audit


def audit_binder_count(target: str) -> RowAudit:
    """Curated binder count (curated_targets.csv) vs row-level binders in the
    packaged cited table. Count-only figures never pass the binder gate."""
    stem = target.upper()
    audit = RowAudit(target=target)
    count: Optional[int] = None
    if os.path.exists(CURATED_TARGETS):
        with open(CURATED_TARGETS, newline="") as f:
            for row in csv.DictReader(f):
                if (row.get("gene_symbol") or "").strip().upper() == stem:
                    raw = (row.get("known_binder_count") or "").strip()
                    try:
                        count = int(raw)
                    except ValueError:
                        count = None
                    break
    audit.binder_count = count
    rows_in_package = 0
    if os.path.exists(BINDER_TABLE):
        with open(BINDER_TABLE, newline="") as f:
            for row in csv.DictReader(f):
                if (row.get("Uniprot") or "").strip().upper() == stem:
                    rows_in_package += 1
    audit.binder_rows_in_package = rows_in_package
    audit.binder_count_only = count is not None and rows_in_package == 0
    return audit