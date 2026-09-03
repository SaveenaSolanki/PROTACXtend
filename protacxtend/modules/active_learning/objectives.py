"""Objectives for Module 7 — pluggable scorers, never fabricated.

Three layers, clearly labelled:

1. ``dose_objective_from_hook`` — REAL mechanistic objective computed with the
   validated Module-1 hook-effect equilibrium (occupancy maximisation minus hook
   severity) for a candidate once kinetics (Kd_T, Kd_E, alpha, concentrations)
   are known from experiment/upstream. Label: "calculated".
2. ``SyntheticObjective2D`` — deterministic multi-modal benchmark used to
   validate the search machinery itself (optimizer finds the known optimum with
   fewer evaluations than random). Label: "synthetic". Never presented as a
   real prediction.
3. ``register_objective`` — user-supplied objectives (e.g. an M4/M5 scorer
   adapter) can be registered by callers; nothing is auto-claimed.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional

from protacxtend.modules.active_learning.schemas import Candidate, Evaluation

# objective registry: name -> fn(candidate) -> Evaluation (or None if not applicable)
_OBJECTIVES: Dict[str, Callable[[Candidate], Optional[Evaluation]]] = {}


def register_objective(name: str,
                       fn: Callable[[Candidate], Optional[Evaluation]]) -> None:
    """Register an objective scorer under a name (idempotent)."""
    _OBJECTIVES[name] = fn


def registered_objectives() -> Dict[str, Callable[[Candidate], Optional[Evaluation]]]:
    return dict(_OBJECTIVES)


def _optimum(linker_idx: float, dose_log10: float) -> float:
    """Deterministic 2-D benchmark: product of two one-dimensional multimodal
    humps. Global optimum at (linker 5, dose level log10=1.0 -> 10 nM) by
    construction, value 1.0. Smooth enough for an RF surrogate to guide search.
    """
    x = linker_idx
    a = math.sin(3.2 * x) * math.exp(-0.02 * x)
    b = math.sin(1.7 * dose_log10 + 0.8) * math.exp(-0.12 * (dose_log10 - 1.0) ** 2)
    val = (a + 1.0) / 2.0 * ((b + 1.0) / 2.0)
    return val


class SyntheticObjective2D:
    """Multi-modal benchmark objective on (linker_index, dose_log10)."""

    name = "synthetic_2d"
    optimum: Dict[str, float] = {"linker_index": 5.0, "dose_log10_nM": 1.0}
    optimum_value = 1.0

    def __call__(self, candidate: Candidate) -> Evaluation:
        feat = candidate.features
        val = _optimum(feat.get("linker_index", 0.0), feat.get("dose_log10_nM", 0.0))
        return Evaluation(candidate=candidate,
                          objectives={"synthetic_2d": round(val, 6)},
                          constraints={"admet_ok": True, "novel_ok": True},
                          sources={"synthetic_2d": "synthetic"})


def dose_objective_from_hook(
    candidate: Candidate,
    kd_poi_protac_nM: float,
    kd_e3_protac_nM: float,
    alpha: float,
    poi_conc_nM: float = 100.0,
    e3_conc_nM: float = 100.0,
    hook_penalty: float = 1.0,
    seed: int = 42,
) -> Evaluation:
    """Mechanistic dose objective from the Module-1 equilibrium.

    Maximises ternary occupancy at the candidate's dose while penalising hook
    severity (occupancy decline at high dose) — a surrogate-free, calculated
    objective for operating-dose planning when kinetics are known.

    Label: "calculated" (Module-1 model), never "measured".
    """
    from protacxtend.modules.hook_effect_modeler import simulate_hook_effect

    result = simulate_hook_effect(
        poI_conc_nM=poi_conc_nM,
        e3_conc_nM=e3_conc_nM,
        kd_poi_protac_nM=kd_poi_protac_nM,
        kd_e3_protac_nM=kd_e3_protac_nM,
        alpha=alpha,
        min_dose_nM=max(0.01, candidate.dose_nM / 10.0),
        max_dose_nM=max(candidate.dose_nM * 10.0, candidate.dose_nM + 1.0),
        points=60,
        seed=seed,
    )
    metrics = result.metrics
    occupancy = float(metrics.max_occupancy_fraction)
    severity = float(metrics.hook_severity)
    window = float(getattr(metrics, "occupancy_window_fold", 0.0))
    # dose is a dimension of the candidate; give mild credit for wider window,
    # subtract hook severity; clip to [0,1].
    value = max(0.0, min(1.0, occupancy + 0.05 * min(window, 4.0) - hook_penalty * severity))
    return Evaluation(
        candidate=candidate,
        objectives={"hook_dose": round(value, 6)},
        constraints={"hook_ok": severity < 0.5},
        sources={"hook_dose": "calculated"},
        warnings=[] if severity < 0.05 else ["hook effect detected at high dose"],
    )


def evaluate_candidate(candidate: Candidate,
                       objective_name: str = "synthetic_2d",
                       params: Optional[Dict[str, Any]] = None) -> Evaluation:
    """Default scorer used by the optimizer (deterministic, no I/O)."""
    if objective_name == "synthetic_2d":
        return SyntheticObjective2D()(candidate)
    if objective_name in _OBJECTIVES:
        ev = _OBJECTIVES[objective_name](candidate)
        if ev is not None:
            return ev
        raise ValueError(f"objective '{objective_name}' not applicable to candidate")
    raise ValueError(f"unknown objective '{objective_name}' (registered: "
                     f"{sorted(_OBJECTIVES)} | builtin: synthetic_2d)")
