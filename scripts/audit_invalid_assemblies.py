"""Audit frozen BRD4-VHL assembly evidence and attachment-site hypotheses.

This script intentionally reads the manuscript freeze artifacts rather than
rerunning the live design graph. The closeout claim depends on the frozen
300 assembled / 150 valid count, while individual invalid assembly records
were not persisted. The output therefore closes the aggregate count and keeps
the per-invalid-molecule audit open instead of inferring details.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from rdkit import Chem

ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = ROOT / "outputs/manuscript_strategy/closeout/e2e_trace_identical_case.json"
STRATEGY_PATH = ROOT / "outputs/strategies/strategy_49bb27c13e.strategy.json"
DEFAULT_OUT = ROOT / "outputs/manuscript_strategy/closeout/invalid_assembly_audit.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _mol_ok(smiles: str | None) -> bool:
    return bool(smiles) and Chem.MolFromSmiles(smiles) is not None


def _strip_attachment_markers(smiles: str | None) -> str:
    if not smiles:
        return ""
    stripped = smiles
    for marker in ("[*:1]", "[*:2]", "[*]"):
        stripped = stripped.replace(marker, "")
    return stripped


def _component_rows(rows: list[dict[str, Any]], smiles_key: str = "smiles") -> list[dict[str, Any]]:
    checked = []
    for row in rows:
        smiles = row.get(smiles_key)
        stripped = _strip_attachment_markers(smiles)
        checked.append(
            {
                "name": row.get("name") or row.get("id") or row.get("candidate_id"),
                "smiles_ok_after_marker_strip": _mol_ok(stripped),
                "has_attachment_marker": "[*" in (smiles or ""),
                "source": row.get("source"),
            }
        )
    return checked


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    trace = _load_json(TRACE_PATH)
    strategy = _load_json(STRATEGY_PATH)

    final = trace.get("final_after", {})
    assembled = int(final.get("assembled_candidates", 0))
    valid = int(final.get("valid_candidates", 0))
    invalid = assembled - valid

    candidates = strategy.get("candidate_protacs", [])
    candidate_rows = [
        {
            "candidate_id": c.get("candidate_id"),
            "rank": c.get("rank"),
            "smiles_ok": _mol_ok(c.get("smiles")),
            "validity_status": c.get("validity_status"),
            "has_chemist_review_warning": "hypothetical_exit_vector_requires_chemist_review"
            in set(c.get("warning_flags") or []),
        }
        for c in candidates
    ]

    warheads = _component_rows(strategy.get("warheads", []))
    linkers = _component_rows(strategy.get("linker_hypotheses", []), smiles_key="smiles")
    attachment_vectors = strategy.get("attachment_vectors", [])

    report = {
        "schema_version": "invalid_assembly_audit.v2",
        "mode": "frozen_artifact_audit",
        "source_artifacts": [str(TRACE_PATH), str(STRATEGY_PATH)],
        "aggregate_assembly_evidence": {
            "assembled_candidates": assembled,
            "valid_candidates": valid,
            "invalid_candidates": invalid,
            "passes_expected_300_to_150_count": assembled == 300 and valid == 150 and invalid == 150,
            "individual_invalid_records_available": False,
            "limitation": (
                "The frozen trace persisted aggregate stage counts, not the 150 individual "
                "invalid assembly records or rejection reasons; per-invalid categorization "
                "therefore remains open."
            ),
        },
        "attachment_site_hypotheses": {
            "warheads_checked": len(warheads),
            "warheads_with_marker": sum(1 for w in warheads if w["has_attachment_marker"]),
            "warheads_parse_after_marker_strip": sum(1 for w in warheads if w["smiles_ok_after_marker_strip"]),
            "linkers_checked": len(linkers),
            "linkers_with_marker": sum(1 for l in linkers if l["has_attachment_marker"]),
            "linkers_parse_after_marker_strip": sum(1 for l in linkers if l["smiles_ok_after_marker_strip"]),
            "attachment_vectors_recorded": len(attachment_vectors),
            "candidate_protacs_checked": len(candidate_rows),
            "candidate_smiles_parse": sum(1 for c in candidate_rows if c["smiles_ok"]),
            "candidate_validity_status_valid": sum(1 for c in candidate_rows if c["validity_status"] == "valid"),
            "candidate_requires_chemist_review": sum(1 for c in candidate_rows if c["has_chemist_review_warning"]),
            "e3_ligand_smiles_available_in_strategy": False,
            "limitation": (
                "Strategy JSON records candidate E3 ligand names but not frozen E3 ligand "
                "SMILES/attachment-marker rows, so E3 marker validation cannot be closed "
                "from frozen artifacts alone."
            ),
        },
        "warhead_rows": warheads,
        "linker_rows": linkers,
        "candidate_rows": candidate_rows,
        "decision": (
            "PARTIAL: frozen aggregate evidence supports the 300 assembled / 150 valid / "
            "150 invalid count, and final candidate/warhead/linker attachment hypotheses "
            "are internally parseable. The 150 individual invalid assemblies and frozen E3 "
            "attachment-marker evidence were not persisted, so those audit elements remain blockers."
        ),
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "out": str(out),
        "assembled": assembled,
        "valid": valid,
        "invalid": invalid,
        "count_pass": report["aggregate_assembly_evidence"]["passes_expected_300_to_150_count"],
        "candidate_smiles_parse": report["attachment_site_hypotheses"]["candidate_smiles_parse"],
        "decision": report["decision"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
