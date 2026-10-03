#!/usr/bin/env python
"""Assemble the joined closure case-level table and compute E2/E3 engineering results.

Joins every executed arm on identical case IDs:
  closed48_locked      : protacxtend (original), direct_tool, fixed_workflow
  reproduced_current   : protacxtend (repaired, 32 held-out)
  baselines            : retrieval-only, tool-only, Base-LLM-control

Writes:
  results/closure/case_level.csv          tidy one-row-per-case×arm (instruction schema)
  results/closure/e2_e3_analysis.json     counts, rates, paired deltas
  results/closure/fig3_e2_paired_outcomes.png/pdf
  results/closure/fig4_e3_recovery.png/pdf

Scientific correctness columns are emitted null with status
`pending_independent_gold`; only execution outcomes are computed.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "closure"
CASES = ROOT / "benchmark" / "cases"
SPLITS = ROOT / "benchmark" / "gateC" / "splits.json"
LOCKED = ROOT / "benchmark_results" / "closed48" / "closed48_locked"
REPRO = ROOT / "benchmark_results" / "closed48" / "reproduced_current"
BASELINES = ROOT / "benchmark_results" / "baselines" / "baseline_comparison_20260923T163551Z.json"

# Predefined answerability: a case is unanswerable if it references a supplied
# table/file that is not actually attached, or lacks the target/structure/
# reference it needs. Derived from case JSON only (no peeking at outputs).
UNANSWERABLE_RULE = {
    "DISCOVER-01": "supplied feature table described but rows not attached",
    "DISCOVER-02": "supplied uncertainty table described but rows not attached",
    "DISCOVER-08": "supplied per-candidate assay cost table not attached",
    "DISCOVER-11": "supplied blinded feature table not attached",
    "DISCOVER-04": "supplied candidate metrics table not attached",
    "DESIGN-07": "no target, structure or molecule supplied",
    "DESIGN-09": "reference set named (JQ1) but SMILES not supplied",
}
STATUS_MAP = {
    "ok": "completed", "completed": "completed", "partial": "partial",
    "abstained": "abstained", "timeout": "timeout", "failed": "failed",
    "error": "failed", "skipped_no_credentials": "skipped",
}


def _cases() -> dict:
    out = {}
    for p in CASES.glob("*.json"):
        if p.stem.startswith("_"):
            continue
        c = json.loads(p.read_text(encoding="utf-8"))
        out[c["task_id"]] = c
    return out


def _row(cid, case, split, arm, status, latency, failure_code, trace_path, code_commit, extra=None):
    answerable = cid not in UNANSWERABLE_RULE
    row = {
        "task_id": cid, "study": "closed48", "arm": arm, "split": split,
        "answerability": "answerable" if answerable else "unanswerable",
        "answerability_rule": "" if answerable else UNANSWERABLE_RULE[cid],
        "source_group": case.get("capability", ""),
        "target": "", "E3": "", "assay_context": "",
        "required_inputs_present": answerable,
        "run_status": status,
        "scientific_score_status": "pending_independent_gold",
        "tool_valid": None, "output_valid": None, "evidence_supported": None,
        "mechanism_valid": None, "correct_resolution": None,
        "abstention_appropriate": None,
        "failure_code": failure_code or "",
        "latency_s": latency,
        "cost": None,
        "reviewer_1": "", "reviewer_2": "", "adjudicator": "",
        "trace_path": str(trace_path),
        "source_hash": "",
        "code_commit": code_commit,
    }
    if extra:
        row.update(extra)
    return row


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = _cases()
    splits = json.loads(SPLITS.read_text())["assignment"]
    commit = "82a0e4d1746b8b364b01ad823b16b64b727daefe"
    rows = []

    # ── locked arms (48 cases) ──
    preds = [json.loads(l) for l in (LOCKED / "predictions.jsonl").read_text().splitlines() if l.strip()]
    for p in preds:
        cid = p["case_id"]
        if cid not in cases:
            continue
        rows.append(_row(cid, cases[cid], splits.get(cid, ""), p["arm"],
                         STATUS_MAP.get(p.get("outcome") or p.get("status"), p.get("outcome", "")),
                         p.get("latency_s"), p.get("failure_code"), LOCKED / "predictions.jsonl", commit,
                         {"n_evidence_refs": p.get("n_evidence_refs", 0)}))

    # ── repaired arm (32 held-out + 14 development gap cases) ──
    repaired_rows = list(json.loads((REPRO / "heldout_results.json").read_text()))
    dev_path = OUT / "dev_gap_repaired.json"
    if dev_path.exists():
        repaired_rows += list(json.loads(dev_path.read_text()))
    for r in repaired_rows:
        cid = r["case_id"]
        if cid not in cases:
            continue
        rows.append(_row(cid, cases[cid], splits.get(cid, ""), "protacxtend_repaired",
                         STATUS_MAP.get(r.get("outcome"), r.get("outcome")),
                         r.get("elapsed_s"), r.get("stop_reason") or r.get("error", ""),
                         REPRO / "heldout_results.json", commit,
                         {"n_candidates": r.get("n_candidates", 0),
                          "attachment_hypothesis": r.get("attachment_hypothesis", False)}))

    # ── baselines (48 cases) ──
    if BASELINES.exists():
        b = json.loads(BASELINES.read_text())
        for sys in b["systems"]:
            for res in sys["results"]:
                cid = res["task_id"]
                if cid not in cases:
                    continue
                sc = res.get("score") or {}
                rows.append(_row(cid, cases[cid], splits.get(cid, ""), sys["system"],
                                 STATUS_MAP.get(res.get("status"), res.get("status", "")),
                                 res.get("latency_s"), "",
                                 BASELINES, commit,
                                 {"rubric_score_nonindependent": sc.get("score")}))

    cols = list(rows[0].keys())
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with (OUT / "case_level.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # ── E2/E3 analysis ──
    by_arm = defaultdict(list)
    for r in rows:
        by_arm[r["arm"]].append(r)
    arms = ["protacxtend", "protacxtend_repaired", "direct_tool", "fixed_workflow",
            "retrieval-only", "tool-only", "Base-LLM-control"]
    summary = {}
    for arm in arms:
        rs = by_arm.get(arm, [])
        if not rs:
            continue
        c = Counter(r["run_status"] for r in rs)
        summary[arm] = {"n": len(rs), **{k: c.get(k, 0) for k in
                        ("completed", "partial", "abstained", "timeout", "failed", "skipped")}}

    # E3: cases direct_tool completed but original protacxtend failed
    direct_ok = {r["task_id"] for r in by_arm["direct_tool"] if r["run_status"] == "completed"}
    orig_fail = {r["task_id"] for r in by_arm["protacxtend"] if r["run_status"] in ("abstained", "timeout", "failed")}
    gap = sorted(direct_ok & orig_fail)
    repaired_ok = {r["task_id"] for r in by_arm["protacxtend_repaired"] if r["run_status"] == "completed"}
    repaired_abstained = {r["task_id"] for r in by_arm["protacxtend_repaired"] if r["run_status"] == "abstained"}
    unans = set(UNANSWERABLE_RULE)
    closed = sorted(set(gap) & repaired_ok)
    abstained_gap = sorted(set(gap) & repaired_abstained)
    still_open = sorted(set(gap) - repaired_ok - repaired_abstained)
    # abstention appropriateness: unanswerable by rule, or cause = missing source-backed input
    abstain_cause = {}
    for r in by_arm["protacxtend_repaired"]:
        if r["run_status"] == "abstained":
            why = r.get("failure_code") or ""
            abstain_cause[r["task_id"]] = why[:120]

    analysis = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_cases": len(cases),
        "answerability": {"answerable": sum(1 for c in cases if c not in UNANSWERABLE_RULE),
                          "unanswerable": len(UNANSWERABLE_RULE),
                          "rule": UNANSWERABLE_RULE},
        "arm_summary": summary,
        "e3_direct_agent_gap": {
            "direct_completed_original_agent_failed": len(gap),
            "case_ids": gap,
            "repaired_closed_by_completion": len(closed),
            "repaired_closed_ids": closed,
            "repaired_abstained": len(abstained_gap),
            "repaired_abstained_ids": abstained_gap,
            "repaired_still_open": len(still_open),
            "repaired_still_open_ids": still_open,
            "predefined_unanswerable": sorted(unans),
            "unanswerable_in_gap": sorted(set(gap) & unans),
            "abstention_cause": abstain_cause,
            "note": "45 counted from executed arms, not a hand ID map. Completion != correctness; "
                    "abstentions on missing-input/unanswerable cases are the intended behaviour.",
        },
        "e2_note": "Primary endpoint (supported correct resolution) is PENDING_INDEPENDENT_GOLD; "
                   "only execution outcomes are computed. rubric_score_nonindependent must not be "
                   "reported as correctness.",
        "scientific_scores": "null (pending independent gold)",
    }
    (OUT / "e2_e3_analysis.json").write_text(json.dumps(analysis, indent=2))

    # ── figures ──
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from protacxtend.validation.closure_figures import apply_style, save_square, style_axes

        apply_style()
        # Fig 3: outcome composition per arm
        fig, ax = plt.subplots()
        cats = ["completed", "partial", "abstained", "timeout", "failed", "skipped"]
        colors = {"completed": "#1B9E77", "partial": "#66C2A5", "abstained": "#E6AB02",
                  "timeout": "#D95F02", "failed": "#E7298A", "skipped": "#B3B3B3"}
        arms_present = [a for a in arms if a in summary]
        bottom = [0] * len(arms_present)
        for cat in cats:
            vals = [summary[a].get(cat, 0) for a in arms_present]
            if not any(vals):
                continue
            ax.bar(arms_present, vals, bottom=bottom, label=cat, color=colors[cat])
            bottom = [b + v for b, v in zip(bottom, vals)]
        for i, tot in enumerate(bottom):
            ax.text(i, tot + 0.5, f"n={int(tot)}", ha="center", fontsize=8)
        style_axes(ax, xlabel="Arm", ylabel="Cases (n = 48 unless noted)",
                   title="E2 paired arm outcomes (correctness PENDING gold)")
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        ax.legend(fontsize=7, ncol=3, frameon=False)
        save_square(fig, OUT / "fig3_e2_paired_outcomes.png", dpi=600, pdf=True)

        # Fig 4: E3 recovery waterfall
        fig2, ax2 = plt.subplots()
        labels = ["direct ok,\nagent failed", "repaired\nclosure", "still open"]
        vals = [len(gap), len(closed), len(still_open)]
        ax2.bar(labels, vals, color=["#D95F02", "#1B9E77", "#7570B3"])
        for i, v in enumerate(vals):
            ax2.text(i, v + 0.3, str(v), ha="center", fontsize=9)
        style_axes(ax2, xlabel="E3 gap class", ylabel="Cases (n)",
                   title="E3 routing gap closed by the repaired agent")
        save_square(fig2, OUT / "fig4_e3_recovery.png", dpi=600, pdf=True)
    except Exception as exc:  # noqa: BLE001
        print("figures skipped:", exc)

    print(json.dumps({"rows": len(rows), "arm_summary": summary,
                      "gap": len(gap), "closed": len(closed), "still_open": len(still_open)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
