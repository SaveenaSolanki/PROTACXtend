#!/usr/bin/env python
"""Build the chemist exit-vector review packet for PROTACXtend design claims.

Why this exists
---------------
Every DESIGN candidate in the current repository uses *hypothetical* attachment
markers (``[*:1]``/``[*:2]``) and every curated warhead/E3 ligand seed is a
``local_demo_*`` record. Until a medicinal chemist signs off source-backed,
atom-mapped exit vectors, no design may be called "validated", BRD4-VHL stays a
legitimate no-go, and the E5 design endpoints cannot be scored.

This script does not decide chemistry. It produces a worksheet that a chemist
can complete, plus a packet that states exactly which claims are blocked.

Outputs (under ``benchmark/gateC/chemist_review/``):
  * ``CHEMIST_REVIEW_WORKSHEET.csv`` — one row per curated component + design case
  * ``CHEMIST_REVIEW_PACKET.md``     — human-readable packet with instructions
  * ``README.md``                    — workflow and acceptance criteria

Run from the repository root::

    python scripts/chemist_exit_vector_review.py
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "protacxtend" / "data"
GOLD = ROOT / "gold_answers_v1.jsonl"
OUT = ROOT / "benchmark" / "gateC" / "chemist_review"

WORKSHEET_COLUMNS = [
    "review_id", "row_kind", "component_type", "name", "target_or_e3",
    "current_source", "is_demo_source", "canonical_smiles",
    "proposed_attachment_label", "proposed_attachment_smarts",
    "exit_vector_confidence", "source_confidence",
    "chemistry_valid", "exit_vector_supported", "atom_map_verified",
    "admissible_for_design", "replacement_source_doi", "replacement_smiles",
    "reviewer", "review_date", "notes",
]

_DEMO_MARKERS = ("demo", "local_demo", "synglue curated")


def _utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_demo(source: str) -> bool:
    low = (source or "").lower()
    return any(marker in low for marker in _DEMO_MARKERS)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_components() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    counter = 0

    for w in _read_csv(DATA / "curated_warheads.csv"):
        counter += 1
        rows.append({
            "review_id": f"WAR-{counter:03d}", "row_kind": "curated_component",
            "component_type": "warhead", "name": w.get("name", ""),
            "target_or_e3": w.get("target", ""), "current_source": w.get("source", ""),
            "is_demo_source": _is_demo(w.get("source", "")),
            "canonical_smiles": w.get("smiles", ""),
            "proposed_attachment_label": "[*:1] (in SMILES)",
            "proposed_attachment_smarts": "",
            "exit_vector_confidence": w.get("exit_vector_confidence", ""),
            "source_confidence": w.get("source_confidence", ""),
        })

    for e in _read_csv(DATA / "curated_e3_ligands.csv"):
        counter += 1
        rows.append({
            "review_id": f"E3L-{counter:03d}", "row_kind": "curated_component",
            "component_type": "e3_ligand", "name": e.get("name", ""),
            "target_or_e3": e.get("e3_ligase", ""), "current_source": e.get("source", ""),
            "is_demo_source": _is_demo(e.get("source", "")),
            "canonical_smiles": e.get("smiles", ""),
            "proposed_attachment_label": e.get("attachment_point", "") or "[*:1] (in SMILES)",
            "proposed_attachment_smarts": "",
            "exit_vector_confidence": e.get("exit_vector_confidence", ""),
            "source_confidence": e.get("source_confidence", ""),
        })

    for m in _read_csv(DATA / "curated_exit_vector_map.csv"):
        counter += 1
        rows.append({
            "review_id": f"EVM-{counter:03d}", "row_kind": "exit_vector_map",
            "component_type": m.get("component_type", ""), "name": m.get("name", ""),
            "target_or_e3": "", "current_source": m.get("source", ""),
            "is_demo_source": _is_demo(m.get("source", "")),
            "canonical_smiles": m.get("smiles", ""),
            "proposed_attachment_label": m.get("attachment_atom_label", ""),
            "proposed_attachment_smarts": m.get("attachment_smarts", ""),
            "exit_vector_confidence": m.get("confidence", ""),
            "source_confidence": "",
        })
    return rows


def design_cases() -> list[dict[str, Any]]:
    if not GOLD.exists():
        return []
    rows: list[dict[str, Any]] = []
    with GOLD.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            g = json.loads(line)
            if g.get("gold_answer_type") == "design_rubric":
                rows.append({
                    "case_id": g["case_id"], "capability": g.get("capability", ""),
                    "split": g.get("split", ""),
                    "frozen_proposal": g.get("proposed_answer_from_frozen_gt", ""),
                    "required_entities": g.get("required_entities", []),
                })
    return rows


def _default_review_fields(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    for col in WORKSHEET_COLUMNS:
        row.setdefault(col, "")
    return row


def build_worksheet() -> list[dict[str, Any]]:
    rows = [_default_review_fields(r) for r in load_components()]
    for case in design_cases():
        rows.append(_default_review_fields({
            "review_id": f"CASE-{case['case_id']}", "row_kind": "design_case",
            "component_type": "design_assembly", "name": case["case_id"],
            "target_or_e3": "",
            "current_source": "hypothetical attachment (no source-backed exit vector)",
            "is_demo_source": True, "canonical_smiles": "",
            "proposed_attachment_label": "[*:1]/[*:2] hypothetical",
            "proposed_attachment_smarts": "",
            "exit_vector_confidence": "", "source_confidence": "",
            "notes": f"required: {', '.join(case['required_entities'])}",
        }))
    return rows


def write_outputs(rows: list[dict[str, Any]]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ws = OUT / "CHEMIST_REVIEW_WORKSHEET.csv"
    with ws.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=WORKSHEET_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in WORKSHEET_COLUMNS})

    n_demo = sum(1 for r in rows if str(r.get("is_demo_source")).lower() == "true")
    n_components = sum(1 for r in rows if r["row_kind"] != "design_case")
    n_cases = sum(1 for r in rows if r["row_kind"] == "design_case")
    cases = design_cases()

    packet = [
        "# Chemist exit-vector review packet",
        "",
        f"_Generated {_utcnow()}._",
        "",
        "## Why every design is currently blocked",
        "",
        "All curated warhead/E3-ligand seeds are `local_demo_*` records and all DESIGN",
        "assemblies use hypothetical attachment markers (`[*:1]`/`[*:2]`). A binder plus",
        "a plain SMILES does **not** validate an exit vector, and a docking score does",
        "not validate ubiquitination or a measured DC50. Until a chemist signs the",
        "worksheet, every DESIGN node must return `hypothetical` and BRD4-VHL remains a",
        "legitimate no-go.",
        "",
        "## Scope",
        "",
        f"- curated components to review: **{n_components}** (of which **{n_demo}** are demo-sourced)",
        f"- design cases needing a source-backed assembly: **{n_cases}**",
        "",
        "## Worksheet",
        "",
        f"`{ws.relative_to(ROOT)}` — one row per component and per design case.",
        "",
        "For each row the reviewer must set:",
        "",
        "| column | allowed values | meaning |",
        "|---|---|---|",
        "| `chemistry_valid` | `yes` / `no` / `unclear` | SMILES parses, valence correct, stereochemistry sane |",
        "| `exit_vector_supported` | `yes` / `no` / `hypothetical` | source documents a derivatizable vector at the stated atom |",
        "| `atom_map_verified` | `yes` / `no` | the attachment atom is unambiguous and mapped |",
        "| `admissible_for_design` | `yes` / `no` | may this component be used in a SCIENTIFIC-mode design claim? |",
        "| `replacement_source_doi` | DOI/PMID | required when the current row is demo-sourced |",
        "| `replacement_smiles` | canonical SMILES | required when a source-backed replacement is supplied |",
        "| `reviewer`, `review_date`, `notes` | free text | accountability |",
        "",
        "## Design cases",
        "",
        "| case | capability | split | blocked claim |",
        "|---|---|---|---|",
    ]
    for case in cases:
        packet.append(
            f"| {case['case_id']} | {case['capability']} | {case['split']} | "
            "validated atom-mapped design until a source-backed exit vector is approved |"
        )
    packet += [
        "",
        "## Acceptance criteria (blocks → unblocks)",
        "",
        "1. Every `is_demo_source=true` row is either replaced by a source-backed",
        "   component or explicitly marked `admissible_for_design=no`.",
        "2. Every component used by a DESIGN case has `exit_vector_supported=yes` and",
        "   `atom_map_verified=yes` with a resolving DOI/PMID.",
        "3. `admissible_for_design=yes` rows require a completing chemist name.",
        "4. Until 1-3 hold, the E5 design endpoint and any \"designed degrader\" sentence",
        "   stay `not measured`; the BRD4-VHL no-go remains the reported example.",
        "",
        "## After review",
        "",
        "Replace demo rows in `protacxtend/data/curated_warheads.csv`,",
        "`curated_e3_ligands.csv` and `curated_exit_vector_map.csv`, then re-run the",
        "design path in SCIENTIFIC mode and confirm the exit-vector gate passes with",
        "atom-level provenance. Do not hand-edit the engine to bypass the gate.",
        "",
    ]
    (OUT / "CHEMIST_REVIEW_PACKET.md").write_text("\n".join(packet), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# Chemist review — operational notes\n\n"
        "1. Copy the worksheet, do not overwrite it per reviewer: `CHEMIST_REVIEW_WORKSHEET.csv`.\n"
        "2. One chemist may cover all rows; if two review, keep separate copies and adjudicate.\n"
        "3. A row is not admissible until `reviewer` and `review_date` are set.\n"
        "4. Return the completed worksheet and this script will be re-run to regenerate the packet status.\n\n"
        "Accepted `exit_vector_supported` values: `yes`, `no`, `hypothetical`.\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "worksheet": str(ws),
        "packet": str(OUT / "CHEMIST_REVIEW_PACKET.md"),
        "rows": len(rows),
        "demo_sourced_rows": n_demo,
        "design_cases": n_cases,
    }, indent=2))


def main() -> int:
    rows = build_worksheet()
    write_outputs(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
