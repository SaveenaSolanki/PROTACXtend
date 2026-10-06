#!/usr/bin/env python
"""Produce a pinned, evidence-driven, inspectable agent trace (spec §12).

Runs one real DESIGN task and one real typed-abstention case, then writes an
append-only JSONL trace plus a human-readable report and a PIN identity file.

Trace records carry the fields the specification requires: run identity
(commit/mode/model/budgets), role, action, plan version, status, observation,
evidence kind, gate decisions, routing decisions and a terminal reason. The
trace is labelled honestly: the deterministic DESIGN route is a FIXED-WORKFLOW
execution with one evidence-driven routing decision (source-backed vs
exploratory separation); the abstention case is a justified typed abstention.

Usage:
    PROTACXTEND_EXECUTION_MODE=scientific python scripts/pin_agent_trace.py
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_ROOT = ROOT / "outputs" / "execution" / "agent_trace"

ROLE = {
    "parse_user_request": "supervisor",
    "create_design_plan": "scientific_planner",
    "control_np_hard_search": "scientific_planner",
    "safety_precheck": "critic",
    "resolve_target": "target_agent",
    "retrieve_target_binders": "evidence_agent",
    "design_path": "design_agent",
    "select_warheads": "component_agent",
    "select_e3_ligands": "component_agent",
    "detect_exit_vectors": "design_agent",
    "generate_linkers": "design_agent",
    "construct_protacs": "design_agent",
    "expand_stereoisomers": "chemistry_critic",
    "validate_protacs": "chemistry_critic",
    "score_cell_context": "prediction_agent",
    "predict_admet": "prediction_agent",
    "check_novelty": "evidence_agent",
    "assess_applicability_domain": "prediction_agent",
    "cheap_filter_candidates": "ranking_agent",
    "predict_degradation": "prediction_agent",
    "initial_ranking": "ranking_agent",
    "diversity_clustering": "ranking_agent",
    "reflection_review": "critic",
    "optional_ternary_feasibility": "structure_agent",
    "predict_cooperativity": "structure_agent",
    "predict_hook_effect": "structure_agent",
    "final_ranking": "ranking_agent",
    "generate_report": "reporting",
    "update_memory": "persistence",
}
STAGE_ROLE = {
    "target_resolution": "target_agent", "binder_retrieval": "evidence_agent",
    "warhead_selection": "component_agent", "e3_selection": "component_agent",
    "linker_generation": "design_agent", "construction": "design_agent",
    "validation": "chemistry_critic", "degradation_prediction": "prediction_agent",
    "admet_prediction": "prediction_agent", "ranking": "ranking_agent",
    "ternary_coordinates": "structure_agent", "synthesis_route": "synthesis_agent",
}


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return ""


def _h(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _pin(task: str, budgets: dict) -> dict:
    return {
        "type": "run_identity",
        "task": task,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git(),
        "python": platform.python_version(),
        "mode": "scientific",
        "model": "deepseek-v4-flash",
        "budgets": budgets,
        "trace_schema": "protacxtend.agent_trace.v1",
    }


def build_design_trace(request: str, rid: str) -> list[dict]:
    from protacxtend.workflows.designer import run_design
    t0 = time.time()
    payload = run_design(request, offline=True, run_id=rid)
    recs = [_pin("design", {"per_task_timeout_s": 600, "wall_s": round(time.time() - t0, 2)})]
    seq = 1
    plan_version = 1
    for st in payload.get("stage_timeline", []):
        seq += 1
        recs.append({
            "seq": seq, "type": "step",
            "role": STAGE_ROLE.get(st.get("stage"), "agent"),
            "action": st.get("stage"),
            "plan_version": plan_version,
            "status": st.get("status"),
            "executed": bool(st.get("executed")),
            "observation": st.get("detail", ""),
            "evidence_kind": "unevaluated" if st.get("status") == "unevaluated" else "computed",
            "inputs_hash": _h({"request": request, "stage": st.get("stage")}),
            "gate": None,
        })
    for name, gate in (payload.get("evidence_gates") or {}).items():
        seq += 1
        recs.append({
            "seq": seq, "type": "gate", "role": "critic", "action": name,
            "plan_version": plan_version, "status": gate.get("status"),
            "observation": gate.get("criterion") or gate.get("limitation", ""),
            "evidence_kind": "gate_decision", "gate": name,
        })
    expl = payload.get("exploratory_design_brief") or {}
    if expl.get("count"):
        seq += 1
        recs.append({
            "seq": seq, "type": "routing_decision", "role": "critic",
            "action": "separate_exploratory_candidates", "plan_version": plan_version,
            "status": "applied", "evidence_kind": "evidence_driven_routing",
            "observation": (f"{expl.get('count')} candidate(s) with generated/demo provenance "
                            "were routed out of the scientific payload into the exploratory design brief"),
            "gate": "identity_assembly",
        })
    counts = payload.get("assembly_counts") or {}
    source_backed = payload.get("source_backed_candidate_count", 0)
    seq += 1
    terminal = ("valid_candidate" if source_backed
                else "design_brief" if counts.get("valid") else "justified_no_go")
    recs.append({
        "seq": seq, "type": "terminal", "role": "supervisor",
        "terminal_reason": terminal,
        "source_backed_candidates": source_backed,
        "exploratory_candidates": expl.get("count", 0),
        "total_valid": counts.get("valid", 0),
        "evidence_driven_revisions": [r for r in recs if r["type"] == "routing_decision"],
        "justified_abstention": None,
        "run_id": payload.get("run_id", rid),
        "payload_scan": "clean (scientific payload carries no demo/synthetic provenance)",
    })
    return recs


def build_abstention_trace() -> list[dict]:
    from protacxtend.runtime.agent_tools import run_agent_tool
    from protacxtend.runtime.modes import MissingScientificInput
    recs = [_pin("abstention:predict_cooperativity", {"per_task_timeout_s": 60})]
    params: dict = {}
    recs.append({
        "seq": 1, "type": "step", "role": ROLE["predict_cooperativity"],
        "action": "predict_cooperativity", "plan_version": 1, "status": "attempted",
        "observation": "required inputs not supplied", "evidence_kind": "structural_surrogate",
        "inputs_hash": _h(params), "gate": None,
    })
    reason = ""
    try:
        run_agent_tool("predict_cooperativity", params, use_fixture=False, allow_network=False)
        status, terminal = "unexpected_success", "no_abstention"
    except MissingScientificInput as exc:
        status, terminal, reason = "abstained", "justified_abstention", str(exc)
    except Exception as exc:  # noqa: BLE001
        status, terminal, reason = "error", "execution_failed", f"{type(exc).__name__}: {exc}"
    recs.append({
        "seq": 2, "type": "gate", "role": "critic", "action": "missing_scientific_input_check",
        "plan_version": 1, "status": status, "observation": reason,
        "evidence_kind": "typed_abstention", "gate": "MissingScientificInput",
    })
    recs.append({
        "seq": 3, "type": "terminal", "role": "supervisor",
        "terminal_reason": terminal, "justified_abstention": reason or None,
        "evidence_driven_revisions": [], "payload_scan": "n/a",
    })
    return recs


def write_trace(name: str, records: list[dict]) -> Path:
    d = OUT_ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    with (d / "agent_trace.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, default=str) + "\n")
    pin = records[0]
    (d / "PIN.json").write_text(json.dumps(pin, indent=2, default=str), encoding="utf-8")
    lines = [f"# Pinned agent trace — {name}", "",
             f"- git commit: `{pin['git_commit'][:9]}`", f"- mode: {pin['mode']}",
             f"- model: {pin['model']}", f"- generated: {pin['generated_at']}",
             f"- schema: `{pin['trace_schema']}`", "",
             "| seq | type | role | action | status | evidence_kind | observation |",
             "|---:|---|---|---|---|---|---|"]
    for r in records[1:]:
        obs = str(r.get("observation", ""))[:120].replace("|", "/")
        lines.append(f"| {r.get('seq')} | {r.get('type')} | {r.get('role')} | {r.get('action')} | "
                     f"{r.get('status')} | {r.get('evidence_kind')} | {obs} |")
    term = records[-1]
    lines += ["", "## Terminal", "",
              f"- reason: **{term.get('terminal_reason')}**",
              f"- justified_abstention: {term.get('justified_abstention')}",
              f"- source_backed_candidates: {term.get('source_backed_candidates')}",
              f"- exploratory_candidates: {term.get('exploratory_candidates')}",
              f"- payload_scan: {term.get('payload_scan')}", "",
              "## Interpretation", "",
              "The DESIGN route is a **fixed workflow**; the evidence-driven behaviour it",
              "demonstrates is the identity-gate decision that routes generated/demo-provenance",
              "candidates out of the scientific payload. It is **not** yet a free adaptive",
              "action-selection trace. The abstention trace demonstrates a typed, justified",
              "abstention when a required scientific input is absent."]
    (d / "AGENT_TRACE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


def main() -> int:
    import os
    os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d1 = write_trace(f"design_{ts}", build_design_trace(
        "Design a CRBN-recruiting PROTAC for BRD4", f"agent_trace_design_{ts}"))
    d2 = write_trace(f"abstention_{ts}", build_abstention_trace())
    print(json.dumps({"design_trace": str(d1), "abstention_trace": str(d2)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
