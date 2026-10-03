#!/usr/bin/env python
"""Diagnose the locked 48-case traces (NO scoring).

Produces, from the frozen run only:

* ``paired_case_table.csv``      — one row per case x arm with task type,
  required inputs, selected tools, completion state, failure/abstention code,
  last successful node, retry count, elapsed time and budget;
* ``abstention_triage.csv``      — the 26 PROTACXtend abstentions grouped into
  scientifically justified vs avoidable, with the stop node and rationale;
* ``timeout_triage.csv``         — the 22 PROTACXtend timeouts grouped by
  bottleneck;
* ``direct_completed_failures.csv`` — for each case the direct tool completed,
  exactly why the integrated agent failed or stopped;
* square, fully-labelled diagnostic PNGs under ``diagnostics/figures/``.

No correctness score is computed or written.

Usage::

    python scripts/probe_closed48_stops.py     # refresh stop_nodes.json (optional)
    python scripts/diagnose_closed48.py --run-dir benchmark_results/closed48/closed48_locked
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from protacxtend.validation.closure_figures import (  # noqa: E402
    apply_style,
    save_square,
    style_axes,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmark" / "cases"
SPLITS = ROOT / "benchmark" / "gateC" / "splits.json"
WORKER = ROOT / "scripts" / "closed48_worker.py"

ROOT_CAUSE_LABEL = {
    "retrieve_target_binders": "network hang: binder retrieval",
    "select_warheads": "no warhead after SCIENTIFIC filtering",
    "construct_protacs": "construction failed (no candidate)",
}


# ── loaders ─────────────────────────────────────────────────────────────

def _load_worker():
    spec = importlib.util.spec_from_file_location("closed48_worker", WORKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_cases() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(CASES.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        out[data["task_id"]] = data
    return out


def load_predictions(run_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (run_dir / "predictions.jsonl")
            .read_text(encoding="utf-8").splitlines() if line.strip()]


def load_stop_nodes(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "diagnostics" / "stop_nodes.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("cases", {})


# ── input classification ────────────────────────────────────────────────

_SMILES_MARKERS = ("[*:", "](", "c1", "C(=O)", "SMILES", "smiles")
_TABLE_MARKERS = ("csv", "table", "rows", "columns", "feature")
_NUMERIC_MARKERS = ("nm", "mw<=", "logp", "<=>=", "budget", "cutoff", "tanimoto", "alpha", "dmax", "dc50")
_TARGET_MARKERS = ("target:", "gene", "uniprot", "brd4", "e3")


def classify_inputs(case: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(str(s) for s in (case.get("supplied_inputs") or []))
    lower = text.lower()
    has_smiles = any(m in text for m in _SMILES_MARKERS) or any(
        m in lower for m in ("warhead smiles", "ligand smiles", "linker smiles")
    )
    has_table = any(m in lower for m in _TABLE_MARKERS)
    has_numeric = any(m in lower for m in _NUMERIC_MARKERS)
    has_target = any(m in lower for m in _TARGET_MARKERS)
    kinds = []
    if has_smiles:
        kinds.append("component_smiles")
    if has_table:
        kinds.append("feature_table")
    if has_numeric:
        kinds.append("numeric_constraints")
    if has_target:
        kinds.append("target_context")
    if not kinds:
        kinds.append("context_text")
    return {
        "supplied": text,
        "required_input": "+".join(kinds),
        "has_smiles": has_smiles,
        "has_table": has_table,
        "has_numeric": has_numeric,
        "has_target": has_target,
    }


# ── paired table ────────────────────────────────────────────────────────

def _tools_for(arm: str, pred: dict[str, Any], stop: dict[str, Any]) -> tuple[str, int]:
    if arm == "direct_tool":
        calls = pred.get("tool_calls") or []
        return ";".join(c.get("tool", "") for c in calls), len(calls)
    if arm == "fixed_workflow":
        calls = pred.get("tool_calls") or []
        return ">".join(c.get("tool", "") for c in calls), len(calls)
    reached = stop.get("reached") or []
    return ">".join(reached), len(reached)


def _retry_count(stop: dict[str, Any]) -> int:
    reached = stop.get("reached") or []
    counts = Counter(reached)
    return sum(v - 1 for v in counts.values() if v > 1)


def _last_successful(arm: str, pred: dict[str, Any], stop: dict[str, Any]) -> str:
    if arm in {"direct_tool", "fixed_workflow"}:
        ok = [s["tool"] for s in (pred.get("steps") or []) if s.get("valid_output")]
        return ok[-1] if ok else ""
    reached = stop.get("reached") or []
    if stop.get("timed_out"):
        # the blocker is the next node that hung; the last node completed
        return reached[-1] if reached else ""
    # on an abstention the blocker itself is the last reached node
    return reached[-2] if len(reached) >= 2 else ""


def build_paired_table(cases, splits, preds, stops, budgets) -> list[dict[str, Any]]:
    assignment = (splits.get("assignment") or {})
    rows: list[dict[str, Any]] = []
    for pred in sorted(preds, key=lambda p: (p["case_id"], p["arm"])):
        case = cases[pred["case_id"]]
        info = classify_inputs(case)
        stop = stops.get(pred["case_id"], {}) if pred["arm"] == "protacxtend" else {}
        tools, n_tools = _tools_for(pred["arm"], pred, stop)
        budget = budgets.get(pred["arm"], 0)
        elapsed = float(pred.get("latency_s") or 0.0)
        blocked = stop.get("blocked_at", "") if pred["arm"] == "protacxtend" else ""
        rows.append({
            "case_id": pred["case_id"],
            "capability": case.get("capability", ""),
            "split": assignment.get(pred["case_id"], ""),
            "arm": pred["arm"],
            "required_input": info["required_input"],
            "has_component_smiles": info["has_smiles"],
            "selected_tools": tools,
            "n_tools": n_tools,
            "completion_state": pred.get("outcome", ""),
            "failure_or_abstention_code": pred.get("failure_code") or ("" if pred.get("outcome") == "completed" else "INSUFFICIENT_EVIDENCE"),
            "blocked_at": blocked,
            "last_successful_node": _last_successful(pred["arm"], pred, stop),
            "retry_count": _retry_count(stop),
            "elapsed_s": round(elapsed, 2),
            "budget_s": budget,
            "over_budget": bool(budget and elapsed > budget),
            "n_evidence_refs": pred.get("n_evidence_refs", 0),
        })
    return rows


# ── triage ──────────────────────────────────────────────────────────────

def abstention_triage(cases, preds, stops) -> list[dict[str, Any]]:
    rows = []
    for pred in sorted(preds, key=lambda p: p["case_id"]):
        if pred["arm"] != "protacxtend" or pred.get("outcome") != "abstained":
            continue
        case = cases[pred["case_id"]]
        info = classify_inputs(case)
        stop = stops.get(pred["case_id"], {})
        blocked = stop.get("blocked_at", "?")
        cap = case.get("capability", "")
        if blocked == "select_warheads" and info["has_smiles"]:
            cls, why = "avoidable", "supplied component SMILES were not propagated; engine searched the network for a warhead and found none"
        elif blocked == "select_warheads" and cap in {"KNOW", "REASON"}:
            cls, why = "avoidable", "non-design question routed through the full design pipeline; aborted at warhead selection"
        elif blocked == "construct_protacs":
            cls, why = "avoidable", "chemistry construction failed because component inputs were not supplied to the assembler"
        elif blocked == "select_warheads":
            cls, why = "avoidable", "warhead selection is unreachable without propagated components"
        else:
            cls, why = "justified", "no independently answerable evidence for the required input"
        rows.append({
            "case_id": pred["case_id"],
            "capability": cap,
            "split": (stops.get("__splits__") or {}).get(pred["case_id"], ""),
            "stop_node": blocked,
            "stop_error": stop.get("block_error", ""),
            "has_component_smiles": info["has_smiles"],
            "classification": cls,
            "rationale": why,
            "elapsed_s": pred.get("latency_s"),
        })
    return rows


def timeout_triage(cases, preds, stops) -> list[dict[str, Any]]:
    rows = []
    for pred in sorted(preds, key=lambda p: p["case_id"]):
        if pred["arm"] != "protacxtend" or pred.get("outcome") != "timeout":
            continue
        stop = stops.get(pred["case_id"], {})
        node = stop.get("blocked_at", "?")
        rows.append({
            "case_id": pred["case_id"],
            "capability": cases.get(pred["case_id"], {}).get("capability", ""),
            "budget_s": 120,
            "bottleneck_node": node,
            "bottleneck": ROOT_CAUSE_LABEL.get(node, node),
            "last_successful_node": (stop.get("reached") or [""])[-1],
            "reached_nodes": len(stop.get("reached") or []),
            "network_bound": node == "retrieve_target_binders",
        })
    return rows


def direct_completed_failures(cases, preds, stops) -> list[dict[str, Any]]:
    by = {(p["case_id"], p["arm"]): p for p in preds}
    rows = []
    for pred in sorted(preds, key=lambda p: p["case_id"]):
        if pred["arm"] != "direct_tool" or pred.get("outcome") != "completed":
            continue
        agent = by.get((pred["case_id"], "protacxtend"), {})
        stop = stops.get(pred["case_id"], {})
        blocked = stop.get("blocked_at", "")
        rows.append({
            "case_id": pred["case_id"],
            "capability": pred.get("capability", ""),
            "direct_tool": (pred.get("tool_calls") or [{}])[0].get("tool", ""),
            "agent_outcome": agent.get("outcome", "?"),
            "agent_stop_node": blocked,
            "agent_root_cause": ROOT_CAUSE_LABEL.get(blocked, blocked or "n/a"),
            "agent_last_successful_node": (stop.get("reached") or [""])[-1] if stop.get("timed_out") else (
                (stop.get("reached") or ["", ""])[-2] if stop.get("reached") else ""),
            "supplied_inputs_ignored": bool(classify_inputs(cases[pred["case_id"]])["has_smiles"]),
        })
    return rows


# ── plots ───────────────────────────────────────────────────────────────

def _bar_square(labels, values, xlabel, ylabel, title, path, colors=None, log=False):
    apply_style()
    fig, ax = plt.subplots()
    ax.bar(labels, values, color=colors)
    for i, v in enumerate(values):
        ax.text(i, v, str(int(v)), ha="center", va="bottom", fontsize=9)
    if log:
        ax.set_yscale("log")
    style_axes(ax, xlabel=xlabel, ylabel=ylabel, title=title)
    ax.tick_params(axis="x", rotation=15)
    save_square(fig, path)


def write_plots(run_dir: Path, stops, preds) -> list[str]:
    out = run_dir / "diagnostics" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    written = []

    # 1. block point of the 48 PROTACXtend runs
    counts = Counter(stops.get(c, {}).get("blocked_at", "?") for c in stops)
    labels = list(counts)
    _bar_square(labels, [counts[k] for k in labels],
                "Pipeline node where the run stopped", "PROTACXtend cases (n = 48)",
                "Where every PROTACXtend case stopped",
                out / "fig_diag_stop_nodes.png",
                colors=["#D55E00", "#0072B2", "#E69F00"][: len(labels)])

    # 2. outcome by arm
    apply_style()
    arms = ["protacxtend", "direct_tool", "fixed_workflow"]
    outcomes = ["completed", "partial", "abstained", "timeout"]
    colors = {"completed": "#009E73", "partial": "#56B4E9", "abstained": "#F0E442", "timeout": "#CC79A7"}
    fig, ax = plt.subplots()
    bottom = np.zeros(len(arms))
    for oc in outcomes:
        vals = np.array([sum(1 for p in preds if p["arm"] == a and p.get("outcome") == oc) for a in arms], float)
        if not vals.any():
            continue
        ax.bar(["PROTACXtend", "direct tool", "fixed workflow"], vals, bottom=bottom, label=oc, color=colors[oc])
        bottom += vals
    style_axes(ax, xlabel="System arm", ylabel="Cases (n = 48 per arm)", title="Outcome by arm")
    ax.legend(fontsize=8, ncol=2, frameon=False)
    save_square(fig, out / "fig_diag_outcomes.png")
    written.append("fig_diag_outcomes.png")

    # 3. abstention triage
    tri = abstention_triage(_CASES_CACHE, preds, stops)
    cls = Counter(r["classification"] for r in tri)
    _bar_square(list(cls), [cls[k] for k in cls],
                "Abstention classification", "PROTACXtend abstentions (n = 26)",
                "Abstentions: justified vs avoidable",
                out / "fig_diag_abstention_triage.png",
                colors=["#D55E00" if k == "avoidable" else "#009E73" for k in cls])
    written.append("fig_diag_abstention_triage.png")

    # 4. timeout bottleneck
    tt = timeout_triage(_CASES_CACHE, preds, stops)
    bn = Counter(r["bottleneck"] for r in tt)
    _bar_square(list(bn), [bn[k] for k in bn],
                "Bottleneck", "PROTACXtend timeouts (n = 22)",
                "Timeouts grouped by bottleneck",
                out / "fig_diag_timeout_bottleneck.png",
                colors=["#CC79A7"] * len(bn))
    written.append("fig_diag_timeout_bottleneck.png")

    # 5. direct-completed cases: what the agent did
    dc = direct_completed_failures(_CASES_CACHE, preds, stops)
    oc = Counter(r["agent_outcome"] for r in dc)
    _bar_square(list(oc), [oc[k] for k in oc],
                "Integrated-agent outcome", "Cases the direct tool completed (n = 45)",
                "Agent outcome on direct-tool-completed cases",
                out / "fig_diag_direct_vs_agent.png",
                colors=["#F0E442", "#CC79A7"][: len(oc)])
    written.append("fig_diag_direct_vs_agent.png")

    # 6. latency vs budget
    apply_style()
    fig, ax = plt.subplots()
    for a, color in zip(arms, ["#0072B2", "#009E73", "#E69F00"], strict=True):
        vals = [float(p["latency_s"]) for p in preds if p["arm"] == a and p.get("latency_s") is not None]
        ax.boxplot([vals], positions=[arms.index(a)], widths=0.5, patch_artist=True,
                   boxprops={"facecolor": color, "alpha": 0.6}, showfliers=True)
    ax.axhline(120, color="#D55E00", linestyle="--", linewidth=1)
    ax.text(0.05, 125, "PROTACXtend budget = 120 s", fontsize=8, color="#D55E00")
    ax.set_yscale("log")
    ax.set_xticks(range(len(arms)))
    ax.set_xticklabels(["PROTACXtend", "direct tool", "fixed workflow"])
    style_axes(ax, xlabel="System arm", ylabel="Per-case wall clock (s, log scale)",
               title="Latency vs locked budget")
    save_square(fig, out / "fig_diag_latency.png")
    written.append("fig_diag_latency.png")

    written += [p.name for p in sorted(out.glob("*.png")) if p.name not in written]
    return written


_CASES_CACHE: dict[str, dict[str, Any]] = {}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path,
                        default=ROOT / "benchmark_results" / "closed48" / "closed48_locked")
    args = parser.parse_args()
    run_dir = args.run_dir
    diag = run_dir / "diagnostics"
    diag.mkdir(parents=True, exist_ok=True)

    global _CASES_CACHE
    _CASES_CACHE = load_cases()
    cases = _CASES_CACHE
    splits = json.loads(SPLITS.read_text(encoding="utf-8"))
    preds = load_predictions(run_dir)
    stops = load_stop_nodes(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    budgets = manifest.get("timeouts_s", {})

    paired = build_paired_table(cases, splits, preds, stops, budgets)
    _write_csv(diag / "paired_case_table.csv", paired)

    tri = abstention_triage(cases, preds, stops)
    for row in tri:
        row["split"] = splits.get("assignment", {}).get(row["case_id"], "")
    _write_csv(diag / "abstention_triage.csv", tri)

    tt = timeout_triage(cases, preds, stops)
    _write_csv(diag / "timeout_triage.csv", tt)

    dc = direct_completed_failures(cases, preds, stops)
    _write_csv(diag / "direct_completed_failures.csv", dc)

    written = write_plots(run_dir, stops, preds)
    print(f"paired rows: {len(paired)}")
    print(f"abstentions: {len(tri)}  avoidable={sum(1 for r in tri if r['classification']=='avoidable')} "
          f"justified={sum(1 for r in tri if r['classification']=='justified')}")
    print(f"timeouts: {len(tt)}  bottlenecks={dict(Counter(r['bottleneck'] for r in tt))}")
    print(f"direct-completed cases: {len(dc)}")
    print("figures:", ", ".join(written))
    print(f"diagnostics dir: {diag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
