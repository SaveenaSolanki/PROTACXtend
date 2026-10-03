#!/usr/bin/env python
"""Gate C / Gate D pilot runner — four question-matched cases.

Executes one case per capability through its matched agent tool in SCIENTIFIC
mode, records the typed outcome and full provenance, and checks the case's
*declared expected behaviour* (e.g. typed abstention, reviewed accession,
known-negative design). It deliberately emits **no benchmark score**: gold for
all four cases is ``PENDING_INDEPENDENT_REVIEW`` until the Gate C reviewer
decisions are signed.

``expected_behavior`` is a pipeline-integrity assertion, not a scientific
grade. The output distinguishes:

  executed_valid        tool ran, schema-valid output
  executed_partial      tool ran, returned a typed partial/warning
  executed_invalid      tool ran but output failed validity checks
  typed_abstention      typed MissingScientificInput (correct for unanswerable)
  typed_refusal         typed SyntheticInputNotAllowed / FixtureUsageError
  failed                tool raised an unexpected error

Usage::

    PROTACXTEND_EXECUTION_MODE=scientific python scripts/gateC_pilot.py --out-dir benchmark_results/gateC_pilot
    python scripts/gateC_pilot.py --online          # permit network retrieval
    python scripts/gateC_pilot.py --cases benchmark/gateC/pilot
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")

DEFAULT_CASES = ROOT / "benchmark" / "gateC" / "pilot"
DEFAULT_OUT = ROOT / "benchmark_results" / "gateC_pilot"


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return ""


def _classify(exc: BaseException) -> str:
    from protacxtend.runtime.modes import (
        FixtureUsageError,
        MissingScientificInput,
        SyntheticInputNotAllowed,
    )
    if isinstance(exc, MissingScientificInput):
        return "typed_abstention"
    if isinstance(exc, (SyntheticInputNotAllowed, FixtureUsageError)):
        return "typed_refusal"
    return "failed"


def _run_case(case: Dict[str, Any], allow_network: bool) -> Dict[str, Any]:
    from protacxtend.runtime.agent_tools import run_agent_tool

    started = time.time()
    outcome_kind = ""
    failure_code = ""
    error = ""
    result: Dict[str, Any] = {}
    try:
        result = run_agent_tool(case["matched_tool"], case.get("tool_params") or {},
                                allow_network=allow_network)
        status = str(result.get("status", ""))
        valid = bool(result.get("VALID_OUTPUT"))
        if status == "ok" and valid:
            outcome_kind = "executed_valid"
        elif status in {"ok", "partial"} and valid:
            outcome_kind = "executed_partial"
        else:
            outcome_kind = "executed_invalid"
        failure_code = str(result.get("failure_code", ""))
    except BaseException as exc:  # noqa: BLE001 - record, never crash
        outcome_kind = _classify(exc)
        error = f"{type(exc).__name__}: {exc}"
        failure_code = type(exc).__name__

    expected = case.get("expected_behavior", "")
    behavior_match = _behavior_match(expected, outcome_kind, result)

    return {
        "pilot_id": case["pilot_id"],
        "source_task": case["source_task"],
        "capability": case["capability"],
        "matched_tool": case["matched_tool"],
        "execution_mode": os.environ.get("PROTACXTEND_EXECUTION_MODE", ""),
        "outcome_kind": outcome_kind,
        "failure_code": failure_code,
        "error": error,
        "expected_behavior": expected,
        "behavior_match": behavior_match,
        "known_negative": bool(case.get("known_negative")),
        "intentional_missing_input": bool(case.get("intentional_missing_input")),
        "latency_s": round(time.time() - started, 3),
        "tool_result": result,
        "scientific_conclusion": "PENDING_INDEPENDENT_REVIEW",
        "gold_status": "PENDING_INDEPENDENT_REVIEW",
        "score": None,
        "score_note": "not scored; requires independently adjudicated gold (Gate C)",
    }


def _behavior_match(expected: str, outcome_kind: str, result: Dict[str, Any]) -> Any:
    if not expected:
        return None
    if expected == "typed_abstention_MISSING_SCIENTIFIC_INPUT":
        return outcome_kind == "typed_abstention"
    if expected == "resolved_reviewed_human_accession":
        data = ((result.get("scientific_result") or {}).get("result") or {}).get("data") or {}
        matches = data.get("matches") or []
        return any(str(m.get("accession")) == "O60885" and
                   str(m.get("organism", "")).lower().startswith("homo") for m in matches)
    if expected == "deterministic_ranking_under_budget":
        data = ((result.get("scientific_result") or {}).get("result") or {}).get("data") or {}
        ranking = data.get("ranking") or data.get("ranked") or data.get("candidates")
        return outcome_kind in {"executed_valid", "executed_partial"} and bool(ranking or data)
    if expected == "linker_hypotheses_around_known_negative_warhead":
        data = ((result.get("scientific_result") or {}).get("result") or {}).get("data") or {}
        linkers = data.get("linkers") or []
        return len(linkers) > 0
    return None


def _load_cases(cases_dir: Path) -> List[Dict[str, Any]]:
    out = []
    for path in sorted(cases_dir.glob("*.json")):
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--online", action="store_true", help="permit network retrieval")
    ap.add_argument("--run-id", default="")
    args = ap.parse_args()

    cases = _load_cases(args.cases)
    if not cases:
        print(f"no pilot cases found under {args.cases}", file=sys.stderr)
        return 2

    run_id = args.run_id or f"gateC_pilot_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out = args.out_dir / run_id
    out.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc).isoformat()
    predictions = [_run_case(c, allow_network=args.online) for c in cases]

    with (out / "predictions.jsonl").open("w", encoding="utf-8") as fh:
        for p in predictions:
            fh.write(json.dumps(p, ensure_ascii=False, default=str) + "\n")
    with (out / "tool_runs.jsonl").open("w", encoding="utf-8") as fh:
        for p in predictions:
            fh.write(json.dumps({
                "pilot_id": p["pilot_id"], "tool": p["matched_tool"],
                "outcome_kind": p["outcome_kind"], "failure_code": p["failure_code"],
                "behavior_match": p["behavior_match"], "latency_s": p["latency_s"],
            }, default=str) + "\n")

    matches = [p["behavior_match"] for p in predictions if p["behavior_match"] is not None]
    manifest = {
        "run_id": run_id,
        "schema_version": "gateC.pilot_run.v1",
        "git_commit": _git(),
        "python": platform.python_version(),
        "host": socket.gethostname(),
        "execution_mode": os.environ.get("PROTACXTEND_EXECUTION_MODE", ""),
        "online": args.online,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "n_cases": len(predictions),
        "outcome_counts": {k: sum(1 for p in predictions if p["outcome_kind"] == k)
                           for k in sorted({p["outcome_kind"] for p in predictions})},
        "behavior_match": f"{sum(1 for m in matches if m)}/{len(matches)}",
        "benchmark_score": None,
        "score_note": "Gate C pilot: no benchmark score is emitted; gold is PENDING_INDEPENDENT_REVIEW.",
        "gold_status": "PENDING_INDEPENDENT_REVIEW",
        "artifacts": ["predictions.jsonl", "tool_runs.jsonl"],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (out / "README.md").write_text(
        "# Gate C pilot run\n\n"
        "Four question-matched cases executed once. **No benchmark score.** "
        "Scientific conclusions are pending independent gold adjudication.\n\n"
        f"- run_id: `{run_id}`\n"
        f"- cases: {len(predictions)}\n"
        f"- behavior_match (pipeline integrity): `{manifest['behavior_match']}`\n"
        f"- outcomes: `{manifest['outcome_counts']}`\n",
        encoding="utf-8",
    )

    print(json.dumps({k: manifest[k] for k in (
        "run_id", "n_cases", "outcome_counts", "behavior_match",
        "benchmark_score", "gold_status")}, indent=2))
    print(f"artifacts: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
