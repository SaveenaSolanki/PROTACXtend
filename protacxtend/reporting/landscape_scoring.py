"""Versioned evidence-to-score pipeline for the M1-M12 landscape rubric.

This module derives every emitted artifact from one scored record.  It fails
closed: missing or placeholder evidence is ``not_assessable`` and never earns a
positive score.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "protacxtend.landscape_score.v1"
DEFAULT_OUT_DIR = Path("outputs/landscape")

DIMENSIONS = {
    "M1": ("target degradability", "Whether a target is degradable in a given cellular context"),
    "M2": ("E3 selection using biological context", "E3 choice from expression/localisation/precedent"),
    "M3": ("warhead and exit-vector reasoning", "Ligandable warhead plus productive exit vector"),
    "M4": ("linker design constraints", "Length, chemistry, rigidity and attachment-point constraints"),
    "M5": ("chemically valid PROTAC construction", "Valid, synthetically plausible assembly"),
    "M6": ("ternary-complex modelling", "POI-ligase ternary geometry and interface feasibility"),
    "M7": ("cooperativity/dynamics", "Alpha/cooperativity and conformational dynamics"),
    "M8": ("ubiquitination/proteasome/hook-effect", "Lysine geometry, E2 accessibility and hook effect"),
    "M9": ("DC50, Dmax and degradation kinetics", "Potency, efficacy and kinetic endpoints"),
    "M10": ("selectivity and resistance", "Neosubstrate/off-target selectivity and resistance"),
    "M11": ("PROTAC/bRo5 developability", "bRo5, chameleonicity, permeability, efflux and ADMET"),
    "M12": ("mechanistic validation experiment design", "Experiments that can falsify the mechanism"),
}

RUBRIC = {0: "absent", 1: "described", 2: "implemented", 3: "validated"}
EXPERT_REVIEW = {"M2", "M4", "M6", "M7", "M8", "M10", "M12"}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _rid(obj: dict[str, Any], fallback: str) -> str:
    return str(obj.get("record_id") or obj.get("candidate_id") or fallback)


def _run_ids(run: dict[str, Any], key: str) -> list[str]:
    value = run.get(key)
    if isinstance(value, dict):
        return [_rid(value, f"run.{key}")]
    if isinstance(value, list):
        return [_rid(v, f"run.{key}[{i}]") for i, v in enumerate(value) if isinstance(v, dict)]
    return []


def _predictions(run: dict[str, Any], *endpoints: str) -> list[dict[str, Any]]:
    wanted = {e.lower() for e in endpoints}
    rows: list[dict[str, Any]] = []
    for pred in run.get("predictions") or []:
        if isinstance(pred, dict):
            rows.append(pred)
    for cand in run.get("candidates") or []:
        if isinstance(cand, dict):
            rows.extend(p for p in cand.get("predictions") or [] if isinstance(p, dict))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pred in rows:
        rid = _rid(pred, "prediction")
        if rid in seen or str(pred.get("endpoint", "")).lower() not in wanted:
            continue
        seen.add(rid)
        if pred.get("available") is True and pred.get("value") is not None:
            out.append(pred)
    return out


def _artifact_ids(rows: list[dict[str, Any]], predicate: Callable[[dict[str, Any]], bool], prefix: str) -> list[str]:
    ids = [_rid(row, f"{prefix}:{i}") for i, row in enumerate(rows, start=1) if predicate(row)]
    return sorted(dict.fromkeys(ids))


def _contains(row: dict[str, Any], *needles: str) -> bool:
    text = json.dumps(row, sort_keys=True, default=str).lower()
    return any(n.lower() in text for n in needles)


def _evidence(rows: list[dict[str, Any]], *needles: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        kind = str(row.get("evidence_kind") or row.get("kind") or row.get("type") or "").lower()
        state = str(row.get("validation_state", "valid")).lower()
        if kind == "missing" or state in {"invalid", "rejected"}:
            continue
        if _contains(row, *needles):
            out.append(row)
    return out


def _dim(dim_id: str, score: int | None, evidence_ids: list[str], rule: str,
         limitation: str, reviewer_decision: str = "") -> dict[str, Any]:
    if score is not None and not evidence_ids:
        raise ValueError(f"{dim_id} positive score requires supporting artifact IDs")
    name, desc = DIMENSIONS[dim_id]
    status = "not_assessable" if score is None else ("review_required" if reviewer_decision else "scored")
    return {
        "dimension_id": dim_id,
        "dimension": name,
        "description": desc,
        "score": score,
        "status": status,
        "maturity_label": None if score is None else RUBRIC[score],
        "supporting_artifact_ids": sorted(dict.fromkeys(evidence_ids)),
        "applied_rubric_rule": rule,
        "limitation": limitation,
        "reviewer_decision": reviewer_decision,
        "expert_review_required": dim_id in EXPERT_REVIEW or bool(reviewer_decision),
    }


def build_scored_record(run_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(run_dir) if run_dir else None
    run = json.loads((root / "run.json").read_text(encoding="utf-8")) if root and (root / "run.json").exists() else {}
    evidence = _jsonl(root / "evidence.jsonl") if root else []
    decisions = _jsonl(root / "decisions.jsonl") if root else []
    trace = _jsonl(root / "trace.jsonl") if root else []
    stream = evidence + decisions + trace

    candidates = [c for c in run.get("candidates") or [] if isinstance(c, dict)]
    valid_candidates = [c for c in candidates if c.get("valid") is True and c.get("structure_valid") is True]
    candidate_ids = [_rid(c, f"run.candidates[{i}]") for i, c in enumerate(valid_candidates)]
    measured = [p for p in _predictions(run, "DC50", "Dmax") if p.get("kind") == "measured"]
    modelled = [p for p in _predictions(run, "DC50", "Dmax") if p.get("kind") in {"model", "predicted"}]
    dc_ids = [_rid(p, "prediction") for p in (measured or modelled)]
    measured_endpoints = {str(p.get("endpoint", "")).lower() for p in measured}

    dims: list[dict[str, Any]] = []
    if {"dc50", "dmax"} <= measured_endpoints:
        dims.append(_dim("M1", 3, _run_ids(run, "target") + dc_ids,
                         "Score 3: measured degradation endpoint evidence is present.",
                         "Known-compound/context evidence is not prospective validation."))
    elif modelled:
        dims.append(_dim("M1", 2, _run_ids(run, "target") + dc_ids,
                         "Score 2: executable degradation model output exists.",
                         "Model output is not experimental validation."))
    else:
        dims.append(_dim("M1", None, [], "Requires target plus available DC50/Dmax evidence.",
                         "Missing endpoint evidence remains not assessable."))

    e3_ev = _evidence(evidence, "e3 ligand", "recruiter", "vhl", "crbn")
    if _run_ids(run, "e3_ligase") and (_run_ids(run, "e3_ligands") or e3_ev):
        dims.append(_dim("M2", 2, _run_ids(run, "e3_ligase") + _run_ids(run, "e3_ligands") + [_rid(e, "evidence") for e in e3_ev],
                         "Score 2: executable E3/recruiter evidence exists; score 3 requires validated biological-context selection.",
                         "Expression/localisation/context suitability is not fully machine-adjudicated.",
                         "Expert review should confirm the biological-context rationale."))
    else:
        dims.append(_dim("M2", None, [], "Requires E3 identity plus recruiter/context evidence.",
                         "Missing E3 evidence cannot imply a suitable ligase.", "Expert review required."))

    warhead_ev = _evidence(evidence, "warhead", "attachment", "exit")
    dims.append(_dim("M3", 2, _run_ids(run, "warheads") + [_rid(e, "evidence") for e in warhead_ev],
                     "Score 2: executable warhead/exit-vector evidence exists.",
                     "No prospective exit-vector validation benchmark is inferred.") if _run_ids(run, "warheads") and warhead_ev else
                _dim("M3", None, [], "Requires valid warhead and attachment/exit-vector evidence.",
                     "Absent warhead records do not score."))

    dims.append(_dim("M4", 2, _run_ids(run, "linkers") + candidate_ids,
                     "Score 2: linker choice feeds a valid assembled candidate.",
                     "Length/rigidity/chemistry constraints need expert confirmation.",
                     "Reviewer should confirm linker rationale beyond successful assembly.") if _run_ids(run, "linkers") and valid_candidates else
                _dim("M4", None, [], "Requires linker record and assembled candidate evidence.",
                     "No linker evidence means no positive linker score.", "Expert review required."))

    match_ev = _evidence(evidence, "inchikey matches", "assembled product")
    if valid_candidates and match_ev:
        dims.append(_dim("M5", 3, candidate_ids + [_rid(e, "evidence") for e in match_ev],
                         "Score 3: chemically valid construction checked against curated source.",
                         "Chemical validity is not biological activity."))
    elif valid_candidates:
        dims.append(_dim("M5", 2, candidate_ids, "Score 2: valid molecular structures were constructed.",
                         "No validation artifact checked the product against a known source."))
    else:
        dims.append(_dim("M5", None, [], "Requires at least one valid, structure-valid candidate.",
                         "Invalid or absent candidates cannot score."))

    for dim_id, needles, rule, limitation in [
        ("M6", ("ternary",), "Requires ternary modelling artifact or completed ternary stage.", "Feasibility scores are not DockQ-validated coordinates."),
        ("M7", ("cooperativity", "alpha"), "Requires alpha/cooperativity/dynamics evidence.", "Experimental alpha/dynamics validation is not inferred."),
        ("M8", ("ubiquitin", "lysine", "hook effect", "hook_effect", "proteasome"), "Requires lysine/E2/proteasome/hook-effect artifact.", "Catalytic competence and E2 accessibility need expert assessment."),
        ("M10", ("selectivity", "off-target", "neosubstrate", "resistance"), "Requires selectivity, neosubstrate, off-target or resistance evidence.", "Off-target/resistance conclusions require expert review."),
        ("M12", ("experiment", "assay", "falsif", "validation design"), "Requires mechanistic validation experiment design artifact.", "Planned experiments are not prospective validation."),
    ]:
        ids = _artifact_ids(stream, lambda r, ns=needles: _contains(r, *ns), dim_id.lower())
        dims.append(_dim(dim_id, 2 if ids else None, ids, ("Score 2: executable evidence exists. " + rule) if ids else rule,
                         limitation if ids else "No supporting artifact was found.", "Expert review required."))

    if {"dc50", "dmax"} <= measured_endpoints:
        dims.append(_dim("M9", 3, dc_ids, "Score 3: measured DC50 and Dmax evidence is present.",
                         "Kinetic time-course parameters are not necessarily present."))
    elif modelled:
        dims.append(_dim("M9", 2, dc_ids, "Score 2: executable potency/efficacy model output exists.",
                         "Model output is not experimental validation."))
    else:
        dims.append(_dim("M9", None, [], "Requires available DC50/Dmax measured or model predictions.",
                         "Unavailable endpoint placeholders are ignored."))

    admet_ids = _artifact_ids(stream, lambda r: _contains(r, "admet", "developability", "permeability", "efflux", "bro5", "chameleonicity"), "m11")
    dims.append(_dim("M11", 2, admet_ids, "Score 2: executable developability/ADMET evidence exists.",
                     "bRo5/chameleonicity/permeability are not externally validated here.") if admet_ids else
                _dim("M11", None, [], "Requires ADMET/developability evidence.",
                     "No developability artifact; no positive score."))

    order = {k: i for i, k in enumerate(DIMENSIONS)}
    dims.sort(key=lambda d: order[d["dimension_id"]])
    scored = [d["score"] for d in dims if d["score"] is not None]
    payload = {"schema_version": SCHEMA_VERSION, "run_id": run.get("run_id") or (root.name if root else ""), "dimensions": dims}
    return {
        **payload,
        "rubric_source": "benchmark_results/landscape/scoring_rubric.md",
        "rubric_scale": RUBRIC,
        "run_dir": str(root) if root else "",
        "artifact_inputs": {"run_json": bool(run), "evidence_jsonl": len(evidence), "decisions_jsonl": len(decisions), "trace_jsonl": len(trace)},
        "summary": {
            "assessable_dimensions": len(scored),
            "not_assessable_dimensions": len(DIMENSIONS) - len(scored),
            "mean_score_0_3": round(sum(scored) / len(scored), 4) if scored else None,
            "normalized_depth_0_10": round(10 * sum(scored) / (3 * len(DIMENSIONS)), 4),
            "expert_review_dimensions": [d["dimension_id"] for d in dims if d["expert_review_required"]],
        },
        "determinism_hash": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
    }


def coordinates_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": record["schema_version"],
        "run_id": record.get("run_id", ""),
        "source_determinism_hash": record.get("determinism_hash", ""),
        "coordinate_rule": "x = M-dimension index; y = rubric score 0..3; not_assessable -> null",
        "coordinates": {
            d["dimension_id"]: {"x": i, "y": d["score"], "label": d["dimension"], "status": d["status"]}
            for i, d in enumerate(record["dimensions"], start=1)
        },
    }


def render_markdown(record: dict[str, Any]) -> str:
    expert = ", ".join(record["summary"]["expert_review_dimensions"]) or "none"
    lines = [
        "## M1-M12 Evidence-to-Score Rubric", "",
        f"- scored record: `{record['schema_version']}`",
        f"- run: `{record.get('run_id') or 'none'}`",
        f"- assessable dimensions: {record['summary']['assessable_dimensions']}/12",
        f"- normalized depth: {record['summary']['normalized_depth_0_10']}/10",
        f"- expert-review dependent dimensions: {expert}",
        f"- determinism hash: `{record['determinism_hash']}`", "",
        "| dimension | score | status | evidence IDs | applied rule | limitation | reviewer decision |",
        "|---|---:|---|---|---|---|---|",
    ]
    for d in record["dimensions"]:
        score = "not_assessable" if d["score"] is None else str(d["score"])
        lines.append(f"| {d['dimension_id']} {d['dimension']} | {score} | {d['status']} | "
                     f"{', '.join(d['supporting_artifact_ids'])} | {d['applied_rubric_rule']} | "
                     f"{d['limitation']} | {d['reviewer_decision']} |")
    return "\n".join(lines) + "\n"


def write_artifacts(record: dict[str, Any], out_dir: str | Path = DEFAULT_OUT_DIR, plot: bool = False) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {"record": out / "scored_record.json", "csv": out / "scores.csv", "markdown": out / "scores.md", "coordinates": out / "coordinates.json"}
    paths["record"].write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    paths["markdown"].write_text(render_markdown(record), encoding="utf-8")
    paths["coordinates"].write_text(json.dumps(coordinates_from_record(record), indent=2, sort_keys=True), encoding="utf-8")
    with paths["csv"].open("w", newline="", encoding="utf-8") as fh:
        fields = ["dimension_id", "dimension", "score", "status", "maturity_label", "supporting_artifact_ids", "applied_rubric_rule", "limitation", "reviewer_decision", "expert_review_required"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for d in record["dimensions"]:
            row = {k: d.get(k, "") for k in fields}
            row["score"] = "not_assessable" if d["score"] is None else d["score"]
            row["supporting_artifact_ids"] = ";".join(d["supporting_artifact_ids"])
            writer.writerow(row)
    if plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            coords = coordinates_from_record(record)["coordinates"]
            xs = [p["x"] for p in coords.values()]
            ys = [0 if p["y"] is None else p["y"] for p in coords.values()]
            colors = ["#999999" if p["y"] is None else "#0072B2" for p in coords.values()]
            fig, ax = plt.subplots(figsize=(9, 3.6))
            ax.scatter(xs, ys, s=80, color=colors)
            for dim_id, p in coords.items():
                ax.annotate(dim_id, (p["x"], 0 if p["y"] is None else p["y"]), textcoords="offset points", xytext=(3, 5), fontsize=8)
            ax.set_ylim(-0.2, 3.2)
            ax.set_xticks(range(1, 13))
            ax.set_xlabel("M1-M12 dimension")
            ax.set_ylabel("rubric score (0-3)")
            fig.savefig(out / "landscape.png", dpi=150, bbox_inches="tight")
            paths["figure"] = out / "landscape.png"
        except Exception as exc:
            paths["figure_error"] = Path(str(exc))
    return {k: str(v) for k, v in paths.items()}


def score_run_artifacts(run_dir: str | Path | None = None, out_dir: str | Path = DEFAULT_OUT_DIR,
                        plot: bool = False) -> tuple[dict[str, Any], dict[str, str]]:
    record = build_scored_record(run_dir)
    return record, write_artifacts(record, out_dir, plot=plot)
