#!/usr/bin/env python
"""Ingest the two 500-task workbooks into a canonical, validated benchmark.

Sources (under todo/):
  * Blinded_Temporal_Challenge_500_Tasks.xlsx   -> suite "temporal"  (BTC-001..500)
  * PROTACxtend_500_Task_Benchmark (1).xlsx     -> suite "general"   (TD-001..500)

Outputs (under benchmark500/):
  cases/temporal_500.jsonl, cases/general_500.jsonl
  manifests/<suite>.manifest.json                (sha256 + counts + distributions)
  splits/<suite>.splits.json                     (target-grouped dev/val/blind/stress)
  INTEGRITY_REPORT.md, data_dictionary.md, pre_registration.md

Read-only with respect to the source workbooks. Nothing is fabricated: every
gold / expected-answer field is emitted as null with an explicit gold_status.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
TODO = ROOT / "todo"
OUT = ROOT / "benchmark500"

DEFAULT_TEMPORAL = TODO / "Blinded_Temporal_Challenge_500_Tasks.xlsx"
DEFAULT_GENERAL = None  # resolved by glob (filename case varies)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_general() -> Path:
    matches = sorted(TODO.glob("*500_Task_Benchmark*.xlsx"))
    if not matches:
        raise FileNotFoundError("PROTACXtend 500-task workbook not found under todo/")
    return matches[0]


def _read_sheet(path: Path, sheet: str) -> tuple[list[str], list[dict]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=True))
    header_idx = next(i for i, r in enumerate(rows) if any(c not in (None, "") for c in r))
    header = [("" if c is None else str(c).strip()) for c in rows[header_idx]]
    out = []
    for r in rows[header_idx + 1:]:
        if not any(c not in (None, "") for c in r):
            continue
        record = {}
        for j, key in enumerate(header):
            if not key:
                continue
            val = r[j] if j < len(r) else None
            record[key] = "" if val is None else (val if not isinstance(val, str) else val.strip())
        out.append(record)
    return header, out


def _int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return default


def _normalize_temporal(row: dict) -> dict:
    cutoff = str(row.get("Evidence_Cutoff_Date") or "")
    return {
        "case_id": row.get("Challenge_ID", ""),
        "suite": "temporal",
        "domain": row.get("Benchmark_Domain", ""),
        "domain_task_no": _int(row.get("Domain_Task_No")),
        "difficulty_level": _int(row.get("Difficulty_L1_L7")),
        "difficulty_name": row.get("Difficulty_Name", ""),
        "task_type": row.get("Difficulty_Name", ""),
        "target": row.get("Target", ""),
        "indication": row.get("Therapeutic_Area_Context", ""),
        "e3": row.get("E3_Ligase_Context", ""),
        "question": row.get("Blinded_Question", ""),
        "required_output": row.get("Required_Output", ""),
        "permitted_tools": row.get("Permitted_Tools", ""),
        "expected_source_types": row.get("Expected_Source_Types", ""),
        "evidence_cutoff_date": cutoff,
        "future_horizon_months": _int(row.get("Future_Horizon_Months")),
        "ground_truth_window_end": row.get("Ground_Truth_Window_End", ""),
        "allowed_evidence_window": row.get("Allowed_Evidence_Window", ""),
        "leakage_exclusions": row.get("Leakage_Exclusions", ""),
        "primary_adjudication_endpoint": row.get("Primary_Adjudication_Endpoint", ""),
        "gold_status": row.get("Ground_Truth_Status", "") or "TO CURATE",
        "gold_answer": None,
        "accepted_alternatives": None,
        "evidence_package": None,
        "leakage_group": row.get("Target", ""),
        "source_row": None,
    }


def _normalize_general(row: dict) -> dict:
    return {
        "case_id": row.get("Task_ID", ""),
        "suite": "general",
        "domain": row.get("Benchmark_Domain", ""),
        "domain_task_no": _int(row.get("Domain_Task_No")),
        "difficulty_level": _int(row.get("Difficulty_L1_L7")),
        "difficulty_name": row.get("Difficulty_Name", ""),
        "task_type": row.get("Task_Type", ""),
        "target": row.get("Target", ""),
        "indication": row.get("Therapeutic_Area_Context", ""),
        "e3": row.get("E3_Ligase_Context", ""),
        "question": row.get("Question", ""),
        "required_output": row.get("Available_Evidence_Required", ""),
        "permitted_tools": row.get("Permitted_Tools", ""),
        "expected_source_types": row.get("Expected_Tools", ""),
        "evidence_cutoff_date": "",
        "future_horizon_months": 0,
        "ground_truth_window_end": "",
        "allowed_evidence_window": "",
        "leakage_exclusions": "",
        "primary_adjudication_endpoint": row.get("Curation_Status", "") or "Not curated",
        "gold_status": row.get("Curation_Status", "") or "Not curated",
        "gold_answer": None,
        "accepted_alternatives": None,
        "evidence_package": None,
        "leakage_group": row.get("Target", ""),
        "source_row": None,
    }


# ── validation ────────────────────────────────────────────────────────
def _validate(cases: list[dict], label: str) -> dict:
    ids = [c["case_id"] for c in cases]
    dups = [k for k, v in collections.Counter(ids).items() if v > 1]
    required = ["case_id", "domain", "difficulty_level", "target", "indication", "e3", "question"]
    missing = {f: sum(1 for c in cases if not c.get(f)) for f in required}
    domains = collections.Counter(c["domain"] for c in cases)
    diffs = collections.Counter(c["difficulty_level"] for c in cases)
    targets = collections.Counter(c["target"] for c in cases)
    e3s = collections.Counter(c["e3"] for c in cases)
    cutoffs = collections.Counter(c["evidence_cutoff_date"] for c in cases)
    # domain/task-number integrity
    dom_no_dupes = {}
    for c in cases:
        key = (c["domain"], c["domain_task_no"])
        dom_no_dupes[key] = dom_no_dupes.get(key, 0) + 1
    bad_no = [k for k, v in dom_no_dupes.items() if v > 1]
    placeholders = sum(
        1 for c in cases
        if str(c.get("gold_status", "")).upper().startswith(("TO CURATE", "NOT CURATED"))
    )
    # question length sanity
    qlens = [len(c["question"]) for c in cases]
    blank_q = sum(1 for L in qlens if L < 20)
    non_ascii = sum(1 for c in cases if re.search(r"[^\x00-\x7F]", c["target"] + c["question"]))
    return {
        "label": label,
        "n_cases": len(cases),
        "unique_ids": len(set(ids)),
        "duplicate_ids": dups,
        "missing_required": {k: v for k, v in missing.items() if v},
        "domains": dict(domains),
        "difficulty": dict(sorted(diffs.items())),
        "n_targets": len(targets),
        "targets_least_common": targets.most_common()[-5:],
        "n_e3": len(e3s),
        "cutoffs": dict(cutoffs),
        "domain_task_no_collisions": bad_no[:5],
        "gold_uncured": placeholders,
        "blank_questions": blank_q,
        "question_len_min_max_mean": [min(qlens), max(qlens), round(sum(qlens) / len(qlens), 1)],
        "non_ascii_rows": non_ascii,
    }


# ── splits ────────────────────────────────────────────────────────────
def _assign_splits(cases: list[dict]) -> dict[str, str]:
    """Target-grouped deterministic splits: stress = L7, else ~20/20/60 by target."""
    import random

    assignment: dict[str, str] = {}
    stress = [c for c in cases if c["difficulty_level"] >= 7]
    for c in stress:
        assignment[c["case_id"]] = "stress"
    rest = [c for c in cases if c["difficulty_level"] < 7]
    targets = sorted({c["leakage_group"] for c in rest})
    rng = random.Random(1234)
    rng.shuffle(targets)
    n = len(targets)
    n_dev = max(1, round(n * 0.20))
    n_val = max(1, round(n * 0.20))
    tgt_split = {}
    for i, t in enumerate(targets):
        if i < n_dev:
            tgt_split[t] = "development"
        elif i < n_dev + n_val:
            tgt_split[t] = "validation"
        else:
            tgt_split[t] = "blind"
    for c in rest:
        assignment[c["case_id"]] = tgt_split[c["leakage_group"]]
    return assignment


def _write_jsonl(path: Path, cases: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
    return _sha256(path)


_DATA_DICTIONARY = '''# benchmark500 — data dictionary

Canonical case records are JSONL under `benchmark500/cases/`. One record per
benchmark task. `gold_*` / `evidence_package` / `accepted_alternatives` are
`null` until adjudicated; `gold_status` records the curation state.

| field | type | meaning | source column |
|---|---|---|---|
| case_id | str | BTC-### (temporal) / TD-### (general) | Challenge_ID / Task_ID |
| suite | str | `temporal` or `general` | workbook |
| domain | str | one of 16 benchmark domains | Benchmark_Domain |
| domain_task_no | int | task index within domain | Domain_Task_No |
| difficulty_level | int | L1–L7 | Difficulty_L1_L7 |
| difficulty_name | str | Retrieval…Adversarial/OOD | Difficulty_Name |
| task_type | str | normalized task type | Difficulty_Name / Task_Type |
| target | str | gene/protein target | Target |
| indication | str | therapeutic area context | Therapeutic_Area_Context |
| e3 | str | E3 ligase context | E3_Ligase_Context |
| question | str | the blinded / general question | Blinded_Question / Question |
| required_output | str | required output artifact | Required_Output / Available_Evidence_Required |
| permitted_tools | str | tool policy | Permitted_Tools |
| expected_source_types | str | expected evidence sources | Expected_Source_Types / Expected_Tools |
| evidence_cutoff_date | str | information cutoff (temporal) | Evidence_Cutoff_Date |
| future_horizon_months | int | 6/12/18/24 (temporal) | Future_Horizon_Months |
| ground_truth_window_end | str | adjudication window end (temporal) | Ground_Truth_Window_End |
| allowed_evidence_window | str | evidence admissibility (temporal) | Allowed_Evidence_Window |
| leakage_exclusions | str | anti-leakage rule (temporal) | Leakage_Exclusions |
| primary_adjudication_endpoint | str | what adjudicators decide | Primary_Adjudication_Endpoint |
| gold_status | str | curation state (all `TO CURATE`) | Ground_Truth_Status / Curation_Status |
| gold_answer | null | adjudicated answer (PENDING) | Ground_Truth_Summary / Expected_Conclusion |
| accepted_alternatives | null | admissible equivalents (PENDING) | — / Accepted_Alternatives |
| evidence_package | null | frozen evidence (PENDING) | Evidence_Package |
| leakage_group | str | grouping key (target) for splits | Target |
| split | str | development/validation/blind/stress | assigned |

## Scoring dimensions (source rubric, 0–5)

Scientific correctness · Temporal compliance · Evidence grounding · Tool execution ·
Mechanistic correctness · Quantitative correctness · Uncertainty calibration ·
Reproducibility · Final decision quality · Future-outcome match.

In this package only **Tool execution**, **Reproducibility** and
**Evidence availability** are scored automatically. The rest require
adjudication (`pending_adjudication`).
'''

_PRE_REGISTRATION = '''# benchmark500 — pre-registration

Frozen before any blind scoring. Source: `PROTACXtend_05_...` §3 Gate C and
`PROTACXtend_01_EXPERIMENTS.md` E2/E7.

## Primary endpoint

**Task-valid, evidence-supported success per eligible case**, scored blind
against independently adjudicated gold, with correct abstention on
unanswerable / insufficient-input cases counted as success where the case is
not answerable.

## Secondary endpoints

Citation support · hallucinated continuation · tool-selection precision ·
output validity · recovery after fault · appropriate abstention · latency · cost.

## Denominators and exclusions

* Denominator = all eligible tasks (published), excluding only formally
  inadmissible cases with a stated reason.
* Gold-uncurated tasks are **not** scored for correctness and are reported
  separately as `pending_adjudication`.
* No result replaces an executed run with offline scorer output.

## Splits (target-grouped; a target never spans splits)

* Development (~20%) — engineering / rubric calibration
* Validation (~20%) — threshold setting only
* Blind test (~50–60%) — primary reported result
* Stress/OOD — all L7 tasks (conflicts, missing tools, invalid inputs)

Exact assignment: `benchmark500/splits/<suite>.splits.json`.

## Temporal suite

Per-task cutoff and 6–24-month horizon. Analysis only valid with a frozen
as-of corpus; without it, temporal compliance is reported as *unverifiable*.

## Statistics (to run once gold exists)

Cluster bootstrap CIs grouped by target/publication; paired differences vs
baselines (general LLM, retrieval-only, tool-only, fixed pipeline) at equal
budget; pre-defined multiplicity policy.

## Status

Gold curation: **0 / 1000**. This file must be frozen (hash recorded) before any
blind scoring round begins.
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--temporal", default=str(DEFAULT_TEMPORAL))
    ap.add_argument("--general", default="")
    args = ap.parse_args()

    temporal_path = Path(args.temporal)
    general_path = Path(args.general) if args.general else _find_general()

    h_t, rows_t = _read_sheet(temporal_path, "Question_Bank_500")
    h_g, rows_g = _read_sheet(general_path, "Tasks_500")
    temporal = [_normalize_temporal(r) for r in rows_t]
    general = [_normalize_general(r) for r in rows_g]

    reports = {}
    for cases, label in ((temporal, "temporal_500"), (general, "general_500")):
        rep = _validate(cases, label)
        splits = _assign_splits(cases)
        for c in cases:
            c["split"] = splits[c["case_id"]]
        rep["splits"] = dict(collections.Counter(splits.values()))
        reports[label] = rep

    # write cases + manifests
    manifest = {}
    for cases, label, src in ((temporal, "temporal_500", temporal_path), (general, "general_500", general_path)):
        path = OUT / "cases" / f"{label}.jsonl"
        h = _write_jsonl(path, cases)
        manifest[label] = {
            "suite": label,
            "source_workbook": str(src.relative_to(ROOT)),
            "source_sha256": _sha256(src),
            "source_sheet": "Question_Bank_500" if label.startswith("temporal") else "Tasks_500",
            "n_cases": len(cases),
            "cases_jsonl": str(path.relative_to(ROOT)),
            "cases_sha256": h,
            "gold_status": "uncurated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "benchmark500.case.v1",
        }
        (OUT / "manifests").mkdir(parents=True, exist_ok=True)
        (OUT / "manifests" / f"{label}.manifest.json").write_text(
            json.dumps({**manifest[label], "validation": reports[label]}, indent=2), encoding="utf-8")
        # splits
        (OUT / "splits").mkdir(parents=True, exist_ok=True)
        (OUT / "splits" / f"{label}.splits.json").write_text(
            json.dumps({c["case_id"]: c["split"] for c in cases}, indent=2), encoding="utf-8")

    # data dictionary + pre-registration
    (OUT / "data_dictionary.md").write_text(_DATA_DICTIONARY, encoding="utf-8")
    (OUT / "pre_registration.md").write_text(_PRE_REGISTRATION, encoding="utf-8")

    # integrity report
    md = ["# benchmark500 — integrity report", "",
          f"Generated {datetime.now(timezone.utc).isoformat()} · read-only over the source workbooks.", ""]
    for label, rep in reports.items():
        md += [f"## {label}", "",
               f"- cases: **{rep['n_cases']}**, unique IDs: **{rep['unique_ids']}**, duplicates: {rep['duplicate_ids'] or 'none'}",
               f"- missing required fields: {rep['missing_required'] or 'none'}",
               f"- domains: {len(rep['domains'])}; per-domain: " + ", ".join(f"{k}={v}" for k, v in rep["domains"].items()),
               f"- difficulty L1–L7: {rep['difficulty']}",
               f"- targets: {rep['n_targets']}; E3 contexts: {rep['n_e3']}",
               f"- cutoffs: {rep['cutoffs']}",
               f"- domain-task-no collisions: {rep['domain_task_no_collisions'] or 'none'}",
               f"- gold uncurated rows: **{rep['gold_uncured']}/{rep['n_cases']}**",
               f"- blank questions: {rep['blank_questions']}; question length min/max/mean: {rep['question_len_min_max_mean']}",
               f"- rows with non-ASCII target/question: {rep['non_ascii_rows']}",
               f"- splits: {rep['splits']}", ""]
    # cross-suite
    md += ["## Reconciliation (temporal vs general)", ""]
    dom_t = set(reports["temporal_500"]["domains"]); dom_g = set(reports["general_500"]["domains"])
    md.append(f"- identical 16-domain taxonomy: **{dom_t == dom_g}** (symmetric diff: {dom_t ^ dom_g or 'none'})")
    md.append(f"- temporal targets {reports['temporal_500']['n_targets']} vs general {reports['general_500']['n_targets']}")
    md.append("- both suites are uncurated question banks: no expected answer, evidence package, or score exists in either workbook.")
    md.append("")
    (OUT / "INTEGRITY_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({k: {"n": v["n_cases"], "gold_uncured": v["gold_uncured"],
                          "splits": v["splits"]} for k, v in reports.items()}, indent=2))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
