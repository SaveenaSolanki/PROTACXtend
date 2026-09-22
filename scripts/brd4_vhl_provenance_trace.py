#!/usr/bin/env python3
"""BRD4–VHL prospective case study — full provenance trace (P0-B).

Runs the blinded six-PROTAC case study and proves that every molecule, score,
structure and evidence object traces to either

  * a real input field in the bundled blinded CSV (origin=RETRIEVED), or
  * an explicit, documented computational generation step (origin=COMPUTED /
    PREDICTED), or
  * is honestly absent (origin=MISSING).

It also fails loudly if any fixture/synthetic scientific input (``CCO``,
``synthetic``, ``demo``, ``placeholder``, toy proteins) leaks into the run.

Outputs:
    outputs/reports/brd4_vhl_provenance_trace.json
    outputs/reports/brd4_vhl_provenance_trace.md
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from protacxtend.case_study.brd4_vhl_six import (  # noqa: E402
    _BASE,
    _JUNCTION_PENALTY,
    _LINKER_PENALTY,
    _VHL_PENALTY,
    resolve_dataset,
    run_brd4_vhl_six_case_study,
)

REPORT_DIR = ROOT / "outputs" / "reports"

# A fixture/synthetic scientific input is any of these appearing as a *value*
# (not as part of a molecule identifier such as "mol1").
_FIXTURE_TOKENS = ("synthetic", "placeholder", "demo_warhead", "stepwise_module_smoke",
                   "toy_protein", "mock_")
_PLACEHOLDER_SMILES = {"CCO", "CC", "C", "O", "CO", "CCOCCO"}


def _scan_fixtures(obj, path="") -> list[dict]:
    """Recursively find fixture/synthetic scientific inputs in a value tree."""
    hits: list[dict] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            hits += _scan_fixtures(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            hits += _scan_fixtures(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        low = obj.lower()
        for tok in _FIXTURE_TOKENS:
            if tok in low:
                hits.append({"path": path, "value": obj, "token": tok})
        # exact placeholder smiles
        if obj in _PLACEHOLDER_SMILES:
            hits.append({"path": path, "value": obj, "token": "placeholder_smiles"})
    return hits


def build_trace() -> dict:
    ds = resolve_dataset()
    rows = {r["id"]: r for r in csv.DictReader(open(ds, encoding="utf-8"))}
    wrapped = run_brd4_vhl_six_case_study()
    result = wrapped["result"]

    trace = []
    arithmetic_ok = True
    for entry in result["ranking"]:
        src = rows[entry["id"]]
        linker_pen = _LINKER_PENALTY.get(src["linker_class"], -1.5)
        junction_pen = _JUNCTION_PENALTY.get(src["warhead_junction"], -1.0)
        vhl_pen = _VHL_PENALTY.get(src["vhl_ligand_status"], -6.0)
        recomputed = round(_BASE + linker_pen + junction_pen + vhl_pen, 3)
        match = (abs(recomputed - entry["score"]) < 1e-9)
        arithmetic_ok &= match
        trace.append({
            "id": entry["id"],
            "rank": entry["rank"],
            "score_reported": entry["score"],
            "score_recomputed": recomputed,
            "arithmetic_match": match,
            "score_terms": [
                {"term": "base", "value": _BASE, "origin": "COMPUTED",
                 "source": "case_study.brd4_vhl_six._BASE"},
                {"term": "linker_penalty", "value": linker_pen, "origin": "COMPUTED",
                 "source": f"_LINKER_PENALTY[{src['linker_class']!r}]",
                 "input_field": "linker_class", "input_origin": "RETRIEVED"},
                {"term": "junction_penalty", "value": junction_pen, "origin": "COMPUTED",
                 "source": f"_JUNCTION_PENALTY[{src['warhead_junction']!r}]",
                 "input_field": "warhead_junction", "input_origin": "RETRIEVED"},
                {"term": "vhl_penalty", "value": vhl_pen, "origin": "COMPUTED",
                 "source": f"_VHL_PENALTY[{src['vhl_ligand_status']!r}]",
                 "input_field": "vhl_ligand_status", "input_origin": "RETRIEVED"},
            ],
            "molecules": {
                "warhead_smiles": {"value": src["warhead_smiles"], "origin": "RETRIEVED",
                                   "source": f"{ds.name}:warhead_smiles"},
                "vhl_ligand_smiles": {"value": src["vhl_ligand_smiles"], "origin": "RETRIEVED",
                                      "source": f"{ds.name}:vhl_ligand_smiles"},
            },
            "evidence": {
                "measured": {"present": False, "origin": "MISSING"},
                "retrieved": ["linker_class", "linker_atoms", "warhead_junction",
                              "vhl_ligand_status", "key_advantage", "key_liability"],
                "calculated": ["warhead_props (RDKit)", "vhl_ligand_props (RDKit)"],
                "predicted": ["score", "band"],
            },
        })

    fixture_hits = _scan_fixtures(result)
    return {
        "case_study": "BRD4–VHL six-PROTAC (prospective, blinded)",
        "dataset": str(ds),
        "dataset_sha256_source": "bundled package data: protacxtend/data/case_study/brd4_vhl_6.csv",
        "execution_mode_recommendation": "SCIENTIFIC",
        "n_records": result["n_records"],
        "classification": result["classification"],
        "measured_present": result["measured_present"],
        "measured_missing": result["measured_missing"],
        "all_scores_arithmetically_traceable": arithmetic_ok,
        "fixture_or_synthetic_inputs_found": fixture_hits,
        "trace": trace,
        "schema_provenance": wrapped.get("provenance"),
        "schema_evidence": wrapped.get("evidence"),
        "errors": wrapped.get("errors"),
        "warnings": wrapped.get("warnings"),
    }


def _md(trace: dict) -> str:
    lines = [
        "# BRD4–VHL provenance trace",
        "",
        f"- dataset: `{trace['dataset']}`",
        f"- records: {trace['n_records']}",
        f"- evidence classification: {trace['classification']}",
        f"- measured present: {trace['measured_present']} "
        f"(missing: {trace['measured_missing']})",
        f"- all scores arithmetically traceable: "
        f"**{trace['all_scores_arithmetically_traceable']}**",
        f"- fixture/synthetic scientific inputs found: "
        f"**{len(trace['fixture_or_synthetic_inputs_found'])}**",
        "",
        "| rank | id | score | recomputed | match | warhead origin | VHL origin | measured |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for t in trace["trace"]:
        lines.append(
            f"| {t['rank']} | {t['id']} | {t['score_reported']} | {t['score_recomputed']} | "
            f"{t['arithmetic_match']} | {t['molecules']['warhead_smiles']['origin']} | "
            f"{t['molecules']['vhl_ligand_smiles']['origin']} | MISSING |")
    lines += [
        "",
        "Each score = `base(8.0, COMPUTED) + linker_penalty + junction_penalty + "
        "vhl_penalty`, where every penalty is looked up from a `RETRIEVED` CSV "
        "field (`linker_class`, `warhead_junction`, `vhl_ligand_status`). "
        "Molecules come from the CSV (`RETRIEVED`); RDKit descriptors are "
        "`COMPUTED`; the score/band is `PREDICTED`. No measured potency exists, "
        "so `measured` is `MISSING` by design.",
    ]
    if trace["fixture_or_synthetic_inputs_found"]:
        lines += ["", "## FIXTURE LEAKS", "", "```json",
                  json.dumps(trace["fixture_or_synthetic_inputs_found"], indent=2), "```"]
    return "\n".join(lines)


def main() -> int:
    trace = build_trace()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "brd4_vhl_provenance_trace.json").write_text(
        json.dumps(trace, indent=2), encoding="utf-8")
    (REPORT_DIR / "brd4_vhl_provenance_trace.md").write_text(_md(trace), encoding="utf-8")
    print(_md(trace))
    ok = trace["all_scores_arithmetically_traceable"] and not trace["fixture_or_synthetic_inputs_found"]
    print(f"\nTRACE {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
