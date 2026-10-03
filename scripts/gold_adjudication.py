#!/usr/bin/env python
"""Gold-adjudication driver for the 48-case governed PROTACXtend benchmark.

This tool is the *operational* half of Gate C. It never invents scientific gold;
it prepares blinded reviewer workbooks, validates them, merges two independent
reviewers plus an adjudicator into ``reviewed_gold/consensus.json``, and reports
inter-rater agreement. Scoring stays impossible until ``approved`` is True.

Subcommands
-----------
  status                 report current adjudication state (writes JSON + MD)
  init                   write blinded reviewer_1/reviewer_2 workbooks + adjudicator file
  validate FILE          check one reviewer workbook for completeness/rule violations
  kappa FILE_A FILE_B    Cohen's kappa on the reviewer verdict columns
  merge                  merge reviewer workbooks (+ adjudicator) into consensus.json
  chemist-packet         build the chemist exit-vector review packet (delegates)

Workflow
--------
  1. ``python scripts/gold_adjudication.py init``
  2. reviewer 1 fills ``reviewed_gold/reviewer_1.csv`` (blind to the other reviewer)
  3. reviewer 2 fills ``reviewed_gold/reviewer_2.csv``
  4. disagreements -> ``reviewed_gold/adjudicator.csv``
  5. ``python scripts/gold_adjudication.py merge``

The reviewer workbooks deliberately omit ``proposed_answer_from_frozen_gt`` so
that the two primary reviews are independent. The adjudicator file *does* carry
the frozen proposal, because the adjudicator's job is to arbitrate against it.

Run from the repository root.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
GOLD_JSONL = ROOT / "gold_answers_v1.jsonl"
CASES_DIR = ROOT / "benchmark" / "cases"
GATEC = ROOT / "benchmark" / "gateC"
REVIEWED = GATEC / "reviewed_gold"
GOLD_REVIEW_TSV = GATEC / "gold_review.tsv"
REVIEWER_DECISIONS_TSV = GATEC / "REVIEWER_DECISIONS.tsv"
CONSENSUS = REVIEWED / "consensus.json"
STATUS_JSON = REVIEWED / "ADJUDICATION_STATUS.json"
STATUS_MD = REVIEWED / "ADJUDICATION_STATUS.md"

VERDICTS = ("approve", "revise", "unanswerable", "unscorable")
ANSWERABILITY = ("answerable", "unanswerable", "insufficient")

REVIEWER_COLUMNS = [
    "case_id", "capability", "split", "gold_answer_type", "question",
    "required_entities", "acceptable_answer", "mandatory_answer_elements",
    "acceptable_alternatives", "evidence_spans", "answerability", "verdict",
    "confidence", "reviewer_name", "notes",
]

ADJUDICATOR_COLUMNS = [
    "case_id", "question",
    "reviewer_1_acceptable_answer", "reviewer_2_acceptable_answer",
    "reviewer_1_answerability", "reviewer_2_answerability",
    "proposed_answer_from_frozen_gt", "adjudicator_decision",
    "adjudicator_answerability", "adjudicator_acceptable_answer",
    "adjudicator_mandatory_answer_elements", "adjudicator_acceptable_alternatives",
    "adjudicator_name", "adjudication_notes",
]


# ── helpers ───────────────────────────────────────────────────────────

def utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _from_json(value: str, default: Any) -> Any:
    if value is None or str(value).strip() == "":
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def load_gold() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with GOLD_JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_case_question(case_id: str) -> str:
    path = CASES_DIR / f"{case_id}.json"
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(data.get("scientific_question") or data.get("title") or "")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def write_csv(path: Path, columns: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


def cohens_kappa(a: list[str], b: list[str]) -> float:
    """Cohen's kappa for two raters over identical categorical items."""
    if not a or len(a) != len(b):
        return float("nan")
    labels = sorted(set(a) | set(b))
    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    expected = 0.0
    for label in labels:
        pa = sum(1 for x in a if x == label) / n
        pb = sum(1 for y in b if y == label) / n
        expected += pa * pb
    if expected >= 1.0:
        return 1.0 if observed >= 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


# ── status ────────────────────────────────────────────────────────────

def adjudication_state() -> dict[str, Any]:
    gold = load_gold()
    review_rows = read_csv_rows(GOLD_REVIEW_TSV) if GOLD_REVIEW_TSV.exists() else []
    decisions = read_csv_rows(REVIEWER_DECISIONS_TSV) if REVIEWER_DECISIONS_TSV.exists() else []
    pending_review = sum(1 for r in review_rows if str(r.get("adjudication_status", "")).startswith("PENDING"))
    pending_decisions = sum(1 for r in decisions if _norm(r.get("status")) in {"pending", ""})
    approved_cases = 0
    approved = False
    if CONSENSUS.exists():
        try:
            cons = json.loads(CONSENSUS.read_text(encoding="utf-8"))
            approved = bool(cons.get("approved"))
            approved_cases = sum(
                1 for v in (cons.get("gold") or {}).values()
                if str(v.get("answerability", "")).lower() in {"answerable", "unanswerable", "insufficient"}
                and (v.get("expected_answer") or str(v.get("answerability", "")).lower() != "answerable")
            )
        except (OSError, ValueError):
            pass
    return {
        "generated_at": utcnow(),
        "cases": len(gold),
        "gold_review_rows": len(review_rows),
        "gold_review_pending": pending_review,
        "reviewer_decisions": len(decisions),
        "reviewer_decisions_pending": pending_decisions,
        "consensus_exists": CONSENSUS.exists(),
        "consensus_approved": approved,
        "consensus_cases_resolved": approved_cases,
        "scoring_possible": approved and approved_cases == len(gold) and len(gold) > 0,
        "reviewer_1_workbook": (REVIEWED / "reviewer_1.csv").exists(),
        "reviewer_2_workbook": (REVIEWED / "reviewer_2.csv").exists(),
        "adjudicator_workbook": (REVIEWED / "adjudicator.csv").exists(),
    }


def cmd_status(_: argparse.Namespace) -> int:
    state = adjudication_state()
    REVIEWED.mkdir(parents=True, exist_ok=True)
    STATUS_JSON.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Gate C — adjudication status",
        "",
        f"_Generated {state['generated_at']}._",
        "",
        "| field | value |",
        "|---|---|",
    ]
    lines += [f"| {k} | `{v}` |" for k, v in state.items() if k != "generated_at"]
    lines += [
        "",
        "**Scoring is blocked until `scoring_possible` is `true`.**",
        "Correctness columns must stay `null`, never `0`, while gold is pending.",
        "",
    ]
    STATUS_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(state, indent=2))
    return 0


# ── init ──────────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> int:
    gold = load_gold()
    REVIEWED.mkdir(parents=True, exist_ok=True)
    r1, r2, adj = [], [], []
    for g in gold:
        cid = g["case_id"]
        question = load_case_question(cid)
        r1.append({
            "case_id": cid, "capability": g.get("capability", ""),
            "split": g.get("split", ""), "gold_answer_type": g.get("gold_answer_type", ""),
            "question": question, "required_entities": _as_json(g.get("required_entities", [])),
            "acceptable_answer": "", "mandatory_answer_elements": "",
            "acceptable_alternatives": "", "evidence_spans": "",
            "answerability": "", "verdict": "", "confidence": "",
            "reviewer_name": "", "notes": "",
        })
        r2.append(dict(r1[-1]))
        adj.append({
            "case_id": cid, "question": question,
            "reviewer_1_acceptable_answer": "", "reviewer_2_acceptable_answer": "",
            "reviewer_1_answerability": "", "reviewer_2_answerability": "",
            "proposed_answer_from_frozen_gt": g.get("proposed_answer_from_frozen_gt", ""),
            "adjudicator_decision": "", "adjudicator_answerability": "",
            "adjudicator_acceptable_answer": "",
            "adjudicator_mandatory_answer_elements": "",
            "adjudicator_acceptable_alternatives": "",
            "adjudicator_name": "", "adjudication_notes": "",
        })
    write_csv(REVIEWED / "reviewer_1.csv", REVIEWER_COLUMNS, r1)
    write_csv(REVIEWED / "reviewer_2.csv", REVIEWER_COLUMNS, r2)
    write_csv(REVIEWED / "adjudicator.csv", ADJUDICATOR_COLUMNS, adj)
    print(f"wrote {len(gold)} rows to reviewer_1.csv, reviewer_2.csv, adjudicator.csv in {REVIEWED}")
    print("Reviewer workbooks are blinded (no proposed_answer_from_frozen_gt).")
    return 0


# ── validate ──────────────────────────────────────────────────────────

def validate_workbook(path: Path) -> dict[str, Any]:
    rows = read_csv_rows(path)
    gold = {g["case_id"]: g for g in load_gold()}
    seen = [r.get("case_id", "") for r in rows]
    errors: list[str] = []
    names = {r.get("reviewer_name", "").strip() for r in rows if r.get("reviewer_name", "").strip()}
    if set(seen) != set(gold):
        missing = sorted(set(gold) - set(seen))
        extra = sorted(set(seen) - set(gold))
        if missing:
            errors.append(f"missing {len(missing)} cases: {missing[:5]}")
        if extra:
            errors.append(f"unknown {len(extra)} cases: {extra[:5]}")
    if len(names) > 1:
        errors.append(f"more than one reviewer_name in file: {sorted(names)}")
    for r in rows:
        cid = r.get("case_id", "?")
        verdict = _norm(r.get("verdict"))
        answerability = _norm(r.get("answerability"))
        if verdict not in VERDICTS:
            errors.append(f"{cid}: verdict {verdict!r} not in {VERDICTS}")
        if answerability not in ANSWERABILITY:
            errors.append(f"{cid}: answerability {answerability!r} not in {ANSWERABILITY}")
        if answerability == "answerable" and not str(r.get("acceptable_answer") or "").strip():
            errors.append(f"{cid}: answerability=answerable but acceptable_answer is empty")
        if verdict == "unanswerable" and answerability not in {"unanswerable", "insufficient"}:
            errors.append(f"{cid}: verdict=unanswerable but answerability={answerability!r}")
    return {"path": str(path), "n_rows": len(rows), "reviewer_names": sorted(names), "errors": errors}


def cmd_validate(args: argparse.Namespace) -> int:
    report = validate_workbook(Path(args.file))
    print(json.dumps(report, indent=2))
    return 1 if report["errors"] else 0


# ── kappa ─────────────────────────────────────────────────────────────

def cmd_kappa(args: argparse.Namespace) -> int:
    a = read_csv_rows(Path(args.file_a))
    b = read_csv_rows(Path(args.file_b))
    by_a = {r["case_id"]: _norm(r.get("verdict")) for r in a}
    by_b = {r["case_id"]: _norm(r.get("verdict")) for r in b}
    shared = sorted(set(by_a) & set(by_b))
    filled = [c for c in shared if by_a[c] and by_b[c]]
    va = [by_a[c] for c in filled]
    vb = [by_b[c] for c in filled]
    kappa = cohens_kappa(va, vb) if filled else float("nan")
    agree = sum(1 for x, y in zip(va, vb) if x == y)
    report = {
        "n_cases_present": len(shared),
        "n_filled_both": len(filled),
        "n_blank_in_one_or_both": len(shared) - len(filled),
        "agree": agree,
        "percent_agreement": round(agree / len(filled), 4) if filled else None,
        "cohens_kappa": None if kappa != kappa else round(kappa, 4),
        "disagreements": [c for c, x, y in zip(filled, va, vb) if x != y],
        "verdict_distribution_a": dict(Counter(va)),
        "verdict_distribution_b": dict(Counter(vb)),
    }
    print(json.dumps(report, indent=2))
    (REVIEWED / "kappa_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


# ── merge ─────────────────────────────────────────────────────────────

def _finalize_entry(gold_row: dict[str, Any], answer: str, answerability: str,
                    mandatory: Any, alternatives: Any, evidence: Any, notes: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": gold_row.get("gold_answer_type", ""),
        "expected_answer": answer or None,
        "expected_value": None,
        "expected_set": None,
        "expected_ranking": None,
        "mandatory_answer_elements": mandatory if isinstance(mandatory, list) else _from_json(mandatory, []),
        "acceptable_alternatives": alternatives if isinstance(alternatives, list) else _from_json(alternatives, []),
        "evidence_spans": evidence if isinstance(evidence, list) else _from_json(evidence, []),
        "answerability": answerability,
        "reviewer_decision_ref": next(
            (d.get("decision_id") for d in read_csv_rows(REVIEWER_DECISIONS_TSV)
             if d.get("task_id") == gold_row["case_id"]), "",
        ) if REVIEWER_DECISIONS_TSV.exists() else "",
        "adjudication_notes": notes,
    }
    # Populate structured fields when the reviewer supplied machine-parseable JSON.
    if isinstance(answer, str):
        parsed = _from_json(answer, None)
        if isinstance(parsed, list):
            entry["expected_set"] = parsed
        elif isinstance(parsed, dict):
            for key in ("expected_value", "expected_set", "expected_ranking"):
                if key in parsed:
                    entry[key] = parsed[key]
    return entry


def cmd_merge(args: argparse.Namespace) -> int:
    def load(name: str) -> dict[str, dict[str, str]]:
        path = Path(args.dir) / name
        if not path.exists():
            raise SystemExit(f"missing workbook: {path}")
        return {r["case_id"]: r for r in read_csv_rows(path)}

    r1 = load("reviewer_1.csv")
    r2 = load("reviewer_2.csv")
    adj = load("adjudicator.csv") if (Path(args.dir) / "adjudicator.csv").exists() else {}
    gold = {g["case_id"]: g for g in load_gold()}

    resolved: dict[str, dict[str, Any]] = {}
    unresolved: list[str] = []
    disagreements: list[str] = []
    for cid, g in gold.items():
        a1, a2 = r1.get(cid, {}), r2.get(cid, {})
        ans1, ans2 = a1.get("acceptable_answer", ""), a2.get("acceptable_answer", "")
        ab1 = _norm(a1.get("answerability"))
        ab2 = _norm(a2.get("answerability"))
        if ans1.strip() and _norm(ans1) == _norm(ans2) and ab1 == ab2:
            resolved[cid] = _finalize_entry(g, ans2, ab2, a2.get("mandatory_answer_elements", ""),
                                            a2.get("acceptable_alternatives", ""),
                                            a2.get("evidence_spans", ""), "two-reviewer agreement")
            continue
        disagreements.append(cid)
        ad = adj.get(cid, {})
        ans_adj = str(ad.get("adjudicator_acceptable_answer") or "").strip()
        ab_adj = _norm(ad.get("adjudicator_answerability"))
        if ans_adj and ab_adj in ANSWERABILITY:
            resolved[cid] = _finalize_entry(g, ans_adj, ab_adj,
                                            ad.get("adjudicator_mandatory_answer_elements", ""),
                                            ad.get("adjudicator_acceptable_alternatives", ""),
                                            a2.get("evidence_spans", ""),
                                            str(ad.get("adjudication_notes") or "adjudicated"))
        else:
            unresolved.append(cid)

    r1_names = sorted({r.get("reviewer_name", "").strip() for r in r1.values() if r.get("reviewer_name", "").strip()})
    r2_names = sorted({r.get("reviewer_name", "").strip() for r in r2.values() if r.get("reviewer_name", "").strip()})
    adj_names = sorted({r.get("adjudicator_name", "").strip() for r in adj.values() if r.get("adjudicator_name", "").strip()})
    kappa_pairs = [
        (_norm(r1[c].get("verdict")), _norm(r2[c].get("verdict")))
        for c in gold
        if _norm(r1[c].get("verdict")) and _norm(r2[c].get("verdict"))
    ]
    kappa = (
        cohens_kappa([a for a, _ in kappa_pairs], [b for _, b in kappa_pairs])
        if kappa_pairs else float("nan")
    )
    approved = (
        not unresolved
        and len(r1_names) == 1 and len(r2_names) == 1 and len(adj_names) == 1
        and r1_names[0] != r2_names[0]
    )
    consensus = {
        "schema": "gateC.reviewed_gold.v1",
        "approved": approved,
        "approved_by": [*r1_names, *r2_names] if approved else [],
        "adjudicator": adj_names[0] if (approved and adj_names) else "",
        "approved_at": utcnow() if approved else "",
        "note": (
            "Two independent reviewers + adjudicator. Generated by "
            "scripts/gold_adjudication.py merge. Never derived from benchmark/scoring/*.json."
        ),
        "agreement": {
            "n": len(gold),
            "cohens_kappa": None if kappa != kappa else round(kappa, 4),
            "n_disagreements": len(disagreements),
            "disagreements": disagreements,
        },
        "gold": resolved,
    }
    REVIEWED.mkdir(parents=True, exist_ok=True)
    out_dir = Path(args.dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    consensus_path = out_dir / "consensus.json"
    consensus_path.write_text(json.dumps(consensus, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "consensus": str(consensus_path),
        "approved": approved,
        "resolved": len(resolved),
        "unresolved": len(unresolved),
        "unresolved_cases": unresolved,
        "n_disagreements": len(disagreements),
        "inter_rater_kappa": None if kappa != kappa else round(kappa, 4),
        "approved_by": consensus["approved_by"],
        "adjudicator": consensus["adjudicator"],
    }, indent=2))
    if not approved:
        print("NOT APPROVED. Scoring remains blocked until all disagreements are adjudicated "
              "and both reviewer names + the adjudicator name are present.", file=sys.stderr)
    return 0 if approved else 1


# ── cli ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="report adjudication state").set_defaults(func=cmd_status)
    sub.add_parser("init", help="write blinded reviewer + adjudicator workbooks").set_defaults(func=cmd_init)

    p_val = sub.add_parser("validate", help="validate a reviewer workbook")
    p_val.add_argument("file")
    p_val.set_defaults(func=cmd_validate)

    p_kappa = sub.add_parser("kappa", help="Cohen's kappa between two reviewer workbooks")
    p_kappa.add_argument("file_a")
    p_kappa.add_argument("file_b")
    p_kappa.set_defaults(func=cmd_kappa)

    p_merge = sub.add_parser("merge", help="merge reviewers + adjudicator into consensus.json")
    p_merge.add_argument("--dir", default=str(REVIEWED))
    p_merge.set_defaults(func=cmd_merge)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
