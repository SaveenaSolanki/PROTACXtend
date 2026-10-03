#!/usr/bin/env python
"""Close the validation gap: frozen 48-case run + gold-independent adjudication.

Runs all 48 closed cases through the same structured entry point
(``protacxtend.agents.structured_run.run_case``) that the CLI/TUI request path
uses, preserves per-case records, and scores seven dimensions *separately*.

Gold is NOT available: every correctness judgement is marked
``PENDING_INDEPENDENT_GOLD`` and ``benchmark_score`` stays ``null``. This script
reports execution facts only.

Provenance is explicit: results here come from the **complete structured agent
workflow**, not from the controlled contract runner
(``protacxtend/contracts/run.py``).

Usage::

    python scripts/close_validation_gap.py --workers 8 --budget 120
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

CASES = ROOT / "benchmark" / "cases"
OUT_DEFAULT = ROOT / "benchmark_results" / "validation_gap_v1"

FREEZE_FILES = [
    "protacxtend/agents/structured_run.py",
    "protacxtend/agents/entity_resolution.py",
    "protacxtend/agents/target_agent.py",
    "protacxtend/contracts/entities.py",
    "protacxtend/contracts/assembly.py",
    "protacxtend/contracts/run.py",
    "protacxtend/run_records.py",
    "scripts/build_verified_components.py",
]
FREEZE_DATA = [
    "protacxtend/data/verified_components.json",
    "protacxtend/data/curated_targets.csv",
    "protacxtend/data/curated_e3_ligands.csv",
    "protacxtend/data/curated_warheads.csv",
]

RUBRIC = {
    "entity_resolution": "resolved POI/E3 gene symbols match the case's expected identities",
    "supported_retrieval": "every asserted retrieval has a source and a retrievable record",
    "chemically_valid_assembly": "each applicable candidate has a valid, sanitizable complete SMILES",
    "evidence_backed_final_answer": "final state is supported by >=1 source-backed evidence item",
    "appropriate_abstention": "abstention is justified by a recorded missing prerequisite",
    "unsupported_continuation": "no design claim is made without structure+evidence",
    "completion_within_time_limit": "terminal status reached within the per-case budget",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_rev() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _versions() -> dict[str, str]:
    out: dict[str, str] = {"python": sys.version.split()[0]}
    for mod in ("rdkit", "pandas", "numpy", "sklearn"):
        try:
            out[mod] = __import__(mod).__version__
        except Exception:
            out[mod] = "missing"
    return out


def freeze(workers: int, budget: float) -> dict[str, Any]:
    return {
        "schema": "validation_gap.freeze.v1",
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_revision": _git_rev(),
        "code_hashes": {p: _sha256(ROOT / p) for p in FREEZE_FILES if (ROOT / p).exists()},
        "data_hashes": {p: _sha256(ROOT / p) for p in FREEZE_DATA if (ROOT / p).exists()},
        "tool_versions": _versions(),
        "timeout_policy": {"per_case_budget_s": budget, "workers": workers,
                           "retry_policy": "no silent retry/repair; every retry recorded in stage_ledger"},
        "entry_point": "protacxtend.agents.structured_run.run_case (complete structured agent workflow)",
        "provenance": "complete_agent_workflow",
        "rubric": RUBRIC,
        "gold_adjudicated": False,
        "benchmark_score": None,
    }


def _valid_smiles(smiles: str) -> bool:
    try:
        from rdkit import Chem
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")
        return bool(smiles) and Chem.MolFromSmiles(smiles) is not None
    except Exception:
        return False


def _worker(task_id: str, budget: float) -> dict[str, Any]:
    import os
    os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")
    from protacxtend.agents.structured_run import run_case

    case = json.loads((CASES / f"{task_id}.json").read_text(encoding="utf-8"))
    t0 = time.time()
    try:
        result = run_case(case, capability=case.get("capability", ""), offline=True, budget_s=budget)
    except Exception as exc:  # never crash the sweep; record the terminal failure
        result = {"case_id": task_id, "status": "error", "outcome": "error",
                  "error": f"{type(exc).__name__}: {exc}", "scientific_state": "invalid_run",
                  "evidence": [], "warnings": [], "errors": [str(exc)]}
    result["wall_s"] = round(time.time() - t0, 3)
    return result


def _adjudicate(result: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Gold-independent execution facts, one row per case."""
    state = str(result.get("scientific_state") or "")
    evidence = result.get("evidence") or []
    n_candidates = int(result.get("n_candidates") or 0)
    n_verified = int(result.get("n_verified_candidates") or 0)
    verified_smiles = result.get("verified_candidate_smiles") or []
    outcome = str(result.get("outcome") or result.get("status") or "")
    elapsed = float(result.get("elapsed_s") or result.get("wall_s") or 0.0)
    budget = float(result.get("budget_s") or 0.0)
    over_budget = bool(result.get("over_budget")) or outcome == "timeout"

    entity = result.get("entity_resolution") or {}
    # Gold-independent consistency check: the *resolved* target must match the
    # parsed target, and an E3 must match when the case names E3 candidate(s).
    # Cases that name no target return "n/a" (never a silent True).
    expected_target = str(entity.get("target") or "").strip()
    resolved = result.get("resolved_target") or {}
    resolved_name = str(resolved.get("target_name") or "").strip()
    expected_e3 = [str(e).upper() for e in (entity.get("e3_ligases") or [])]
    resolved_e3 = str(result.get("resolved_e3") or "").upper()
    if not expected_target:
        entity_ok: Any = "n/a"
    elif result.get("error"):
        entity_ok = False
    else:
        entity_ok = bool(resolved_name) and resolved_name.upper() == expected_target.upper()
        if entity_ok and expected_e3:
            entity_ok = bool(resolved_e3) and resolved_e3 in expected_e3

    supported_retrieval = len(evidence) > 0
    chemical_valid = ("n/a" if n_candidates == 0
                      else all(_valid_smiles(s) for s in verified_smiles) if verified_smiles
                      else False)
    evidence_backed = state in {"supported_answer", "valid_candidate", "conditional_hypothesis",
                                "justified_no_go", "design_brief"} and len(evidence) > 0
    abstained = outcome in {"abstained", "timeout"} or state in {"justified_no_go", "design_brief", "abstained"}
    appropriate_abstention = (bool(result.get("abstention_justified")) if abstained else "n/a")
    unsupported_continuation = bool(
        state == "valid_candidate" and not verified_smiles
    ) or bool(result.get("unsupported_continuation"))
    completion = (not over_budget) and outcome not in {"timeout", "error"}

    return {
        "case_id": result.get("case_id", case.get("task_id", "")),
        "capability": case.get("capability", ""),
        "question": (case.get("scientific_question") or "")[:120],
        "outcome": outcome,
        "scientific_state": state,
        "classification": _classification(state, n_verified, abstained, result),
        "entity_resolution_consistent": entity_ok,
        "supported_retrieval": supported_retrieval,
        "chemically_valid_assembly": chemical_valid,
        "evidence_backed_final_answer": evidence_backed,
        "appropriate_abstention": appropriate_abstention,
        "unsupported_continuation": unsupported_continuation,
        "completion_within_time_limit": completion,
        "n_evidence": len(evidence),
        "n_candidates": n_candidates,
        "n_verified_candidates": n_verified,
        "elapsed_s": round(elapsed, 2),
        "correctness": "PENDING_INDEPENDENT_GOLD",
        "provenance": "complete_agent_workflow",
    }


def _classification(state: str, n_verified: int, abstained: bool, result: dict[str, Any]) -> str:
    if state == "valid_candidate" and n_verified > 0:
        return "verified_candidate"
    if state == "design_brief":
        return "design_brief"
    if state in {"justified_no_go", "abstained"} or abstained:
        return "abstention"
    if state == "invalid_run" or result.get("error"):
        return "invalid_run"
    if state == "conditional_hypothesis":
        return "conditional_hypothesis"
    if state == "supported_answer":
        return "supported_answer"
    return state or "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--budget", type=float, default=120.0)
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()

    out = args.out_dir
    (out / "cases").mkdir(parents=True, exist_ok=True)
    case_ids = sorted(p.stem for p in CASES.glob("*.json") if not p.stem.startswith("_"))
    print(f"running {len(case_ids)} cases · budget {args.budget}s · workers {args.workers}")

    freeze_payload = freeze(args.workers, args.budget)
    (out / "freeze.json").write_text(json.dumps(freeze_payload, indent=2))

    results: list[dict[str, Any]] = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(_worker, cid, args.budget): cid for cid in case_ids}
        for fut in as_completed(futs):
            res = fut.result()
            results.append(res)
            cid = res.get("case_id", futs[fut])
            (out / "cases" / f"{cid}.json").write_text(json.dumps(res, indent=2, default=str))
    results.sort(key=lambda r: r.get("case_id", ""))
    (out / "results.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in results))

    # 48-row adjudication table
    rows = []
    for res in results:
        cid = res.get("case_id", "")
        case_path = CASES / f"{cid}.json"
        case = json.loads(case_path.read_text()) if case_path.exists() else {}
        rows.append(_adjudicate(res, case))
    fieldnames = list(rows[0].keys()) if rows else []
    with (out / "adjudication_table.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # markdown table
    md = ["# 48-case adjudication table (validation_gap_v1)", "",
          f"provenance: **complete structured agent workflow** · git `{freeze_payload['git_revision'][:12]}` · "
          f"budget {args.budget}s · gold **PENDING_INDEPENDENT_GOLD**",
          f"benchmark_score: **null**", "",
          "| case | cap | outcome | state | classification | entity | retrieval | chem | evidence | abstain | unsupported | complete |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append("| {case_id} | {capability} | {outcome} | {scientific_state} | {classification} | "
                  "{entity_resolution_consistent} | {supported_retrieval} | {chemically_valid_assembly} | "
                  "{evidence_backed_final_answer} | {appropriate_abstention} | {unsupported_continuation} | "
                  "{completion_within_time_limit} |".format(**r))
    (out / "adjudication_table.md").write_text("\n".join(md) + "\n")

    _aggregate(out, rows, freeze_payload, time.time() - t0)
    print(f"wrote {out}")
    return 0


def _aggregate(out: Path, rows: list[dict], freeze_payload: dict, wall: float) -> None:
    def frac(key: str) -> str:
        vals = [r[key] for r in rows if r[key] in (True, False)]
        if not vals:
            return "n/a"
        return f"{sum(1 for v in vals if v)}/{len(vals)}"

    states = Counter(r["scientific_state"] for r in rows)
    classes = Counter(r["classification"] for r in rows)
    outcomes = Counter(r["outcome"] for r in rows)
    failures = [r for r in rows if r["outcome"] in ("timeout", "error")]
    unsupported = [r for r in rows if r["unsupported_continuation"]]
    chem = [r for r in rows if r["chemically_valid_assembly"] is True and r["n_candidates"]]

    lines = [
        "# validation_gap_v1 — aggregate (execution facts only)", "",
        "> Gold is not adjudicated. **benchmark_score: null.** No correctness is claimed.",
        "> Provenance: **complete structured agent workflow** (`structured_run.run_case`),",
        "> not the controlled contract runner.",
        "",
        f"- cases: {len(rows)}",
        f"- wall time: {wall:.1f}s",
        f"- entity resolution consistency (resolved == parsed where a target is expected): {frac('entity_resolution_consistent')}",
        f"- supported retrieval (>=1 sourced evidence): {frac('supported_retrieval')}",
        f"- chemically valid assembly (applicable cases): {frac('chemically_valid_assembly')}",
        f"- evidence-backed final answer: {frac('evidence_backed_final_answer')}",
        f"- appropriate abstention (of abstentions): {frac('appropriate_abstention')}",
        f"- unsupported continuation: {sum(1 for r in rows if r['unsupported_continuation'])} (must be 0)",
        f"- completion within time limit: {frac('completion_within_time_limit')}",
        "",
        "## distributions",
        f"- outcomes: {dict(outcomes)}",
        f"- scientific states: {dict(states)}",
        f"- classifications: {dict(classes)}",
        "",
        "## failure analysis",
    ]
    if failures:
        for r in failures:
            lines.append(f"- {r['case_id']} ({r['capability']}): {r['outcome']} — {r['scientific_state']}")
    else:
        lines.append("- no timeout/error cases")
    lines += ["", "## unsupported continuation (must be empty)"]
    lines += [f"- {r['case_id']}: state={r['scientific_state']}" for r in unsupported] or ["- none"]
    lines += ["", "## frozen environment",
              f"- git: {freeze_payload['git_revision']}",
              f"- tool versions: {freeze_payload['tool_versions']}",
              f"- timeout policy: {freeze_payload['timeout_policy']}",
              "",
              "## caveat",
              "- `research`-grade claim: these are execution facts; correctness requires independent gold.",
              f"- Cases with a verified candidate: {', '.join(r['case_id'] for r in chem) or 'none'}"]
    (out / "aggregate.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
