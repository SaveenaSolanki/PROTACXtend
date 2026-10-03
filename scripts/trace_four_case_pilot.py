#!/usr/bin/env python3
"""Trace the frozen four-case pilot (KNOW-06, REASON-03, REASON-05, DISCOVER-04)
from input -> routing -> retrieval -> tools -> synthesis -> rubric.

Modes:
  node   : run the deterministic graph with capability routing + node trace
  pilot  : run the exact pilot path (run_protacpilot -> canonical strategy) and
           grade with benchmark_runner.grader
Use --tag to label the run (e.g., before|after) for output files.
"""
from __future__ import annotations

import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "docs", "architecture", "benchmark_traces")
os.makedirs(OUTDIR, exist_ok=True)

TASKS = ["KNOW-06", "REASON-03", "REASON-05", "DISCOVER-04"]


def load_case(task):
    with open(os.path.join(ROOT, "benchmark", "cases", f"{task}.json")) as f:
        return json.load(f)


def grade(task, answer):
    sys.path.insert(0, ROOT)
    from benchmark_runner.grader import grade_answer
    return grade_answer(task, answer)


def trace_node_graph(question, capability, tag, task):
    sys.path.insert(0, ROOT)
    import warnings; warnings.filterwarnings("ignore")
    from protacxtend.agents.graph import run_syn_glue_workflow
    traces = []
    state = run_syn_glue_workflow(question, capability=capability or "", trace=traces)
    return {
        "task": task, "capability": capability or "(engine default)",
        "nodes": traces,
        "n_nodes_entered": len(traces),
        "state": {
            "target": getattr(state, "target_record", None) and getattr(state.target_record, "gene_symbol", "") or "",
            "n_binders": len(state.retrieved_binders or []),
            "n_warheads": len(state.selected_warheads or []),
            "n_candidates": len(state.final_ranked_candidates or []),
            "scientific_answer": bool(getattr(state, "scientific_answer", None)),
            "errors_tail": list(state.errors or [])[-3:],
        },
    }


def trace_pilot(task, tag):
    sys.path.insert(0, ROOT)
    from scripts.run_benchmark_pilot import _run_one, _load_cases
    cases = [c for c in _load_cases() if c["task_id"] == task]
    assert cases, f"case {task} missing"
    case = cases[0]
    result = _run_one(case, "deterministic")   # current pilot path (pre/post patch same call)
    return {"task": task, "capability": case.get("capability"), "result": result}


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "before"
    mode = sys.argv[2] if len(sys.argv) > 2 else "both"
    out = {"tag": tag, "tasks": []}
    for task in TASKS:
        case = load_case(task)
        rec = {"task": task, "capability": case.get("capability"),
               "question": case.get("scientific_question")}
        if mode in ("node", "both"):
            rec["node_trace"] = trace_node_graph(case.get("scientific_question", ""),
                                                 case.get("capability", ""), tag, task)
        if mode in ("pilot", "both"):
            rec["pilot"] = trace_pilot(task, tag)
            res = rec["pilot"]["result"]
            if res.get("abstained"):
                rec["rubric"] = {"score": None, "status": "abstained",
                                 "reason": res.get("abstention_reason", "")}
            elif res.get("score") is not None and isinstance(res.get("score"), dict):
                rec["rubric"] = {k: res["score"].get(k) for k in ("score", "status", "method", "dimensions", "requires_expert_review")}
            else:
                ans = res.get("answer", "")
                g = grade(task, ans)
                rec["rubric"] = {k: g.get(k) for k in ("score", "status", "method", "dimensions", "requires_expert_review")}
        out["tasks"].append(rec)
    path = os.path.join(OUTDIR, f"four_case_{tag}.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("wrote", path)
    for rec in out["tasks"]:
        print(rec["task"], rec["capability"], "rubric:", rec.get("rubric", {}).get("score"))


if __name__ == "__main__":
    main()