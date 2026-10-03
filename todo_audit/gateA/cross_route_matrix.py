#!/usr/bin/env python
"""Gate A3 — cross-route scientific-input integration matrix.

Exercises the public surfaces that can reach a scientific tool and records,
for each (route, case), whether the failure is typed, whether anything was
executed, whether output was validated, and whether provenance is attached.

Routes
  1. canonical parser      (ScientificRequestParser)
  2. canonical orchestrator (injected engine state; mode recorded)
  3. agent tool            (run_capability -> agent_tool:*)
  4. capability runner     (run_capability -> lightweight backend)
  5. CLI                   (python -m protacxtend.cli)
  6. API                   (FastAPI TestClient)

Writes: todo_audit/gateA/cross_route_matrix.csv + .md
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_CSV = ROOT / "todo_audit" / "gateA" / "cross_route_matrix.csv"
OUT_MD = ROOT / "todo_audit" / "gateA" / "cross_route_matrix.md"

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
ROWS: list[dict] = []


def record(route, case, inputs, outcome, *, executed="", valid="", code="", detail=""):
    ROWS.append({
        "route": route, "case": case, "inputs": inputs, "outcome": outcome,
        "executed": executed, "valid_output": valid, "failure_code": code,
        "detail": str(detail)[:220],
    })


def classify(exc: Exception) -> str:
    from protacxtend.runtime import modes
    if isinstance(exc, modes.FixtureUsageError):
        return modes.FailureCode.FIXTURE_FORBIDDEN.value
    if isinstance(exc, modes.SyntheticInputNotAllowed):
        return modes.FailureCode.SYNTHETIC_INPUT_FORBIDDEN.value
    if isinstance(exc, modes.MissingScientificInput):
        return modes.FailureCode.MISSING_SCIENTIFIC_INPUT.value
    if isinstance(exc, modes.ScientificInputError):
        return modes.FailureCode.INVALID_SCIENTIFIC_INPUT.value
    return f"{type(exc).__name__}"


# ── 1. canonical parser ────────────────────────────────────────────────
def route_parser():
    from protacxtend.canonical.request_parser import ScientificRequestParser
    p = ScientificRequestParser()
    r = p.parse("Can you suggest a degrader strategy?")
    record("canonical-parser", "missing target", "no target/E3/cell/dose",
           "abstain_reported", detail=f"missing_required={r.missing_required}")
    r2 = p.parse("Design a VHL PROTAC against BRD4")
    record("canonical-parser", "target only", "target=BRD4, no cell/dose",
           "parsed", detail=f"target={r2.target} e3={r2.e3_ligase} missing={r2.missing_required}")


# ── 2. canonical orchestrator (injected state) ─────────────────────────
def route_canonical():
    from protacxtend.canonical import CanonicalOrchestrator
    from protacxtend.runtime import modes
    fake = {
        "target_record": {"target_name": "BRD4", "uniprot_id": "O60885", "structures": ["2OSS"]},
        "selected_warheads": [{"name": "JQ1", "smiles": "CC1", "source": "local_demo_jq1_like_warhead"}],
        "selected_e3_ligands": [{"e3_ligase": "VHL", "name": "VH032"}],
        "valid_candidates": [{"candidate_id": "c1", "full_protac_smiles": "CC1CCOCC"}],
        "degradation_predictions": [{"candidate_id": "c1", "log_dc50": 2.1, "dmax": 0.8, "model_version": "m"}],
    }
    res = CanonicalOrchestrator().review_engine_state(
        "Design a VHL PROTAC against BRD4", fake, run_id="gateA-canonical")
    record("canonical-orchestrator", "demo warhead injected", "engine state with local_demo warhead",
           "demo_warheads_dropped" if not res.strategy.warheads else "LEAKED",
           executed=True, valid=bool(res.strategy.candidate_protacs),
           detail=f"mode={res.strategy.execution_mode} warheads={len(res.strategy.warheads)}")


# ── 3/4. agent tool + capability runner ────────────────────────────────
def route_executor():
    from protacxtend.runtime.executor import run_capability
    cases = [
        ("agent-tool", "missing input", "agent_tool:inspect_smiles", {}),
        ("agent-tool", "placeholder SMILES", "agent_tool:inspect_smiles", {"smiles": "CCO"}),
        ("agent-tool", "real SMILES", "agent_tool:inspect_smiles", {"smiles": ASPIRIN}),
        ("agent-tool", "unknown tool", "agent_tool:does_not_exist", {}),
        ("capability-runner", "missing SMILES", "chemistry", {}),
        ("capability-runner", "invalid SMILES", "chemistry", {"smiles": "not_a_smiles"}),
        ("capability-runner", "invalid PDB id", "protein_structure", {"identifier": "ZZZZ"}),
    ]
    for route, case, name, params in cases:
        try:
            r = run_capability(name, params)
            result = r.get("result") or {}
            status = result.get("status", "?")
            record(route, case, json.dumps(params), f"returned:{status}",
                   executed=bool(r.get("executed")), valid=bool(r.get("output_valid")),
                   detail=f"backend={result.get('backend','')} "
                          f"origins={r.get('provenance',{}).get('input_origins','')}")
        except Exception as exc:  # noqa: BLE001
            record(route, case, json.dumps(params), "typed_failure", code=classify(exc), detail=exc)


# ── 5. CLI ─────────────────────────────────────────────────────────────
def route_cli():
    cases = [
        ("missing target", ""),
        ("target+E3", "Design a VHL PROTAC against BRD4"),
    ]
    for case, req in cases:
        p = subprocess.run(
            [sys.executable, "-m", "protacxtend.cli", "--execution-mode", "scientific",
             "strategy", req],
            capture_output=True, text=True, cwd=str(ROOT), timeout=300,
        )
        out = (p.stdout + p.stderr)
        mode = ""
        for line in out.splitlines():
            if "execution_mode" in line:
                mode = line.strip()
        record("cli", case, req or "<empty>",
               "exit0" if p.returncode == 0 else f"exit{p.returncode}",
               detail=(mode or out.strip().splitlines()[-1] if out.strip() else ""))


# ── 6. API (FastAPI TestClient) ────────────────────────────────────────
def route_api():
    try:
        from fastapi.testclient import TestClient
        from protacxtend.backend.api_routes import get_app
    except Exception as exc:  # noqa: BLE001
        record("api", "client unavailable", "", "skipped", detail=exc)
        return
    client = TestClient(get_app(), raise_server_exceptions=False)
    for case, params in [("missing input", {}), ("real SMILES", {"smiles": ASPIRIN})]:
        try:
            resp = client.post("/tools/inspect_smiles/run", json={"params": params})
            record("api", case, json.dumps(params), f"http:{resp.status_code}",
                   detail=resp.text[:180])
        except Exception as exc:  # noqa: BLE001
            record("api", case, json.dumps(params), "typed_failure", code=classify(exc), detail=exc)


def main():
    from protacxtend.runtime import modes
    print("mode:", modes.get_execution_mode().value)
    for fn in (route_parser, route_canonical, route_executor, route_cli, route_api):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            record(fn.__name__, "route crashed", "", "route_error", detail=exc)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ROWS[0].keys()))
        w.writeheader()
        w.writerows(ROWS)

    lines = ["# Gate A3 — cross-route integration matrix",
             "", f"Generated with `PROTACXTEND_EXECUTION_MODE={os.environ.get('PROTACXTEND_EXECUTION_MODE')}`.",
             "", "| route | case | inputs | outcome | executed | valid | failure_code | detail |",
             "|---|---|---|---|---|---|---|---|"]
    for r in ROWS:
        lines.append(
            "| {route} | {case} | {inputs} | {outcome} | {executed} | {valid_output} | "
            "{failure_code} | {detail} |".format(**r)
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_CSV} ({len(ROWS)} rows) and {OUT_MD}")


if __name__ == "__main__":
    main()
