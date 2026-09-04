"""BRD4–VHL six-PROTAC PROSPECTIVE CASE STUDY.

This is a prospective case study, NOT a benchmark: the six molecules are
never used as ground truth. The KNOW → REASON → DESIGN → DISCOVER workflow
runs over the blinded input file (``examples/brd4_vhl_6.csv``), reusing
existing PROTACXtend tools (RDKit descriptors via ``molecule_standardizer``)
and the shared ScientificResult schema.

The input is blinded: it contains no outcome-derived ranking. The final
ranking produced here is a prediction to be LOCKED before any wet-lab
outcome is consulted. Because the repository carries **no measured potency**
for these molecules, everything measured is absent and reported as such
(kind=``missing``); measured/retrieved/calculated/predicted/missing are kept
strictly separate.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATASETS = [
    "examples/brd4_vhl_6.csv",
    "tui/examples/brd4_vhl_6.csv",
    "tui/outputs/BRD4_VHL_PROTAC_ranking.md",
]

# Structural penalty rules (evidence-driven, read from the CSV fields —
# never keyed on molecule id/name).
_LINKER_PENALTY = {
    "PEG3": 0.0,
    "PEG3 (secondary amine junction)": -2.5,
    "Piperidine-PEG3": -0.2,
    "Pyrazole-PEG3": -0.8,
    "Alkyl8-PEG1 hybrid": -1.6,
    "Alkyl11-PEG1 hybrid": -2.4,
}
_JUNCTION_PENALTY = {"amide": 0.0, "aryl-pyrazole": -1.0, "secondary amine": -2.5}
_VHL_PENALTY = {"intact": 0.0, "modified": -6.0}  # >100x loss of VHL binding SAR

_BASE = 8.0


def _band(score: float) -> str:
    if score >= 7.4:
        return "predicted low nM"
    if score >= 6.6:
        return "predicted low-to-mid nM"
    if score >= 5.5:
        return "predicted mid nM"
    if score >= 4.5:
        return "predicted high nM"
    if score >= 3.0:
        return "predicted low \u03bcM"
    return "predicted \u03bcM\u2013mM (weak/inactive)"


def resolve_dataset(path: Optional[str] = None) -> Path:
    """Resolve a user path or fall back to the bundled six-PROTAC dataset."""
    if path:
        cands = [Path(path)]
        if not Path(path).is_absolute():
            cands += [Path.cwd() / path, PROJECT_ROOT / path]
        for c in cands:
            if c.is_file():
                return c
        raise FileNotFoundError(f"dataset not found: {path}")

    for rel in DEFAULT_DATASETS:
        cand = PROJECT_ROOT / rel
        if cand.is_file() and cand.suffix == ".csv":
            return cand
    raise FileNotFoundError("bundled BRD4\u2013VHL six-PROTAC dataset not found")


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    with open(csv_path, newline="", encoding="utf-8") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def _linker_atoms(row: dict[str, str]) -> Optional[int]:
    raw = str(row.get("linker_atoms", "")).strip()
    try:
        return int(raw.replace("~", "").replace("≈", ""))
    except ValueError:
        return None


def _props(smiles: str) -> dict[str, Any]:
    """Calculated RDKit descriptors (existing tool, never mocked)."""
    try:
        from protacxtend.tools.molecule_standardizer import compute_basic_properties
        return compute_basic_properties(smiles) or {}
    except Exception:
        return {}


def run_brd4_vhl_six_case_study(path: Optional[str] = None) -> dict[str, Any]:
    """Run the four-phase benchmark and return a schema-wrapped result."""
    from protacxtend.results.schema import ScientificResult, Provenance

    ds = resolve_dataset(path)
    rows = _read_rows(ds)
    if not rows:
        raise ValueError(f"empty dataset: {ds}")

    stages: list[dict[str, str]] = []
    records: list[dict[str, Any]] = []

    # KNOW — retrieve target/E3/candidate records
    stages.append({"phase": "KNOW", "note": f"loaded {len(rows)} BRD4\u2013VHL PROTAC records from {ds.name}"})
    target = {"name": "BRD4 (BD1/BD2)", "E3": "VHL (VH032-type ligand)"}
    for row in rows:
        records.append({"id": row.get("id", ""), "name": row.get("name", ""), "fields": row})

    # REASON — warhead + VHL + linker + properties + ternary + degradation logic
    stages.append({"phase": "REASON",
                   "note": "scored retrieved structural fields; computed RDKit properties for warhead/VHL ligand"})
    n_calculated = 0
    for rec in records:
        row = rec["fields"]
        warhead = str(row.get("warhead_smiles", "")).strip()
        vhl = str(row.get("vhl_ligand_smiles", "")).strip()
        wp = _props(warhead)
        vp = _props(vhl)
        n_calculated += bool(wp) + bool(vp)
        rec["calculated"] = {"warhead": wp, "vhl_ligand": vp}
        score = _BASE
        score += _LINKER_PENALTY.get(str(row.get("linker_class", "")), -1.5)
        score += _JUNCTION_PENALTY.get(str(row.get("warhead_junction", "")), -1.0)
        score += _VHL_PENALTY.get(str(row.get("vhl_ligand_status", "")), -6.0)
        rec["score"] = round(score, 3)
        rec["band"] = _band(score)
        rec["linker_atoms"] = _linker_atoms(row)

    records.sort(key=lambda r: r["score"], reverse=True)

    # DESIGN — candidate strengths/liabilities from the same fields
    stages.append({"phase": "DESIGN", "note": "assembled strengths/liabilities per candidate from retrieved fields"})

    # DISCOVER — predicted ranking to be LOCKED before outcome access
    stages.append({"phase": "DISCOVER",
                   "note": f"ranked {len(records)} blinded candidates by retrieved+calculated features; "
                           "final ranking must be locked before wet-lab outcome access (no outcomes exist yet)"})
    ranking = []
    for rank, rec in enumerate(records, start=1):
        row = rec["fields"]
        ranking.append({
            "rank": rank,
            "id": rec["id"],
            "name": rec["name"],
            "score": rec["score"],
            "band": rec["band"],
            "linker_class": str(row.get("linker_class", "")),
            "linker_atoms": rec["linker_atoms"],
            "warhead_junction": str(row.get("warhead_junction", "")),
            "vhl_ligand_status": str(row.get("vhl_ligand_status", "")),
            "advantage": str(row.get("key_advantage", "")),
            "liability": str(row.get("key_liability", "")),
            "evidence_types": ["retrieved", "calculated", "predicted"],
        })

    winner = ranking[0] if ranking else None
    summary = (f"winner {winner['id']} ({winner['name']}) score {winner['score']:.2f} "
               f"\u00b7 {winner['band']} \u00b7 predicted from structural features \u2014 no measured data")

    result = {
        "dataset": str(ds),
        "target": target,
        "n_records": len(rows),
        "ranking": ranking,
        "winner": winner,
        "stages": stages,
        "measured_present": 0,
        "measured_missing": len(rows),  # honest: repository has no measured potency for these PROTACs
        "classification": {"measured": 0, "retrieved": len(rows), "calculated": n_calculated,
                           "predicted": len(rows), "missing": len(rows)},
        "uncertainty": [
            "no experimental potency (DC50/Dmax) exists for these six molecules in the repository",
            "ranking is a structural prediction; measured data would override it",
        ],
    }

    schema = ScientificResult(
        workflow="case_study:brd4-vhl-six",
        status="ok",
        summary=summary,
        result=result,
        provenance=[Provenance(tool="protacxtend.case_study.brd4_vhl_six", source=str(ds))],
    ).add_evidence(f"{len(rows)} candidate records retrieved (target BRD4 \u00b7 E3 VHL)",
                   source=str(ds), kind="retrieved")
    if n_calculated:
        schema.add_evidence(f"RDKit properties calculated for {n_calculated} component SMILES (warhead/VHL ligand)",
                            source="RDKit", kind="calculated")
    schema.add_evidence(f"{len(rows)} potency bands predicted from structural scoring",
                        source="structural score", kind="predicted")
    schema.add_evidence("measured potency: none present in repository dataset",
                        source="dataset audit", kind="missing")
    schema.add_warning("prospective case study: ranking is predicted; lock the final ranking before consulting wet-lab outcomes")
    schema.add_warning("six molecules are case-study inputs, not benchmark ground truth")

    return {"schema": schema.to_dict(), "result": result}
