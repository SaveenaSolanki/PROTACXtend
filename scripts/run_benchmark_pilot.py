#!/usr/bin/env python
"""Run a PROTACXtend-only benchmark pilot and grade it.

Two modes:

``--offline-smoke``
    Fast validation of the grading pipeline: grades each task's own authored
    ground-truth answer against its derived criteria.  No scientific pipeline
    is executed.  Use this to verify the scoring engine end-to-end.

default
    Runs the canonical PROTACXtend stack (deterministic engine) for each task
    and grades its emitted ``TherapeuticStrategy``.

Examples::

    python scripts/run_benchmark_pilot.py --offline-smoke
    python scripts/run_benchmark_pilot.py --limit 3 --capability DESIGN
    python scripts/run_benchmark_pilot.py --tasks DESIGN-01,KNOW-01

The full report is written under ``benchmark_results/pilots/``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark_runner.grader import grade_answer, load_ground_truth  # noqa: E402

CASES = ROOT / "benchmark" / "cases"
OUT_DIR = ROOT / "benchmark_results" / "pilots"


def _load_cases() -> List[Dict[str, Any]]:
    cases = []
    for path in sorted(CASES.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        cases.append(json.loads(path.read_text(encoding="utf-8")))
    return cases


def _answer_from_result(result: Dict[str, Any]) -> str:
    """Extract a gradeable answer string from a canonical run result.

    KNOW/REASON evidence is surfaced from the run's own scientific_answer
    (knowledge answer / identifier comparison / evidence cards) — never
    invented by the display layer — alongside the typed strategy."""
    strategy = result.get("therapeutic_strategy") or {}
    parts = []
    if strategy:
        parts.append(json.dumps(strategy, default=str))
    state = result.get("state") or {}
    sa = getattr(state, "scientific_answer", None) or {}
    if isinstance(sa, dict) and (sa.get("answer") or sa.get("identifier_comparison") or sa.get("evidence_cards")):
        parts.append(json.dumps({"scientific_answer": sa}, default=str))
    return (" || ".join(parts)) or json.dumps(result.get("summary") or result, default=str)


_STOPWORDS = {
    "which","what","are","the","for","with","and","that","this","these","those","from",
    "into","onto","does","whether","assess","explain","mechanistic","liabilities","retains",
    "critical","motifs","supplied","context","documented","family","via","use","any","all",
    "between","both","each","either","their","them","will","would","can","could","should",
}


def _question_tokens(question: str) -> list[str]:
    import re
    toks = []
    for t in re.split(r"[^A-Za-z0-9]+", (question or "").lower()):
        if len(t) >= 4 and t not in _STOPWORDS:
            toks.append(t)
    return toks


def _relevant(answer: str, question: str, grounded: dict) -> bool:
    """Relevance gate: the grounded KNOW/REASON answer must actually address
    the question's key terms, otherwise we abstain. Only GROUNDED knowledge
    content counts — the strategy JSON may echo the question and must not
    inflate relevance."""
    if not grounded:
        return False
    text = (" ".join(str(v) for v in grounded.values())).lower()
    q = _question_tokens(question)
    hits = [t for t in q if t in text]
    return len(hits) >= 2


def _grounded_knowledge_fields(result: Dict[str, Any]) -> dict:
    """Non-empty grounded KNOW/REASON evidence fields, or {} (unsupported)."""
    state = result.get("state") or {}
    sa = getattr(state, "scientific_answer", None) or {}
    if not isinstance(sa, dict):
        return {}
    out = {}
    for key in ("answer", "identifier_comparison", "evidence_cards"):
        if sa.get(key):
            out[key] = sa[key]
    return out


_ABSTAIN_CAPABILITIES = {"KNOW", "REASON"}


def _run_one(case: Dict[str, Any], engine: str) -> Dict[str, Any]:
    from protacxtend.agents.runtime import run_protacpilot

    question = case.get("scientific_question") or case.get("title") or ""
    capability = case.get("capability", "")
    started = time.monotonic()
    try:
        result = run_protacpilot(question, mode=engine,
                                 config={"record_run": False, "capability": capability})
        answer = _answer_from_result(result)
        grounded = _grounded_knowledge_fields(result)
        relevant = _relevant(answer, question, grounded)

        # Capability-specific retrieval + answer synthesis trace: KNOW/REASON
        # answers may only claim what retrieved, relevant evidence supports.
        # GOLD-FREE contract (2026-09-24): ground truth is NEVER loaded during
        # execution — retrieval queries, relevance judging and claim synthesis
        # use only the question; gold lives in the post-run grader/evaluator.
        evidence_trace = {}
        if capability in _ABSTAIN_CAPABILITIES:
            from protacxtend.evidence.trace import trace_query_to_evidence
            evidence_trace = trace_query_to_evidence(
                capability, question,
                required=[],   # inert metadata; never consumed during the run
                task=case["task_id"], offline=True)
            # synthesis gate: no claims from retrieval -> must abstain
            if evidence_trace.get("answer_claims"):
                claims_text = " || ".join(c["claim"] for c in evidence_trace["answer_claims"][:5])
                answer = claims_text + " || " + answer if answer else claims_text
                grounded = {"retrieved_claims": evidence_trace["answer_claims"]}
                relevant = True
        error = ""
        status = "ok"
        # KNOW/REASON honesty rule: the system ABSTAINS (a) when the knowledge
        # path produced no grounded evidence at all, or (b) when the grounded
        # answer is off-topic for the specific question (relevance gate). It
        # never lets a design-strategy JSON stand in as the answer.
        abstained = False
        abstention_reason = ""
        if capability in _ABSTAIN_CAPABILITIES:
            # Answer synthesis requires RETRIEVAL-SUPPORTED claims. Other state
            # text (strategy JSON, binder names) may echo question terms or
            # compound names and must not count as evidence.
            claims = (evidence_trace or {}).get("answer_claims") or []
            if not claims:
                abstained = True
                abstention_reason = (
                    "capability-specific retrieval produced no supporting evidence "
                    f"({len((evidence_trace or {}).get('results') or [])} tool calls inspected; "
                    f"{sum(1 for r in (evidence_trace or {}).get('results') or [] if r.get('relevance')=='supporting')} supporting); "
                    "abstained rather than answered with strategy text that is not retrieval-supported."
                )
        if abstained:
            answer = ""
    except Exception as exc:  # noqa: BLE001 - record, never crash the pilot
        answer = ""
        grounded = {}
        error = f"{type(exc).__name__}: {exc}"
        status = "failed"
        abstained = False
        abstention_reason = ""
    score = grade_answer(case["task_id"], answer)
    from protacxtend.evidence.evaluate import classify_outcome
    outcome = classify_outcome(evidence_trace, error)
    return {
        "task_id": case["task_id"],
        "capability": capability,
        "run_status": status,
        "abstained": abstained if status == "ok" else False,
        "abstention_reason": abstention_reason if abstained else "",
        "outcome": outcome,
        "grounded_knowledge_fields": sorted((grounded or {}).keys()),
        "evidence_trace": evidence_trace,
        "error": error,
        "latency_s": round(time.monotonic() - started, 2),
        "score": None if abstained else score,
    }


def _smoke_one(case: Dict[str, Any]) -> Dict[str, Any]:
    gt = load_ground_truth(case["task_id"])
    answer = str(gt.get("expected_answer") or "")
    score = grade_answer(case["task_id"], answer)
    return {
        "task_id": case["task_id"],
        "capability": case.get("capability", ""),
        "run_status": "offline_smoke",
        "error": "",
        "latency_s": 0.0,
        "score": score,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-smoke", action="store_true",
                        help="Grade authored GT answers instead of running the pipeline.")
    parser.add_argument("--engine", choices=["deterministic", "agentic"], default="deterministic")
    parser.add_argument("--capability", default="", help="Filter by capability (KNOW/REASON/DESIGN/DISCOVER).")
    parser.add_argument("--tasks", default="", help="Comma-separated task ids.")
    parser.add_argument("--limit", type=int, default=0, help="Max tasks (0 = all).")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    cases = _load_cases()
    if args.capability:
        cases = [c for c in cases if c.get("capability") == args.capability]
    if args.tasks:
        wanted = {t.strip() for t in args.tasks.split(",") if t.strip()}
        cases = [c for c in cases if c["task_id"] in wanted]
    if args.limit:
        cases = cases[: args.limit]

    results = []
    for case in cases:
        results.append(_smoke_one(case) if args.offline_smoke else _run_one(case, args.engine))

    scored = [r["score"]["score"] for r in results if r.get("score") is not None and r["score"].get("score") is not None]
    abstained = [r for r in results if r.get("abstained")]
    mean = round(sum(scored) / len(scored), 4) if scored else None
    # Fixed-denominator outcome buckets. Denominator = every KNOW/REASON case
    # that produced a retrieval trace (design/discover cases have no retrieval
    # path and are reported separately, never folded into answer buckets).
    from protacxtend.evidence.evaluate import fixed_denominator_report
    traced = [r for r in results if r.get("evidence_trace") is not None and (
        r.get("evidence_trace") or {}).get("results") is not None]
    fd_report = fixed_denominator_report([
        {"task_id": r["task_id"], "trace": r.get("evidence_trace") or {},
         "error": r.get("error") or "", "status": r.get("run_status")} for r in traced])
    report = {
        "schema_version": "2.0.0-gold-free",
        "system": "PROTACXtend",
        "engine": "offline-smoke" if args.offline_smoke else args.engine,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "n_tasks": len(results),
        "n_scored": len(scored),
        "n_abstained": len(abstained),
        "mean_score": mean,
        "gold_access": {
            "during_execution": False,
            "note": "ground truth loaded ONLY by the post-run grader/evaluator (benchmark_runner.grader.grade_answer, protacxtend.evidence.evaluate)",
        },
        "fixed_denominator_outcomes": fd_report,
        "results": results,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out_dir / f"pilot_{report['engine']}_{stamp}.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"tasks={report['n_tasks']} scored={report['n_scored']} mean_score={mean}")
    print("fixed-denominator outcomes:", json.dumps(fd_report["buckets"]))
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
