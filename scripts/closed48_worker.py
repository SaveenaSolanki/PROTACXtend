#!/usr/bin/env python
"""One (case, arm) execution for the closed 48-case benchmark.

Invoked as a subprocess by ``scripts/run_closed_48.py`` so that a stuck
deterministic run can be hard-killed by the orchestrator's timeout. Writes one
JSON result to ``--out`` and prints nothing else.

Arms
----
protacxtend     canonical deterministic runtime (``run_protacpilot``)
direct_tool     one matched agent-tool call (no orchestration)
fixed_workflow  the same fixed tool chain for every case (no adaptivity)

No correctness is computed here: gold is PENDING_INDEPENDENT_REVIEW.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")

JQ1 = "COc1cc2c(cc1c1c(C)onc1C)cc(c(=O)n2Cc1ccccn1)"
VH032 = "N[C@@H](C(C)(C)C)C(=O)N1C[C@@H](C[C@H]1C(=O)N[C@H](c1ccc(cc1)c1scnc1C)C)O"
LINKER = "[*:1]CCOCCOCC[*:2]"
PARACETAMOL = "CC(=O)Nc1ccc(O)cc1"
ABLATED = "COc1cc2c(cc1c1conc1)cc(c(=O)n2Cc1ccccn1)"

TARGETS = ["BRD4", "BRD2", "BTK", "CDK9", "ESR1", "MAP2K1", "SMARCA4", "AKT1",
           "AURKA", "AURKB", "XIAP", "RIPK1", "IKZF3", "ALK", "FGFR2", "TYK2",
           "PLK1", "AR", "ER", "KRAS", "MYC", "BCL6", "STAT3"]
E3S = ["VHL", "CRBN", "DCAF15", "DCAF16", "FEM1B", "XIAP", "IAP", "MDM2", "KEAP1"]

# Matched direct-tool baseline: the single capability tool for each task.
DIRECT: Dict[str, Dict[str, Any]] = {
    "KNOW-01": {"tool": "resolve_target", "params": {"target_name": "BRD4"}},
    "KNOW-02": {"tool": "retrieve_target_binders", "params": {"target_name": "BRD4", "top_k": 5}},
    "KNOW-03": {"tool": "search_pubmed", "params": {"query": "dBET1 MZ1 JQ1 BRD4 degrader", "page_size": 5}},
    "KNOW-04": {"tool": "retrieve_target_binders", "params": {"target_name": "BRD4", "top_k": 10}},
    "KNOW-05": {"tool": "select_e3_ligase", "params": {"target": "BRD4", "preferred_e3": "CRBN"}},
    "KNOW-06": {"tool": "search_chembl", "params": {"term": "JQ1", "top_k": 5}},
    "KNOW-07": {"tool": "retrieve_pdb", "params": {"target": "BRD4", "e3": "VHL", "top_k": 3}},
    "KNOW-08": {"tool": "diagnose_capability", "params": {"capability": "data_provenance", "internal_tool": "retrieve_target_binders"}},
    "KNOW-09": {"tool": "inspect_smiles", "params": {"smiles": PARACETAMOL}},
    "KNOW-10": {"tool": "predict_cell_context", "params": {"smiles": PARACETAMOL, "cell_line": "HEK293T", "poi": "BRD4", "e3": "CRBN"}},
    "KNOW-11": {"tool": "verify_crossref", "params": {"doi": "10.1126/science.aab1433"}},
    "KNOW-12": {"tool": "retrieve_target_binders", "params": {"target_name": "BRD4", "top_k": 10}},
    "REASON-01": {"tool": "simulate_hook_effect", "params": {"target_conc_nM": 100.0, "e3_conc_nM": 100.0, "alpha": 0.5}},
    "REASON-02": {"tool": "predict_cooperativity", "params": {"warhead_smiles": JQ1, "linker_smiles": LINKER, "e3_smiles": VH032, "pose_pdb": ""}},
    "REASON-03": {"tool": "inspect_smiles", "params": {"smiles": "N[C@@H](C(C)(C)C)C(=O)N1C[C@@H](C[C@H]1C(=O)NCc1ccc(cc1)c1scnc1C)O"}},
    "REASON-04": {"tool": "predict_cooperativity", "params": {"warhead_smiles": JQ1, "linker_smiles": LINKER, "e3_smiles": VH032, "pose_pdb": ""}},
    "REASON-05": {"tool": "inspect_smiles", "params": {"smiles": JQ1}},
    "REASON-06": {"tool": "model_ternary_complex", "params": {"target": "BRD4", "e3": "VHL", "linker_smiles": LINKER, "smiles": JQ1}},
    "REASON-07": {"tool": "predict_degradation", "params": {"smiles": JQ1, "e3": "VHL", "cell_line": "HEK293T", "target": "BRD4"}},
    "REASON-08": {"tool": "detect_exit_vectors", "params": {"smiles": JQ1, "role": "warhead"}},
    "REASON-09": {"tool": "retrieve_pdb", "params": {"target": "BRD4", "e3": "VHL", "top_k": 3}},
    "REASON-10": {"tool": "predict_admet", "params": {"smiles": JQ1}},
    "REASON-11": {"tool": "predict_degradation", "params": {"smiles": JQ1, "e3": "VHL", "cell_line": "HEK293T", "target": "BRD4"}},
    "REASON-12": {"tool": "predict_admet", "params": {"smiles": LINKER}},
    "DESIGN-01": {"tool": "generate_linkers", "params": {"warhead_smiles": JQ1, "e3_smiles": VH032, "count": 5}},
    "DESIGN-02": {"tool": "construct_protac", "params": {"warhead_smiles": JQ1, "linker_smiles": LINKER, "e3_smiles": VH032}},
    "DESIGN-03": {"tool": "generate_linkers", "params": {"warhead_smiles": JQ1, "e3_smiles": VH032, "count": 2}},
    "DESIGN-04": {"tool": "select_e3_ligase", "params": {"target": "BRD4", "preferred_e3": "CRBN"}},
    "DESIGN-05": {"tool": "predict_admet", "params": {"smiles": JQ1}},
    "DESIGN-06": {"tool": "generate_linkers", "params": {"warhead_smiles": JQ1, "e3_smiles": VH032, "count": 3}},
    "DESIGN-07": {"tool": "simulate_hook_effect", "params": {"target_conc_nM": 100.0, "e3_conc_nM": 100.0, "alpha": 1.0}},
    "DESIGN-08": {"tool": "generate_linkers", "params": {"warhead_smiles": JQ1, "e3_smiles": VH032, "count": 8}},
    "DESIGN-09": {"tool": "generate_linkers", "params": {"warhead_smiles": JQ1, "e3_smiles": VH032, "count": 3}},
    "DESIGN-10": {"tool": "select_e3_ligase", "params": {"target": "BRD4", "preferred_e3": "VHL"}},
    "DESIGN-11": {"tool": "predict_degradation", "params": {"smiles": JQ1, "e3": "VHL", "cell_line": "HEK293T", "target": "BRD4"}},
    "DESIGN-12": {"tool": "generate_linkers", "params": {"warhead_smiles": ABLATED, "e3_smiles": VH032, "count": 3}},
    "DISCOVER-01": {"tool": "rank_candidates", "params": {"candidates": [{"candidate_id": "a", "log_dc50": 1.0}, {"candidate_id": "b", "log_dc50": 2.0}, {"candidate_id": "c", "log_dc50": 1.5}]}},
    "DISCOVER-02": {"tool": "build_candidate_dossier", "params": {"candidate_id": "a", "candidate": {"candidate_id": "a", "log_dc50": 1.0, "uncertainty": 0.3}}},
    "DISCOVER-03": {"tool": "build_candidate_dossier", "params": {"candidate_id": "a", "candidate": {"candidate_id": "a", "log_dc50": 1.0}}},
    "DISCOVER-04": {"tool": "rank_candidates", "params": {"candidates": [{"candidate_id": "a", "log_dc50": 1.0, "admet_pass": True}, {"candidate_id": "b", "log_dc50": 2.0, "admet_pass": False}]}},
    "DISCOVER-05": {"tool": "simulate_hook_effect", "params": {"target_conc_nM": 100.0, "e3_conc_nM": 100.0, "alpha": 1.0}},
    "DISCOVER-06": {"tool": "predict_cell_context", "params": {"smiles": JQ1, "cell_line": "MM1.S", "poi": "BRD4", "e3": "CRBN"}},
    "DISCOVER-07": {"tool": "predict_degradation", "params": {"smiles": JQ1, "e3": "CRBN", "cell_line": "HEK293T", "target": "BRD4"}},
    "DISCOVER-08": {"tool": "rank_candidates", "params": {"candidates": [{"candidate_id": "a", "log_dc50": 1.0, "cost_usd": 300}, {"candidate_id": "b", "log_dc50": 2.0, "cost_usd": 900}, {"candidate_id": "c", "log_dc50": 1.5, "cost_usd": 150}], "budget_usd": 1000}},
    "DISCOVER-09": {"tool": "build_candidate_dossier", "params": {"candidate_id": "a", "candidate": {"candidate_id": "a", "log_dc50": 1.0}}},
    "DISCOVER-10": {"tool": "build_candidate_dossier", "params": {"candidate_id": "a", "candidate": {"candidate_id": "a", "log_dc50": 1.0}}},
    "DISCOVER-11": {"tool": "rank_candidates", "params": {"candidates": [{"candidate_id": "a", "log_dc50": 1.0}, {"candidate_id": "b", "log_dc50": 2.0}]}},
    "DISCOVER-12": {"tool": "rank_candidates", "params": {"candidates": [{"candidate_id": "a", "log_dc50": 1.0}, {"candidate_id": "b", "log_dc50": 2.0}]}},
}


def _extract_target_e3(case: Dict[str, Any]) -> tuple[str, str]:
    """Word-boundary entity extraction via the shared resolver.

    The previous substring scan matched ``AR`` inside ``warhead`` and ``ER``
    inside other words; this is the audited wrong-target defect.
    """
    from protacxtend.agents.entity_resolution import resolve_entities

    entities = resolve_entities(case)
    target = entities.get("target") or ""
    e3 = (entities.get("e3_ligases") or [""])[0]
    if not target:
        # Only fall back to a curated symbol that appears as a whole token.
        text = " ".join([case.get("scientific_question", ""), " ".join(case.get("supplied_inputs") or [])])
        tokens = set(re.split(r"[^A-Za-z0-9]+", text.upper()))
        target = next((t for t in TARGETS if t in tokens), "")
    return target, e3


def _fixed_steps(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    target, e3 = _extract_target_e3(case)
    return [
        {"tool": "resolve_target", "params": {"target_name": target}},
        {"tool": "retrieve_target_binders", "params": {"target_name": target, "top_k": 5}},
        {"tool": "select_e3_ligase", "params": {"target": target, "preferred_e3": e3 or "VHL"}},
        {"tool": "retrieve_pdb", "params": {"target": target, "e3": e3 or "VHL", "top_k": 2}},
        {"tool": "generate_linkers", "params": {"warhead_smiles": JQ1, "e3_smiles": VH032, "count": 5}},
        {"tool": "construct_protac", "params": {"warhead_smiles": JQ1, "linker_smiles": LINKER, "e3_smiles": VH032}},
        {"tool": "predict_degradation", "params": {"smiles": JQ1, "e3": e3 or "VHL", "cell_line": "HEK293T", "target": target}},
    ]


def _classify(exc: BaseException) -> str:
    from protacxtend.runtime.modes import (
        FixtureUsageError, MissingScientificInput, SyntheticInputNotAllowed,
    )
    if isinstance(exc, MissingScientificInput):
        return "abstained"
    if isinstance(exc, (SyntheticInputNotAllowed, FixtureUsageError)):
        return "refused"
    return "failed"


def _call_tool(tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
    from protacxtend.runtime.agent_tools import run_agent_tool
    try:
        r = run_agent_tool(tool, params, allow_network=False)
        status = str(r.get("status", ""))
        valid = bool(r.get("VALID_OUTPUT"))
        if status == "ok" and valid:
            outcome = "completed"
        elif status in {"ok", "partial"} and valid:
            outcome = "partial"
        else:
            outcome = "failed"
        return {"tool": tool, "outcome": outcome, "status": status,
                "valid_output": valid, "failure_code": r.get("failure_code", ""),
                "error": r.get("error", ""), "latency_s": r.get("latency_s"),
                "evidence_kind": r.get("evidence_kind", ""),
                "summary": (r.get("scientific_result") or {}).get("summary", ""),
                "envelope": r.get("scientific_result")}
    except BaseException as exc:  # noqa: BLE001
        return {"tool": tool, "outcome": _classify(exc), "status": "exception",
                "valid_output": False, "failure_code": type(exc).__name__,
                "error": f"{type(exc).__name__}: {exc}", "latency_s": None,
                "evidence_kind": "", "summary": "", "envelope": None}


def run_arm(case: Dict[str, Any], arm: str) -> Dict[str, Any]:
    t0 = time.time()
    base = {"case_id": case["task_id"], "capability": case.get("capability"), "arm": arm,
            "execution_mode": os.environ.get("PROTACXTEND_EXECUTION_MODE", ""),
            "scientific_conclusion": "PENDING_INDEPENDENT_REVIEW",
            "correctness": "PENDING_INDEPENDENT_GOLD", "score": None}
    if arm == "protacxtend":
        from protacxtend.agents.structured_run import run_case
        try:
            r = run_case(case, capability=case.get("capability", ""),
                         offline=os.environ.get("PROTACXTEND_ARM_OFFLINE", "0") == "1",
                         budget_s=120.0)
            base.update({
                "outcome": r["outcome"], "status": r["status"],
                "stopping_state": r["scientific_state"],
                "answer": json.dumps({
                    "scientific_state": r["scientific_state"],
                    "answer": r["answer"],
                    "verified_candidate_smiles": r["verified_candidate_smiles"],
                    "design_brief_candidate_count": r["n_design_brief_candidates"],
                }, default=str)[:20000],
                "target": r["resolved_target"].get("uniprot_id") if isinstance(r["resolved_target"], dict) else None,
                "e3": r.get("resolved_e3"),
                "n_candidates": r["n_candidates"],
                "n_evidence_refs": len(r.get("evidence") or []),
                "failure_code": "" if r["outcome"] != "failed" else "RUNTIME_ERROR",
                "error": r.get("error", ""),
                "scientific_state": r["scientific_state"],
                "execution_status": r.get("execution_status", ""),
                "evidence_status": r.get("evidence_status", ""),
                "answer_status": r.get("answer_status", ""),
                "retrieval_telemetry": r.get("retrieval_telemetry", []),
                "entity_resolution": r.get("entity_resolution"),
                "routing": r.get("routing"),
                "stage_ledger": r.get("stage_ledger"),
                "trace": r.get("trace"),
                "tool_calls": None,
            })
        except BaseException as exc:  # noqa: BLE001
            base.update({"outcome": _classify(exc), "status": "exception",
                         "answer": "",
                         "failure_code": type(exc).__name__,
                         "error": f"{type(exc).__name__}: {exc}",
                         "stopping_state": "", "n_candidates": 0,
                         "n_evidence_refs": 0, "tool_calls": None})
    elif arm == "direct_tool":
        spec = DIRECT[case["task_id"]]
        step = _call_tool(spec["tool"], spec["params"])
        base.update({"outcome": step["outcome"], "status": step["status"],
                     "answer": step.get("summary", ""),
                     "failure_code": step["failure_code"], "error": step["error"],
                     "n_evidence_refs": 1 if step.get("envelope") else 0,
                     "tool_calls": [{"tool": step["tool"], "outcome": step["outcome"],
                                     "failure_code": step["failure_code"]}],
                     "steps": [step],
                     "baseline_note": (
                         "Single matched tool call, not an orchestrated answer. "
                         "The tool summary is not a question-responsive final answer."
                     )})
    elif arm == "fixed_workflow":
        steps = [_call_tool(s["tool"], s["params"]) for s in _fixed_steps(case)]
        outcomes = [s["outcome"] for s in steps]
        if all(o == "completed" for o in outcomes):
            outcome = "completed"
        elif any(o in {"completed", "partial"} for o in outcomes):
            outcome = "partial"
        elif all(o in {"abstained", "refused"} for o in outcomes):
            outcome = "abstained"
        else:
            outcome = "failed"
        base.update({"outcome": outcome, "status": "ok" if outcome == "completed" else outcome,
                     "answer": " | ".join(s.get("summary", "") for s in steps),
                     "failure_code": ";".join(sorted({s["failure_code"] for s in steps if s["failure_code"]})),
                     "error": "", "n_evidence_refs": sum(1 for s in steps if s.get("envelope")),
                     "tool_calls": [{"tool": s["tool"], "outcome": s["outcome"],
                                     "failure_code": s["failure_code"]} for s in steps],
                     "steps": steps,
                     "baseline_note": (
                         "Fixed baseline: the same JQ1/VH032/LINKER inputs are used for every case, "
                         "so any DC50/Dmax value is a fixed-input heuristic, not an individualized prediction."
                     )})
    else:
        raise ValueError(f"unknown arm {arm!r}")
    base["latency_s"] = round(time.time() - t0, 3)
    return base


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", required=True)
    ap.add_argument("--arm", required=True, choices=["protacxtend", "direct_tool", "fixed_workflow"])
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "benchmark" / "cases")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    case = json.loads((args.cases_dir / f"{args.case}.json").read_text(encoding="utf-8"))
    result = run_arm(case, args.arm)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
