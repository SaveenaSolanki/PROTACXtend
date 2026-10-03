#!/usr/bin/env python
"""Figures for the closed 48-case benchmark (gold-independent).

Reads ``<run-dir>/predictions.jsonl`` (+ optional scored ``scores.json``) and
writes **square**, fully-labelled publication-style PNGs plus a captions file
and per-figure CSV data.

Design contract (checked by ``tests/test_figure_quality.py``):

* every panel is square (``axes.set_box_aspect(1)`` + square figure canvas);
* every axis carries an explicit x label and y label with units;
* correctness is only drawn when gold is reviewer-approved.

Usage::

    python scripts/plot_closed_48.py --run-dir benchmark_results/closed48/<run_id>
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from protacxtend.validation.closure_figures import (  # noqa: E402
    OUTCOME_COLORS,
    OUTCOME_ORDER,
    apply_style,
    save_square,
    style_axes,
)

# Arm display order used across the figures.
ARM_ORDER = ["protacxtend", "direct_tool", "fixed_workflow"]
ARM_LABELS = {"protacxtend": "PROTACXtend", "direct_tool": "direct tool",
              "fixed_workflow": "fixed workflow"}


def load(run_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (run_dir / "predictions.jsonl")
            .read_text(encoding="utf-8").splitlines() if line.strip()]


def savefig(fig, out: Path, name: str, captions: list[str], caption: str,
            *, size_in: float = 6.5) -> None:
    save_square(fig, out / name, size_in=size_in)
    captions.append(f"## {name}\n\n{caption}\n")


def fig_outcomes_by_arm(preds, out, captions):
    arms = [a for a in ARM_ORDER if any(p["arm"] == a for p in preds)]
    labels = [ARM_LABELS.get(a, a) for a in arms]
    apply_style()
    fig, ax = plt.subplots()
    bottom = np.zeros(len(arms))
    for outcome in OUTCOME_ORDER:
        vals = np.array([sum(1 for p in preds if p["arm"] == a and p["outcome"] == outcome)
                         for a in arms], dtype=float)
        if not vals.any():
            continue
        ax.bar(labels, vals, bottom=bottom, label=outcome, color=OUTCOME_COLORS[outcome])
        bottom += vals
    for i, total in enumerate(bottom):
        ax.text(i, total + 0.6, f"n={int(total)}", ha="center", fontsize=9)
    style_axes(
        ax,
        xlabel="System arm",
        ylabel="Cases (n = 48 per arm)",
        title="Outcome composition by arm",
    )
    ax.set_ylim(0, 56)
    ax.tick_params(axis="x", rotation=10)
    ax.legend(fontsize=8, ncol=3, frameon=False, loc="upper center")
    savefig(fig, out, "fig1_outcomes_by_arm.png", captions,
            "Outcome composition for each of the three arms over the 48 cases. "
            "Correctness is not shown; gold is pending independent adjudication.")


def fig_outcomes_by_capability(preds, out, captions):
    arms = [a for a in ARM_ORDER if any(p["arm"] == a for p in preds)]
    caps = sorted({p.get("capability", "?") for p in preds})
    completed = np.array([
        [sum(1 for p in preds if p["arm"] == a and p.get("capability") == c
             and p["outcome"] == "completed") for a in arms]
        for c in caps
    ], dtype=float)
    apply_style()
    fig, ax = plt.subplots()
    im = ax.imshow(completed, cmap="YlGn", aspect="equal", vmin=0, vmax=max(1.0, completed.max()))
    ax.set_xticks(np.arange(len(arms)))
    ax.set_xticklabels([ARM_LABELS.get(a, a) for a in arms])
    ax.set_yticks(np.arange(len(caps)))
    ax.set_yticklabels(caps)
    for i in range(len(caps)):
        for j in range(len(arms)):
            value = int(completed[i, j])
            ax.text(j, i, str(value), ha="center", va="center", fontsize=9,
                    color="white" if value > completed.max() * 0.6 else "black")
    style_axes(
        ax,
        xlabel="System arm",
        ylabel="Capability",
        title="Completed cases by capability and arm",
    )
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Completed cases (n)")
    savefig(fig, out, "fig2_outcomes_by_capability.png", captions,
            "Completed cases per capability and arm over the 48 cases.")


def fig_runtime(preds, out, captions):
    arms = [a for a in ARM_ORDER if any(p["arm"] == a for p in preds)]
    data = [[float(p["latency_s"]) for p in preds
             if p["arm"] == a and p.get("latency_s") is not None] for a in arms]
    apply_style()
    fig, ax = plt.subplots()
    bp = ax.boxplot(data, tick_labels=[ARM_LABELS.get(a, a) for a in arms], showfliers=True,
                    patch_artist=True)
    for patch, arm in zip(bp["boxes"], arms, strict=True):
        patch.set_facecolor({"protacxtend": "#0072B2", "direct_tool": "#009E73",
                             "fixed_workflow": "#E69F00"}.get(arm, "#999999"))
        patch.set_alpha(0.6)
    ax.set_yscale("log")
    style_axes(
        ax,
        xlabel="System arm",
        ylabel="Wall-clock latency (s, log scale)",
        title="Per-case wall time by arm (locked budgets)",
    )
    ax.tick_params(axis="x", rotation=10)
    savefig(fig, out, "fig3_runtime_by_arm.png", captions,
            "Per-case wall time. Values at the locked budget are cut-offs, not natural runtimes.")


def fig_failure_taxonomy(preds, out, captions):
    arms = [a for a in ARM_ORDER if any(p["arm"] == a for p in preds)]
    codes = sorted({p.get("failure_code", "") for p in preds if p.get("failure_code")})
    if not codes:
        codes = ["(none)"]
    apply_style()
    fig, ax = plt.subplots()
    height = 0.8 / max(1, len(arms))
    for i, arm in enumerate(arms):
        counts = [sum(1 for p in preds if p["arm"] == arm and (p.get("failure_code") or "(none)") == c)
                  for c in codes]
        ax.barh([y + i * height for y in range(len(codes))], counts, height=height,
                label=ARM_LABELS.get(arm, arm))
    ax.set_yticks(range(len(codes)))
    ax.set_yticklabels(codes, fontsize=8)
    style_axes(
        ax,
        xlabel="Cases (n)",
        ylabel="Typed failure / abstention code",
        title="Typed failure taxonomy by arm",
    )
    ax.legend(fontsize=8, frameon=False)
    savefig(fig, out, "fig4_failure_taxonomy.png", captions,
            "Typed failure/abstention codes by arm.")


def fig_correctness(run_dir: Path, out: Path, captions) -> None:
    sp = run_dir / "scores.json"
    if not sp.exists():
        return
    doc = json.loads(sp.read_text(encoding="utf-8"))
    if doc.get("status") != "scored_against_approved_gold":
        return
    summary = doc.get("summary", {}).get("arms", {})
    arms = [a for a in ARM_ORDER if summary.get(a, {}).get("mean_correctness") is not None]
    if not arms:
        arms = [a for a in summary if summary[a].get("mean_correctness") is not None]
    if not arms:
        return
    vals = [summary[a]["mean_correctness"] for a in arms]
    apply_style()
    fig, ax = plt.subplots()
    ax.bar([ARM_LABELS.get(a, a) for a in arms], vals, color="#0072B2")
    for i, value in enumerate(vals):
        ax.text(i, value + 0.01, f"{value:.3f}", ha="center", fontsize=9)
    style_axes(
        ax,
        xlabel="System arm",
        ylabel="Mean correctness (reviewer-approved gold)",
        title="Mean correctness vs approved gold (48 cases)",
    )
    ax.set_ylim(0, max(1.0, max(vals) * 1.2))
    ax.tick_params(axis="x", rotation=10)
    savefig(fig, out, "fig5_correctness_by_arm.png", captions,
            "Mean task correctness against reviewer-approved gold. Only present when gold is approved.")


def _write_source_csv(preds, out: Path) -> None:
    with (out / "fig1_source_data.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["arm", "outcome", "n"])
        for arm in sorted({p["arm"] for p in preds}):
            for outcome in OUTCOME_ORDER:
                n = sum(1 for p in preds if p["arm"] == arm and p["outcome"] == outcome)
                if n:
                    writer.writerow([arm, outcome, n])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    preds = load(args.run_dir)
    out = args.run_dir / "figures"
    out.mkdir(parents=True, exist_ok=True)
    captions: list[str] = ["# Closed 48-case benchmark — figure captions\n"]
    fig_outcomes_by_arm(preds, out, captions)
    fig_outcomes_by_capability(preds, out, captions)
    fig_runtime(preds, out, captions)
    fig_failure_taxonomy(preds, out, captions)
    fig_correctness(args.run_dir, out, captions)
    (out / "CAPTIONS.md").write_text("\n".join(captions), encoding="utf-8")
    _write_source_csv(preds, out)
    print(f"figures: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
