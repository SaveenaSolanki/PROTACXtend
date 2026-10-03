"""Stage-level diagnostic: zero-candidate scientific-mode case (pre-fix).

Reproduces the exact manuscript case:
  python -m protacxtend.cli --execution-mode scientific strategy \
    "Design a VHL PROTAC against BRD4"
and records candidate counts after every graph stage: parsing, target/E3
resolution, binder retrieval, warhead selection, linker generation,
construction, validity, filters, structural checks, ranking.
"""
from __future__ import annotations

import json
import sys
import time

from protacxtend.agents.graph import LocalSynGlueWorkflowGraph
from protacxtend.backend.schemas import WorkflowState
from protacxtend.runtime import modes

REQUEST = "Design a VHL PROTAC against BRD4"

def stage_counts(state: WorkflowState) -> dict:
    return {
        "retrieved_binders": len(state.retrieved_binders),
        "selected_warheads": len(state.selected_warheads),
        "selected_e3_ligands": len(state.selected_e3_ligands),
        "generated_linkers": len(state.generated_linkers),
        "assembled_candidates": len(state.assembled_candidates),
        "valid_candidates": len(state.valid_candidates),
        "evolved_candidates": len(state.evolved_candidates),
        "admet_predictions": len(state.admet_predictions),
        "ranking_results": len(state.ranking_results),
        "final_ranked_candidates": len(state.final_ranked_candidates),
        "degradation_predictions": len(state.degradation_predictions),
        "ternary_feasibility_results": len(state.ternary_feasibility_results),
    }

def main() -> int:
    modes.set_execution_mode("scientific")
    graph = LocalSynGlueWorkflowGraph()
    # DESIGN-capability node order (same as production routing for a design request)
    from protacxtend.agents.graph import CAPABILITY_NODES
    wanted = set(CAPABILITY_NODES["DESIGN"])
    nodes = [(n, f) for n, f in graph.nodes if n in wanted]
    state = WorkflowState(user_request=REQUEST)
    trace = []
    report = {"request": REQUEST, "execution_mode": "scientific", "stages": []}
    t0 = time.time()
    for node_name, node in nodes:
        started = time.time()
        pre = stage_counts(state)
        state = node(state)
        elapsed = round(time.time() - started, 3)
        post = stage_counts(state)
        report["stages"].append({
            "node": node_name,
            "elapsed_s": elapsed,
            "pre": pre,
            "post": post,
            "summary": " | ".join(
                [f"{k}={v}" for k, v in post.items() if v != pre.get(k)]
            ),
            "errors": list(state.errors),
            "warnings_tail": [w for w in state.warnings[-6:]],
        })
        trace.append({"node": node_name, "elapsed_s": elapsed,
                      "errors": list(state.errors)})
        if graph._should_stop(state):
            report["stopped_after"] = node_name
            report["stop_reason"] = [e for e in state.errors if any(
                m in e for m in ["Planner requires", "No warheads", "No E3",
                                 "No PROTAC", "No valid"])]
            break
    report["total_s"] = round(time.time() - t0, 2)
    report["final"] = stage_counts(state)
    report["final_errors"] = list(state.errors)
    report["final_warnings"] = list(state.warnings)
    # warhead source census
    ws = [w.model_dump() if hasattr(w, "model_dump") else dict(w)
          for w in state.selected_warheads]
    report["warhead_sources"] = sorted({w.get("source", "?") for w in ws})
    report["warhead_names"] = [w.get("name") for w in ws]
    if state.retrieved_binders:
        b0 = state.retrieved_binders[0]
        report["first_binder"] = {
            "name": b0.name, "source": b0.source,
            "activity_nM": b0.activity_nM, "p_activity": b0.p_activity,
        }
    out = sys.argv[1] if len(sys.argv) > 1 else "outputs/manuscript_strategy/diagnostic_zero_candidate_pre_fix.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=1, default=str)
    print(json.dumps({"stopped_after": report.get("stopped_after"),
                      "final": report["final"],
                      "stop_reason": report.get("stop_reason")}, indent=1))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())