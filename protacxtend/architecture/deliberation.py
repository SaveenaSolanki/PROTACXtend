"""Model deliberation: disagreement and experiment discrimination (v1).

Disagreement is represented by scientific axis — never collapsed into one opaque
score. Experiment selection chooses the experiment that best discriminates
between competing hypotheses.
"""
from __future__ import annotations

from protacxtend.architecture.ontology import Disagreement, ScientificAxisProfile


def analyze_disagreement(axes: ScientificAxisProfile,
                         evidence_ids: list[str] | None = None) -> list[Disagreement]:
    """Return decision-relevant disagreements between scientific axes.

    Each returned object names the axis, the disagreeing positions, whether it
    is decision-relevant, and a concrete resolving action. No averaging.
    """
    out: list[Disagreement] = []
    ev = list(evidence_ids or [])

    def add(axis: str, positions: dict, interpretation: str, action: str) -> None:
        out.append(Disagreement(
            disagreement_id=f"dis_{axis}_{len(out)}", axis=axis, positions=positions,
            decision_relevant=True, interpretation=interpretation,
            resolving_action=action, evidence_ids=ev))

    d = axes.degradation_ml
    geom = axes.ternary_geometry
    if d == "HIGH" and geom in {"LOW", "UNKNOWN"}:
        add("ternary_geometry_vs_degradation_ml",
            {"degradation_ml": d, "ternary_geometry": geom},
            "Similarity to known degraders does not establish productive "
            "interaction-state geometry.",
            "Perform a higher-confidence ternary/cooperativity assessment.")
    if d == "HIGH" and axes.permeability in {"LOW", "UNKNOWN"}:
        add("permeability_vs_degradation_ml",
            {"degradation_ml": d, "permeability": axes.permeability},
            "A predicted degrader cannot act if cellular exposure is limiting.",
            "Run a permeability/efflux assessment.")
    if axes.ubiquitination_competence == "LOW" and d == "HIGH":
        add("ubiquitination_vs_degradation_ml",
            {"ubiquitination_competence": "LOW", "degradation_ml": d},
            "Ternary formation without transfer competence need not degrade the target.",
            "Assess lysine accessibility and ubiquitination competence.")
    return out


def select_discriminating_experiment(hypotheses: list[str],
                                     experiments: list[dict]) -> dict:
    """Choose the experiment whose predicted outcomes best separate hypotheses.

    ``experiments`` is a list of dicts: {name, outcomes: {H1: str, ...}, controls: [...]}.
    Discrimination score = number of distinct predicted outcomes across hypotheses
    (higher = better separates them). Ties broken by the caller-provided order.
    """
    best = None
    best_score = -1
    for exp in experiments:
        outcomes = exp.get("outcomes") or {}
        vals = [str(outcomes.get(h, "")) for h in hypotheses]
        score = len({v for v in vals if v})
        if score > best_score:
            best, best_score = exp, score
    if best is None:
        return {}
    return {
        "experiment": best.get("name", ""),
        "competing_hypotheses": list(hypotheses),
        "predicted_outcome_under": {h: str((best.get("outcomes") or {}).get(h, ""))
                                    for h in hypotheses},
        "information_gain": f"separates {best_score} distinct outcome(s) across "
                            f"{len(hypotheses)} hypotheses",
        "required_controls": list(best.get("controls") or []),
        "decision_after_each_outcome": dict(best.get("decision_after") or {}),
        "discrimination_score": best_score,
    }


__all__ = ["analyze_disagreement", "select_discriminating_experiment"]
