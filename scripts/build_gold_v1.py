#!/usr/bin/env python
"""Build the 48-case gold schema and adjudication workflow.

Produces:
  * ``gold_answers_v1.jsonl``          — one schema record per case
  * ``gold_adjudication_template.csv`` — the two-reviewer + adjudicator template

**No scientific gold answer is invented here.** The frozen pre-existing ground
truth (``benchmark/ground_truth/<case>.json``) is carried as a *proposal* only;
``acceptable_answer`` is left blank and every record is marked
``AWAITING_EXPERT_REVIEW``. Mechanical fields (required entities, expected
route, expected stop state, minimum evidence) are derived from the case inputs
and the router, not from scientific judgement.

Run::

    python scripts/build_gold_v1.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = ROOT / "benchmark" / "cases"
GT = ROOT / "benchmark" / "ground_truth"
OUT_JSONL = ROOT / "gold_answers_v1.jsonl"
OUT_CSV = ROOT / "gold_adjudication_template.csv"

COLUMNS = [
    "case_id", "capability", "split", "required_entities", "gold_answer_type",
    "acceptable_answer", "proposed_answer_from_frozen_gt", "mandatory_facts",
    "prohibited_claims", "expected_route", "expected_stop_state",
    "minimum_evidence", "acceptable_alternatives", "reviewer_1_decision",
    "reviewer_2_decision", "adjudicator_decision", "consensus_notes", "status",
]

#: Claims that must never be made from this benchmark's evidence.
_COMMON_PROHIBITED = [
    "claiming measured DC50/Dmax from a model prediction",
    "claiming biological activity from chemical validity alone",
    "claiming a new candidate when only a source-backed reference was reassembled",
    "claiming entity correctness is answer correctness",
    "claiming execution success is scientific validation",
]

_PROHIBITED_BY_TYPE = {
    "design_rubric": ["claiming a designed molecule is synthesised or active",
                      "presenting a design brief with hypothetical attachments as a final PROTAC"],
    "mechanistic_rubric": ["asserting a computed mechanism from a qualitative rubric",
                           "reporting a cooperativity alpha as measured"],
    "ranked": ["using outcome data not present in the supplied table",
               "ranking rows that were never supplied"],
    "exact": ["inventing an accession/identifier not returned by a permitted source"],
}


def _load_jsonl_types() -> dict[str, str]:
    out = {}
    for path in GT.glob("*.json"):
        try:
            out[path.stem] = json.loads(path.read_text(encoding="utf-8")).get("type", "")
        except Exception:  # noqa: BLE001
            out[path.stem] = ""
    return out


def _gt(case_id: str) -> dict[str, Any]:
    path = GT / f"{case_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _required_entities(case: dict[str, Any]) -> list[str]:
    from protacxtend.agents.entity_resolution import resolve_entities

    entities = resolve_entities(case)
    required: list[str] = []
    if entities.get("target"):
        required.append(f"target:{entities['target']}")
    for e3 in entities.get("e3_ligases") or []:
        required.append(f"e3:{e3}")
    # Component roles supplied by the case (not scientific answers).
    for raw in case.get("supplied_inputs") or []:
        text = str(raw)
        if ":" not in text:
            continue
        key = text.split(":", 1)[0].strip().lower()
        if "warhead" in key:
            required.append("component:warhead")
        elif "e3 ligand" in key or "e3-ligand" in key:
            required.append("component:e3_ligand")
    return sorted(set(required)) or ["none_declared"]


def _minimum_evidence(case: dict[str, Any], capability: str) -> dict[str, Any]:
    requirements: dict[str, Any] = {"min_evidence_items": 1, "required_sources": []}
    if capability in {"KNOW", "REASON"}:
        requirements["required_sources"].append("permitted public database or literature")
    if capability == "DESIGN":
        requirements = {
            "min_evidence_items": 1,
            "required_sources": ["source-backed atom-mapped component or declared missing input"],
            "requires_chemical_validity": True,
        }
    if capability == "DISCOVER":
        requirements["required_sources"].append("supplied candidate/table input")
    return requirements


def _expected_stop_state(case: dict[str, Any], capability: str) -> str:
    """Conservative expected state; the adjudicator may override."""
    if capability == "KNOW":
        return "supported_answer OR conditional_hypothesis OR justified_no_go"
    if capability == "REASON":
        return "conditional_hypothesis OR justified_no_go"
    if capability == "DESIGN":
        return "valid_candidate (source-backed) OR design_brief OR justified_no_go"
    return "conditional_hypothesis OR justified_no_go"


def _prohibited(case: dict[str, Any], gt_type: str, capability: str) -> list[str]:
    claims = list(_COMMON_PROHIBITED)
    claims.extend(_PROHIBITED_BY_TYPE.get(gt_type, []))
    if capability == "DESIGN":
        claims.append("claiming selectivity, degradation or safety without measurement")
    if capability == "DISCOVER":
        claims.append("claiming experimental outcomes from a plan")
    return sorted(set(claims))


def main() -> int:
    from protacxtend.agents.routing import route_for

    splits = json.loads((ROOT / "benchmark/gateC/splits.json").read_text())["assignment"]
    types = _load_jsonl_types()
    records: list[dict[str, Any]] = []
    for case_path in sorted(CASES.glob("*.json")):
        if case_path.stem.startswith("_"):
            continue
        case = json.loads(case_path.read_text(encoding="utf-8"))
        case_id = case.get("task_id", case_path.stem)
        capability = (case.get("capability") or "").upper()
        gt = _gt(case_id)
        gt_type = types.get(case_id, "")
        route, routing = route_for(case, capability)
        record = {
            "case_id": case_id,
            "capability": capability,
            "split": splits.get(case_id, ""),
            "required_entities": _required_entities(case),
            "gold_answer_type": gt_type,
            # Deliberately blank: scientific gold must come from an expert.
            "acceptable_answer": "",
            "proposed_answer_from_frozen_gt": gt.get("expected_answer", ""),
            "mandatory_facts": gt.get("mandatory_answer_elements", []),
            "prohibited_claims": _prohibited(case, gt_type, capability),
            "expected_route": route,
            "expected_route_rationale": routing.get("rationale", ""),
            "expected_stop_state": _expected_stop_state(case, capability),
            "minimum_evidence": _minimum_evidence(case, capability),
            "acceptable_alternatives": gt.get("acceptable_alternatives", []),
            "expert_labels": {
                "reviewer_1": {"decision": "", "notes": "", "reviewed_at": ""},
                "reviewer_2": {"decision": "", "notes": "", "reviewed_at": ""},
                "adjudicator": {"decision": "", "notes": "", "decided_at": ""},
            },
            "consensus_notes": "AWAITING_EXPERT_REVIEW",
            "status": "AWAITING_EXPERT_REVIEW",
            "provenance": {
                "frozen_ground_truth": f"benchmark/ground_truth/{case_id}.json",
                "case_file": f"benchmark/cases/{case_id}.json",
                "schema": "gold_answers.v1",
                "note": "Mechanical fields derived from inputs/router; scientific answer requires expert adjudication.",
            },
        }
        records.append(record)

    OUT_JSONL.write_text("\n".join(json.dumps(r, default=str) for r in records) + "\n", encoding="utf-8")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "case_id": r["case_id"],
                "capability": r["capability"],
                "split": r["split"],
                "required_entities": ";".join(r["required_entities"]),
                "gold_answer_type": r["gold_answer_type"],
                "acceptable_answer": "",  # expert only
                "proposed_answer_from_frozen_gt": r["proposed_answer_from_frozen_gt"],
                "mandatory_facts": ";".join(r["mandatory_facts"]),
                "prohibited_claims": " | ".join(r["prohibited_claims"]),
                "expected_route": ">".join(r["expected_route"]),
                "expected_stop_state": r["expected_stop_state"],
                "minimum_evidence": json.dumps(r["minimum_evidence"]),
                "acceptable_alternatives": ";".join(r["acceptable_alternatives"]),
                "reviewer_1_decision": "",
                "reviewer_2_decision": "",
                "adjudicator_decision": "",
                "consensus_notes": r["consensus_notes"],
                "status": r["status"],
            })
    print(f"wrote {OUT_JSONL} ({len(records)} records)")
    print(f"wrote {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
