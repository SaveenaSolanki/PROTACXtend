"""Required figures and result tables (Section 26).

Figure builders return the *data contract* for each figure so the plots can be
generated only when real scored data exists. ``render_figure`` refuses on
non-measured data, which keeps illustrative placeholders out of the paper.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FigureSpec:
    number: int
    name: str
    rows: List[str]
    columns: List[str]
    data_source: str
    status: str = "NOT YET MEASURED"


FIGURES: List[FigureSpec] = [
    FigureSpec(1, "PROTACXtend architecture",
               ["agent nodes", "tool registry", "evidence engine", "planner",
                "structure/ternary", "critic", "provenance"],
               ["component", "role", "wired?", "backend"],
               "introspection (sota/PROTACXTEND_AUDIT.md)"),
    FigureSpec(2, "500-task benchmark design",
               ["16 domains"], ["7 difficulty levels", "controlled",
                                "end-to-end", "temporal"],
               "tpdeval/config/allocation_500.json"),
    FigureSpec(3, "Head-to-head capability heatmap",
               ["16 domains"], ["PROTACXtend", "Biomni", "TPD agent",
                                "General LLM", "Tool-only"],
               "scored runs (per-domain means)"),
    FigureSpec(4, "Tool performance",
               ["tool-selection precision", "tool-selection recall",
                "execution success", "output validity",
                "interpretation correctness", "failure recovery"],
               ["systems"], "tpdeval.toolenv + tpdeval.failure"),
    FigureSpec(5, "End-to-end discovery decision trajectories",
               ["9 trajectory steps"], ["systems"],
               "tpdeval.trajectory"),
    FigureSpec(6, "TPD specialization",
               ["E3", "linker", "ternary", "degradation mechanism",
                "failure diagnosis"],
               ["systems"], "100-task stress subset"),
    FigureSpec(7, "Blinded temporal challenge",
               ["SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED",
                "UNRESOLVED", "temporal leakage"],
               ["systems", "T0+6/12/18/24mo"], "tpdeval.temporal"),
    FigureSpec(8, "Reliability",
               ["uncertainty (ECE)", "reproducibility", "failure recovery",
                "provenance completeness"],
               ["systems"], "tpdeval.calibration + reproducibility"),
    FigureSpec(9, "Ablation",
               ["full", "minus planner", "minus evidence", "minus structure",
                "minus critic", "minus provenance", "minus routing",
                "minus recovery", "same-LLM different-planner"],
               ["domain", "overall"], "tpdeval.ablation"),
]

FIGURE_INDEX = {f.number: f for f in FIGURES}

RESULT_TABLES: List[Dict[str, Any]] = [
    {"id": "T1", "name": "Per-domain separate-metric scores",
     "rows": "domain x system", "columns": "16 separate dimensions"},
    {"id": "T2", "name": "Paired statistics",
     "rows": "system pair x domain", "columns": "n, statistic, p, Holm-adjusted p, effect size"},
    {"id": "T3", "name": "Tool selection & execution",
     "rows": "system x task-class", "columns": "precision, recall, efficiency, execution, validity, interpretation, QC"},
    {"id": "T4", "name": "Evidence grounding",
     "rows": "system", "columns": "citation precision/coverage, primary-source rate, unsupported-claim rate, context match, temporal compliance"},
    {"id": "T5", "name": "Mechanistic graph match",
     "rows": "system x mechanistic domain", "columns": "node/edge P/R/F1, missing, unsupported, reversed"},
    {"id": "T6", "name": "Decision trajectory",
     "rows": "system x task", "columns": "validity, evidence adequacy, coherence, constraint satisfaction, consistency"},
    {"id": "T7", "name": "Temporal challenge",
     "rows": "system x aspect", "columns": "supported, partial, contradicted, unresolved, leakage"},
    {"id": "T8", "name": "Failure recovery",
     "rows": "system x fault type", "columns": "detection, diagnosis, retry, fallback, recovery, abstention, unsafe continuation, hallucination"},
    {"id": "T9", "name": "Reproducibility",
     "rows": "system", "columns": "decision agreement, rank Spearman, numeric variance, tool agreement, replay"},
    {"id": "T10", "name": "Efficiency",
     "rows": "system", "columns": "wall-clock, calls, tokens, failed calls, sources, compute, cost, memory"},
    {"id": "T11", "name": "Ablation",
     "rows": "ablation", "columns": "domain deltas + overall"},
    {"id": "T12", "name": "Fairness controls",
     "rows": "axis", "columns": "per-system values + whether matched"},
    {"id": "T13", "name": "Human expert subset + IRR",
     "rows": "task x system (blinded)", "columns": "expert scores, kappa, adjudication"},
    {"id": "T14", "name": "Final verdict",
     "rows": "20 areas", "columns": "PROTACXtend, Biomni, TPD agent, general LLM, experiment required"},
]


def can_plot(spec: FigureSpec) -> bool:
    return spec.status not in ("NOT YET MEASURED", "ILLUSTRATIVE")


def render_guard(data_present: bool) -> str:
    if not data_present:
        raise RuntimeError(
            "refusing to render a benchmark figure without measured data "
            "(no illustrative placeholders in the paper)")
    return "ok"
