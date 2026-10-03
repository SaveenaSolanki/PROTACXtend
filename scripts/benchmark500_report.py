#!/usr/bin/env python
"""Render benchmark500 results: workbook, adjudication queue, report, figures."""
from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmark500" / "results"
CASES = ROOT / "benchmark500" / "cases"
OUT = ROOT / "benchmark500"

HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(color="FFFFFF", bold=True)
PENDING_FILL = PatternFill("solid", fgColor="FFF2CC")   # gold-dependent
SCORED_FILL = PatternFill("solid", fgColor="E2EFDA")    # objective
ABSTAIN_FILL = PatternFill("solid", fgColor="FCE4D6")

CASE_FIELDS = ["case_id", "suite", "split", "domain", "difficulty_level", "difficulty_name",
               "task_type", "target", "indication", "e3", "question",
               "required_output", "permitted_tools", "evidence_cutoff_date",
               "future_horizon_months", "ground_truth_window_end", "primary_adjudication_endpoint",
               "gold_status"]

RUN_FIELDS = ["run_id", "run_status", "abstention_reason", "failure_code", "capability_attempted",
              "tool_executed", "valid_output", "evidence_items", "latency_s"]
OBJ_FIELDS = ["Tool_Execution_0_5", "Reproducibility_0_5", "Evidence_Availability_0_5"]
GOLD_FIELDS = ["Temporal_Compliance_0_5", "Tool_Selection_0_5", "Evidence_Grounding_0_5",
               "Mechanistic_Correctness_0_5", "Quantitative_Correctness_0_5",
               "Uncertainty_Calibration_0_5", "Final_Decision_Quality_0_5",
               "Scientific_Correctness_0_5", "Future_Outcome_Match_0_5"]
EXTRA = ["adjudication_status", "agent_answer", "agent_confidence_0_100", "adjudicator_notes", "final_score_pct"]


def _style(ws, ncols, widths):
    for j in range(1, ncols + 1):
        c = ws.cell(row=1, column=j)
        c.fill = HEAD_FILL; c.font = HEAD_FONT; c.alignment = Alignment(vertical="center")
    for j, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = "A2"


def _load(run_id):
    run_dir = RESULTS / run_id
    preds = {json.loads(l)["case_id"]: json.loads(l)
             for l in (run_dir / "predictions.jsonl").read_text().splitlines() if l.strip()}
    scored = json.loads((run_dir / "scores.json").read_text())
    cases = {}
    for suite, label in (("temporal_500", "temporal"), ("general_500", "general")):
        for l in (CASES / f"{suite}.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                c = json.loads(l)
                cases[c["case_id"]] = c
    return run_dir, preds, scored, cases


def build_results_workbook(run_id, preds, scored, cases, prefix="PROTACXtend_500_Results"):
    wb = Workbook()
    ws = wb.active; ws.title = "Tasks_Scored"
    cols = CASE_FIELDS + RUN_FIELDS + OBJ_FIELDS + GOLD_FIELDS + EXTRA
    ws.append(cols)
    for cid in sorted(cases):
        c = cases[cid]; p = preds.get(cid, {}); s = {}
        row = [c.get(f, "") for f in CASE_FIELDS]
        row += [p.get(f, "") for f in RUN_FIELDS]
        # objective scores from the scored json
        row += ["" for _ in OBJ_FIELDS]  # filled below from scored cases
        row += [None for _ in GOLD_FIELDS]
        row += ["pending_adjudication", "", None, "", None]
        ws.append(row)
    # fill objective columns from scored cases
    scored_cases = {r["case_id"]: r for r in scored["cases"]}
    obj_start = CASE_FIELDS.index("case_id") + 1  # not used; locate by header
    header = {name: i + 1 for i, name in enumerate(cols)}
    for r_i in range(2, ws.max_row + 1):
        cid = ws.cell(row=r_i, column=header["case_id"]).value
        sc = scored_cases.get(cid, {})
        for f in OBJ_FIELDS:
            ws.cell(row=r_i, column=header[f]).value = sc.get(f)
        ws.cell(row=r_i, column=header["Temporal_Compliance_0_5"]).value = None
    _style(ws, len(cols), [10, 10, 12, 26, 8, 16, 18, 10, 16, 8, 60, 26, 26, 12, 10, 12, 30, 12] +
           [30, 12, 22, 20, 20, 12, 12, 10, 10] + [10, 12, 14] + [12] * len(GOLD_FIELDS) + [20, 40, 12, 24, 12])
    # colour the score columns
    for f in OBJ_FIELDS:
        for r_i in range(2, ws.max_row + 1):
            ws.cell(row=r_i, column=header[f]).fill = SCORED_FILL
    for f in GOLD_FIELDS:
        for r_i in range(2, ws.max_row + 1):
            ws.cell(row=r_i, column=header[f]).fill = PENDING_FILL

    # summary sheets
    agg = scored["summary"]["aggregates"]
    for sheet, key in (("Summary_By_Domain", "by_domain"), ("Summary_By_Difficulty", "by_difficulty"),
                       ("Summary_By_Split", "by_split"), ("Summary_By_Suite", "by_suite")):
        w = wb.create_sheet(sheet)
        rows = agg[key]
        if not rows:
            continue
        w.append(list(rows[0].keys()))
        for r in rows:
            w.append(list(r.values()))
        _style(w, len(rows[0]), [30] + [12] * (len(rows[0]) - 1))

    f = wb.create_sheet("Funnel")
    f.append(["Stage", "N", "Notes"])
    notes = {
        "planned": "tasks authored in the two workbooks",
        "eligible_uncurated": "eligible but with uncurated gold",
        "executed": "a real capability/probe produced traceable evidence",
        "valid_output": "schema-valid, non-empty output",
        "typed_abstention": "explicit typed abstention (no fabrication)",
        "adjudicated": "expert-adjudicated (PENDING)",
        "gold_curated": "gold answers curated (PENDING)",
    }
    for k, v in scored["summary"]["funnel"].items():
        f.append([k, v, notes.get(k, "")])
    _style(f, 3, [24, 10, 60])

    readme = wb.create_sheet("README", 0)
    readme.append(["PROTACXtend 500-task benchmark — results"])
    readme.append(["run_id", run_id])
    readme.append(["cases", scored["summary"]["n_cases"]])
    readme.append(["objective dimensions", ", ".join(scored["summary"]["objective_dimensions"])])
    readme.append(["pending adjudication", ", ".join(scored["summary"]["adjudicated_dimensions"])])
    readme.append(["green cells", "objectively scored from the run"])
    readme.append(["yellow cells", "gold-dependent — BLANK until expert adjudication"])
    for lim in scored["summary"]["limitations"]:
        readme.append(["limitation", lim])
    _style(readme, 2, [26, 100])

    path = OUT / f"{prefix}.xlsx"
    wb.save(path)
    return path


def build_adjudication_queue(run_id, preds, cases, prefix="ADJUDICATION_QUEUE"):
    """Blank expert-scoring sheet for the 1000 tasks, pre-filled with question + evidence."""
    wb = Workbook(); ws = wb.active; ws.title = "Adjudication_Queue"
    cols = ["case_id", "suite", "split", "domain", "difficulty_level", "target", "indication", "e3",
            "question", "required_output", "evidence_cutoff_date", "temporal_blinding",
            "system_status", "system_evidence_summary", "system_answer_placeholder",
            *GOLD_FIELDS, "adjudicator_id", "adjudication_date", "consensus_notes", "leakage_flag"]
    ws.append(cols)
    for cid in sorted(cases):
        c = cases[cid]; p = preds.get(cid, {}); ev = p.get("evidence") or {}
        summ = (f"target={ev.get('target')}; structures={len(ev.get('structures') or [])}; "
                f"e3_ligands={ev.get('e3_ligands')}; binders={ev.get('binders')}; warheads={ev.get('warheads')}")
        ws.append([
            c["case_id"], c["suite"], c["split"], c["domain"], c["difficulty_level"], c["target"],
            c["indication"], c["e3"], c["question"], c["required_output"], c["evidence_cutoff_date"],
            "cutoff-enforced" if c["suite"] == "temporal" else "n/a",
            p.get("status", ""), summ, "[awaiting LLM/agent answer]",
            *[None] * len(GOLD_FIELDS), "", "", "", "Not assessed",
        ])
    _style(ws, len(cols), [10, 10, 12, 26, 8, 10, 16, 8, 70, 26, 12, 14, 12, 50, 26] + [10] * len(GOLD_FIELDS) + [14, 14, 40, 12])
    for j, f in enumerate(GOLD_FIELDS, start=15):
        for r in range(2, ws.max_row + 1):
            ws.cell(row=r, column=j).fill = PENDING_FILL
    path = OUT / f"{prefix}.xlsx"
    wb.save(path)
    return path


def build_report(run_id, preds, scored, prefix="REPORT"):
    s = scored["summary"]
    agg = s["aggregates"]
    def table(rows, key):
        out = [f"| {key} | N | executed | abstained | exec rate | mean tool-exec | mean evidence |",
               "|---|---|---|---|---|---|---|"]
        for r in rows:
            out.append(f"| {r[key]} | {r['n']} | {r['executed']} | {r['abstained']} | "
                       f"{r['execution_rate']*100:.1f}% | {r['mean_tool_execution']} | {r['mean_evidence_availability']} |")
        return "\n".join(out)
    md = f"""# PROTACXtend 500-task benchmark — results report

Run: `{run_id}` · generated from `benchmark500/results/{run_id}/`.

## 1. What these numbers mean (read first)

The two source workbooks (`Blinded_Temporal_Challenge_500_Tasks.xlsx`,
`PROTACxtend_500_Task_Benchmark (1).xlsx`) are **question banks with no curated
gold**: all 1000 tasks carry `TO CURATE` / `Not curated` and empty expected
answers, evidence packages and scores.

Therefore this run reports **execution and evidence-readiness**, objectively
measured. It does **not** report scientific correctness, because no adjudicated
ground truth exists and none was invented. Reasoning-dependent dimensions
(Scientific correctness, Mechanistic correctness, Quantitative correctness,
Uncertainty calibration, Final decision quality, Future-outcome match,
Temporal compliance, Tool-selection correctness) are emitted blank with
`pending_adjudication` and are ready to fill in `ADJUDICATION_QUEUE.xlsx`.

Additional hard constraints in this environment:

* **No LLM provider is authenticated** (`protacxtend setup` required), so L4–L6
  reasoning tasks cannot be answered. They are recorded as typed abstentions.
* **No frozen pre-cutoff corpus** exists, so temporal compliance for the
  temporal suite is *unverifiable* rather than passed.

## 2. Coverage funnel

| stage | N |
|---|---|
| planned tasks | {s['funnel']['planned']} |
| eligible (uncurated gold) | {s['funnel']['eligible_uncurated']} |
| executed (real capability/probe) | {s['funnel']['executed']} |
| valid output | {s['funnel']['valid_output']} |
| typed abstention | {s['funnel']['typed_abstention']} |
| expert-adjudicated | **0 (pending)** |
| gold curated | **0 (pending)** |

## 3. By suite

{table(agg['by_suite'], 'suite')}

## 4. By domain

{table(agg['by_domain'], 'domain')}

## 5. By difficulty (L1–L7)

{table(agg['by_difficulty'], 'difficulty_level')}

## 6. By split (target-grouped; no target leakage across splits)

{table(agg['by_split'], 'split')}

## 7. What "done" requires next

1. Curate gold answers + evidence (DOI/PMID/date) for the {s['n_cases']} tasks;
   two independent adjudicators per the source rubric.
2. Freeze pre-cutoff corpora per cutoff date (12 distinct cutoffs) for the
   temporal suite, and pin tool/model versions ≤ cutoff.
3. Authenticate an LLM/agent (`protacxtend setup`) and re-run with
   `--mode llm`; then fill the reasoning dimensions.
4. Re-run `benchmark500_score.py` and this report with gold present.

## 8. Reproduce

```bash
python scripts/benchmark500_ingest.py
python scripts/benchmark500_run.py --suite both --mode probe --run-id {run_id}
python scripts/benchmark500_score.py --run-id {run_id}
python scripts/benchmark500_report.py --run-id {run_id}
```

## 9. Limitations (verbatim from scores.json)

""" + "\n".join(f"- {x}" for x in s["limitations"]) + "\n"
    path = OUT / f"{prefix}.md"
    path.write_text(md, encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--prefix", default="")
    args = ap.parse_args()
    run_dir, preds, scored, cases = _load(args.run_id)
    pre = args.prefix or ("PROTACXtend_500_Results" if args.run_id == "b500_probe_20260923" else f"PROTACXtend_500_Results_{args.run_id}")
    adjud = "ADJUDICATION_QUEUE" if pre == "PROTACXtend_500_Results" else f"ADJUDICATION_QUEUE_{args.run_id}"
    rep = "REPORT" if pre == "PROTACXtend_500_Results" else f"REPORT_{args.run_id}"
    r1 = build_results_workbook(args.run_id, preds, scored, cases, pre)
    r2 = build_adjudication_queue(args.run_id, preds, cases, adjud)
    r3 = build_report(args.run_id, preds, scored, rep)
    print("wrote", r1); print("wrote", r2); print("wrote", r3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
