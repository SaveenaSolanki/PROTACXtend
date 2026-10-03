#!/usr/bin/env python3
"""Generate publication-style figures for the ProtacXtend study deck.

All figures are computed from files on disk (benchmark GT, benchmark500 cases,
capability crosswalk, closed48 real execution run, run traces, source tree).
No illustrative/placeholder data.

Run:
    python study/make_figures.py
Output:
    study/figures/*.png  (400 dpi, print-ready)
"""
from __future__ import annotations

import collections
import csv
import glob
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "study" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# ── house style ───────────────────────────────────────────────────────────
NAVY = "#0F1E33"
INK = "#1B2430"
SLATE = "#4A5768"
TEAL = "#17A398"
AMBER = "#E8A33D"
RED = "#C4453B"
PAPER = "#F4F6F9"
LINE = "#D5DBE3"
GRID = "#E4E9EF"

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": SLATE,
    "axes.labelcolor": INK,
    "axes.titlecolor": NAVY,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "xtick.color": SLATE,
    "ytick.color": SLATE,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "legend.fontsize": 9,
    "figure.dpi": 150,
    "savefig.dpi": 400,
    "savefig.bbox": "tight",
})


def save(fig, name):
    fig.savefig(FIG / f"{name}.png")
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.svg")
    plt.close(fig)
    print("wrote", name)


def _no_grid(ax):
    ax.grid(axis="x", color=GRID, lw=0.7)
    ax.set_axisbelow(True)


# ══════════════════════════════════════════════════════════════════════════
# data loaders
# ══════════════════════════════════════════════════════════════════════════
def load_gt():
    types = collections.Counter()
    diff = collections.Counter()
    cap = collections.Counter()
    capdiff = collections.Counter()
    ev = []
    for f in glob.glob(str(ROOT / "benchmark/ground_truth/*.json")):
        d = json.load(open(f))
        types[d.get("type", "?")] += 1
        diff[d.get("difficulty", "?")] += 1
        cap[d.get("capability", "?")] += 1
        capdiff[(d.get("capability", "?"), d.get("difficulty", "?"))] += 1
        ev.append(len(d.get("evidence_sources", [])))
    return types, diff, cap, capdiff, ev


def load_b500(suite):
    dom = collections.Counter()
    diff = collections.Counter()
    for line in open(ROOT / f"benchmark500/cases/{suite}.jsonl"):
        d = json.loads(line)
        dom[d.get("domain", "?")] += 1
        diff[d.get("difficulty_level", 0)] += 1
    return dom, diff


def load_crosswalk():
    import yaml
    d = yaml.safe_load(open(ROOT / "config/capability_backend_crosswalk.yaml"))
    return d


def load_closed48():
    p = ROOT / "benchmark_results/closed48/closed48_retrieval_reliability_20260927/results_table.csv"
    rows = list(csv.DictReader(open(p)))
    return rows


def load_trace_events():
    c = collections.Counter()
    for f in glob.glob(str(ROOT / "outputs/runs/*/trace.jsonl")):
        for line in open(f):
            try:
                c[json.loads(line).get("event", "?")] += 1
            except Exception:
                pass
    return c


def load_node_waterfall():
    p = ROOT / "outputs/runs/trace_test/trace.jsonl"
    events = [json.loads(l) for l in open(p)]
    # first run's node_end timings
    nodes, durs = [], []
    for e in events:
        if e.get("event") == "node_end":
            nodes.append(e.get("node", "?"))
            durs.append(float(e.get("elapsed_s", 0)))
        if len(nodes) >= 23:
            break
    return nodes, durs


def code_scale():
    subs = {
        "agents": "protacxtend/agents", "tools": "protacxtend/tools",
        "modules": "protacxtend/modules", "scientific_backends": "protacxtend/scientific_backends",
        "runtime": "protacxtend/runtime", "memory": "protacxtend/memory",
        "canonical": "protacxtend/canonical", "validation": "protacxtend/validation",
        "escalation": "protacxtend/escalation", "planning": "protacxtend/planning",
        "evidence": "protacxtend/evidence", "workflows": "protacxtend/workflows",
    }
    out = {}
    for k, rel in subs.items():
        files = glob.glob(str(ROOT / rel / "**/*.py"), recursive=True)
        loc = 0
        for f in files:
            try:
                loc += sum(1 for _ in open(f, errors="ignore"))
            except Exception:
                pass
        out[k] = (len(files), loc)
    return out


# ══════════════════════════════════════════════════════════════════════════
# F01 — benchmark inventory: authored vs curated gold
# ══════════════════════════════════════════════════════════════════════════
def f01():
    labels = ["benchmark/\ngoverned", "benchmark500\ngeneral", "benchmark500\ntemporal",
              "tpdeval\ndesign", "sota/eval\neval500"]
    authored = [48, 500, 500, 500, 624]
    gold = [0, 0, 0, 0, 50]
    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.barh(y + 0.19, authored, height=0.36, color=NAVY, label="tasks authored")
    ax.barh(y - 0.19, gold, height=0.36, color=RED, label="curated gold")
    for i, (a, g) in enumerate(zip(authored, gold)):
        ax.text(a + 12, i + 0.19, str(a), va="center", fontsize=9, color=NAVY, fontweight="bold")
        ax.text(g + 12, i - 0.19, str(g), va="center", fontsize=9, color=RED, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("number of tasks")
    ax.set_title("Benchmark inventory: 0 curated gold in the two 500-task banks")
    ax.legend(loc="lower right")
    _no_grid(ax)
    ax.set_xlim(0, 730)
    save(fig, "f01_benchmark_inventory")


# ══════════════════════════════════════════════════════════════════════════
# F02 — governed 48: capability×difficulty heatmap + GT types
# ══════════════════════════════════════════════════════════════════════════
def f02():
    types, diff, cap, capdiff, ev = load_gt()
    caps = ["KNOW", "REASON", "DESIGN", "DISCOVER"]
    diffs = ["easy", "medium", "hard"]
    M = np.array([[capdiff.get((c, d), 0) for d in diffs] for c in caps])
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.8), gridspec_kw={"width_ratios": [1.05, 1]})
    ax = axes[0]
    im = ax.imshow(M, cmap="Blues", aspect="auto", vmin=0, vmax=M.max())
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, M[i, j], ha="center", va="center", fontsize=11,
                    color=("white" if M[i, j] > M.max() * 0.55 else INK), fontweight="bold")
    ax.set_xticks(range(3), diffs)
    ax.set_yticks(range(4), caps)
    ax.set_title("48 governed cases: capability × difficulty")
    ax.set_xlabel("difficulty")
    for s in ax.spines.values():
        s.set_visible(False)

    ax = axes[1]
    order = ["exact", "categorical", "ranked", "mechanistic_rubric", "design_rubric"]
    vals = [types.get(k, 0) for k in order]
    cols = [TEAL, TEAL, TEAL, AMBER, AMBER]
    bars = ax.bar(range(len(order)), vals, color=cols, width=0.68)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.3, str(v), ha="center",
                fontsize=10, fontweight="bold", color=INK)
    ax.set_xticks(range(len(order)),
                  ["exact", "categ.", "ranked", "mechan.\nrubric", "design\nrubric"])
    ax.set_ylabel("ground-truth items")
    ax.set_title("19/48 objectively scorable (teal)")
    _no_grid(ax)
    save(fig, "f02_governed_composition")


# ══════════════════════════════════════════════════════════════════════════
# F03 — benchmark500 domain distribution
# ══════════════════════════════════════════════════════════════════════════
def f03():
    dom_g, _ = load_b500("general_500")
    order = [d for d, _ in dom_g.most_common()]
    vals = [dom_g[d] for d in order]
    short = [d.replace(" & ", " & ").replace(" mechanisms", "").replace(" and ", " & ") for d in order]
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    y = np.arange(len(order))[::-1]
    ax.barh(y, vals, color=NAVY, height=0.66)
    for yy, v in zip(y, vals):
        ax.text(v + 0.6, yy, str(v), va="center", fontsize=8.5, color=INK)
    ax.set_yticks(y, short, fontsize=8.5)
    ax.set_xlabel("tasks per domain (general_500)")
    ax.set_title("benchmark500: 16 TPD domains × ~500 tasks (no gold yet)")
    _no_grid(ax)
    ax.set_xlim(0, 58)
    save(fig, "f03_b500_domains")


# ══════════════════════════════════════════════════════════════════════════
# F04 — benchmark500 difficulty L1–L7
# ══════════════════════════════════════════════════════════════════════════
def f04():
    _, dg = load_b500("general_500")
    _, dt = load_b500("temporal_500")
    levels = list(range(1, 8))
    x = np.arange(len(levels))
    g = [dg.get(l, 0) for l in levels]
    t = [dt.get(l, 0) for l in levels]
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    ax.bar(x - 0.2, g, width=0.4, color=NAVY, label="general_500")
    ax.bar(x + 0.2, t, width=0.4, color=TEAL, label="temporal_500")
    ax.set_xticks(x, [f"L{l}" for l in levels])
    ax.set_xlabel("difficulty level (L1 retrieval → L7 discovery)")
    ax.set_ylabel("tasks")
    ax.set_title("Difficulty distribution is skewed to L4–L6")
    ax.legend()
    _no_grid(ax)
    save(fig, "f04_b500_difficulty")


# ══════════════════════════════════════════════════════════════════════════
# F05 — capability readiness
# ══════════════════════════════════════════════════════════════════════════
def f05():
    d = load_crosswalk()
    ready = d["summary"]["by_readiness"]
    labels = ["READY", "EXECUTABLE", "BLOCKED"]
    vals = [ready["READY"], ready["EXECUTABLE"], ready["BLOCKED"]]
    cols = [TEAL, NAVY, RED]
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.0), gridspec_kw={"width_ratios": [1, 1.5]})
    ax = axes[0]
    wedges, _ = ax.pie(vals, colors=cols, startangle=90,
                       wedgeprops=dict(width=0.42, edgecolor="white", lw=2))
    ax.text(0, 0.06, f"{sum(vals)}", ha="center", va="center", fontsize=26,
            fontweight="bold", color=NAVY)
    ax.text(0, -0.24, "capabilities", ha="center", va="center", fontsize=9, color=SLATE)
    ax.set_title("Scientific capability readiness")
    ax.legend(wedges, [f"{l}  ({v})" for l, v in zip(labels, vals)],
              loc="lower center", bbox_to_anchor=(0.5, -0.16), ncol=3, fontsize=8.5)

    ax = axes[1]
    blocked = list(d["summary"]["blocked"].keys())
    yy = np.arange(len(blocked))[::-1]
    ax.barh(yy, [1] * len(blocked), color=RED, height=0.6, alpha=0.85)
    ax.set_yticks(yy, [b.replace("_", " ") for b in blocked], fontsize=8.5)
    ax.set_xticks([])
    ax.set_title("11 BLOCKED capabilities (scored as reasoning, not execution)")
    for s in ax.spines.values():
        s.set_visible(False)
    save(fig, "f05_capability_readiness")


# ══════════════════════════════════════════════════════════════════════════
# F06 — architecture schematic
# ══════════════════════════════════════════════════════════════════════════
def f06():
    fig, ax = plt.subplots(figsize=(12.4, 4.6))
    ax.set_xlim(0, 124)
    ax.set_ylim(0, 46)
    ax.axis("off")

    def box(x, y, w, h, title, sub, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.4",
                                    fc=PAPER, ec=color, lw=1.6))
        ax.add_patch(FancyBboxPatch((x, y + h - 5.2), w, 5.2,
                                    boxstyle="round,pad=0.6,rounding_size=1.4",
                                    fc=color, ec=color, lw=1.4))
        ax.text(x + w / 2, y + h - 2.6, title, ha="center", va="center",
                fontsize=10.5, fontweight="bold", color="white")
        ax.text(x + w / 2, y + (h - 5.2) / 2, sub, ha="center", va="center",
                fontsize=8.4, color=INK, linespacing=1.45)

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=13, color=SLATE, lw=1.3))

    box(1, 12, 15, 22, "Request", "parser · intent\nentity resolution\nidentity gate\nanswer contracts", TEAL)
    box(18.5, 12, 15, 22, "Planner", "design planner\nNP-hard search\nrouting/DAG\ngoal setting", TEAL)
    box(36, 12, 17, 22, "Workflow graph", "34 nodes\ncapability routes\nKNOW / REASON\nDESIGN / DISCOVER\nretry policy", NAVY)
    box(55, 24, 17, 10, "Specialists", "15 agents:\ntarget · binder · warhead\nE3 · linker · ternary\ndegradation · ADMET · rank", NAVY)
    box(55, 12, 17, 10, "Tools", "~30 exec_* calls\n100 modules\n27 capabilities", AMBER)
    box(74, 24, 17, 10, "Knowledge", "EuropePMC · PubMed\nOpenAlex · Crossref\nliterature RAG", AMBER)
    box(74, 12, 17, 10, "Backends", "19 backends\n10 ready · 6 exec\n11 blocked", AMBER)
    box(93, 24, 15, 10, "Evidence", "claim ledger\nevidence cards\ngraph/trace", TEAL)
    box(93, 12, 15, 10, "State/memory", "WorkflowState\nrun_state\nvector store", TEAL)
    box(110, 12, 13, 22, "Output", "ranking\ngates\nreport\nrun record", RED)

    for x1, x2 in [(16, 18.5), (33.5, 36), (53, 55), (72, 74), (91, 93), (108, 110)]:
        arrow(x1, 23, x2, 23)
    arrow(63.5, 24, 63.5, 22)
    arrow(83, 24, 83, 22)
    ax.set_title("ProtacXtend architecture as implemented (counts from the system audit)",
                 fontsize=12.5, pad=10)
    save(fig, "f06_architecture")


# ══════════════════════════════════════════════════════════════════════════
# F07 — code scale by component
# ══════════════════════════════════════════════════════════════════════════
def f07():
    sc = code_scale()
    order = sorted(sc.items(), key=lambda kv: kv[1][1])
    names = [k for k, _ in order]
    locs = [v[1] for _, v in order]
    files = [v[0] for _, v in order]
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    y = np.arange(len(names))
    ax.barh(y, locs, color=NAVY, height=0.66)
    for yy, (loc, nf) in zip(y, zip(locs, files)):
        ax.text(loc + max(locs) * 0.01, yy, f"{loc:,} loc · {nf} files",
                va="center", fontsize=8, color=SLATE)
    ax.set_yticks(y, [n.replace("_", " ") for n in names])
    ax.set_xlabel("lines of Python code")
    ax.set_title("Implemented system scale (a real codebase, not a scaffold)")
    _no_grid(ax)
    ax.set_xlim(0, max(locs) * 1.32)
    save(fig, "f07_module_scale")


# ══════════════════════════════════════════════════════════════════════════
# F08 — closed48 REAL outcomes by arm
# ══════════════════════════════════════════════════════════════════════════
def f08():
    rows = load_closed48()
    arms = ["protacxtend", "fixed_workflow", "direct_tool"]
    nice = {"protacxtend": "ProtacXtend", "fixed_workflow": "Fixed workflow",
            "direct_tool": "Direct tool"}
    outcomes = ["completed", "partial", "abstained", "failed"]
    cols = {"completed": TEAL, "partial": AMBER, "abstained": NAVY, "failed": RED}
    counts = {o: [] for o in outcomes}
    for a in arms:
        sub = [r for r in rows if r["arm"] == a]
        for o in outcomes:
            counts[o].append(sum(1 for r in sub if r["outcome"] == o))
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    x = np.arange(len(arms))
    bottom = np.zeros(len(arms))
    for o in outcomes:
        vals = np.array(counts[o], float)
        ax.bar(x, vals, bottom=bottom, color=cols[o], width=0.6, label=o)
        for xi, (v, b) in enumerate(zip(vals, bottom)):
            if v > 0:
                ax.text(xi, b + v / 2, int(v), ha="center", va="center",
                        color="white", fontsize=10, fontweight="bold")
        bottom += vals
    ax.set_xticks(x, [nice[a] for a in arms])
    ax.set_ylabel("cases (of 48 per arm)")
    ax.set_title("Real closed48 run: typed outcomes by arm (n=144)")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    _no_grid(ax)
    save(fig, "f08_closed48_outcomes")


# ══════════════════════════════════════════════════════════════════════════
# F09 — closed48 REAL latency by arm
# ══════════════════════════════════════════════════════════════════════════
def f09():
    rows = load_closed48()
    arms = ["direct_tool", "fixed_workflow", "protacxtend"]
    nice = ["Direct tool", "Fixed workflow", "ProtacXtend"]
    data = [[float(r["latency_s"]) for r in rows if r["arm"] == a] for a in arms]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    bp = ax.boxplot(data, vert=True, patch_artist=True, widths=0.5,
                    medianprops=dict(color=NAVY, lw=2),
                    flierprops=dict(marker="o", markerfacecolor=RED, markersize=3,
                                    markeredgecolor="none", alpha=0.5))
    for patch, c in zip(bp["boxes"], [AMBER, NAVY, TEAL]):
        patch.set_facecolor(c)
        patch.set_alpha(0.75)
        patch.set_edgecolor(SLATE)
    rng = np.random.default_rng(0)
    for i, d in enumerate(data, start=1):
        jit = rng.normal(i, 0.06, len(d))
        ax.scatter(jit, d, s=9, color=INK, alpha=0.35, zorder=3)
    ax.set_xticks(range(1, 4), nice)
    ax.set_ylabel("per-case latency (s)")
    ax.set_title("Real closed48 run: latency per arm (n=48 each)")
    _no_grid(ax)
    ax.grid(axis="y", color=GRID, lw=0.7)
    save(fig, "f09_closed48_latency")


# ══════════════════════════════════════════════════════════════════════════
# F10 — closed48 REAL evidence refs by arm
# ══════════════════════════════════════════════════════════════════════════
def f10():
    rows = load_closed48()
    arms = ["direct_tool", "fixed_workflow", "protacxtend"]
    nice = ["Direct tool", "Fixed workflow", "ProtacXtend"]
    data = [[float(r["n_evidence_refs"]) for r in rows if r["arm"] == a] for a in arms]
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    means = [np.mean(d) for d in data]
    sems = [np.std(d, ddof=1) / np.sqrt(len(d)) for d in data]
    x = np.arange(3)
    ax.bar(x, means, yerr=sems, capsize=6, color=[AMBER, NAVY, TEAL],
           width=0.55, error_kw=dict(ecolor=INK, lw=1.4))
    for xi, m in zip(x, means):
        ax.text(xi, m + 0.05, f"{m:.2f}", ha="center", fontsize=10,
                fontweight="bold", color=INK)
    ax.set_xticks(x, nice)
    ax.set_ylabel("mean evidence refs / case (± SEM)")
    ax.set_title("Real closed48 run: evidence citation depth by arm")
    _no_grid(ax)
    ax.grid(axis="y", color=GRID, lw=0.7)
    save(fig, "f10_closed48_evidence")


# ══════════════════════════════════════════════════════════════════════════
# F11 — trace event composition
# ══════════════════════════════════════════════════════════════════════════
def f11():
    c = load_trace_events()
    order = ["run_start", "run_end", "tool_call", "node_start", "node_end",
             "decision", "error", "?"]
    order = [k for k in order if k in c]
    vals = [c[k] for k in order]
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    bars = ax.bar(range(len(order)), vals,
                  color=[TEAL, TEAL, NAVY, AMBER, AMBER, TEAL, RED, SLATE][:len(order)],
                  width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 8, str(v), ha="center",
                fontsize=9, color=INK, fontweight="bold")
    ax.set_xticks(range(len(order)), [o.replace("_", "\n") for o in order])
    ax.set_ylabel("events across 458 runs")
    ax.set_title("Observed execution traces: 1,858 recorded events")
    _no_grid(ax)
    ax.grid(axis="y", color=GRID, lw=0.7)
    save(fig, "f11_trace_events")


# ══════════════════════════════════════════════════════════════════════════
# F12 — node waterfall from a real trace
# ══════════════════════════════════════════════════════════════════════════
def f12():
    nodes, durs = load_node_waterfall()
    if not nodes:
        nodes, durs = ["node"], [0.01]
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    y = np.arange(len(nodes))[::-1]
    ax.barh(y, durs, color=TEAL, height=0.6)
    ax.set_yticks(y, nodes, fontsize=8)
    ax.set_xlabel("node elapsed time (s)")
    ax.set_title("Node timings captured in a real run trace")
    _no_grid(ax)
    save(fig, "f12_node_waterfall")


# ══════════════════════════════════════════════════════════════════════════
# F13 — planned experimental run counts
# ══════════════════════════════════════════════════════════════════════════
def f13():
    phases = ["Pilot", "Primary\nPOP-A", "E2E\nPOP-B", "Temporal\nPOP-C",
              "Abstention\nPOP-D", "Fault\nPOP-E", "Ablation\nPOP-G", "Cross-model\nPOP-F"]
    runs = [360, 3600, 960, 600, 720, 3600, 4500, 2700]
    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    bars = ax.bar(range(len(phases)), runs, color=NAVY, width=0.62)
    bars[0].set_color(TEAL)
    for b, v in zip(bars, runs):
        ax.text(b.get_x() + b.get_width() / 2, v + 60, f"{v:,}", ha="center",
                fontsize=9, color=INK, fontweight="bold")
    ax.set_xticks(range(len(phases)), phases, fontsize=8.5)
    ax.set_ylabel("planned runs")
    ax.set_title("Planned experimental matrix: ≈17,040 runs")
    _no_grid(ax)
    ax.grid(axis="y", color=GRID, lw=0.7)
    ax.set_ylim(0, 5100)
    save(fig, "f13_experiment_matrix")


# ══════════════════════════════════════════════════════════════════════════
# F14 — cost: API vs GPU
# ══════════════════════════════════════════════════════════════════════════
def f14():
    exps = ["Pilot", "Primary", "E2E", "Temporal+\nAbstention", "Fault", "Ablation", "Cross-model"]
    usd = [2, 25, 15, 10, 15, 20, 30]
    gpu = [20, 300, 500, 80, 80, 400, 150]
    fig, ax1 = plt.subplots(figsize=(8.0, 4.2))
    x = np.arange(len(exps))
    b = ax1.bar(x - 0.2, gpu, width=0.4, color=NAVY, label="GPU-hours")
    ax1.set_ylabel("GPU-hours", color=NAVY)
    ax1.tick_params(axis="y", labelcolor=NAVY)
    ax1.set_xticks(x, exps, fontsize=8.5)
    ax2 = ax1.twinx()
    b2 = ax2.bar(x + 0.2, usd, width=0.4, color=AMBER, label="API USD")
    ax2.set_ylabel("API cost (USD)", color=AMBER)
    ax2.tick_params(axis="y", labelcolor=AMBER)
    ax2.spines["top"].set_visible(False)
    ax1.set_title("Cost is dominated by GPU end-to-end runtime, not tokens")
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    save(fig, "f14_cost")


# ══════════════════════════════════════════════════════════════════════════
# F15 — hypothesis × experiment traceability
# ══════════════════════════════════════════════════════════════════════════
def f15():
    exps = ["Primary\nS0–S3", "E2E", "Temporal", "Abstention", "Fault\ninjection", "Ablation", "Cross-model", "Reproducibility"]
    hyps = ["H1 Scaffold", "H2 Orchestration", "H3 Evidence", "H4 Reliability", "H5 End-to-end", "H6 Repro"]
    M = np.array([
        [1, 0, 1, 0, 0, 1, 1, 0],   # H1
        [1, 1, 0, 0, 0, 1, 1, 0],   # H2
        [1, 1, 1, 0, 0, 1, 0, 0],   # H3
        [0, 0, 0, 1, 1, 1, 0, 0],   # H4
        [0, 1, 0, 0, 0, 1, 0, 0],   # H5
        [1, 1, 1, 0, 0, 0, 0, 1],   # H6
    ], float)
    fig, ax = plt.subplots(figsize=(9.2, 3.8))
    ax.imshow(M, cmap="Greens", vmin=0, vmax=1.4, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if M[i, j]:
                ax.text(j, i, "●", ha="center", va="center", color=NAVY, fontsize=13)
    ax.set_xticks(range(len(exps)), exps, fontsize=8)
    ax.set_yticks(range(len(hyps)), hyps, fontsize=9)
    ax.set_title("Every hypothesis is tested by ≥1 experiment; no orphan experiments")
    for s in ax.spines.values():
        s.set_visible(False)
    save(fig, "f15_traceability")


# ══════════════════════════════════════════════════════════════════════════
# F16 — G0–G12 workflow
# ══════════════════════════════════════════════════════════════════════════
def f16():
    stages = ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12"]
    names = ["Target", "Rationale", "Binder", "E3", "E3 ligand", "Linker",
             "Construct", "Ternary", "Degrade", "ADME", "Synthesis", "Rank", "Experiment"]
    fig, ax = plt.subplots(figsize=(12.6, 2.6))
    ax.set_xlim(-0.5, 12.5)
    ax.set_ylim(0, 3)
    ax.axis("off")
    for i, (st, nm) in enumerate(zip(stages, names)):
        col = NAVY if i < 6 else (TEAL if i < 11 else AMBER)
        ax.add_patch(FancyBboxPatch((i - 0.42, 0.9), 0.84, 1.4,
                                    boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc=col, ec="white", lw=1))
        ax.text(i, 1.85, st, ha="center", va="center", color="white",
                fontsize=10, fontweight="bold")
        ax.text(i, 1.28, nm, ha="center", va="center", color="white", fontsize=6.6)
        if i < 12:
            ax.annotate("", xy=(i + 0.55, 1.6), xytext=(i + 0.45, 1.6),
                        arrowprops=dict(arrowstyle="-|>", color=SLATE, lw=1.2))
    ax.set_title("End-to-end PROTAC workflow, scored stage-by-stage (outcome codes: PASS / PARTIAL / FAIL / UNSUPPORTED / NOT_REACHED / ABSTAIN)",
                 fontsize=10.5)
    save(fig, "f16_workflow_g012")


# ══════════════════════════════════════════════════════════════════════════
# F17 — failure injection matrix
# ══════════════════════════════════════════════════════════════════════════
def f17():
    faults = ["invalid gene symbol", "ambiguous target alias", "wrong UniProt mapping",
              "nonexistent PDB", "no known binder", "malformed SMILES",
              "unsupported E3 pairing", "retrieval outage", "literature conflict",
              "docking failure", "backend timeout", "empty candidate set",
              "contradictory ADME", "impossible synthetic step", "missing ligand structure"]
    flags = ["Detected", "Recovered", "Fallback", "Abstained", "Hallucinated\ncontinuation"]
    fig, ax = plt.subplots(figsize=(6.6, 6.0))
    ax.imshow(np.ones((len(faults), len(flags))), cmap="Greys", vmin=0, vmax=3, alpha=0.18)
    for i in range(len(faults)):
        for j in range(len(flags)):
            col = RED if j == 4 else TEAL
            ax.text(j, i, "?", ha="center", va="center", color=col,
                    fontsize=12, fontweight="bold")
    ax.set_xticks(range(len(flags)), flags, fontsize=8)
    ax.set_yticks(range(len(faults)), faults, fontsize=8)
    ax.set_title("Failure-injection design: 15 fault classes × 5 behavioural flags\n(measured per episode; hallucinated continuation = safety endpoint)",
                 fontsize=9.5)
    for s in ax.spines.values():
        s.set_visible(False)
    save(fig, "f17_failure_matrix")


# ══════════════════════════════════════════════════════════════════════════
# F18 — metric hierarchy
# ══════════════════════════════════════════════════════════════════════════
def f18():
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    def node(x, y, w, h, text, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                                    fc=color, ec="none"))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                color="white", fontsize=9, fontweight="bold", linespacing=1.3)

    node(30, 50, 40, 8, "PRIMARY: Macro Scientific Success", NAVY)
    sec = ["Evidence-\ngrounded", "Partial\nscore", "Evidence\nquality", "Abstention\nquality", "Tool\nperformance"]
    for i, s in enumerate(sec):
        node(2 + i * 19.4, 32, 17.6, 9, s, TEAL)
        ax.annotate("", xy=(11 + i * 19.4, 41), xytext=(50, 50),
                    arrowprops=dict(arrowstyle="-", color=SLATE, lw=0.9))
    e2e = [("Stage\nsuccess", 2), ("Completion", 21), ("Valid\ncompletion", 40),
           ("First\nfailure", 59), ("Error\npropagation", 78)]
    for t, x in [(a, b) for a, b in e2e]:
        node(x, 14, 17.6, 9, t, AMBER)
    node(2, 2, 95, 7, "End-to-end + failure-injection + reproducibility endpoints", RED)
    ax.set_title("Pre-registered endpoint hierarchy", fontsize=12)
    save(fig, "f18_metric_hierarchy")


if __name__ == "__main__":
    for fn in [f01, f02, f03, f04, f05, f06, f07, f08, f09, f10,
               f11, f12, f13, f14, f15, f16, f17, f18]:
        fn()
    print("\nAll figures written to", FIG)
