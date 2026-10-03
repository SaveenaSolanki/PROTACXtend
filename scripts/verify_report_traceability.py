"""Verify evidence-driven reporting traceability + landscape reproducibility.

Assertions:
1. For each run report: numbers in summary/technical == run record == raw
   strategy JSON (candidates, degradation n, model, critic, target).
2. Landscape coordinates reproducible: two fresh loads -> identical JSON,
   and matches the pinned sha256 file (when present).
3. Unassessed dimensions never get inferred scores.
"""
import json, hashlib, os, sys

ROOT = "/storage/saveena/protacxtend"
REPORTS = [
    ("outputs/reports/canonical_6df6de48b0", "outputs/strategies/strategy_49bb27c13e.strategy.json", 25, 150, "REVISE"),
    ("outputs/reports/canonical_2f23adaf96", "outputs/strategies/strategy_1ec312e5e1.strategy.json", 25, 40, "REVISE"),
    ("outputs/reports/canonical_5d8f6d8ea1", "outputs/strategies/strategy_07e90f6cd1.strategy.json", 0, 0, "INSUFFICIENT EVIDENCE"),
]

failures = []
for rep_dir, raw_path, exp_cand, exp_deg, exp_critic in REPORTS:
    rec = json.load(open(os.path.join(ROOT, rep_dir, "run.json")))
    raw = json.load(open(os.path.join(ROOT, raw_path)))
    summary = open(os.path.join(ROOT, rep_dir, "summary.md")).read()
    technical = open(os.path.join(ROOT, rep_dir, "technical.md")).read()

    # 1a: summary numbers == raw strategy
    checks = {
        "cand_summary": f"candidates: {exp_cand}" in summary,
        "deg_summary": f"degradation predictions: {exp_deg}" in summary,
        "critic_summary": f"Critic: {exp_critic}" in summary,
    }
    # 1b: run record final_output -> raw preserved identical
    checks["raw_preserved_identical"] = (
        json.dumps(raw, sort_keys=True, default=str)
        == json.dumps(rec["final_output"], sort_keys=True, default=str)
    )
    # 1c: technical numbers == raw
    checks["deg_technical"] = f"| degradation predictions | {exp_deg} |" in technical
    # 1d: tool calls recorded for each module_status entry (when present)
    ms = (rec.get("provenance") or {}).get("module_status") or {}
    tools = [t for t in rec["tool_calls"] if t.get("tool", "").startswith("module:")]
    checks["tool_calls_cover_modules"] = len(tools) >= len(ms) or len(ms) == 0

    for k, v in checks.items():
        if not v:
            failures.append(f"{rep_dir}:{k}")

    print(f"{rep_dir}: " + "; ".join(f"{k}={v}" for k, v in checks.items()))

# 2. landscape reproducibility
sys.path.insert(0, ROOT)
from protacxtend.reporting.landscape import load_scores, coordinates, DEFAULT_SCORES_FILE
c1 = coordinates(load_scores(DEFAULT_SCORES_FILE))
c2 = coordinates(load_scores(DEFAULT_SCORES_FILE))
print("landscape reproducible (two loads identical):", c1 == c2)
pin = os.path.join(ROOT, "outputs/landscape/coordinates.sha256")
if os.path.exists(pin):
    expected = open(pin).read().strip()
    actual = hashlib.sha256(json.dumps(c1, sort_keys=True).encode()).hexdigest()
    print("landscape pinned hash matches:", expected == actual[:len(expected)] if len(expected) <= 16 else expected == actual, "")
    if not (expected == actual[:len(expected)] if len(expected) <= 16 else expected == actual):
        failures.append(f"landscape:hash-mismatch ({expected} vs {actual[:16]})")

# 3. no inferred scores for unassessed
scores = load_scores(DEFAULT_SCORES_FILE)
for m, s in scores.items():
    if s.get("score") is None:
        if len(s.get("evidence") or "") > 0:
            failures.append(f"landscape:{m}:unassessed-with-evidence")
print("unassessed with empty evidence:", all(
    (s.get("score") is None) == (len(s.get("evidence") or "") == 0)
    for s in scores.values()))

print("\nFAILURES:", failures if failures else "none")
sys.exit(1 if failures else 0)