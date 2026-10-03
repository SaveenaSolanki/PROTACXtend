"""Capability landscape (M1-M12): separate from any individual scientific run.

Scores are recorded ONLY from rubric-applied evidence (file or run ID,
reviewer, date, reason). Dimensions without evidence stay ``unassessed`` —
a tool emitting JSON is never treated as evidence of capability. Plot
coordinates are computed deterministically from the recorded scores, so
re-running this module reproduces the same coordinates.

Rubric conventions (validation levels):
  0 unassessed (no rubric evidence on file)
  1 declared/registered (registry entry only)
  2 executable (real input completes under pinned env)
  3 output-validated (schema/units/provenance checks pass)
  4 benchmarked (frozen split, metric, denominator, CI on file)
  5 externally validated (independent dataset/host)
  6 prospectively validated (pre-registered outcome)
"""

from __future__ import annotations

import json, os
from typing import Any

LANDSCAPE_DIR = "outputs/landscape"
DEFAULT_SCORES_FILE = os.path.join(LANDSCAPE_DIR, "scores.json")

MODULES = {
    "M1": "Hook-effect equilibrium modeler",
    "M2": "Lysine-ubiquitination feasibility",
    "M3": "Cooperativity alpha predictor",
    "M4": "Degradation ML (pDC50/Dmax)",
    "M5": "Cell-context degradation model",
    "M6": "E3-opportunity ranking engine",
    "M7": "Active learning / experiment selection",
    "M8": "BRD/BET intelligence",
    "M9": "Chameleonicity 3D",
    "M10": "Neosubstrate risk",
    "M11": "Resistance mechanisms",
    "M12": "Ternary coordinate prediction (reserved)",
}

_RUBRIC = {
    0: "unassessed: no rubric evidence on file; JSON emission is not evidence.",
    1: "declared/registered: registry entry only (protacxtend/toolkit/registry.py).",
    2: "executable: real input completes under pinned environment (TOOLKIT_TRUTH.md).",
    3: "output-validated: schema/units/provenance checks pass (results/audit).",
    4: "benchmarked: frozen split + metric + denominator + CI on file (results/BENCHMARK_RESULTS_V2.md, module VALIDATION docs).",
    5: "externally validated: independent dataset/host (claims_audit external fields).",
    6: "prospectively validated: pre-registered outcome (none yet).",
}


def _rubric_text(level: int | None) -> str:
    return _RUBRIC[level] if level is not None else _RUBRIC[0]


DEFAULT_SCORES: dict[str, dict[str, Any]] = {
    m: {
        "module": MODULES[m],
        "score": None,          # None == unassessed; integers map to rubric levels
        "validation_level": "unassessed",
        "rubric": _rubric_text(level=None),
        "evidence": "",
        "reviewer": "",
        "date": "",
        "reason": "No rubric evidence on file; JSON emission is not evidence.",
    }
    for m in MODULES
}

def load_scores(path: str = DEFAULT_SCORES_FILE) -> dict[str, dict[str, Any]]:
    if os.path.exists(path):
        with open(path) as f:
            stored = json.load(f)
        merged = {m: dict(DEFAULT_SCORES[m]) for m in MODULES}
        for m, v in stored.items():
            if m in merged and isinstance(v, dict):
                merged[m].update({k: val for k, val in v.items() if val is not None or k not in ("score", "evidence")})
                if v.get("score") is None or v.get("score") == "":
                    merged[m].setdefault("score", None)
        return merged
    return dict(DEFAULT_SCORES)


def record_score(module: str, score: int | None, *, evidence: str, reviewer: str,
                 date: str, reason: str, path: str = DEFAULT_SCORES_FILE) -> dict[str, Any]:
    if module not in MODULES:
        raise KeyError(f"unknown module {module}; choose from {sorted(MODULES)}")
    if score is not None and not (0 <= int(score) <= 6):
        raise ValueError("score must be an integer 0..6 or None (unassessed)")
    scores = load_scores(path)
    level = score if score is not None else 0
    scores[module] = {
        "module": MODULES[module],
        "score": score,
        "validation_level": ["unassessed", "declared", "executable", "output-validated",
                             "benchmarked", "externally-validated", "prospectively-validated"][level],
        "rubric": _rubric_text(score),
        "evidence": evidence,
        "reviewer": reviewer,
        "date": date,
        "reason": reason,
    }
    _write(scores, path)
    return scores[module]


def coordinates(scores: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Deterministic coordinates from recorded scores: x = rubric level,
    y = score (same value); unassessed -> (0, None). Deterministic and
    reproducible because it is a pure function of scores.json."""
    pts = {}
    for m in MODULES:
        s = scores[m].get("score")
        pts[m] = {"x": 0 if s is None else int(s),
                  "y": None if s is None else int(s),
                  "label": scores[m]["module"]}
    return {"coordinates": pts,
            "coordinate_rule": "x = validation level (0..6); y = recorded score; unassessed -> (0, null)"}


def _write(scores: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(scores, f, indent=1)


def render_table(scores: dict[str, dict[str, Any]]) -> str:
    lines = ["| module | score | level | rubric | evidence | reviewer | date | reason |",
             "|---|---|---|---|---|---|---|---|"]
    for m in MODULES:
        s = scores[m]
        score_txt = "unassessed" if s.get("score") is None else str(s["score"])
        lines.append(f"| {m} | {score_txt} | {s['validation_level']} | {s['rubric']} | "
                     f"{s['evidence']} | {s['reviewer']} | {s['date']} | {s['reason']} |")
    return "\n".join(lines) + "\n"