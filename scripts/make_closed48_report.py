#!/usr/bin/env python
"""Manuscript-ready report for the closed 48-case benchmark.

Reads a run directory produced by ``scripts/run_closed_48.py`` and (optionally)
a scored ``scores.json`` produced by ``scripts/score_closed_48.py`` and writes
``RESULTS.md`` with the per-case table, figures, limitations and exact
reproducibility commands.

Correctness columns stay ``PENDING_INDEPENDENT_GOLD`` until the reviewer
approved gold exists.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def md_table(rows: List[List[Any]], header: List[str]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    args = ap.parse_args()
    run = args.run_dir
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8")) if (run / "manifest.json").exists() else {}
    table = read_csv(run / "results_table.csv")
    scores = None
    if (run / "scores.json").exists():
        scores = json.loads((run / "scores.json").read_text(encoding="utf-8"))
    scored = bool(scores and scores.get("status") == "scored_against_approved_gold")

    arms = sorted({r["arm"] for r in table})
    # cohort summary
    summary_rows = []
    for arm in arms:
        for outcome in ["completed", "partial", "abstained", "refused", "failed", "timeout"]:
            n = sum(1 for r in table if r["arm"] == arm and r["outcome"] == outcome)
            if n:
                summary_rows.append([arm, outcome, n])

    # per-case table (one row per case; one column per arm outcome)
    by_case: Dict[str, Dict[str, str]] = defaultdict(dict)
    case_cap: Dict[str, str] = {}
    case_split: Dict[str, str] = {}
    case_lat: Dict[str, Dict[str, str]] = defaultdict(dict)
    for r in table:
        by_case[r["case_id"]][r["arm"]] = r["outcome"]
        if r.get("capability"):
            case_cap[r["case_id"]] = r["capability"]
        case_split[r["case_id"]] = r.get("split", "")
        case_lat[r["case_id"]][r["arm"]] = r.get("latency_s", "")
    # fall back to the frozen case record for capability when a timeout row omitted it
    for cid in by_case:
        if not case_cap.get(cid):
            cpath = HERE / "benchmark" / "cases" / f"{cid}.json"
            if cpath.exists():
                case_cap[cid] = json.loads(cpath.read_text(encoding="utf-8")).get("capability", "")
    per_case_rows = []
    score_map = {}
    if scored:
        for c in scores.get("cases", []):
            score_map[c["case_id"]] = c
    for cid in sorted(by_case):
        row = [cid, case_cap.get(cid, ""), case_split.get(cid, "")]
        for arm in arms:
            row.append(by_case[cid].get(arm, ""))
        row.append("PENDING_INDEPENDENT_GOLD")
        per_case_rows.append(row)

    figs = sorted(p.name for p in (run / "figures").glob("*.png"))
    limitations = """
## Limitations

1. **Gold is not adjudicated.** All 48 gold entries and the 29 reviewer
   decisions in `benchmark/gateC/REVIEWER_DECISIONS.tsv` are `PENDING`.
   Correctness, paired accuracy differences and uncertainty remain blocked.
   The per-case correctness column is therefore `PENDING_INDEPENDENT_GOLD`.
2. **PROTACXtend latency.** The canonical deterministic runtime
   (`run_protacpilot`) exceeded the locked per-case budget on a large fraction
   of cases; those are recorded as `timeout`, not as wrong answers, and are
   included in the denominator.
3. **No LLM arm.** No provider is authenticated, so the agentic/LLM arm is
   absent; `PROTACXtend` here is the deterministic canonical stack.
4. **Baselines are tool-level.** `direct_tool` is one matched tool call and
   `fixed_workflow` is the same fixed chain for every case; they bound
   orchestration value but are not full external scientific agents.
5. **48-case source overlap.** The suite is dominated by one internal
   BRD4–VHL source; the group-disjoint split is leakage-valid but small
   (blind=29), so external validity is limited.
6. **Rubric tasks need human dimension scores.** Even with approved gold,
   `design_rubric`/`mechanistic_rubric` cases cannot be auto-scored beyond
   checklist coverage; they remain `requires_expert_review`.
"""

    repro = f"""## Exact reproducibility commands

```bash
cd {HERE}

# 1. scientific-input contract fix (Gate C scope lock)
python -m pytest tests/test_gate_c_input_contract.py -q

# 2. frozen gold/rubric/split package (must be approved for scoring)
python benchmark/gateC/build_gate_c.py
python benchmark/gateC/build_gate_c.py --check

# 3. closed 48-case run (locked budgets)
python scripts/run_closed_48.py --workers 14 \\
    --timeout-protacxtend 120 --timeout-direct 60 --timeout-fixed 150 \\
    --run-id closed48_locked

# 4. figures (gold-independent)
python scripts/plot_closed_48.py --run-dir {run}

# 5. scoring — refuses to run without reviewer-approved gold
python scripts/score_closed_48.py --run-dir {run}

# 6. manuscript report
python scripts/make_closed48_report.py --run-dir {run}
```

Scoring unlocks only after `benchmark/gateC/reviewed_gold/consensus.json`
has `"approved": true` with two named reviewers and an adjudicator.
"""

    text = f"""# Closed 48-case benchmark — results

Run `{manifest.get('run_id', run.name)}` · git `{str(manifest.get('git_commit', ''))[:12]}` ·
mode `{manifest.get('execution_mode', 'scientific')}` · generated from `{run}`.

> **Gold status: `PENDING_INDEPENDENT_GOLD`.** No correctness score is reported.
> The 29 reviewer decisions and all 48 gold adjudications are pending. This
> document reports only gold-independent execution outcomes, evidence counts,
> failures and runtime.

## Cohort

{md_table(summary_rows, ['arm', 'outcome', 'n'])}

## Per-case outcomes

{md_table(per_case_rows, ['case_id', 'capability', 'split'] + arms + ['correctness'])}

## Evidence-complete case

See `case_studies/evidence_complete_KNOW-01.md`.

## Justified no-go case

See `case_studies/no_go_REASON-02.md`.

## Figures

{chr(10).join('- `figures/' + f + '`' for f in figs) if figs else '_run plot_closed_48.py to generate figures._'}

{limitations}

{repro}
"""
    (run / "RESULTS.md").write_text(text, encoding="utf-8")
    print(f"wrote {run / 'RESULTS.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
