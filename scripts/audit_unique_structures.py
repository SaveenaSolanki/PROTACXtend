#!/usr/bin/env python
"""Stereochemistry-aware unique-structure audit for a candidate evidence file.

Reports raw record count, unique isomeric structures, and unique constitutional
graphs, so a repeated/conformer set is never described as N novel molecules.

Usage:
    python scripts/audit_unique_structures.py outputs/execution/design_evidence/candidate_evidence.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def _canon(smiles: str, stereo: bool) -> str | None:
    try:
        from rdkit import Chem
        m = Chem.MolFromSmiles(smiles or "")
        if m is None:
            return None
        return Chem.MolToSmiles(m, isomericSmiles=stereo)
    except Exception:  # noqa: BLE001
        return None


def main(argv: list[str]) -> int:
    path = Path(argv[1] if len(argv) > 1 else
                "outputs/execution/design_evidence/candidate_evidence.json")
    rows = json.loads(path.read_text(encoding="utf-8"))
    smis = [r.get("canonical_smiles") or r.get("full_protac_smiles") or "" for r in rows]
    iso = [c for c in (_canon(s, True) for s in smis) if c]
    con = [c for c in (_canon(s, False) for s in smis) if c]
    ids = Counter(r.get("candidate_id", "").split("_st")[0] for r in rows)
    print(json.dumps({
        "source": str(path),
        "raw_records": len(rows),
        "unparseable": len(rows) - len(iso),
        "unique_isomeric": len(set(iso)),
        "unique_constitutional": len(set(con)),
        "duplicate_isomeric_records": len(iso) - len(set(iso)),
        "identity_pass": sum(1 for r in rows
                             if (r.get("identity_assembly_gate") or {}).get("all_required_passed")),
        "parent_candidate_ids": dict(ids),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
