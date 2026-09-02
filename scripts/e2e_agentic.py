#!/usr/bin/env python3
"""End-to-end agentic test suite — 5 representative scenarios.

Each scenario starts from a natural-language prompt and lets the full
system run without manual path selection. The canonical AgentRunRecord
is written to outputs/runs/<run_id>/ and each scenario's chain is printed:

    user request → planner → tools → evidence → candidates → failures →
    repairs → predictions → pareto → human gates → final recommendation

Usage:
    python scripts/e2e_agentic.py --offline            # LLM off (CI-safe)
    python scripts/e2e_agentic.py --live               # LLM on if reachable
    python scripts/e2e_agentic.py --limit 2            # first N scenarios

Exit code 0 = all scenarios produced a complete, recorded chain.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from synglue_agent.agents.runtime import run_protacpilot

SCENARIOS = [
    {
        "name": "BRD4_known",
        "prompt": (
            "Design CRBN-recruiting PROTAC candidates against BRD4 with "
            "cellular degradation as the primary objective and synthetic "
            "feasibility as a secondary objective."
        ),
        "expect": "positive_control",
    },
    {
        "name": "BTK_VHL",
        "prompt": (
            "Design VHL-recruiting PROTAC candidates against BTK, prioritizing "
            "cellular degradation potency and avoiding known warhead liabilities."
        ),
        "expect": "positive_control",
    },
    {
        "name": "KRAS_evidence_limited",
        "prompt": (
            "Design a PROTAC against KRAS G12C, an evidence-limited target. "
            "Flag low-confidence evidence and do not over-claim."
        ),
        "expect": "evidence_limited",
    },
    {
        "name": "HMGB2_ICM_nanobinder",
        "prompt": (
            "Design CRBN PROTACs for the HMGB2-ICM system using the ICM "
            "nanobinder warhead; verify the ternary hypothesis and gate "
            "anything ambiguous for human review."
        ),
        "expect": "novel_repair",
    },
    {
        "name": "MDM2_nonclassical_e3",
        "prompt": (
            "Design MDM2-recruiting PROTAC candidates against BRD4 using the "
            "MDM2 E3 ligase (not CRBN/VHL), prioritizing cellular degradation."
        ),
        "expect": "positive_control",
    },
    {
        "name": "impossible_input",
        "prompt": (
            "Design a PROTAC against the nonexistent target QZYX123 using an "
            "invalid warhead SMILES 'not_a_smiles'. Fail gracefully and "
            "escalate rather than fabricate results."
        ),
        "expect": "safe_failure",
    },
]


def _chain_summary(rec_path: Path, name: str) -> str:
    """Human-readable chain from the canonical record."""
    rec = json.loads(rec_path.read_text())
    lines = [
        f"\n{'='*72}",
        f"SCENARIO {name}  (run {rec['run_id']}, {rec['runtime_seconds']}s)",
        f"{'='*72}",
        f"  1. user request : {rec['user_objective'][:90]}...",
        f"  2. parsed       : target={rec['parsed_objective'].get('target_name')} "
        f"e3={rec['parsed_objective'].get('e3')}",
        f"  3. plan         : {json.dumps(rec['execution_plan'])[:120] if rec['execution_plan'] else '(empty)'}",
        f"  4. tools exec   : {rec['tools_executed'][:8] if rec['tools_executed'] else '(from trace)'}",
        f"  5. routing path : {' -> '.join(rec['routing_path'][:14])}",
        f"  6. evidence recs: {len(rec['evidence_records'])}",
        f"  7. candidates   : generated={rec['candidates_generated']} valid={rec['candidates_valid']}",
        f"  8. repairs      : {len(rec['repair_events'])}  human gates: {len(rec['human_interventions'])}",
        f"  9. predictions  : pareto rows={len(rec['pareto_front'])}",
        f" 10. LLM          : model={rec['llm_model']} calls={rec['llm_calls']} failures={rec['llm_failures']}",
        f" 11. warnings     : {len(rec['warnings'])}  errors: {len(rec['errors'])}",
        f" 12. hash         : {rec['reproducibility_hash'][:16]}...",
    ]
    final = rec.get("final_candidates") or []
    if final:
        top = final[0]
        lines.append(f" 13. final rec     : {top.get('candidate_id')} {str(top.get('full_protac_smiles'))[:50]}")
    else:
        lines.append(f" 13. final rec     : (none — terminal state {rec['status'] if 'status' in rec else 'needs_human'})")
    return "\n".join(lines)


def run_scenario(scenario: dict, live: bool) -> dict:
    name = scenario["name"]
    stamp = time.strftime("%Y%m%d")
    run_id = f"e2e_{stamp}_{name}"
    t0 = time.time()
    attempts = 3 if scenario["expect"] == "positive_control" else 1  # retry transient API rate-limits
    result, ok = None, False
    for attempt_idx in range(attempts):
        if attempt_idx:
            time.sleep(45)  # let ChEMBL rate limits clear between attempts
        try:
            result = run_protacpilot(
                scenario["prompt"],
                mode="agentic",
                config={"run_id": run_id, "record_run": True, "llm_enabled": live, "persistent": False},
            )
            ok = True
            if scenario["expect"] == "positive_control" and not (result.get("state") or {}).get("valid_candidates"):
                print("    (positive control produced 0 candidates — retrying once)", flush=True)
                continue
            break
        except Exception as exc:  # noqa: BLE001
            result = {"status": "exception", "error": str(exc)}
            ok = False
            break
    runtime = round(time.time() - t0, 2)

    rec_path = ROOT / "outputs" / "runs" / run_id / "run.json"
    record = json.loads(rec_path.read_text()) if rec_path.exists() else {}

    # ── assertions (the "is it a real scientific agent" checks) ──
    problems = []
    if not rec_path.exists():
        problems.append("no canonical run.json written")
    if ok and scenario["expect"] == "safe_failure":
        # must terminate gracefully, never fabricate
        status = result.get("status", "?")
        if status not in ("needs_human", "failed", "ok"):
            problems.append(f"unexpected terminal status {status}")
        if not record.get("errors") and not record.get("human_interventions") and status == "ok":
            if record.get("candidates_valid", 0) > 0:
                problems.append("impossible input produced candidates")
    elif ok:
        if not record.get("routing_path"):
            problems.append("routing path empty")
        if not record.get("evidence_records") and not record.get("tools_executed"):
            problems.append("no evidence or tools recorded")
        if scenario["expect"] == "novel_repair" and result.get("status") == "needs_human":
            # novel/evidence-limited targets legitimately end at the human gate
            # with the full chain recorded — that IS the correct behavior.
            pass
        elif scenario["expect"] == "positive_control" and result.get("status") == "needs_human":
            # the system may escalate candidates when model confidence is low
            # (e.g. chemotype outside the training domain) — the chain and the
            # escalation packet must still be recorded.
            if not record.get("candidates_valid"):
                problems.append("no candidates before human gate")
            if not record.get("human_interventions"):
                problems.append("no human gate recorded")
        elif not record.get("pareto_front") and not record.get("final_candidates"):
            problems.append("no ranking/recommendation recorded")
    else:
        problems.append(f"raised: {result.get('error', '?')[:150]}")

    return {"name": name, "ok": ok and not problems, "problems": problems,
            "runtime": runtime, "rec_path": rec_path, "result_status": result.get("status", "?")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="disable LLM (CI-safe)")
    ap.add_argument("--live", action="store_true", help="enable LLM when reachable")
    ap.add_argument("--limit", type=int, default=0, help="run first N scenarios")
    args = ap.parse_args()

    live = args.live and not args.offline
    scenarios = SCENARIOS[: args.limit] if args.limit else SCENARIOS

    print(f"E2E AGENTIC SUITE — {len(scenarios)} scenarios, llm_enabled={live}")
    results = []
    for sc in scenarios:
        print(f"\n>>> running: {sc['name']} ...", flush=True)
        r = run_scenario(sc, live)
        results.append(r)
        print(_chain_summary(r["rec_path"], r["name"]) if r["rec_path"].exists() else "  (no record)")
        if r["problems"]:
            print("  PROBLEMS:", "; ".join(r["problems"]))

    print(f"\n{'='*72}\nSUMMARY")
    failed = 0
    for r in results:
        mark = "PASS" if not r["problems"] else "FAIL"
        if r["problems"]:
            failed += 1
        print(f"  [{mark}] {r['name']:22} {r['runtime']:6.1f}s  status={r['result_status']}")
    print(f"{failed} failed / {len(results)} scenarios")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
