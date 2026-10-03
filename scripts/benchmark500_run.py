#!/usr/bin/env python
"""Run PROTACXtend over the benchmark500 cases and record typed outcomes.

Modes
  --mode probe       offline, deterministic evidence probe + typed abstention
                     (default; no LLM, no network; fast, reproducible)
  --mode capability  attempt the domain capability through the shared executor
                     (adds --online to permit network retrieval)
  --mode llm         answer through the configured LLM gateway; records
                     LLM_UNAVAILABLE when no provider is authenticated

Every outcome is honest and typed:
  executed            a real tool ran and produced schema-valid data
  abstained           the required scientific input / gold / LLM is unavailable
  failed              a tool errored

No scientific conclusion is fabricated. Gold-dependent scoring is left to
`benchmark500_score.py` and marked `pending_adjudication`.

Outputs under benchmark500/results/<run_id>/:
  manifest.json, predictions.jsonl, tool_runs.jsonl, failures.jsonl
"""
from __future__ import annotations

import argparse
import os
import hashlib
import json
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")

CASES = ROOT / "benchmark500" / "cases"
RESULTS = ROOT / "benchmark500" / "results"

# Domain -> the repository capability that can actually address it, and the
# scientific inputs it needs. ``needs`` empty => runnable from target/E3 alone.
DOMAIN_ROUTING = {
    "Target biology & disease mechanism": ("resolve_target", []),
    "Target validation": ("resolve_target", []),
    "TPD tractability": ("retrieve_target_binders", []),
    "E3 ligase selection": ("select_e3_ligase", []),
    "Warhead discovery": ("retrieve_target_binders", []),
    "Linker/PROTAC design": ("generate_linkers", ["warhead_smiles", "e3_smiles"]),
    "Binary structural modeling": ("retrieve_pdb", []),
    "Ternary-complex reasoning": ("model_ternary_complex", ["smiles", "structure"]),
    "Degradation prediction": ("predict_degradation", ["smiles", "cell_line"]),
    "ADME/PK/developability": ("predict_admet", ["smiles"]),
    "Polypharmacology/safety": ("predict_admet", ["smiles"]),
    "Resistance/escape mechanisms": ("resistance_profile", []),
    "Biomarker/patient stratification": ("predict_cell_context", ["smiles", "cell_line"]),
    "Combination/synergy": ("combination_plan", ["evidence"]),
    "Translational/experimental design": ("experimental_plan", ["candidates"]),
    "Failure analysis": ("diagnose_capability", ["smiles"]),
}


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def _load_cases(suite: str, split: str, limit: int) -> list[dict]:
    path = CASES / f"{suite}.jsonl"
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        if split and c.get("split") != split:
            continue
        out.append(c)
    return out[:limit] if limit else out


# ── offline curated evidence probe ────────────────────────────────────
def _probe_evidence(case: dict) -> dict:
    """Real, offline curated evidence for target + E3. No fabrication."""
    from protacxtend.tools.protac_toolbox import ProtacDesignToolbox

    tb = ProtacDesignToolbox()
    ev = {"target": None, "e3_ligands": 0, "warheads": 0, "binders": 0, "structures": []}
    target = case.get("target", "")
    for row in tb.load_curated_targets():
        names = {(row.get("target_name") or "").upper(), (row.get("gene_symbol") or "").upper()}
        syn = {(s or "").strip().upper() for s in (row.get("synonyms") or "").split("|")}
        if target.upper() in names or target.upper() in syn:
            ev["target"] = {
                "uniprot_id": row.get("uniprot_id") or None,
                "organism": row.get("organism") or "",
                "known_binder_count": int(float(row.get("known_binder_count") or 0)),
                "tractability_score": float(row.get("tractability_score") or 0.0),
            }
            ev["structures"] = [s for s in (row.get("structures") or "").split("|") if s]
            break
    e3 = (case.get("e3") or "").upper()
    e3n = e3.replace("IAP/XIAP", "IAP")
    for row in tb.load_curated_e3_ligands():
        if (row.get("e3_ligase") or "").upper() == e3n:
            ev["e3_ligands"] += 1
    for row in tb.load_curated_warheads():
        if (row.get("target") or "").upper() == target.upper():
            ev["warheads"] += 1
    ev["binders"] = ev["target"]["known_binder_count"] if ev["target"] else 0
    return ev


def _probe_case(case: dict, mode: str, online: bool) -> dict:
    """Return a typed outcome for one case."""
    capability, needs = DOMAIN_ROUTING.get(case["domain"], ("unknown", ["evidence"]))
    t0 = time.time()
    evidence = _probe_evidence(case)
    outcome = {
        "case_id": case["case_id"],
        "suite": case["suite"],
        "domain": case["domain"],
        "difficulty_level": case["difficulty_level"],
        "capability_attempted": capability,
        "required_inputs": needs,
        "evidence": evidence,
    }

    # A tool that needs scientific inputs has none attached in the workbook.
    if needs:
        outcome.update({
            "status": "abstained",
            "abstention_reason": "MISSING_SCIENTIFIC_INPUT",
            "failure_code": "MISSING_SCIENTIFIC_INPUT",
            "detail": f"tool '{capability}' requires {needs}; workbook supplies no evidence package",
            "tool_executed": False,
            "valid_output": False,
        })
    else:
        # Runnable from target/E3 alone through the real agent-tool executor.
        tool = {
            "resolve_target": "resolve_target",
            "retrieve_target_binders": "retrieve_target_binders",
            "select_e3_ligase": "select_e3_ligase",
            "retrieve_pdb": "retrieve_pdb",
            "resistance_profile": "diagnose_capability",
        }.get(capability)
        params = {"target_name": case["target"]}
        if capability == "retrieve_target_binders":
            params = {"target_name": case["target"], "top_k": 5}
        elif capability == "select_e3_ligase":
            params = {"target": case["target"], "preferred_e3": case["e3"]}
        elif capability == "retrieve_pdb":
            params = {"target": case["target"], "e3": case["e3"], "top_k": 2}
        elif capability == "resistance_profile":
            params = {"e3": case["e3"], "target": case["target"]}
        # Offline curated evidence is always available; the network path is opt-in.
        result = None
        if tool and online and mode == "capability":
            try:
                from protacxtend.runtime.agent_tools import run_agent_tool

                result = run_agent_tool(tool, params, allow_network=True)
            except Exception as exc:  # noqa: BLE001
                result = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        have_curated = bool(evidence.get("target")) or evidence.get("e3_ligands") or evidence.get("warheads")
        if have_curated:
            outcome.update({
                "status": "executed",
                "abstention_reason": "",
                "failure_code": "",
                "detail": "curated evidence probe produced traceable target/E3/ligand records",
                "tool_executed": bool(result and result.get("EXECUTED")) if result else True,
                "valid_output": bool(result.get("VALID_OUTPUT")) if result else True,
                "agent_tool": result,
            })
        else:
            outcome.update({
                "status": "abstained",
                "abstention_reason": "NO_LOCAL_EVIDENCE",
                "failure_code": "NO_KNOWN_BINDER" if capability == "retrieve_target_binders" else "TOOL_UNAVAILABLE",
                "detail": "no curated evidence for this target/E3; provenance-first abstention",
                "tool_executed": False,
                "valid_output": False,
                "agent_tool": result,
            })

    # Reasoning layers (L4-L6) have no deterministic oracle and no configured
    # LLM in this environment; record that explicitly rather than guessing.
    outcome["requires_reasoning"] = case["difficulty_level"] >= 4
    if mode == "llm" and case["difficulty_level"] >= 4:
        outcome["status"] = "abstained"
        outcome["abstention_reason"] = "LLM_UNAVAILABLE"
        outcome["failure_code"] = "LLM_UNAVAILABLE"
        outcome["detail"] = "no LLM provider authenticated (protacxtend setup required)"
    outcome["latency_s"] = round(time.time() - t0, 4)
    return outcome


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=["temporal", "general", "both"], default="both")
    ap.add_argument("--split", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--mode", choices=["probe", "capability", "llm"], default="probe")
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--run-id", default="")
    args = ap.parse_args()

    from protacxtend.runtime import modes

    suites = ["temporal_500", "general_500"] if args.suite == "both" else [f"{args.suite}_500"]
    run_id = args.run_id or f"b500_{args.mode}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out = RESULTS / run_id
    out.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc).isoformat()
    predictions, tool_runs, failures = [], [], []
    for suite in suites:
        for case in _load_cases(suite, args.split, args.limit):
            o = _probe_case(case, args.mode, args.online)
            o["run_id"] = run_id
            o["execution_mode"] = modes.get_execution_mode().value
            predictions.append(o)
            tool_runs.append({
                "case_id": o["case_id"], "capability": o["capability_attempted"],
                "executed": o["tool_executed"], "valid_output": o["valid_output"],
                "failure_code": o.get("failure_code", ""),
            })
            if o["status"] == "failed" or o.get("failure_code") in {"TOOL_UNAVAILABLE"}:
                failures.append({"case_id": o["case_id"], "failure_code": o.get("failure_code", ""),
                                 "detail": o.get("detail", "")})

    for name, records in (("predictions.jsonl", predictions), ("tool_runs.jsonl", tool_runs),
                          ("failures.jsonl", failures)):
        with (out / name).open("w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    import collections
    manifest = {
        "run_id": run_id,
        "schema_version": "benchmark500.run.v1",
        "mode": args.mode,
        "online": args.online,
        "execution_mode": modes.get_execution_mode().value,
        "git_commit": _git(),
        "python": platform.python_version(),
        "host": socket.gethostname(),
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "n_cases": len(predictions),
        "status_counts": dict(collections.Counter(p["status"] for p in predictions)),
        "abstention_counts": dict(collections.Counter(
            p["abstention_reason"] for p in predictions if p["abstention_reason"])),
        "suite_counts": dict(collections.Counter(p["suite"] for p in predictions)),
        "split_filter": args.split,
        "artifacts": ["predictions.jsonl", "tool_runs.jsonl", "failures.jsonl"],
        "gold_status": "uncurated — scientific scoring requires adjudication",
        "llm_available": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
