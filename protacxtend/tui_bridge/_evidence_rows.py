"""Row-level packaged evidence audit for /reason-style questions.

Answers "which PROTACs work for <symbol>" with the packaged measured rows
when they exist, otherwise an explicit evidence-gap conclusion. Used by
``handle_diagnose`` so the TUI never presents a scenario diagnosis as if it
answered the row-level question.
"""

from __future__ import annotations

import csv
import os
import re
from functools import lru_cache
from typing import Any

_CONTEXT_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "protacxtend", "modules", "cell_context_selector", "data", "context_joined.csv",
)
_SYMBOL_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,7})\b")


@lru_cache(maxsize=1)
def _context_rows() -> list[dict[str, str]]:
    if not os.path.exists(_CONTEXT_CSV):
        return []
    with open(_CONTEXT_CSV, newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _symbols_in_request(request: str) -> list[str]:
    """Candidate symbols = uppercase tokens, longest first."""
    tokens = [t for t in _SYMBOL_RE.findall(request or "")]
    seen: list[str] = []
    for t in sorted(set(tokens), key=len, reverse=True):
        if t not in seen:
            seen.append(t)
    return seen


def _rows_for_symbol(rows: list[dict[str, str]], symbol: str) -> list[dict[str, str]]:
    sym = symbol.upper()
    out = []
    for r in rows:
        if str(r.get("target", "")).upper() == sym or str(r.get("target_symbol", "")).upper() == sym:
            out.append(r)
    return out


def _row_summary(r: dict[str, str]) -> str:
    name = str(r.get("protac_name") or r.get("protac_smiles_canonical") or "?")
    e3 = str(r.get("e3") or r.get("e3_gene") or "?")
    cell = str(r.get("cell_line") or r.get("cell_line_raw") or "?")
    dc50 = str(r.get("dc50_nM") or "-") + " nM" if str(r.get("dc50_nM") or "").strip() else "DC50 n/a"
    dmax = str(r.get("dmax_pct") or "") + "%" if str(r.get("dmax_pct") or "").strip() else "Dmax n/a"
    doi = str(r.get("doi") or "no DOI")
    return f"{name} | E3 {e3} | {cell} | {dc50} | {dmax} | {doi}"


def row_audit_for_request(request: str) -> tuple[list[str], str, str]:
    """Return (direct_answer_lines, evidence_gap_conclusion, case_source)."""
    rows = _context_rows()
    total = len(rows)
    for sym in _symbols_in_request(request):
        hit = _rows_for_symbol(rows, sym)
        if hit:
            lines = [f"{sym}: {len(hit)} measured degradation row(s) in the packaged context set"
                     f" ({total} total non-demo rows):"]
            for r in hit[:6]:
                lines.append("  " + _row_summary(r))
            if len(hit) > 6:
                lines.append(f"  … and {len(hit) - 6} more rows (full row audit in context_joined.csv).")
            return lines, "", "packaged_context_rows"
        gap = (
            f"Evidence-gap: 0 measured degradation rows for {sym} in the packaged context set "
            f"({total} total non-demo rows). No in-repo verification exists; live literature "
            f"retrieval (Europe PMC/PubMed) is the required next evidence step and was not "
            f"available offline."
        )
        return [], gap, "packaged_context_rows"
    return [], "Evidence-gap: no packaged measured degradation rows match this request; live retrieval required.", (
        "packaged_causal_record"
    )