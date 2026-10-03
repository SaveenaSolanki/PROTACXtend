#!/usr/bin/env bash
# PROTACXtend todo/ closure audit — reproducible fast checks.
# Usage:  bash todo_audit/verify.sh
# Writes machine-readable evidence into todo_audit/evidence/.
set -uo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
OUT="$ROOT/todo_audit/evidence"
PY="${PYTHON:-python}"
mkdir -p "$OUT"

echo "== PROTACXtend audit verify @ $(date -u +%Y-%m-%dT%H:%M:%SZ) =="
echo "root: $ROOT"

echo "[1/8] git state"
{
  echo "HEAD: $(git rev-parse HEAD 2>&1)"
  echo "branch: $(git branch --show-current 2>&1)"
  git status --short | awk '{print $1}' | sort | uniq -c
} | tee "$OUT/git_state.txt"

echo "[2/8] installed console script"
{
  pip show protacxtend 2>/dev/null | sed -n '1,3p'
  echo "--- bin/protacxtend ---"
  head -4 "$(command -v protacxtend 2>/dev/null)" 2>&1
  echo "--- 'protacxtend --help' exit ---"
  protacxtend --help >/dev/null 2>&1 && echo "exit 0" || echo "NONZERO: $(protacxtend --help 2>&1 | head -1)"
} | tee "$OUT/console_script.txt"

echo "[3/8] parser gate (>=0.98)"
$PY scripts/evaluate_parser.py 2>&1 | tee "$OUT/parser_eval.txt"

echo "[4/8] scorable manifest"
$PY scripts/build_scorable_manifest.py 2>&1 | tee "$OUT/scorable_manifest.txt"

echo "[5/8] offline smoke (self-grading; NOT a performance result)"
$PY scripts/run_benchmark_pilot.py --offline-smoke 2>&1 | tee "$OUT/offline_smoke.txt"

echo "[6/8] registry summary"
$PY - <<'PY' 2>&1 | tee "$OUT/registry_summary.txt"
from protacxtend.toolkit.registry import load_toolkit_registry, summarize_toolkit_status
r = load_toolkit_registry()
total = 0
for sec in r.get("sections", []):
    n = len(r.get(sec, [])); total += n
    print(f"{sec}: {n}")
print("TOTAL registered rows:", total)
print("summarize_toolkit_status totals:", summarize_toolkit_status()["totals"])
from protacxtend.runtime.agent_tools import list_agent_tools
print("agent tools:", len(list_agent_tools()))
PY

echo "[7/8] scientific-mode guardrail probe"
PROTACXTEND_EXECUTION_MODE=scientific $PY - <<'PY' 2>&1 | tee "$OUT/mode_probe.txt"
import os
from protacxtend.runtime import modes
from protacxtend.runtime.agent_tools import run_agent_tool
print("mode:", modes.get_execution_mode())
def probe(label, fn):
    try:
        r = fn()
        print(f"[{label}] OK", {k: r.get(k) for k in ('used_fixture','failure_code','input_origin','status','VALID_OUTPUT')})
    except Exception as e:
        print(f"[{label}] RAISED {type(e).__name__}: {str(e)[:120]}")
probe("missing-input predict_degradation", lambda: run_agent_tool("predict_degradation", {}, allow_network=False))
probe("explicit fixture request", lambda: run_agent_tool("inspect_smiles", use_fixture=True))
probe("placeholder smiles CCO", lambda: run_agent_tool("inspect_smiles", {"smiles": "CCO"}))
probe("no params inspect_smiles", lambda: run_agent_tool("inspect_smiles", {}))
PY

echo "[8/8] canonical demo vs scientific divergence"
$PY - <<'PY' 2>&1 | tee "$OUT/canonical_mode_divergence.txt"
import json, subprocess, sys
from pathlib import Path
def run(mode):
    out = subprocess.run([sys.executable, "-m", "protacxtend.cli", "--execution-mode", mode,
                          "strategy", "Design a VHL PROTAC against BRD4"],
                         capture_output=True, text=True)
    path = ""
    for line in out.stdout.splitlines():
        if line.startswith("strategy:"):
            path = line.split(":", 1)[1].strip()
    return path
def sig(p):
    d = json.load(open(p))
    return {
        "uniprot": d["target_validation"].get("uniprot_id"),
        "warhead_sources": sorted({w.get("source") for w in d.get("warheads", [])}),
        "n_candidates": len(d.get("candidate_protacs", [])),
        "stopping_state": d.get("stopping_state"),
        "top_smiles": d["candidate_protacs"][0]["smiles"] if d.get("candidate_protacs") else None,
    }
sp = run("scientific"); dp = run("demo")
s, de = sig(sp), sig(dp)
print("scientific:", json.dumps(s, indent=2))
print("demo      :", json.dumps(de, indent=2))
print("IDENTICAL:", s == de)
PY

echo "== done; evidence in todo_audit/evidence/ =="
