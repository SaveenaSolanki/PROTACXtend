"""Run matched per-task evaluations across engines on frozen tasks and emit a
per-task matrix (answer, cited evidence, score, error category, cost, latency).

Protocol exclusion (engine not applicable) is engine_ineligible; system
abstention is the engine running and declining with a reason; both are
reported separately and only system abstention is excluded from correctness
means under the frozen protocol.
"""
from __future__ import annotations

import argparse, csv, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmark" / "cases"

from benchmark_runner.grader import grade_answer  # noqa: E402
from benchmark_runner.adapters import ADAPTERS  # noqa: E402


def load_cases() -> list[dict]:
    out = []
    for p in sorted(CASES.glob("*.json")):
        if p.stem.startswith("_"):
            continue
        out.append(json.loads(p.read_text()))
    return out


def run_matrix(task_ids: list[str], engines: list[str], out_dir: str,
               llm_model: str = "deepseek-r1:7b") -> str:
    cases = {c["task_id"]: c for c in load_cases()}
    rows = []
    for tid in task_ids:
        case = cases[tid]
        q = case.get("scientific_question") or case.get("title") or ""
        for eng in engines:
            adapter = ADAPTERS[eng]
            t0 = time.monotonic()
            try:
                if eng == "llm_only":
                    r = adapter(q, model=llm_model)
                else:
                    r = adapter(q)
            except Exception as exc:
                r = {"answer": "", "status": "engine_error",
                     "latency_s": round(time.monotonic() - t0, 2), "cost_usd": 0.0}
            score = grade_answer(tid, r.get("answer", ""))
            row = {
                "task_id": tid, "capability": case.get("capability"),
                "engine": eng, "status": r.get("status"), "answer": (r.get("answer") or "")[:600],
                "evidence": "; ".join(r.get("evidence") or []),
                "cited_evidence": r.get("evidence") or [],
                "score": (score.get("score") if isinstance(score, dict) else score),
                "score_detail": json.dumps(score, default=str)[:300],
                "error_category": r.get("error_category", ""),
                "cost_usd": r.get("cost_usd", 0.0),
                "latency_s": r.get("latency_s", 0.0),
                "model": r.get("model", ""),
            }
            rows.append(row)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "matrix.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader(); w.writerows(rows)
    with open(os.path.join(out_dir, "matrix.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    return os.path.join(out_dir, "matrix.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True, help="comma-separated task ids")
    ap.add_argument("--engines", default="deterministic,llm_only,retrieval_only,tool_only,agentic")
    ap.add_argument("--out", default="outputs/audit_b1_e3/matched")
    ap.add_argument("--llm-model", default="deepseek-r1:7b")
    a = ap.parse_args()
    path = run_matrix(a.tasks.split(","), a.engines.split(","), a.out, a.llm_model)
    print(f"matrix: {path}")