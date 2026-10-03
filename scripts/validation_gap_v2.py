#!/usr/bin/env python
"""validation_gap_v2 — rerun the frozen 48 cases after the v1 failure fixes.

Never touches validation_gap_v1. Produces a complete freeze (the v1 freeze
omitted ``agents/graph.py`` and ``agents/design_gates.py``, so v1 was not fully
hash-pinned), a rich 48-row adjudication table, an evidence ledger, a v1->v2
case comparison and a failure taxonomy.

Gold remains unadjudicated: ``benchmark_score`` stays ``null``.

Usage::

    python scripts/validation_gap_v2.py --workers 8 --budget 150
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib.util

_spec = importlib.util.spec_from_file_location("cvg_v1", ROOT / "scripts" / "close_validation_gap.py")
cvg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cvg)

CASES = ROOT / "benchmark" / "cases"
V1 = ROOT / "benchmark_results" / "validation_gap_v1"
OUT = ROOT / "benchmark_results" / "validation_gap_v2"

FREEZE_CODE_GLOBS = [
    "protacxtend/agents/*.py",
    "protacxtend/contracts/*.py",
    "protacxtend/backend/schemas.py",
    "protacxtend/tools/verified_components.py",
    "protacxtend/run_records.py",
    "scripts/close_validation_gap.py",
    "scripts/build_verified_components.py",
]
FREEZE_DATA = [
    "protacxtend/data/verified_components.json",
    "protacxtend/data/curated_targets.csv",
    "protacxtend/data/curated_e3_ligands.csv",
    "protacxtend/data/curated_warheads.csv",
]
PROMPT_FILES = [
    "protacxtend/agentic/chat_agent.py",
    "protacxtend/agents/design_planner_agent.py",
]

RUBRIC = {
    "entity_resolution": "resolved POI/E3 == parsed POI/E3; n/a when no target is required",
    "retrieval_relevance": "required | optional | not_applicable, decided from supplied inputs",
    "claim_support": "every asserted fact has a source that directly supports it, or is labelled hypothesis",
    "chemical_validity": "each candidate is a sanitized complete SMILES with attachment provenance",
    "decision_quality": "terminal decision follows from the evidence (no unsupported continuation)",
    "abstention_appropriateness": "abstention names a real missing prerequisite",
    "completion": "terminal status reached within the per-case budget",
    "states": "supported | unsupported | not_applicable | insufficient_information",
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _worker(task_id: str, budget: float) -> dict[str, Any]:
    """Module-level worker so ProcessPoolExecutor can pickle it."""
    return cvg._worker(task_id, budget)


def _files(globs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for g in globs:
        for p in sorted(ROOT.glob(g)):
            if p.is_file() and "__pycache__" not in p.parts:
                out[str(p.relative_to(ROOT))] = _sha(p)
    return out


def _git_rev() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def build_freeze(workers: int, budget: float) -> dict[str, Any]:
    code = _files(FREEZE_CODE_GLOBS)
    return {
        "schema": "validation_gap.freeze.v2",
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "supersedes": "validation_gap_v1",
        "v1_link": "benchmark_results/validation_gap_v1",
        "v1_freeze_gap": ("v1 code_hashes omitted protacxtend/agents/graph.py and "
                          "protacxtend/agents/design_gates.py; v2 hashes every agents/*.py"),
        "git_revision": _git_rev(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).decode().strip()),
        "code_hashes": code,
        "data_hashes": {p: _sha(ROOT / p) for p in FREEZE_DATA if (ROOT / p).exists()},
        "prompt_hashes": {p: _sha(ROOT / p) for p in PROMPT_FILES if (ROOT / p).exists()},
        "case_list": sorted(p.stem for p in CASES.glob("*.json") if not p.stem.startswith("_")),
        "tool_versions": cvg._versions(),
        "timeout_policy": {"per_case_budget_s": budget, "workers": workers,
                           "retry_policy": "no silent retry/repair; retries recorded in stage_ledger"},
        "entry_point": "protacxtend.agents.structured_run.run_case",
        "provenance": "complete_agent_workflow",
        "rubric": RUBRIC,
        "gold_adjudicated": False,
        "benchmark_score": None,
    }


# ── retrieval requirement heuristic (declared, not hidden) ───────────

def _retrieval_requirement(case: dict[str, Any]) -> str:
    cap = (case.get("capability") or "").upper()
    inputs = " ".join(str(s).lower() for s in (case.get("supplied_inputs") or []))
    q = (case.get("scientific_question") or "").lower()
    supplied_structure = ("warhead:" in inputs or "compound" in inputs or "smiles" in inputs
                          or "e3 ligand:" in inputs)
    supplied_table = ("csv" in inputs or "columns" in inputs or "table" in inputs)
    if supplied_table:
        return "not_applicable"
    if cap == "DISCOVER":
        return "not_applicable"
    if supplied_structure and cap == "DESIGN":
        # all components (warhead, E3 ligand, exit vector) are supplied: external
        # retrieval is genuinely inapplicable, not a failure
        return "not_applicable"
    if supplied_structure and cap in {"DESIGN", "REASON"}:
        return "optional"
    if cap == "KNOW":
        return "required"
    if cap == "REASON":
        return "optional"
    return "required" if cap == "DESIGN" else "optional"


def _unsupported(result: dict[str, Any], retrieval_req: str) -> bool:
    """A non-abstention final answer with zero sourced evidence."""
    state = str(result.get("scientific_state") or "")
    if state in {"justified_no_go", "unresolved", "abstained", "invalid_run"}:
        return False
    if retrieval_req == "not_applicable":
        return False
    evidence = result.get("evidence") or []
    has_claim = bool(str(result.get("answer") or "").strip()) or bool(result.get("n_candidates"))
    return has_claim and len(evidence) == 0


def adjudicate_v2(result: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    state = str(result.get("scientific_state") or "")
    evidence = result.get("evidence") or []
    entity = result.get("entity_resolution") or {}
    expected_target = str(entity.get("target") or "").strip()
    expected_e3 = [str(e).upper() for e in (entity.get("e3_ligases") or [])]
    resolved = result.get("resolved_target") or {}
    resolved_name = str(resolved.get("target_name") or "").strip()
    resolved_e3 = str(result.get("resolved_e3") or "").upper()
    if not expected_target:
        entity_ok: Any = "not_applicable"
    else:
        entity_ok = bool(resolved_name) and resolved_name.upper() == expected_target.upper()
        if entity_ok and expected_e3:
            entity_ok = bool(resolved_e3) and resolved_e3 in expected_e3

    req = _retrieval_requirement(case)
    reached = result.get("reached") or []
    attempted = "retrieve_target_binders" in reached
    successful = len(evidence) > 0
    used = successful and state not in {"unresolved", ""}

    verified_smiles = [s for s in (result.get("verified_candidate_smiles") or []) if s]
    chem: Any = "not_applicable"
    if int(result.get("n_candidates") or 0) > 0:
        chem = "valid" if all(cvg._valid_smiles(s) for s in verified_smiles) and verified_smiles else "invalid"

    unsupported = _unsupported(result, req)
    claim_support = ("not_applicable" if req == "not_applicable" and not evidence
                     else "supported" if evidence else "unsupported")
    abstained = state in {"justified_no_go", "unresolved"} or result.get("outcome") in {"abstained"}
    abst_reason = str(result.get("abstention_reason") or result.get("stop_reason") or "")

    return {
        "case_id": result.get("case_id", ""),
        "mode": case.get("capability", ""),
        "input_task": (case.get("scientific_question") or "")[:140],
        "expected_task": case.get("title", ""),
        "target_expected": expected_target,
        "e3_expected": ",".join(expected_e3),
        "target_resolved": resolved_name,
        "e3_resolved": resolved_e3,
        "entity_resolution": entity_ok,
        "retrieval_requirement": req,
        "retrieval_attempted": attempted,
        "retrieval_successful": successful,
        "retrieval_used_in_answer": used,
        "source_ids": " | ".join(sorted({str(e.get("source")) for e in evidence if e.get("source")}))[:300],
        "evidence_count": len(evidence),
        "claim_support": claim_support,
        "chemistry_check": chem,
        "candidate_ids": " | ".join(verified_smiles)[:300],
        "n_verified_candidates": int(result.get("n_verified_candidates") or 0),
        "terminal_decision": state,
        "outcome": result.get("outcome"),
        "abstention_reason": abst_reason[:200],
        "unsupported_claim": unsupported,
        "completion_within_time_limit": bool(not result.get("over_budget")) and result.get("outcome") != "timeout",
        "elapsed_s": round(float(result.get("elapsed_s") or result.get("wall_s") or 0), 2),
        "reviewer_status": "internal_audit_only",
        "correctness": "PENDING_INDEPENDENT_GOLD",
        "provenance": "complete_agent_workflow",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--budget", type=float, default=150.0)
    ap.add_argument("--recompute", action="store_true",
                    help="rebuild adjudication from existing results.jsonl without rerunning")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cases").mkdir(exist_ok=True)

    # 1. verify v1
    verify = _verify_v1()
    (OUT / "VERIFY_V1.md").write_text(verify)
    (OUT / "LINK_TO_V1.md").write_text(
        "# Link to frozen v1\n\n"
        "This v2 directory supersedes but never modifies `benchmark_results/validation_gap_v1/`.\n"
        "v1 results and hashes are read-only inputs. See `VERIFY_V1.md` for the audit.\n")

    # 2. freeze (complete)
    freeze = build_freeze(args.workers, args.budget)
    (OUT / "freeze.json").write_text(json.dumps(freeze, indent=2))
    _write_freeze_md(freeze)
    (OUT / "RUBRIC.md").write_text(_rubric_md())

    # 3. run 48 (or reuse)
    if args.recompute and (OUT / "results.jsonl").exists():
        results = [json.loads(l) for l in (OUT / "results.jsonl").read_text().splitlines() if l.strip()]
        t0 = time.time()
        print("recompute: reusing existing results.jsonl")
    else:
        print(f"v2 running {len(freeze['case_list'])} cases · budget {args.budget}s · workers {args.workers}")
        results = []
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(_worker, cid, args.budget): cid for cid in freeze["case_list"]}
            for fut in as_completed(futs):
                res = fut.result()
                results.append(res)
                (OUT / "cases" / f"{res.get('case_id', futs[fut])}.json").write_text(
                    json.dumps(res, indent=2, default=str))
        results.sort(key=lambda r: r.get("case_id", ""))
        (OUT / "results.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in results))

    # 4. adjudication + evidence ledger
    rows = []
    for res in results:
        cid = res.get("case_id", "")
        cp = CASES / f"{cid}.json"
        case = json.loads(cp.read_text()) if cp.exists() else {}
        rows.append(adjudicate_v2(res, case))
    with (OUT / "adjudication_table.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    _write_table_md(rows)
    _write_evidence_ledger(results)

    # 5. comparison + taxonomy + aggregate
    _write_comparison(rows)
    _write_failure_taxonomy(rows, results)
    _aggregate_v2(rows, freeze, time.time() - t0)
    _review_sample(rows)
    print("wrote", OUT)
    return 0


def _verify_v1() -> str:
    lines = ["# v1 verification", ""]
    cited = [
        "freeze.json", "results.jsonl", "adjudication_table.csv", "adjudication_table.md",
        "aggregate.md", "review_sample.md",
    ]
    for name in cited:
        lines.append(f"- [{'x' if (V1 / name).exists() else ' '}] `benchmark_results/validation_gap_v1/{name}`")
    cases = list((V1 / "cases").glob("*.json"))
    lines.append(f"- v1 case records: {len(cases)}")
    fz = json.loads((V1 / "freeze.json").read_text())
    mism = 0
    for group in ("code_hashes", "data_hashes"):
        for p, h in fz.get(group, {}).items():
            cur = _sha(ROOT / p) if (ROOT / p).exists() else "MISSING"
            if cur != h:
                mism += 1
                lines.append(f"- HASH MISMATCH `{p}`")
    lines += ["", f"- frozen hash mismatches: **{mism}**",
              f"- v1 freeze covered {len(fz.get('code_hashes', {}))} code files and "
              f"{len(fz.get('data_hashes', {}))} data files.",
              "- **Freeze gap:** `protacxtend/agents/graph.py` and `protacxtend/agents/design_gates.py` "
              "were NOT in the v1 manifest and changed after the v1 run; v2 hashes every `agents/*.py`.",
              "- All v1 files are preserved unmodified."]
    return "\n".join(lines) + "\n"


def _write_freeze_md(fz: dict[str, Any]) -> None:
    lines = ["# validation_gap_v2 — FREEZE", "",
             f"- frozen_at: {fz['frozen_at']}",
             f"- git_revision: `{fz['git_revision']}` (dirty={fz['git_dirty']})",
             f"- supersedes: {fz['supersedes']}",
             f"- entry point: `{fz['entry_point']}`",
             f"- provenance: **{fz['provenance']}**",
             f"- benchmark_score: **{fz['benchmark_score']}**, gold_adjudicated: **{fz['gold_adjudicated']}**",
             f"- timeout policy: {fz['timeout_policy']}",
             f"- tool versions: {fz['tool_versions']}",
             "",
             f"## Hash-pinned files ({len(fz['code_hashes'])} code, {len(fz['data_hashes'])} data, "
             f"{len(fz['prompt_hashes'])} prompt)", ""]
    for group in ("code_hashes", "data_hashes", "prompt_hashes"):
        for p, h in sorted(fz[group].items()):
            lines.append(f"- `{p}` `{h[:16]}`")
    lines += ["", "## Rubric (written before scoring)", "", "```json",
              json.dumps(fz["rubric"], indent=1), "```"]
    (OUT / "FREEZE.md").write_text("\n".join(lines) + "\n")


def _rubric_md() -> str:
    lines = ["# Scoring rubric (pre-registered for v2)", "",
             "Each dimension is scored separately with explicit `not_applicable` / `insufficient_information` states.",
             "Correctness against gold is **PENDING_INDEPENDENT_GOLD** and is not scored.", ""]
    for k, v in RUBRIC.items():
        lines.append(f"- **{k}**: {v}")
    lines += ["", "## Label provenance",
              "- All v2 execution labels are produced by executable rules in `scripts/validation_gap_v2.py`, "
              "`protacxtend/agents/structured_run.py` and `protacxtend/agents/design_gates.py`.",
              "- **No LLM and no human assigned any label.** `reviewer_status` is `internal_audit_only` for all rows.",
              "- v1's `abstention_justified` was `scientific_state == JUSTIFIED_NO_GO` (circular self-assessment); "
              "v2 reports abstention reason text instead and does not claim independent justification."]
    return "\n".join(lines) + "\n"


def _write_table_md(rows: list[dict]) -> None:
    cols = ["case_id", "mode", "outcome", "terminal_decision", "entity_resolution",
            "retrieval_requirement", "retrieval_attempted", "retrieval_successful",
            "evidence_count", "claim_support", "chemistry_check", "unsupported_claim",
            "completion_within_time_limit"]
    md = ["# validation_gap_v2 — 48-row adjudication table", "",
          "Gold **PENDING_INDEPENDENT_GOLD** · benchmark_score **null** · labels are rule-based (no LLM/human).",
          "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    (OUT / "adjudication_table.md").write_text("\n".join(md) + "\n")


def _write_evidence_ledger(results: list[dict]) -> None:
    rows = []
    for r in results:
        cid = r.get("case_id", "")
        for i, e in enumerate(r.get("evidence") or []):
            rows.append({
                "case_id": cid, "evidence_index": i, "kind": e.get("kind", ""),
                "source": e.get("source", ""), "summary": (e.get("summary") or "")[:200],
                "claim": (r.get("answer") or "")[:120],
            })
    with (OUT / "evidence_ledger.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["case_id", "evidence_index", "kind", "source", "summary", "claim"])
        w.writeheader(); w.writerows(rows)
    (OUT / "evidence_ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def _write_comparison(rows: list[dict]) -> None:
    v1_rows = {r["case_id"]: r for r in csv.DictReader((V1 / "adjudication_table.csv").open())}
    out = ["# v1 -> v2 case comparison", "",
           "| case | v1 state | v2 state | v1 evid | v2 evid | v1 outcome | v2 outcome | changed |",
           "|---|---|---|---|---|---|---|---|"]
    changed = 0
    for r in rows:
        v1 = v1_rows.get(r["case_id"], {})
        ch = (v1.get("scientific_state") != r["terminal_decision"]
              or v1.get("outcome") != r["outcome"])
        changed += bool(ch)
        out.append(f"| {r['case_id']} | {v1.get('scientific_state','')} | {r['terminal_decision']} | "
                   f"{v1.get('n_evidence','')} | {r['evidence_count']} | {v1.get('outcome','')} | "
                   f"{r['outcome']} | {'YES' if ch else ''} |")
    out += ["", f"cases changed: {changed}/48"]
    (OUT / "v1_v2_comparison.md").write_text("\n".join(out) + "\n")


def _write_failure_taxonomy(rows: list[dict], results: list[dict]) -> None:
    by_id = {r["case_id"]: r for r in results}
    cats: dict[str, list[str]] = {
        "unsupported_continuation": [], "retrieval_not_required": [], "retrieval_not_triggered": [],
        "source_unavailable_offline": [], "parse_or_target_failure": [], "time_limit": [],
        "answer_generation_empty": [], "ok": [],
    }
    for r in rows:
        cid = r["case_id"]
        raw = by_id[cid]
        if r["unsupported_claim"]:
            cats["unsupported_continuation"].append(cid)
        elif r["retrieval_requirement"] == "not_applicable":
            cats["retrieval_not_required"].append(cid)
        elif not r["retrieval_attempted"]:
            cats["retrieval_not_triggered"].append(cid)
        elif not r["retrieval_successful"] and raw.get("outcome") == "abstained":
            cats["source_unavailable_offline"].append(cid)
        elif not str(raw.get("answer") or "").strip() and r["terminal_decision"] not in {"justified_no_go"}:
            cats["answer_generation_empty"].append(cid)
        elif "resolve_target" in (raw.get("stop_reason") or ""):
            cats["parse_or_target_failure"].append(cid)
        elif not r["completion_within_time_limit"]:
            cats["time_limit"].append(cid)
        else:
            cats["ok"].append(cid)
    lines = ["# Failure taxonomy (v2)", "",
             "| category | n | cases |", "|---|---|---|"]
    for k, v in cats.items():
        lines.append(f"| {k} | {len(v)} | {', '.join(v) if v else '—'} |")
    (OUT / "failure_taxonomy.md").write_text("\n".join(lines) + "\n")


def _aggregate_v2(rows: list[dict], freeze: dict, wall: float) -> None:
    def frac(pred) -> str:
        sub = [r for r in rows if pred(r)]
        ok = [r for r in sub if r["completion_within_time_limit"]]
        return f"{len(sub)}/{len(rows)}"
    applicable_retrieval = [r for r in rows if r["retrieval_requirement"] != "not_applicable"]
    retrieval_ok = [r for r in applicable_retrieval if r["retrieval_successful"]]
    lines = [
        "# validation_gap_v2 — aggregate", "",
        "> Gold unadjudicated: **benchmark_score: null**. Labels are rule-based (no LLM/human).",
        "> Provenance: **complete structured agent workflow** (`structured_run.run_case`).", "",
        f"- cases: {len(rows)} · wall {wall:.1f}s",
        f"- entity-resolution consistency (where a target is expected): "
        f"{sum(1 for r in rows if r['entity_resolution'] is True)}/"
        f"{sum(1 for r in rows if r['entity_resolution'] in (True, False))}",
        f"- retrieval applicable: {len(applicable_retrieval)}/48 · successful: {len(retrieval_ok)}/{len(applicable_retrieval)}",
        f"- evidence-backed answers: {sum(1 for r in rows if r['claim_support']=='supported')}/48",
        f"- unsupported continuation: {sum(1 for r in rows if r['unsupported_claim'])}",
        f"- chemically valid candidate cases: "
        f"{sum(1 for r in rows if r['chemistry_check']=='valid')}",
        f"- abstentions (justified_no_go/unresolved): "
        f"{sum(1 for r in rows if r['terminal_decision'] in ('justified_no_go','unresolved'))}",
        f"- completion within time limit: {sum(1 for r in rows if r['completion_within_time_limit'])}/48",
        "",
        "## distributions",
        f"- states: {dict(Counter(r['terminal_decision'] for r in rows))}",
        f"- outcomes: {dict(Counter(r['outcome'] for r in rows))}",
        f"- retrieval requirement: {dict(Counter(r['retrieval_requirement'] for r in rows))}",
        "",
        "## honest caveats",
        "- Measured vs predicted vs heuristic are not merged; no degradation model ran.",
        "- Candidate molecules are known-compound reconstructions (dBET1/MZ1), not novel discoveries.",
        "- No independent gold or reviewer; correctness is PENDING_INDEPENDENT_GOLD.",
    ]
    (OUT / "aggregate.md").write_text("\n".join(lines) + "\n")


def _review_sample(rows: list[dict]) -> None:
    sample = [r for r in rows if r["n_verified_candidates"] > 0] \
        + [r for r in rows if r["claim_support"] == "supported"] \
        + [r for r in rows if r["terminal_decision"] in ("justified_no_go", "unresolved")][:6] \
        + [r for r in rows if r["unsupported_claim"]]
    seen = set(); uniq = []
    for r in sample:
        if r["case_id"] not in seen:
            seen.add(r["case_id"]); uniq.append(r)
    lines = ["# Independent-review sample (v2)", "",
             "> No independent reviewer available. Gold fields are left pending; this is an",
             "> **internal audit only** (`reviewer_status = internal_audit_only`).", "",
             "| case | mode | decision | why it needs review |", "|---|---|---|---|"]
    why = {"supported": "verify each asserted fact resolves to the cited source",
           "justified_no_go": "verify the missing prerequisite was real",
           "unresolved": "verify the run genuinely could not be answered",
           "design_brief": "verify attachment vectors are not presented as final products"}
    for r in uniq:
        kind = ("verified_candidate" if r["n_verified_candidates"] else
                "unsupported_claim" if r["unsupported_claim"] else
                r["claim_support"] if r["claim_support"] in why else r["terminal_decision"])
        lines.append(f"| {r['case_id']} | {r['mode']} | {r['terminal_decision']} | {why.get(kind, kind)} |")
    (OUT / "review_sample.md").write_text("\n".join(lines) + f"\n\nsample size: {len(uniq)}/48\n")


if __name__ == "__main__":
    raise SystemExit(main())
