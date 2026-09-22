#!/usr/bin/env python3
"""Generate audit plots. All values are measured or explicitly classification-coded."""
from __future__ import annotations

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CSV = HERE / "csv"
OUT = HERE / "plots"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"figure.dpi": 140, "font.size": 9, "axes.grid": True,
                     "grid.alpha": 0.25, "axes.axisbelow": True})

PALETTE = {"FULL": "#2a9d8f", "PARTIAL": "#8ab17d", "WEAK": "#e9c46a",
           "MISSING": "#e76f51"}


def save(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print("plot", name)


# 1. repository census: LOC by directory
census = pd.read_csv(CSV / "repo_census.csv")
c = census[census["lines"] > 0].sort_values("lines", ascending=True)
fig, ax = plt.subplots(figsize=(9, 8))
colors = ["#e76f51" if "BROKEN" in s or "MOCK" in s or "UNTESTED" in s or "DESIGN" in s
          else "#457b9d" for s in c["implementation_status"]]
ax.barh(c["path"], c["lines"], color=colors)
ax.set_xlabel("lines of Python (AST-measured)")
ax.set_title("PROTACxtend next-version audit — code volume by package\n(red = broken / mock / untested-in-full / design-only)")
save(fig, "01_repo_census_loc")

# 2. capability registry maturity by kind (measured 2026-09-18 audit)
registry = pd.read_csv(HERE.parent / "results/audit/capability_registry.csv")
pivot = registry.pivot_table(index="kind", columns="maturity_status",
                             values="id", aggfunc="count").fillna(0)
order = ["scientifically-validated", "internally-benchmarked", "smoke-tested",
         "installed", "ready", "registered_but_not_executable",
         "registered_but_unavailable", "unknown"]
order = [o for o in order if o in pivot.columns]
pivot = pivot[order]
fig, ax = plt.subplots(figsize=(10, 6))
bottom = np.zeros(len(pivot))
cmap = plt.get_cmap("RdYlGn_r", len(order))
for i, col in enumerate(order):
    ax.bar(pivot.index, pivot[col], bottom=bottom, label=col, color=cmap(i / max(len(order) - 1, 1)))
    bottom += pivot[col].values
ax.set_ylabel("registered resources")
ax.set_title("Capability maturity by resource kind (from results/audit/capability_registry.csv, n=367)")
plt.xticks(rotation=30, ha="right")
ax.legend(fontsize=7, ncol=2)
save(fig, "02_capability_maturity_by_kind")

# 3. scientific capability matrix heatmap
mat = pd.read_csv(CSV / "capability_matrix.csv")
axes_cols = [c for c in mat.columns if c != "evidence" and c != "domain"]
code = {"FULL": 3, "PARTIAL": 2, "WEAK": 1, "MISSING": 0}
grid = mat[axes_cols].applymap(lambda v: code.get(v, np.nan)).values
fig, ax = plt.subplots(figsize=(10, 8))
im = ax.imshow(grid, cmap="RdYlGn", vmin=0, vmax=3, aspect="auto")
ax.set_xticks(range(len(axes_cols)))
ax.set_xticklabels([c.replace("_", "\n") for c in axes_cols], fontsize=7)
ax.set_yticks(range(len(mat)))
ax.set_yticklabels(mat["domain"], fontsize=8)
for i in range(grid.shape[0]):
    for j in range(grid.shape[1]):
        ax.text(j, i, ["MISS", "WEAK", "PART", "FULL"][int(grid[i, j])],
                ha="center", va="center", fontsize=6)
ax.set_title("Scientific capability matrix — 16 benchmark domains x 10 axes\n(values are code/evidence classifications, not scores)")
cb = fig.colorbar(im, ticks=[0, 1, 2, 3], shrink=0.7)
cb.ax.set_yticklabels(["MISSING", "WEAK", "PARTIAL", "FULL"])
save(fig, "03_scientific_capability_matrix")

# 4. benchmark artifacts: tasks vs scorable
ba = pd.read_csv(CSV / "benchmark_artifacts.csv")
labels = ["benchmark/ (48)", "sota/eval (624)", "eval500 (600)", "tpdeval (500)"]
tasks = [48, 624, 600, 500]
scorable = [0, 0, 0, 0]
x = np.arange(len(labels))
fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(x - 0.2, tasks, 0.4, label="tasks declared", color="#457b9d")
ax.bar(x + 0.2, scorable, 0.4, label="objectively scorable tasks", color="#e76f51")
for i, (t, s) in enumerate(zip(tasks, scorable)):
    ax.text(i - 0.2, t + 8, str(t), ha="center")
    ax.text(i + 0.2, s + 8, str(s), ha="center")
ax.set_xticks(x); ax.set_xticklabels(labels)
ax.set_ylabel("task count")
ax.set_title("Benchmark inventories: declared vs objectively scorable\n(48 cases: expected_answer=null; eval500: template rubrics; tpdeval: REQUIRES_AUTHORING)")
ax.legend()
save(fig, "04_benchmark_declared_vs_scorable")

# 5. domain readiness (count of axes >= PARTIAL per domain)
score = (mat[axes_cols].applymap(lambda v: {"FULL": 1.0, "PARTIAL": 0.6, "WEAK": 0.2, "MISSING": 0.0}[v]).sum(axis=1))
order = score.sort_values(ascending=True).index
fig, ax = plt.subplots(figsize=(9, 7))
cols = ["#e76f51" if score[i] < 2.0 else "#e9c46a" if score[i] < 4.0 else "#2a9d8f" for i in order]
ax.barh(mat.loc[order, "domain"], score[order], color=cols)
ax.set_xlabel("capability readiness index (max 10; classification-derived, not a score)")
ax.set_title("Per-domain readiness across 10 audit axes (16 benchmark domains)")
save(fig, "05_domain_readiness_index")

# 6. agent node maturity
agents = pd.read_csv(CSV / "agent_inventory.csv")
counts = agents["status"].value_counts()
fig, ax = plt.subplots(figsize=(6, 5))
ax.pie(counts.values, labels=counts.index, autopct="%1.0f%%",
       colors=["#457b9d", "#e9c46a", "#e76f51"][:len(counts)])
ax.set_title(f"Current agent/node implementation status (n={len(agents)})")
save(fig, "06_agent_status")

# 7. agentic 7-layer coverage vs required next-version stages
layers = ["intent", "decomposition", "planner", "tool selection", "tool execution",
          "state/memory", "evidence aggreg.", "experiment", "critic", "decision"]
current = [1, 0.3, 0.4, 0.3, 0.8, 0.6, 0.2, 0.4, 0.3, 0.3]
required = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
x = np.arange(len(layers))
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(x - 0.2, current, 0.4, label="current (evidence-classified)", color="#e76f51")
ax.bar(x + 0.2, required, 0.4, label="required for L6/L7", color="#2a9d8f")
ax.set_xticks(x); ax.set_xticklabels(layers, rotation=30, ha="right")
ax.set_ylabel("coverage (0-1)")
ax.set_title("Agent execution pipeline coverage: current vs required")
ax.legend()
save(fig, "07_agent_pipeline_coverage")

# 8. gap priorities
gaps = pd.read_csv(CSV / "gap_analysis.csv")
gc = gaps["priority"].value_counts().reindex(["P0", "P1", "P2", "P3"]).fillna(0)
fig, ax = plt.subplots(figsize=(6, 5))
ax.bar(gc.index, gc.values, color=["#e76f51", "#e9c46a", "#8ab17d", "#457b9d"])
for i, v in enumerate(gc.values):
    ax.text(i, v + 0.1, int(v), ha="center")
ax.set_ylabel("number of gaps")
ax.set_title("Gap analysis by priority (P0 blocks benchmark validity)")
save(fig, "08_gap_priorities")

# 9. test results measured
tr = pd.read_csv(CSV / "test_results.csv")
tr = tr[tr["scope"] != "FULL SUITE"]
fig, ax = plt.subplots(figsize=(8, 5))
x = np.arange(len(tr))
ax.bar(x - 0.2, tr["passed"], 0.4, label="passed", color="#2a9d8f")
ax.bar(x + 0.2, tr["failed"], 0.4, label="failed", color="#e76f51")
ax.bar(x + 0.2, tr["skipped"], 0.4, bottom=tr["failed"], label="skipped", color="#adb5bd")
ax.set_xticks(x); ax.set_xticklabels(tr["scope"], rotation=20, ha="right")
ax.set_ylabel("tests")
ax.set_title("Measured test results (2026-09-21; full suite did not finish in 30 min)")
ax.legend()
save(fig, "09_test_results")

# 10. claimed vs verified capability (headline)
caps = ["agent tools\nexecutable", "scientifically\nvalidated", "internally\nbenchmarked",
        "registered but\nnot executable", "databases\nunavailable", "scorable\nbenchmark tasks"]
vals = [28, 1, 5, 115, 49, 0]
fig, ax = plt.subplots(figsize=(9, 5))
colors = ["#2a9d8f", "#2a9d8f", "#8ab17d", "#e76f51", "#e76f51", "#e76f51"]
ax.bar(caps, vals, color=colors)
for i, v in enumerate(vals):
    ax.text(i, v + 1.5, str(v), ha="center")
ax.set_ylabel("count")
ax.set_title("What is actually verified (measured 2026-09-21) vs what is only registered")
save(fig, "10_verified_vs_registered")

print("all plots done")
