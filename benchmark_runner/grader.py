"""Benchmark scoring engine (deterministic, LLM-free).

Dispatches a system answer against a task's frozen ground truth.  It supports
the ground-truth types used by the PROTACXtend benchmark and the wider TPD
vocabulary:

    exact, categorical, ranked, numeric, set, constraint,
    design_rubric, mechanistic_rubric, causal_graph, trajectory

Design rules
------------
* Automatically scorable types are graded deterministically.  No LLM judge is
  ever used (see ``SCORING_RUBRIC.md``).
* Rubric types are scored on their explicit ``mandatory_answer_elements``
  checklist and additionally flagged ``requires_expert_review`` for the
  subjective dimensions.  A rubric is therefore *partially* automatic and
  *never* silently treated as a complete score.
* A ground truth whose declared type lacks the fields needed to grade it is
  reported ``unscorable_missing_fields`` rather than assigned a fake score.

Every call returns a ``ScoreRecord``-shaped dict.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from benchmark_runner import scoring as sc

ROOT = Path(__file__).resolve().parents[1]
SCORING_DIR = ROOT / "benchmark" / "scoring"

DETERMINISTIC_TYPES = {
    "exact", "categorical", "ranked", "numeric", "set", "constraint",
}
RUBRIC_TYPES = {"design_rubric", "mechanistic_rubric"}
STRUCTURED_TYPES = {"causal_graph", "trajectory"}
SCORE_SCHEMA_VERSION = "1.0.0"


# ── ground-truth loading / readiness ─────────────────────────────────────

def _load_overlay(task_id: str, scoring_dir: Path | str | None = None) -> Dict[str, Any]:
    base = Path(scoring_dir) if scoring_dir else SCORING_DIR
    path = base / f"{task_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _merge_overlay(gt: Mapping[str, Any], overlay: Mapping[str, Any]) -> Dict[str, Any]:
    """Merge derived scoring criteria without overriding authored GT fields."""
    merged = dict(gt)
    if overlay:
        if "mandatory_elements" in overlay and not merged.get("mandatory_answer_elements"):
            merged["mandatory_answer_elements"] = list(overlay.get("mandatory_elements") or [])
        for key in ("expected_value", "expected_set", "expected_ranking", "tolerance",
                    "constraints", "causal_graph", "decision_trajectory"):
            if key in overlay and not merged.get(key):
                merged[key] = overlay[key]
        merged.setdefault("_scoring_overlay", dict(overlay))
    return merged


def load_ground_truth(task_id: str, gt_dir: Path | str | None = None) -> Dict[str, Any]:
    base = Path(gt_dir) if gt_dir else ROOT / "benchmark" / "ground_truth"
    path = base / f"{task_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"ground truth not found for task {task_id!r}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def gt_type(gt: Mapping[str, Any]) -> str:
    value = str(gt.get("type") or gt.get("gt_type") or "").strip()
    return value


def required_fields_for(gtype: str) -> List[str]:
    if gtype == "exact":
        return ["expected_value"]
    if gtype == "categorical":
        return ["expected_set"]
    if gtype == "ranked":
        return ["expected_ranking"]
    if gtype == "numeric":
        return ["expected_value"]
    if gtype == "set":
        return ["expected_set"]
    if gtype == "constraint":
        return ["constraints"]
    if gtype in RUBRIC_TYPES:
        return ["mandatory_answer_elements"]
    if gtype == "causal_graph":
        return ["causal_graph"]
    if gtype == "trajectory":
        return ["decision_trajectory"]
    return []


def _structured_expected(gt: Mapping[str, Any], gtype: str) -> Any:
    """Best-effort structured expectation from the GT payload.

    Falls back to ``mandatory_answer_elements`` for types whose canonical
    structured field is absent, so legacy rubric-style GTs remain gradeable on
    their explicit checklist.
    """
    if gtype == "exact":
        return gt.get("expected_value", gt.get("expected_answer"))
    if gtype in ("categorical", "set"):
        return gt.get("expected_set") or gt.get("mandatory_answer_elements") or []
    if gtype == "ranked":
        return gt.get("expected_ranking") or gt.get("expected_answer") or []
    if gtype == "numeric":
        return gt.get("expected_value")
    if gtype == "constraint":
        return gt.get("constraints") or gt.get("mandatory_answer_elements") or []
    return None


def scorable_status(gt: Mapping[str, Any], *, task_id: str = "",
                    scoring_dir: Path | str | None = None) -> Dict[str, Any]:
    """Report whether a ground truth can be graded and by which path."""
    if task_id:
        gt = _merge_overlay(gt, _load_overlay(task_id, scoring_dir))
    gtype = gt_type(gt)
    if not gtype:
        return {"scorable": False, "gtype": "", "reason": "no gt type",
                "mode": "unscorable", "missing_fields": []}
    missing = [f for f in required_fields_for(gtype) if not gt.get(f)]
    if gtype in DETERMINISTIC_TYPES:
        # Legacy GTs may encode the expectation inside expected_answer; allow
        # checklist grading when mandatory elements exist.
        if missing and gt.get("mandatory_answer_elements"):
            return {"scorable": True, "gtype": gtype, "mode": "checklist",
                    "reason": "structured field absent; grading explicit checklist",
                    "missing_fields": missing}
        return {"scorable": not missing, "gtype": gtype, "mode": "deterministic",
                "reason": "" if not missing else "missing structured expectation",
                "missing_fields": missing}
    if gtype in RUBRIC_TYPES:
        scorable = bool(gt.get("mandatory_answer_elements"))
        return {"scorable": scorable, "gtype": gtype, "mode": "rubric_checklist",
                "reason": "" if scorable else "rubric has no explicit checklist",
                "missing_fields": [] if scorable else ["mandatory_answer_elements"]}
    if gtype in STRUCTURED_TYPES:
        return {"scorable": not missing, "gtype": gtype, "mode": "structured",
                "reason": "" if not missing else "structured payload absent",
                "missing_fields": missing}
    return {"scorable": False, "gtype": gtype, "mode": "unknown",
            "reason": f"unsupported gt type {gtype!r}", "missing_fields": []}


# ── grading ──────────────────────────────────────────────────────────────

def _checklist_score(answer_text: str, elements: Sequence[str]) -> Dict[str, Any]:
    text = sc._norm(answer_text)
    present, missing = [], []
    for element in elements:
        token = sc._norm(element)
        if token and token in text:
            present.append(element)
        else:
            # fall back to token-level coverage for multi-word elements
            tokens = [t for t in re.split(r"[\s/,;()]+", token) if len(t) > 2]
            hit = bool(tokens) and all(t in text for t in tokens)
            (present if hit else missing).append(element)
    score = len(present) / len(elements) if elements else 0.0
    return {"score": round(score, 4), "present": present, "missing": missing,
            "method": "checklist"}


def grade_answer(
    task_id: str,
    answer: Any,
    *,
    gt: Optional[Mapping[str, Any]] = None,
    gt_dir: Path | str | None = None,
    use_overlay: bool = True,
) -> Dict[str, Any]:
    """Grade ``answer`` against the ground truth for ``task_id``.

    Set ``use_overlay=False`` to grade against a reviewer-approved gold object
    without merging the self-derived ``benchmark/scoring/*.json`` overlay.

    Returns a ScoreRecord-shaped dict with ``status`` in
    {``scored``, ``requires_expert_review``, ``unscorable_missing_fields``}.
    """
    gt_data = dict(gt) if gt is not None else load_ground_truth(task_id, gt_dir)
    if use_overlay:
        gt_data = _merge_overlay(gt_data, _load_overlay(task_id))
    gtype = gt_type(gt_data)
    readiness = scorable_status(gt_data)
    record: Dict[str, Any] = {
        "schema_version": SCORE_SCHEMA_VERSION,
        "task_id": task_id,
        "gt_type": gtype,
        "method": readiness["mode"],
        "scorable": readiness["scorable"],
        "score": None,
        "dimensions": {},
        "evidence": [],
        "requires_expert_review": gtype in RUBRIC_TYPES,
        "warnings": [],
        "errors": [],
    }
    if not readiness["scorable"]:
        record["status"] = "unscorable_missing_fields"
        record["errors"].append(readiness["reason"])
        return record

    answer_text = answer if isinstance(answer, str) else json.dumps(answer, default=str)

    if gtype == "exact":
        expected = _structured_expected(gt_data, gtype)
        if gt_data.get("expected_value") is not None:
            record["score"] = sc.exact_score(answer, expected)
        else:
            record["dimensions"] = _checklist_score(answer_text, gt_data.get("mandatory_answer_elements") or [])
            record["score"] = record["dimensions"]["score"]
        record["status"] = "scored"
    elif gtype in ("categorical", "set", "constraint"):
        expected = _structured_expected(gt_data, gtype)
        mandatory = gt_data.get("mandatory_answer_elements") or expected
        record["dimensions"] = sc.categorical_score(
            answer, expected, mandatory=mandatory,
            alternatives=gt_data.get("acceptable_alternatives") or [],
        )
        record["score"] = record["dimensions"]["score"]
        record["status"] = "scored"
    elif gtype == "ranked":
        expected = _structured_expected(gt_data, gtype)
        if isinstance(answer, str):
            predicted = [p.strip() for p in re.split(r"[,\n;]+", answer) if p.strip()]
        else:
            predicted = list(answer or [])
        record["dimensions"] = sc.rank_score(predicted, list(expected or []))
        record["score"] = record["dimensions"]["score"]
        if record["dimensions"].get("no_prediction"):
            record["status"] = "unanswered"
        else:
            record["status"] = "scored"
    elif gtype == "numeric":
        expected = gt_data.get("expected_value")
        try:
            predicted_value = float(re.sub(r"[^0-9eE+\-.]", "", answer_text))
            expected_value = float(expected)
            tolerance = float(gt_data.get("tolerance") or 0.0)
            record["score"] = 1.0 if abs(predicted_value - expected_value) <= tolerance else 0.0
            record["dimensions"] = {"predicted": predicted_value, "expected": expected_value,
                                    "tolerance": tolerance, "method": "numeric"}
            record["status"] = "scored"
        except (TypeError, ValueError):
            record["status"] = "unscorable_missing_fields"
            record["errors"].append("could not parse a numeric answer/expectation")
    elif gtype in RUBRIC_TYPES:
        record["dimensions"] = _checklist_score(
            answer_text, gt_data.get("mandatory_answer_elements") or [])
        record["score"] = record["dimensions"]["score"]
        record["status"] = "requires_expert_review"
        record["warnings"].append(
            "checklist coverage is automatic; rubric dimensions require blind expert review")
    elif gtype == "causal_graph":
        # Structural match on node/edge sets.
        expected_graph = gt_data.get("causal_graph") or {}
        try:
            predicted_graph = answer if isinstance(answer, Mapping) else json.loads(answer_text)
        except Exception:
            predicted_graph = {}
        exp_nodes = set(expected_graph.get("nodes") or [])
        pred_nodes = set((predicted_graph or {}).get("nodes") or [])
        exp_edges = {tuple(e) for e in (expected_graph.get("edges") or [])}
        pred_edges = {tuple(e) for e in ((predicted_graph or {}).get("edges") or [])}
        node_score = len(exp_nodes & pred_nodes) / len(exp_nodes) if exp_nodes else 0.0
        edge_score = len(exp_edges & pred_edges) / len(exp_edges) if exp_edges else 0.0
        record["dimensions"] = {"node_overlap": round(node_score, 4),
                                "edge_overlap": round(edge_score, 4), "method": "causal_graph"}
        record["score"] = round(0.5 * node_score + 0.5 * edge_score, 4)
        record["status"] = "scored"
    elif gtype == "trajectory":
        expected_steps = gt_data.get("decision_trajectory") or []
        try:
            predicted_steps = answer if isinstance(answer, list) else json.loads(answer_text)
        except Exception:
            predicted_steps = []
        predicted_ids = [str(s.get("step") or s.get("id") or "") for s in predicted_steps]
        expected_ids = [str(s.get("step") or s.get("id") or "") for s in expected_steps]
        record["dimensions"] = sc.topk_agreement(predicted_ids, expected_ids)
        record["score"] = record["dimensions"]["topk"]
        record["status"] = "scored"
    else:
        record["status"] = "unscorable_missing_fields"
        record["errors"].append(f"no grader for gt type {gtype!r}")
    return record


__all__ = [
    "DETERMINISTIC_TYPES",
    "RUBRIC_TYPES",
    "grade_answer",
    "gt_type",
    "load_ground_truth",
    "required_fields_for",
    "scorable_status",
]
