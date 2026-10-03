"""M2 benchmark harness over published/complied ternary complex sets.

Spec §5: build from the published ternary-complex validation set identified in
the competitive scan — the PROTAC-shotgun ternary-in-PDB catalog (64 rows) plus
the local TERNARY_V1 set (12 RCSB PDBs) — up to the maximum fully recoverable
subset. Structures are fetched from RCSB and analyzed independently with the
M2 lysine module; results are not compared to literature-reported scores.

``known_productive`` is the experimental fact that the ternary complex was
resolved; ``known_lysine_geometry`` requires an E2 catalytic residue in the
deposited structure (absent in this set -> recorded as not_computable).
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

from protacxtend.mechanistic.m2_lysine import M2Config, analyze_lysines

SHOTGUN_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "protac_repos" / "repos" / \
    "PROTAC-shotgun" / "Ternary_Complexes_in_PDB" / "PROTAC_Ternary_Complex_from_PDB.csv"


def _load_sets() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if SHOTGUN_CSV.exists():
        with open(SHOTGUN_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                pdb = (r.get("PDB ID") or "").strip().lower()
                if not pdb:
                    continue
                rows.append({
                    "pdb": pdb, "poi": (r.get("POI") or "").strip(), "e3": (r.get("E3") or "").strip(),
                    "protac": (r.get("PROTAC res name") or "").strip(),
                    "poi_chain": (r.get("POI chain") or "").strip() or "A",
                    "e3_chain": (r.get("E3 chain") or "").strip() or "B",
                    "source": "PROTAC-shotgun ternary-in-PDB catalog (published compilation)",
                })
    from protacxtend.validation.datasets import TERNARY_V1
    for c in TERNARY_V1["complexes"]:
        rows.append({
            "pdb": str(c["pdb"]).lower(), "poi": "", "e3": "",
            "protac": str(c.get("ligand") or ""),
            "poi_chain": str(c.get("target_chain") or "A"),
            "e3_chain": str(c.get("e3_chain") or "B"),
            "source": "local TERNARY_V1 (RCSB PDB curated set)",
        })
    seen: set[str] = set()
    out = []
    for r in rows:
        if r["pdb"] not in seen:
            seen.add(r["pdb"])
            out.append(r)
    return out


def run_m2_benchmark(max_complexes: int = 40, out_dir: Path | None = None) -> dict[str, Any]:
    from protacxtend.validation.curation import fetch_structure

    complexes = _load_sets()[:max_complexes]
    rows: list[dict[str, Any]] = []
    failures_rows: list[dict[str, Any]] = []
    n_recovered = n_fail = n_with_e2 = 0
    failures: dict[str, int] = {}
    distances: list[float] = []
    sasa_rels: list[float] = []

    for i, c in enumerate(complexes):
        _t0 = time.time()
        rec: dict[str, Any] = {
            "benchmark_id": f"m2_{i:03d}", "pdb": c["pdb"], "poi": c["poi"], "e3": c["e3"],
            "protac": c["protac"], "source": c["source"],
            "known_productive": True, "known_interface": True,
            "known_lysine_geometry_if_available": "not_computable_no_e2_in_structure",
            "predicted_best_lysine": "", "predicted_geometry_score": "",
            "pass_fail": "", "reason": "",
        }
        try:
            p = fetch_structure(c["pdb"])
            _chains = {c["e3_chain"], "B", "C", "D"} - {c["poi_chain"]}
            cfg = M2Config(poi_chain=c["poi_chain"], e3_chains=tuple(_chains))
            res = analyze_lysines([p], cfg)
            rec["recovered"] = "yes"
            rec["poi_chain"] = c["poi_chain"]
            rec["e3_chain"] = c["e3_chain"]
            agg = res.get("aggregate") or {}
            rec["predicted_best_lysine"] = agg.get("best_lysine") or ""
            rec["predicted_geometry_score"] = agg.get("ubiquitination_geometry_score")
            rec["n_accessible_lysines"] = agg.get("n_accessible_lysines")
            rec["e2_reference_status"] = agg.get("e2_reference_status", "UNAVAILABLE")
            rec["status"] = res.get("status")
            rec["reason"] = res.get("reason") or ""
            if agg.get("e2_reference_status") == "present":
                n_with_e2 += 1
            for r in res.get("per_residue", []):
                if r.get("distance_to_E3") is not None:
                    distances.append(float(r["distance_to_E3"]))
                sasa_rels.append(float(r.get("SASA_relative", 0.0)))
            rec["pass_fail"] = ("PARTIAL" if res.get("status") in ("PARTIAL", "SUPPORTED") else "REJECT")
            n_recovered += 1
        except Exception as exc:
            rec["recovered"] = "no"
            rec["reason"] = f"{type(exc).__name__}: {str(exc)[:120]}"
            key = type(exc).__name__
            failures[key] = failures.get(key, 0) + 1
            n_fail += 1
            failures_rows.append({
                "benchmark_id": rec["benchmark_id"], "pdb": c["pdb"], "stage": "fetch_or_parse",
                "failure_type": key, "message": str(exc)[:200],
            })
        rec["runtime_s"] = round(time.time() - _t0, 2)
        rows.append(rec)

    n_e2_in_set = n_with_e2
    metrics = {
        "n_attempted": len(complexes),
        "n_recovered": n_recovered,
        "n_failed": n_fail,
        "complex_recovery_rate": round(n_recovered / len(complexes), 4) if complexes else 0.0,
        "n_complexes_with_e2_reference": n_e2_in_set,
        "productive_geometry_recall": "not_computable_no_e2_in_benchmark_set" if n_e2_in_set == 0 else None,
        "top1_lysine_recovery": "not_computable_no_known_lysine_labels",
        "top3_lysine_recovery": "not_computable_no_known_lysine_labels",
        "false_positive_rate": "not_computable_no_negative_reference_set",
        "distance_distribution": _dist_summary(distances),
        "SASA_distribution": _dist_summary(sasa_rels),
        "failure_categories": failures,
        "failures_rows": failures_rows,
        "total_runtime_s": round(sum(float(r.get("runtime_s") or 0) for r in rows), 2),
        "median_runtime_s": round(sorted(float(r.get("runtime_s") or 0) for r in rows)[len(rows) // 2], 2) if rows else None,
    }
    summary_text = (
        f"M2 benchmark: attempted {metrics['n_attempted']}, recovered {metrics['n_recovered']} "
        f"(recovery {metrics['complex_recovery_rate']}); E2-bearing complexes in set: "
        f"{metrics['n_complexes_with_e2_reference']} -> productive-geometry recall and E2-distance "
        f"fields are UNAVAILABLE (no fabricated geometry); per-complex rows in "
        f"m2_lysine_geometry_benchmark.csv."
    )
    return {"rows": rows, "metrics": metrics, "summary_text": summary_text}


def _dist_summary(xs: list[float]) -> dict[str, float] | str:
    if not xs:
        return "no_values"
    xs = sorted(xs)
    n = len(xs)

    def pct(q: float) -> float:
        return xs[min(n - 1, int(q * n))]

    return {"n": n, "median": round(pct(0.5), 3), "p25": round(pct(0.25), 3),
            "p75": round(pct(0.75), 3), "min": round(xs[0], 3), "max": round(xs[-1], 3)}