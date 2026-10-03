"""Publication-quality square figures for the E1–E8 experiment closure.

Design contract (enforced by ``tests/test_figure_quality.py``):

* every panel is **square** (``axes.set_box_aspect(1)`` and a square figure);
* every axis has an explicit **x label and y label**, with units where relevant;
* every study/bar is annotated with its exact numerator/denominator;
* the figure is *honest*: engineering closure and scientific closure are shown
  separately, and no pre-gold score is drawn as accuracy.

The module is data-first: :data:`CLOSURE_DATA` is the single machine-readable
source for the closure matrix, and ``write_closure_figures`` writes both the
PNGs and the plotted values as CSV.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

#: Colour-blind-safe palette (Okabe–Ito derived).
PALETTE = {
    "engineering": "#0072B2",
    "scientific_open": "#D55E00",
    "scientific_closed": "#009E73",
    "required": "#999999",
    "executed": "#56B4E9",
    "adjudicated": "#009E73",
    "protacxtend": "#0072B2",
    "direct_tool": "#009E73",
    "fixed_workflow": "#E69F00",
}
OUTCOME_COLORS = {
    "completed": "#009E73", "partial": "#56B4E9", "abstained": "#F0E442",
    "refused": "#E69F00", "failed": "#D55E00", "timeout": "#CC79A7",
}
OUTCOME_ORDER = ["completed", "partial", "abstained", "refused", "failed", "timeout"]

#: E1–E8 closure matrix. ``required_n`` is the target cohort; ``executed_n`` is
#: the number actually run at the declared unit; ``adjudicated_n`` is the number
#: with independent gold. ``engineering_closed`` means the code + tests exist;
#: ``scientific_closed`` means the scientific endpoint is independently met.
CLOSURE_DATA: list[dict[str, Any]] = [
    {
        "id": "E1", "name": "Capability audit",
        "engineering_closed": True, "scientific_closed": False,
        "required_n": 123, "executed_n": 0, "adjudicated_n": 0,
        "evidence": "123 tools classified; 34/34 adapters clean; 0 per-tool real-input runs",
        "blocker": "per-tool positive/negative execution matrix",
    },
    {
        "id": "E2", "name": "Task performance",
        "engineering_closed": True, "scientific_closed": False,
        "required_n": 48, "executed_n": 48, "adjudicated_n": 0,
        "evidence": "48 cases x 3 arms executed; gold 0/48",
        "blocker": "independent gold adjudication",
    },
    {
        "id": "E3", "name": "Orchestration",
        "engineering_closed": True, "scientific_closed": False,
        "required_n": 100, "executed_n": 0, "adjudicated_n": 0,
        "evidence": "policy + 3 critics implemented and tested; 0 fault trials",
        "blocker": "frozen fault schedule + paired runs",
    },
    {
        "id": "E4", "name": "Therapeutic reasoning",
        "engineering_closed": False, "scientific_closed": False,
        "required_n": 50, "executed_n": 0, "adjudicated_n": 0,
        "evidence": "typed strategy can represent reasoning; 0 blinded expert cases",
        "blocker": "50 curated cases + blinded review",
    },
    {
        "id": "E5", "name": "TPD mechanics",
        "engineering_closed": False, "scientific_closed": False,
        "required_n": 100, "executed_n": 0, "adjudicated_n": 0,
        "evidence": "modules run; 0 casewise mechanistic gold",
        "blocker": "curated context-level assay records",
    },
    {
        "id": "E6", "name": "Ablations",
        "engineering_closed": False, "scientific_closed": False,
        "required_n": 48, "executed_n": 0, "adjudicated_n": 0,
        "evidence": "components individually testable; 0 ablated arms",
        "blocker": "frozen E2/E5 candidate cases",
    },
    {
        "id": "E7", "name": "Temporal validation",
        "engineering_closed": True, "scientific_closed": False,
        "required_n": 1000, "executed_n": 476, "adjudicated_n": 0,
        "evidence": "1000 ingested; 476 executed; 0 curated outcomes",
        "blocker": "frozen as-of corpus + post-cutoff outcomes",
    },
    {
        "id": "E8", "name": "End-to-end discovery",
        "engineering_closed": False, "scientific_closed": False,
        "required_n": 5, "executed_n": 0, "adjudicated_n": 0,
        "evidence": "typed plans + go/no-go emitted; 0 prospective programs",
        "blocker": "locked target programs + assays",
    },
]

#: Gold-independent closed 48-case execution outcomes (from
#: ``benchmark_results/closed48/closed48_locked``).
CLOSED48_OUTCOMES: dict[str, dict[str, int]] = {
    "protacxtend": {"abstained": 26, "timeout": 22},
    "direct_tool": {"completed": 45, "partial": 1, "abstained": 2},
    "fixed_workflow": {"partial": 48},
}

#: Pre-gold matched-compute baseline means (NOT accuracy).
BASELINE_MEANS: dict[str, dict[str, float]] = {
    "retrieval-only": {"KNOW": 0.0417, "REASON": 0.0, "DESIGN": 0.0417, "DISCOVER": 0.1667},
    "tool-only": {"KNOW": 0.0417, "REASON": 0.0, "DESIGN": 0.0833, "DISCOVER": 0.1875},
    "Base-LLM-control": {"KNOW": 0.2708, "REASON": 0.0278, "DESIGN": 0.1667, "DISCOVER": 0.2083},
}


#: Gold-independent 1000-task execution funnel (benchmark500, engineering only).
EXECUTION_FUNNEL: list[tuple[str, int]] = [
    ("Planned tasks", 1000),
    ("Eligible (uncurated gold)", 1000),
    ("Executed (real capability)", 476),
    ("Valid output", 476),
    ("Typed abstention", 524),
    ("Gold curated", 0),
    ("Expert adjudicated", 0),
]


def apply_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
        "figure.constrained_layout.use": True,
    })


def style_axes(ax, *, xlabel: str, ylabel: str, title: str = "") -> None:
    """Apply the mandatory square aspect and explicit axis labels."""
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.set_box_aspect(1)


def save_square(fig, path: str | Path, *, size_in: float = 6.5, dpi: int = 300, pdf: bool = False) -> None:
    """Save a figure that is guaranteed to be square in pixels.

    ``bbox_inches='tight'`` is deliberately **not** used because it changes the
    aspect ratio and produces non-square output. Constrained layout (enabled in
    :func:`apply_style`) fits the labels inside a fixed square canvas instead.
    """
    fig.set_size_inches(size_in, size_in)
    fig.savefig(path, dpi=dpi)
    if pdf:
        fig.savefig(Path(path).with_suffix(".pdf"))
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════
# Panels
# ══════════════════════════════════════════════════════════════════════

def build_closure_status_figure(data: list[dict[str, Any]] | None = None):
    """Engineering vs scientific closure per study (square, labelled)."""
    apply_style()
    data = data or CLOSURE_DATA
    studies = [d["id"] for d in data]
    x = np.arange(len(studies))
    width = 0.38
    eng = [1 if d["engineering_closed"] else 0 for d in data]
    sci = [1 if d["scientific_closed"] else 0 for d in data]

    fig, ax = plt.subplots()
    ax.bar(x - width / 2, eng, width, label="Engineering closure", color=PALETTE["engineering"])
    ax.bar(x + width / 2, sci, width, label="Scientific closure", color=PALETTE["scientific_open"])
    ax.set_xticks(x)
    ax.set_xticklabels(studies)
    style_axes(
        ax,
        xlabel="Study",
        ylabel="Closed (0 = no, 1 = yes)",
        title="E1–E8 closure: engineering vs scientific",
    )
    ax.set_ylim(0, 1.25)
    ax.set_yticks([0, 1])
    ax.legend(loc="upper center", ncol=2, frameon=False, fontsize=9)
    return fig


def build_closure_denominator_figure(data: list[dict[str, Any]] | None = None):
    """Required vs executed vs independently-adjudicated cohort per study."""
    apply_style()
    data = data or CLOSURE_DATA
    studies = [d["id"] for d in data]
    y = np.arange(len(studies))
    height = 0.26
    required = [max(1, int(d["required_n"])) for d in data]
    executed = [int(d["executed_n"]) for d in data]
    adjudicated = [int(d["adjudicated_n"]) for d in data]

    fig, ax = plt.subplots()
    ax.barh(y + height, required, height, label="Required / target", color=PALETTE["required"])
    ax.barh(y, executed, height, label="Executed", color=PALETTE["executed"])
    ax.barh(y - height, adjudicated, height, label="Independently adjudicated", color=PALETTE["adjudicated"])
    for yi, (req, exe, adj) in enumerate(zip(required, executed, adjudicated, strict=True)):
        ax.text(req * 1.1, yi + height, f"{req}", va="center", fontsize=8)
        ax.text(max(exe, 0.9) * 1.1 if exe else 0.9, yi, f"{exe}", va="center",
                fontsize=8, color="black" if exe else "grey")
        ax.text(max(adj, 0.9) * 1.1 if adj else 0.9, yi - height, f"{adj}", va="center",
                fontsize=8, color="black" if adj else "grey")
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(studies)
    ax.set_xlim(0.7, max(required) * 3)
    style_axes(
        ax,
        xlabel="Cases / units (log scale)",
        ylabel="Study",
        title="Cohort funnel: required → executed → adjudicated",
    )
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    return fig


def build_execution_funnel_figure(
    funnel: list[tuple[str, int]] | None = None,
):
    """1000-task execution funnel: planned → executed → gold (square, labelled)."""
    apply_style()
    funnel = funnel or EXECUTION_FUNNEL
    stages = [stage for stage, _ in funnel]
    counts = [count for _, count in funnel]
    colors = [PALETTE["required"], PALETTE["required"], PALETTE["executed"],
              PALETTE["executed"], OUTCOME_COLORS["abstained"],
              PALETTE["scientific_closed"], PALETTE["scientific_closed"]]

    fig, ax = plt.subplots()
    y = np.arange(len(stages))[::-1]
    ax.barh(y, [max(c, 0.5) for c in counts], color=colors[: len(stages)])
    for yi, count in zip(y, counts, strict=True):
        ax.text(max(count, 0.5) * 1.05, yi, f"{count}", va="center", fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels(stages, fontsize=9)
    ax.set_xscale("log")
    ax.set_xlim(0.4, 2600)
    style_axes(
        ax,
        xlabel="Tasks (log scale)",
        ylabel="Pipeline stage",
        title="1000-task execution funnel (engineering only; gold 0)",
    )
    return fig


def build_closed48_outcomes_figure(
    outcomes: dict[str, dict[str, int]] | None = None,
):
    """Gold-independent outcome composition of the three closed-48 arms."""
    apply_style()
    outcomes = outcomes or CLOSED48_OUTCOMES
    arms = ["protacxtend", "direct_tool", "fixed_workflow"]
    labels = ["PROTACXtend", "direct tool", "fixed workflow"]

    fig, ax = plt.subplots()
    bottom = np.zeros(len(arms))
    for outcome in OUTCOME_ORDER:
        vals = np.array([outcomes.get(arm, {}).get(outcome, 0) for arm in arms], dtype=float)
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
        title="Closed 48-case outcomes (gold-independent)",
    )
    ax.set_ylim(0, 54)
    ax.tick_params(axis="x", rotation=10)
    ax.legend(fontsize=8, ncol=3, frameon=False, loc="upper center")
    return fig


def build_baseline_capability_figure(
    means: dict[str, dict[str, float]] | None = None,
):
    """Pre-gold matched-compute baseline means by capability (not accuracy)."""
    apply_style()
    means = means or BASELINE_MEANS
    caps = ["KNOW", "REASON", "DESIGN", "DISCOVER"]
    systems = list(means)
    x = np.arange(len(caps))
    width = 0.8 / max(1, len(systems))

    fig, ax = plt.subplots()
    colors = [PALETTE["protacxtend"], PALETTE["direct_tool"], PALETTE["fixed_workflow"]]
    for i, system in enumerate(systems):
        vals = [means[system].get(cap, 0.0) for cap in caps]
        ax.bar(x + i * width - 0.4 + width / 2, vals, width, label=system,
               color=colors[i % len(colors)])
    ax.set_xticks(x)
    ax.set_xticklabels(caps)
    style_axes(
        ax,
        xlabel="Capability",
        ylabel="Mean checklist score (pre-gold, not accuracy)",
        title="Matched-compute baselines on 48 tasks",
    )
    ax.set_ylim(0, 0.34)
    ax.legend(fontsize=8, frameon=False)
    return fig


def build_closure_overview_figure(data: list[dict[str, Any]] | None = None):
    """2×2 square-panel summary of the closure evidence."""
    apply_style()
    fig, axes = plt.subplots(2, 2)
    fig.set_size_inches(11, 11)
    # Reuse the single-panel builders on the overview axes by drawing directly.
    data = data or CLOSURE_DATA
    studies = [d["id"] for d in data]

    # (0,0) closure level
    ax = axes[0, 0]
    x = np.arange(len(studies))
    width = 0.38
    ax.bar(x - width / 2, [1 if d["engineering_closed"] else 0 for d in data], width,
           label="Engineering", color=PALETTE["engineering"])
    ax.bar(x + width / 2, [1 if d["scientific_closed"] else 0 for d in data], width,
           label="Scientific", color=PALETTE["scientific_open"])
    ax.set_xticks(x)
    ax.set_xticklabels(studies)
    ax.set_ylim(0, 1.25)
    ax.set_yticks([0, 1])
    style_axes(ax, xlabel="Study", ylabel="Closed (0 = no, 1 = yes)",
               title="A  Engineering vs scientific closure")
    ax.legend(fontsize=8, frameon=False, ncol=2)

    # (0,1) cohort funnel
    ax = axes[0, 1]
    y = np.arange(len(studies))
    h = 0.26
    ax.barh(y + h, [max(1, d["required_n"]) for d in data], h, label="Required",
            color=PALETTE["required"])
    ax.barh(y, [d["executed_n"] for d in data], h, label="Executed", color=PALETTE["executed"])
    ax.barh(y - h, [d["adjudicated_n"] for d in data], h, label="Adjudicated",
            color=PALETTE["adjudicated"])
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(studies)
    style_axes(ax, xlabel="Cases / units (log scale)", ylabel="Study",
               title="B  Cohort funnel")
    ax.legend(fontsize=8, frameon=False, loc="lower right")

    # (1,0) closed-48 outcomes
    ax = axes[1, 0]
    outcomes = CLOSED48_OUTCOMES
    arms = ["protacxtend", "direct_tool", "fixed_workflow"]
    labels = ["PROTACXtend", "direct tool", "fixed workflow"]
    bottom = np.zeros(len(arms))
    for outcome in OUTCOME_ORDER:
        vals = np.array([outcomes.get(a, {}).get(outcome, 0) for a in arms], dtype=float)
        if not vals.any():
            continue
        ax.bar(labels, vals, bottom=bottom, label=outcome, color=OUTCOME_COLORS[outcome])
        bottom += vals
    style_axes(ax, xlabel="System arm", ylabel="Cases (n = 48 per arm)",
               title="C  Closed-48 outcomes (gold-independent)")
    ax.set_ylim(0, 54)
    ax.tick_params(axis="x", rotation=10)
    ax.legend(fontsize=7, ncol=3, frameon=False, loc="upper center")

    # (1,1) baseline capability
    ax = axes[1, 1]
    caps = ["KNOW", "REASON", "DESIGN", "DISCOVER"]
    systems = list(BASELINE_MEANS)
    xi = np.arange(len(caps))
    w = 0.8 / len(systems)
    colors = [PALETTE["protacxtend"], PALETTE["direct_tool"], PALETTE["fixed_workflow"]]
    for i, system in enumerate(systems):
        ax.bar(xi + i * w - 0.4 + w / 2, [BASELINE_MEANS[system].get(c, 0.0) for c in caps],
               w, label=system, color=colors[i % len(colors)])
    ax.set_xticks(xi)
    ax.set_xticklabels(caps)
    style_axes(ax, xlabel="Capability",
               ylabel="Mean checklist score (pre-gold, not accuracy)",
               title="D  Matched-compute baselines")
    ax.set_ylim(0, 0.34)
    ax.legend(fontsize=8, frameon=False)

    fig.suptitle("PROTACXtend E1–E8 experiment closure", fontsize=14)
    return fig


# ══════════════════════════════════════════════════════════════════════
# Writer
# ══════════════════════════════════════════════════════════════════════

def _write_closure_csv(out_dir: Path) -> None:
    with (out_dir / "closure_data.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "study", "name", "engineering_closed", "scientific_closed",
            "required_n", "executed_n", "adjudicated_n", "evidence", "blocker",
        ])
        for d in CLOSURE_DATA:
            writer.writerow([
                d["id"], d["name"], d["engineering_closed"], d["scientific_closed"],
                d["required_n"], d["executed_n"], d["adjudicated_n"],
                d["evidence"], d["blocker"],
            ])


def write_closure_figures(out_dir: str | Path = "benchmark_results/figures") -> dict[str, str]:
    """Write the square closure figures + CSV; return path map."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}

    panels = {
        "fig_closure_status.png": build_closure_status_figure,
        "fig_closure_denominators.png": build_closure_denominator_figure,
        "fig_execution_funnel.png": build_execution_funnel_figure,
        "fig_closed48_outcomes.png": build_closed48_outcomes_figure,
        "fig_baseline_capability.png": build_baseline_capability_figure,
    }
    for name, builder in panels.items():
        save_square(builder(), out / name)
        written[name] = str(out / name)

    save_square(build_closure_overview_figure(), out / "fig_closure_overview.png", size_in=11)
    written["fig_closure_overview.png"] = str(out / "fig_closure_overview.png")

    _write_closure_csv(out)
    written["closure_data.csv"] = str(out / "closure_data.csv")

    # Machine-readable closure matrix for downstream reports.
    (out / "experiment_closure.json").write_text(
        json.dumps({"schema": "experiment_closure.v1", "studies": CLOSURE_DATA},
                   indent=2),
        encoding="utf-8",
    )
    written["experiment_closure.json"] = str(out / "experiment_closure.json")
    return written


__all__ = [
    "BASELINE_MEANS",
    "CLOSED48_OUTCOMES",
    "CLOSURE_DATA",
    "EXECUTION_FUNNEL",
    "apply_style",
    "build_baseline_capability_figure",
    "build_closed48_outcomes_figure",
    "build_closure_denominator_figure",
    "build_closure_overview_figure",
    "build_closure_status_figure",
    "build_execution_funnel_figure",
    "save_square",
    "style_axes",
    "write_closure_figures",
]
